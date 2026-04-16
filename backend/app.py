
import cv2
import numpy as np
from flask import Flask, jsonify, request, Response
from flask_cors import CORS
import time
import threading
import os
from datetime import datetime, timedelta
import random
import json
from collections import deque
import requests as http_requests
import logging
from functools import wraps

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Configure logging for city-scale operations
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# Try importing ultralytics for YOLOv11
try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
    print("Ultralytics YOLO loaded successfully")
except ImportError:
    YOLO_AVAILABLE = False
    print("WARNING: ultralytics not installed. Run: pip install ultralytics")

# Try importing pymongo
try:
    import pymongo
    from bson import ObjectId
    PYMONGO_AVAILABLE = True
except ImportError:
    PYMONGO_AVAILABLE = False
    print("WARNING: pymongo not installed. Database features disabled.")

app = Flask(__name__)
CORS(app)

# ============= API KEY AUTHENTICATION =============
API_KEY = os.getenv("API_KEY", "")  # Set in .env for production; empty = no auth

def require_api_key(f):
    """Decorator to require API key for sensitive endpoints"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not API_KEY:
            return f(*args, **kwargs)  # No key configured = open access
        key = request.headers.get("X-API-Key") or request.args.get("api_key")
        if key != API_KEY:
            return jsonify({"success": False, "error": "Unauthorized: invalid or missing API key"}), 401
        return f(*args, **kwargs)
    return decorated

# ============= CUDA CACHE =============
_cuda_available = None

def _has_cuda():
    """Check if CUDA is available (cached at first call)"""
    global _cuda_available
    if _cuda_available is None:
        try:
            import torch
            _cuda_available = torch.cuda.is_available()
        except ImportError:
            _cuda_available = False
        logger.info(f"CUDA available: {_cuda_available}")
    return _cuda_available

# ============= MONGODB SETUP =============
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/")
mongo_client = None
db = None
violations_collection = None
patterns_collection = None
learning_logs_collection = None
intersections_collection = None
zones_collection = None

if PYMONGO_AVAILABLE:
    try:
        mongo_client = pymongo.MongoClient(MONGODB_URI, serverSelectionTimeoutMS=2000)
        mongo_client.server_info()
        db = mongo_client["traffic_management"]
        violations_collection = db["violations"]
        patterns_collection = db["traffic_patterns"]
        learning_logs_collection = db["learning_logs"]
        intersections_collection = db["intersections"]
        zones_collection = db["zones"]
        print("Successfully connected to MongoDB")
    except Exception as e:
        print(f"Warning: Could not connect to MongoDB: {e}")
        print("Vehicle violations will not be stored in database")

# ============= SIGNAL CONTROLLER INTEGRATION =============
# Sends commands to physical traffic signal hardware via HTTP/MQTT/GPIO
signal_controller_lock = threading.Lock()

class SignalController:
    """Manages communication with physical traffic signal controllers"""

    def __init__(self):
        self.controllers = {}  # {intersection_id: controller_config}
        self.command_queue = deque(maxlen=10000)
        self.command_history = deque(maxlen=5000)
        self._running = True
        self._sender_thread = threading.Thread(target=self._command_sender, daemon=True)
        self._sender_thread.start()

    def register_controller(self, intersection_id, config):
        """Register a signal controller for an intersection.
        config: {
            'type': 'http' | 'mqtt' | 'gpio' | 'mock',
            'endpoint': 'http://192.168.1.x:8080/signal',
            'auth_token': 'optional',
            'timeout': 5,
            'retry_count': 3,
        }
        """
        with signal_controller_lock:
            self.controllers[intersection_id] = {
                **config,
                'last_command': None,
                'last_response': None,
                'last_sent_at': None,
                'failures': 0,
                'total_commands': 0,
                'status': 'registered',
            }
        logger.info(f"Signal controller registered for {intersection_id}: {config.get('type', 'http')}")

    def unregister_controller(self, intersection_id):
        with signal_controller_lock:
            self.controllers.pop(intersection_id, None)

    def send_signal(self, intersection_id, signal_state, priority="normal"):
        """Queue a signal command to be sent to the physical controller"""
        self.command_queue.append({
            'intersection_id': intersection_id,
            'signal': signal_state,
            'priority': priority,
            'timestamp': time.time(),
            'queued_at': datetime.now().isoformat(),
        })

    def _command_sender(self):
        """Background thread that processes the command queue"""
        while self._running:
            try:
                if not self.command_queue:
                    time.sleep(0.05)
                    continue

                cmd = self.command_queue.popleft()
                int_id = cmd['intersection_id']

                with signal_controller_lock:
                    controller = self.controllers.get(int_id)

                if not controller:
                    continue  # No physical controller registered

                ctrl_type = controller.get('type', 'mock')
                success = False
                response = None

                try:
                    if ctrl_type == 'http':
                        success, response = self._send_http(controller, cmd)
                    elif ctrl_type == 'mqtt':
                        success, response = self._send_mqtt(controller, cmd)
                    elif ctrl_type == 'gpio':
                        success, response = self._send_gpio(controller, cmd)
                    elif ctrl_type == 'mock':
                        success, response = True, {'status': 'ok', 'mock': True}

                    with signal_controller_lock:
                        controller['last_command'] = cmd['signal']
                        controller['last_response'] = response
                        controller['last_sent_at'] = datetime.now().isoformat()
                        controller['total_commands'] += 1
                        if success:
                            controller['failures'] = 0
                            controller['status'] = 'connected'
                        else:
                            controller['failures'] += 1
                            controller['status'] = 'error' if controller['failures'] > 3 else 'retrying'

                except Exception as e:
                    logger.error(f"Signal controller error for {int_id}: {e}")
                    with signal_controller_lock:
                        controller['failures'] += 1
                        controller['status'] = 'error'

                self.command_history.append({
                    **cmd,
                    'success': success,
                    'response': str(response)[:200] if response else None,
                    'sent_at': datetime.now().isoformat(),
                })

            except Exception as e:
                logger.error(f"Command sender error: {e}")
                time.sleep(0.1)

    def _send_http(self, controller, cmd):
        """Send signal command via HTTP REST API"""
        endpoint = controller.get('endpoint', '')
        if not endpoint:
            return False, 'No endpoint configured'

        headers = {'Content-Type': 'application/json'}
        auth_token = controller.get('auth_token')
        if auth_token:
            headers['Authorization'] = f'Bearer {auth_token}'

        payload = {
            'intersection_id': cmd['intersection_id'],
            'signal': cmd['signal'],
            'priority': cmd['priority'],
            'timestamp': cmd['queued_at'],
        }

        timeout = controller.get('timeout', 5)
        retry_count = controller.get('retry_count', 3)

        for attempt in range(retry_count):
            try:
                resp = http_requests.post(endpoint, json=payload, headers=headers, timeout=timeout)
                if resp.status_code == 200:
                    return True, resp.json() if resp.headers.get('content-type', '').startswith('application/json') else resp.text
                logger.warning(f"HTTP signal send failed (attempt {attempt+1}): {resp.status_code}")
            except http_requests.exceptions.Timeout:
                logger.warning(f"HTTP signal timeout (attempt {attempt+1})")
            except Exception as e:
                logger.warning(f"HTTP signal error (attempt {attempt+1}): {e}")

        return False, 'All retries failed'

    def _send_mqtt(self, controller, cmd):
        """Send signal command via MQTT (placeholder - requires paho-mqtt)"""
        try:
            import paho.mqtt.publish as publish
            broker = controller.get('broker', 'localhost')
            port = controller.get('port', 1883)
            topic = controller.get('topic', f"traffic/signals/{cmd['intersection_id']}")

            payload = json.dumps({
                'signal': cmd['signal'],
                'priority': cmd['priority'],
                'timestamp': cmd['queued_at'],
            })

            publish.single(topic, payload, hostname=broker, port=port)
            return True, {'published': True, 'topic': topic}
        except ImportError:
            logger.warning("paho-mqtt not installed. MQTT signal control unavailable.")
            return False, 'paho-mqtt not installed'
        except Exception as e:
            return False, str(e)

    def _send_gpio(self, controller, cmd):
        """Send signal command via GPIO (for Raspberry Pi / embedded systems)"""
        try:
            import RPi.GPIO as GPIO
            pins = controller.get('pins', {})
            red_pin = pins.get('red', 17)
            yellow_pin = pins.get('yellow', 27)
            green_pin = pins.get('green', 22)

            GPIO.setmode(GPIO.BCM)
            for pin in [red_pin, yellow_pin, green_pin]:
                GPIO.setup(pin, GPIO.OUT)
                GPIO.output(pin, GPIO.LOW)

            signal = cmd['signal']
            if signal == 'red':
                GPIO.output(red_pin, GPIO.HIGH)
            elif signal == 'yellow':
                GPIO.output(yellow_pin, GPIO.HIGH)
            elif signal == 'green':
                GPIO.output(green_pin, GPIO.HIGH)

            return True, {'gpio': True, 'signal': signal}
        except ImportError:
            return False, 'RPi.GPIO not available (not on Raspberry Pi)'
        except Exception as e:
            return False, str(e)

    def get_status(self):
        """Get status of all signal controllers"""
        with signal_controller_lock:
            return {int_id: {
                'type': c.get('type', 'unknown'),
                'status': c.get('status', 'unknown'),
                'last_command': c.get('last_command'),
                'last_sent_at': c.get('last_sent_at'),
                'failures': c.get('failures', 0),
                'total_commands': c.get('total_commands', 0),
            } for int_id, c in self.controllers.items()}

    def get_command_history(self, limit=50):
        return list(self.command_history)[-limit:]


# Global signal controller instance
signal_controller = SignalController()


# ============= ZONE / REGION MANAGEMENT (City-Scale) =============
# Zones group intersections for coordinated control across a city
zone_registry = {}  # {zone_id: {name, intersection_ids, green_wave_config, ...}}
zone_lock = threading.Lock()

def create_zone(zone_id, name, intersection_ids=None, config=None):
    """Create a traffic management zone"""
    with zone_lock:
        zone_registry[zone_id] = {
            'id': zone_id,
            'name': name,
            'intersection_ids': intersection_ids or [],
            'green_wave': {
                'enabled': False,
                'direction': 'north_south',  # or 'east_west'
                'speed_kmh': 50,
                'offset_seconds': {},  # {int_id: offset} for green wave timing
            },
            'emergency_corridor': {
                'active': False,
                'path': [],  # Ordered list of intersection IDs for green corridor
                'vehicle_id': None,
            },
            'config': config or {},
            'created_at': datetime.now().isoformat(),
        }
    logger.info(f"Zone created: {zone_id} ({name}) with {len(intersection_ids or [])} intersections")


def activate_emergency_corridor(zone_id, path_intersection_ids, vehicle_id=None):
    """Activate green corridor across a zone for emergency vehicles"""
    with zone_lock:
        zone = zone_registry.get(zone_id)
        if not zone:
            return False

        zone['emergency_corridor'] = {
            'active': True,
            'path': path_intersection_ids,
            'vehicle_id': vehicle_id,
            'activated_at': datetime.now().isoformat(),
        }

    # Set all intersections in path to green, others to red
    with data_lock:
        for int_id in path_intersection_ids:
            idata = intersection_registry.get(int_id)
            if idata:
                idata['signal'] = 'green'
                idata['has_emergency'] = True
                idata['auto_control']['last_change_time'] = time.time()
                signal_controller.send_signal(int_id, 'green', priority='emergency')

                # Log emergency event to DB
                log_emergency_event(int_id, 'green_corridor_activated', {
                    'zone_id': zone_id,
                    'vehicle_id': vehicle_id,
                    'path': path_intersection_ids,
                })

        # Set non-path intersections in this zone to red
        for int_id in zone.get('intersection_ids', []):
            if int_id not in path_intersection_ids:
                idata = intersection_registry.get(int_id)
                if idata and idata['signal'] != 'red':
                    idata['signal'] = 'red'
                    signal_controller.send_signal(int_id, 'red', priority='emergency')

    logger.info(f"Emergency corridor activated in zone {zone_id}: {path_intersection_ids}")
    return True


def deactivate_emergency_corridor(zone_id):
    """Deactivate emergency corridor and resume normal operations"""
    with zone_lock:
        zone = zone_registry.get(zone_id)
        if not zone:
            return False
        zone['emergency_corridor'] = {'active': False, 'path': [], 'vehicle_id': None}
        # Copy intersection IDs while still holding the lock
        zone_intersection_ids = list(zone.get('intersection_ids', []))

    with data_lock:
        for int_id in zone_intersection_ids:
            idata = intersection_registry.get(int_id)
            if idata:
                idata['has_emergency'] = False

    logger.info(f"Emergency corridor deactivated in zone {zone_id}")
    return True


# ============= EMERGENCY & SIGNAL HISTORY LOGGING =============
emergency_events_collection = None
signal_history_collection = None

if PYMONGO_AVAILABLE and db is not None:
    try:
        emergency_events_collection = db["emergency_events"]
        signal_history_collection = db["signal_history"]
        # Create indexes for efficient querying at city scale
        emergency_events_collection.create_index([("timestamp", -1)])
        emergency_events_collection.create_index([("intersection_id", 1)])
        signal_history_collection.create_index([("timestamp", -1)])
        signal_history_collection.create_index([("intersection_id", 1)])
        violations_collection.create_index([("timestamp", -1)])
        violations_collection.create_index([("type", 1)])
        logger.info("Database indexes created for city-scale operations")
    except Exception as e:
        logger.warning(f"Could not create DB indexes: {e}")


def log_emergency_event(int_id, event_type, data):
    """Log emergency events to centralized database"""
    event = {
        'intersection_id': int_id,
        'event_type': event_type,
        'data': data,
        'timestamp': datetime.now().isoformat(),
    }
    if emergency_events_collection is not None:
        try:
            emergency_events_collection.insert_one(event)
        except Exception as e:
            logger.error(f"Error logging emergency event: {e}")


def log_signal_change(int_id, old_signal, new_signal, reason="auto"):
    """Log signal changes to centralized database for audit trail"""
    entry = {
        'intersection_id': int_id,
        'old_signal': old_signal,
        'new_signal': new_signal,
        'reason': reason,
        'timestamp': datetime.now().isoformat(),
    }
    if signal_history_collection is not None:
        try:
            signal_history_collection.insert_one(entry)
        except Exception as e:
            logger.error(f"Error logging signal change: {e}")

    # Also send to physical signal controller
    signal_controller.send_signal(int_id, new_signal,
                                  priority='emergency' if reason == 'emergency' else 'normal')


# ============= DYNAMIC INTERSECTION REGISTRY =============
# All intersection data is stored here - intersections can be added/removed at runtime
intersection_registry = {}  # {intersection_id: {...config...}}
data_lock = threading.Lock()
frame_lock = threading.Lock()

# Global YOLO model (shared across all detection threads for efficiency)
yolo_model = None
yolo_model_lock = threading.Lock()

# ============= CONFIGURATION =============
LEARNING_RATE = 0.1
PATTERN_UPDATE_INTERVAL = 60
SPEED_LIMIT = 40
PIXELS_PER_METER = 10
CONFIDENCE_THRESHOLD = 0.35
IOU_THRESHOLD = 0.45
YOLO_MODEL_NAME = "yolo11n.pt"  # YOLOv11 nano - fast and accurate. Options: yolo11n/s/m/l/x

# Vehicle classes from COCO dataset
VEHICLE_CLASSES = {"car", "truck", "bus", "motorcycle", "bicycle"}
PERSON_CLASS = "person"

# PCE (Passenger Car Equivalent) values for traffic density estimation
# Standard PCE values used in traffic engineering
PCE_VALUES = {
    "car": 1.0,
    "truck": 3.0,
    "bus": 3.0,
    "motorcycle": 0.5,
    "bicycle": 0.2,
}

# Frame processing config
FRAME_CONFIG = {
    "skip_frames": 3,          # Process detection every N frames (reduced from 5 for better tracking)
    "frame_quality": 75,       # JPEG quality for streaming
    "max_width": 800,          # Max stream width (increased from 640)
    "stream_fps": 20,          # Target stream FPS (increased from 15)
    "detection_size": 640,     # YOLO input size
}

# Two-wheeler violation config
TWO_WHEELER_CONFIG = {
    "person_count_threshold": 2,
    "helmet_color_ranges": {
        "black": [(0, 0, 0), (180, 255, 50)],
        "white": [(0, 0, 200), (180, 30, 255)],
        "red": [(0, 100, 100), (10, 255, 255)],
        "blue": [(100, 100, 100), (130, 255, 255)],
        "yellow": [(20, 100, 100), (35, 255, 255)],
    }
}

# Emergency vehicle detection config
EMERGENCY_CONFIG = {
    "min_size": 80,            # Minimum bounding box dimension in pixels
    "min_area": 8000,          # Minimum bounding box area (w*h) to filter small vehicles
    "red_threshold": 3.0,      # Minimum red color percentage
    "blue_threshold": 3.0,     # Minimum blue color percentage
    "require_both_colors": True,  # Require BOTH red AND blue (siren pattern) to reduce false positives
    "top_region_ratio": 0.4,   # Only check top 40% of vehicle (where sirens are mounted)
}


def create_intersection_data(intersection_id, name, camera_source="0", camera_type="usb"):
    """Create a new intersection data structure"""
    return {
        # Basic info
        "id": intersection_id,
        "name": name,
        "camera_source": camera_source,
        "camera_type": camera_type,
        "camera_status": "configured",

        # Location (for city-scale mapping)
        "latitude": 0.0,
        "longitude": 0.0,
        "zone_id": None,

        # Traffic data
        "vehicle_count": 0,
        "pce_density": 0.0,  # PCE-weighted traffic density
        "vehicle_type_counts": {},  # {type: count} for PCE breakdown
        "has_emergency": False,
        "emergency_count": 0,
        "timestamp": "",

        # Signal
        "signal": "red",
        "signal_controller": {
            "type": "mock",  # 'http', 'mqtt', 'gpio', 'mock'
            "endpoint": "",
            "auth_token": "",
            "timeout": 5,
            "retry_count": 3,
        },
        "auto_control": {
            "enabled": False,
            "last_change_time": time.time(),
            "cycle_times": {"red": 30, "yellow": 5, "green": 30},
            "vehicle_thresholds": {"low": 5, "medium": 15},
            "cycle_adjustments": {"low": 0.7, "medium": 1.0, "high": 1.3},
            "use_predictions": True,
        },

        # Patterns and predictions (online learning)
        "patterns": {hour: {"avg_count": 0, "samples": 0, "peak_detected": False} for hour in range(24)},
        "predictions": {"next_hour_prediction": 0, "trend": "stable", "confidence": 0.0,
                        "current_hour_avg": 0, "is_peak_hour": False},

        # Vehicle tracking
        "detected_vehicles": [],
        "last_vehicle_positions": {},  # {vehicle_id: (x, y)}
        "vehicle_tracking_history": {},  # {vehicle_id: deque([(x, y, t), ...])}
        "vehicle_speeds": {},  # {vehicle_id: speed_kmh}
        "next_vehicle_id": 1,

        # Speed calibration (per-intersection, adjustable via API)
        "pixels_per_meter": PIXELS_PER_METER,

        # Stop line / violations
        "stop_line": {"y_position": 350, "tolerance": 20},
        "vehicles_crossed_stop_line": [],  # list instead of set for JSON serialization

        # Frames
        "latest_frame": None,
        "processed_frame": None,

        # Thread control
        "detection_thread": None,
        "running": False,
    }


def init_default_intersections():
    """Initialize default intersections only if no intersections exist"""
    with data_lock:
        if len(intersection_registry) > 0:
            return  # Already have intersections (loaded from DB or added at runtime)
        intersection_registry["int-001"] = create_intersection_data(
            "int-001", "Main Street Intersection", "0", "usb"
        )
        intersection_registry["int-001"]["signal"] = "red"
        intersection_registry["int-002"] = create_intersection_data(
            "int-002", "Park Avenue Intersection", "1", "usb"
        )
        intersection_registry["int-002"]["signal"] = "green"
    logger.info("Initialized default intersections (int-001, int-002)")


# ============= DATA PERSISTENCE (MongoDB) =============

def _serializable_intersection(idata):
    """Extract persistable fields from intersection data (skip threads, frames, sets)"""
    return {
        "id": idata["id"],
        "name": idata["name"],
        "camera_source": idata["camera_source"],
        "camera_type": idata["camera_type"],
        "latitude": idata.get("latitude", 0.0),
        "longitude": idata.get("longitude", 0.0),
        "zone_id": idata.get("zone_id"),
        "signal": idata["signal"],
        "pixels_per_meter": idata.get("pixels_per_meter", PIXELS_PER_METER),
        "stop_line": idata.get("stop_line", {"y_position": 350, "tolerance": 20}),
        "auto_control_enabled": idata["auto_control"]["enabled"],
        "cycle_times": idata["auto_control"]["cycle_times"],
        "vehicle_thresholds": idata["auto_control"]["vehicle_thresholds"],
        "cycle_adjustments": idata["auto_control"]["cycle_adjustments"],
    }


def save_intersection_to_db(int_id):
    """Persist a single intersection config to MongoDB"""
    if intersections_collection is None:
        return
    idata = intersection_registry.get(int_id)
    if not idata:
        return
    try:
        doc = _serializable_intersection(idata)
        intersections_collection.update_one(
            {"id": int_id}, {"$set": doc}, upsert=True
        )
    except Exception as e:
        logger.error(f"Error persisting intersection {int_id}: {e}")


def remove_intersection_from_db(int_id):
    """Remove an intersection from MongoDB"""
    if intersections_collection is None:
        return
    try:
        intersections_collection.delete_one({"id": int_id})
    except Exception as e:
        logger.error(f"Error removing intersection {int_id} from DB: {e}")


def save_zone_to_db(zone_id):
    """Persist a zone config to MongoDB"""
    if zones_collection is None:
        return
    zone = zone_registry.get(zone_id)
    if not zone:
        return
    try:
        doc = {
            "id": zone_id,
            "name": zone["name"],
            "intersection_ids": zone["intersection_ids"],
            "green_wave": zone.get("green_wave", {}),
            "config": zone.get("config", {}),
        }
        zones_collection.update_one({"id": zone_id}, {"$set": doc}, upsert=True)
    except Exception as e:
        logger.error(f"Error persisting zone {zone_id}: {e}")


def remove_zone_from_db(zone_id):
    """Remove a zone from MongoDB"""
    if zones_collection is None:
        return
    try:
        zones_collection.delete_one({"id": zone_id})
    except Exception as e:
        logger.error(f"Error removing zone {zone_id} from DB: {e}")


def load_persisted_data():
    """Load intersection and zone configs from MongoDB on startup"""
    loaded_ints = 0
    loaded_zones = 0

    if intersections_collection is not None:
        try:
            for doc in intersections_collection.find():
                int_id = doc["id"]
                idata = create_intersection_data(
                    int_id, doc.get("name", int_id),
                    doc.get("camera_source", "0"), doc.get("camera_type", "usb")
                )
                idata["latitude"] = doc.get("latitude", 0.0)
                idata["longitude"] = doc.get("longitude", 0.0)
                idata["zone_id"] = doc.get("zone_id")
                idata["signal"] = doc.get("signal", "red")
                idata["pixels_per_meter"] = doc.get("pixels_per_meter", PIXELS_PER_METER)
                idata["stop_line"] = doc.get("stop_line", {"y_position": 350, "tolerance": 20})
                idata["auto_control"]["enabled"] = doc.get("auto_control_enabled", False)
                if "cycle_times" in doc:
                    idata["auto_control"]["cycle_times"] = doc["cycle_times"]
                if "vehicle_thresholds" in doc:
                    idata["auto_control"]["vehicle_thresholds"] = doc["vehicle_thresholds"]
                if "cycle_adjustments" in doc:
                    idata["auto_control"]["cycle_adjustments"] = doc["cycle_adjustments"]
                with data_lock:
                    intersection_registry[int_id] = idata
                loaded_ints += 1
        except Exception as e:
            logger.error(f"Error loading intersections from DB: {e}")

    if zones_collection is not None:
        try:
            for doc in zones_collection.find():
                zid = doc["id"]
                create_zone(zid, doc.get("name", zid), doc.get("intersection_ids", []),
                            doc.get("config"))
                loaded_zones += 1
        except Exception as e:
            logger.error(f"Error loading zones from DB: {e}")

    logger.info(f"Loaded {loaded_ints} intersections and {loaded_zones} zones from MongoDB")


# ============= YOLO MODEL LOADING =============

def load_yolo_model():
    """Load YOLOv11 model (shared instance)"""
    global yolo_model
    if not YOLO_AVAILABLE:
        print("ERROR: ultralytics not installed. Cannot load YOLO model.")
        return None

    with yolo_model_lock:
        if yolo_model is not None:
            return yolo_model

        try:
            print(f"Loading YOLOv11 model: {YOLO_MODEL_NAME}")
            yolo_model = YOLO(YOLO_MODEL_NAME)

            # Warm up the model with a dummy inference
            dummy = np.zeros((640, 640, 3), dtype=np.uint8)
            yolo_model.predict(dummy, verbose=False)
            print(f"YOLOv11 model loaded and warmed up successfully")
            return yolo_model
        except Exception as e:
            print(f"Error loading YOLOv11 model: {e}")
            return None


# ============= ONLINE LEARNING FUNCTIONS =============

def update_traffic_pattern(int_id, vehicle_count):
    """Update traffic patterns using exponential moving average"""
    current_hour = datetime.now().hour
    idata = intersection_registry[int_id]
    pattern = idata["patterns"][current_hour]

    if pattern["samples"] == 0:
        pattern["avg_count"] = vehicle_count
    else:
        pattern["avg_count"] = (1 - LEARNING_RATE) * pattern["avg_count"] + LEARNING_RATE * vehicle_count

    pattern["samples"] += 1

    all_hours_avg = sum(p["avg_count"] for p in idata["patterns"].values()) / 24
    pattern["peak_detected"] = pattern["avg_count"] > all_hours_avg * 1.3 if all_hours_avg > 0 else False

    update_traffic_predictions(int_id)
    log_learning_event(int_id, "pattern_update", {
        "hour": current_hour,
        "vehicle_count": vehicle_count,
        "new_avg": round(pattern["avg_count"], 2),
        "samples": pattern["samples"]
    })


def update_traffic_predictions(int_id):
    """Generate predictions based on learned patterns"""
    current_hour = datetime.now().hour
    next_hour = (current_hour + 1) % 24
    idata = intersection_registry[int_id]

    current_avg = idata["patterns"][current_hour]["avg_count"]
    next_avg = idata["patterns"][next_hour]["avg_count"]
    samples = idata["patterns"][current_hour]["samples"]

    confidence = min(1.0, samples / 100)

    if next_avg > current_avg * 1.1:
        trend = "increasing"
    elif next_avg < current_avg * 0.9:
        trend = "decreasing"
    else:
        trend = "stable"

    idata["predictions"] = {
        "next_hour_prediction": round(next_avg, 1),
        "trend": trend,
        "confidence": round(confidence, 3),
        "current_hour_avg": round(current_avg, 1),
        "is_peak_hour": idata["patterns"][current_hour]["peak_detected"]
    }


def log_learning_event(int_id, event_type, data):
    """Log learning events to database"""
    if db is not None and learning_logs_collection is not None:
        try:
            learning_logs_collection.insert_one({
                "intersection_id": int_id,
                "event_type": event_type,
                "data": data,
                "timestamp": datetime.now().isoformat()
            })
        except Exception as e:
            print(f"Error logging learning event: {e}")


def get_adaptive_cycle_time(int_id, signal_type):
    """Get adaptive signal cycle time based on predictions"""
    idata = intersection_registry[int_id]
    base_time = idata["auto_control"]["cycle_times"][signal_type]

    if not idata["auto_control"].get("use_predictions", False):
        return base_time

    prediction = idata["predictions"]

    if prediction["trend"] == "increasing" and prediction["confidence"] > 0.5:
        if signal_type == "green":
            return base_time * 1.2
        elif signal_type == "red":
            return base_time * 0.8
    elif prediction["trend"] == "decreasing" and prediction["confidence"] > 0.5:
        if signal_type == "green":
            return base_time * 0.8
        elif signal_type == "red":
            return base_time * 1.2

    return base_time


# ============= SPEED TRACKING =============

def calculate_vehicle_speed(int_id, vehicle_id, current_position, current_time):
    """Calculate vehicle speed from position history"""
    idata = intersection_registry[int_id]

    if vehicle_id not in idata["vehicle_tracking_history"]:
        idata["vehicle_tracking_history"][vehicle_id] = deque(maxlen=10)

    history = idata["vehicle_tracking_history"][vehicle_id]
    history.append((current_position[0], current_position[1], current_time))

    if len(history) < 2:
        return 0

    old_x, old_y, old_time = history[0]
    new_x, new_y, new_time = history[-1]

    displacement_pixels = np.sqrt((new_x - old_x) ** 2 + (new_y - old_y) ** 2)
    time_diff = new_time - old_time

    if time_diff <= 0:
        return 0

    ppm = idata.get("pixels_per_meter", PIXELS_PER_METER)
    displacement_meters = displacement_pixels / ppm
    speed_mps = displacement_meters / time_diff
    speed_kmh = speed_mps * 3.6

    idata["vehicle_speeds"][vehicle_id] = round(speed_kmh, 1)
    return speed_kmh


# ============= VIOLATION DETECTION =============

def detect_red_light_violation(int_id, vehicle_id, vehicle_position):
    """Detect red light violation by stop-line crossing"""
    idata = intersection_registry[int_id]
    current_signal = idata["signal"]
    stop_line = idata["stop_line"]
    vehicle_y = vehicle_position[1]

    crossed_line = vehicle_y > stop_line["y_position"] - stop_line["tolerance"]

    if crossed_line:
        was_already_crossed = vehicle_id in idata["vehicles_crossed_stop_line"]

        if not was_already_crossed:
            if vehicle_id not in idata["vehicles_crossed_stop_line"]:
                idata["vehicles_crossed_stop_line"].append(vehicle_id)
            if current_signal == "red":
                return True, "Vehicle crossed stop line during red signal"

    return False, None


def detect_speeding(int_id, vehicle_id):
    """Check if vehicle is speeding"""
    idata = intersection_registry[int_id]
    speed = idata["vehicle_speeds"].get(vehicle_id, 0)
    return (speed > SPEED_LIMIT, speed)


def detect_helmet(person_roi):
    """Helmet detection using color analysis and edge density on head region.
    Returns True if helmet is detected, False if not.
    Uses top 40% of person ROI and checks for helmet-like color regions
    plus high edge density (helmets have smooth, uniform surfaces).
    """
    if person_roi is None or person_roi.size == 0:
        return True  # Assume helmet present if we can't check

    try:
        height, width = person_roi.shape[:2]
        if height < 20 or width < 15:
            return True  # Too small to analyze reliably

        # Use top 40% of person ROI for head region (increased from 30%)
        head_region = person_roi[0:int(height * 0.4), :]
        if head_region.size == 0:
            return True

        head_pixels = head_region.shape[0] * head_region.shape[1]
        if head_pixels == 0:
            return True

        hsv = cv2.cvtColor(head_region, cv2.COLOR_BGR2HSV)
        helmet_color_score = 0.0

        for color_name, (lower, upper) in TWO_WHEELER_CONFIG["helmet_color_ranges"].items():
            mask = cv2.inRange(hsv, np.array(lower), np.array(upper))
            ratio = cv2.countNonZero(mask) / head_pixels
            helmet_color_score = max(helmet_color_score, ratio)

        # Color match: if a strong helmet color covers >12% of head region
        if helmet_color_score > 0.12:
            return True

        # Edge density check: helmets produce distinct circular edges
        gray = cv2.cvtColor(head_region, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 50, 150)
        edge_ratio = cv2.countNonZero(edges) / head_pixels

        # High edge density in head region suggests structured headgear
        if edge_ratio > 0.15:
            # Additional roundness check via contours
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for cnt in contours:
                area = cv2.contourArea(cnt)
                perimeter = cv2.arcLength(cnt, True)
                if perimeter > 0 and area > 100:
                    circularity = 4 * np.pi * area / (perimeter * perimeter)
                    if circularity > 0.4:  # Somewhat round shape
                        return True

        return False
    except Exception:
        return True  # Fail safe: assume helmet present


def detect_emergency_vehicle(frame, x, y, w, h):
    """Detect emergency vehicle by red/blue siren color analysis on top region.
    Requires both red AND blue presence (siren pattern) to reduce false positives
    from regular red/blue colored vehicles.
    """
    if w < EMERGENCY_CONFIG["min_size"] or h < EMERGENCY_CONFIG["min_size"]:
        return False

    if w * h < EMERGENCY_CONFIG.get("min_area", 8000):
        return False

    height, width = frame.shape[:2]
    if x < 0 or y < 0 or x + w >= width or y + h >= height:
        return False

    # Only analyze the top portion of the vehicle (where sirens/lights are)
    top_ratio = EMERGENCY_CONFIG.get("top_region_ratio", 0.4)
    top_h = max(1, int(h * top_ratio))
    vehicle_top_roi = frame[y:y + top_h, x:x + w]

    if vehicle_top_roi.size == 0:
        return False

    hsv = cv2.cvtColor(vehicle_top_roi, cv2.COLOR_BGR2HSV)

    # Red detection (two ranges for red hue wrap-around)
    mask_red1 = cv2.inRange(hsv, np.array([0, 120, 70]), np.array([10, 255, 255]))
    mask_red2 = cv2.inRange(hsv, np.array([170, 120, 70]), np.array([180, 255, 255]))
    mask_red = mask_red1 | mask_red2

    # Blue detection
    mask_blue = cv2.inRange(hsv, np.array([100, 50, 50]), np.array([130, 255, 255]))

    total_pixels = w * top_h
    red_percent = cv2.countNonZero(mask_red) / total_pixels * 100
    blue_percent = cv2.countNonZero(mask_blue) / total_pixels * 100

    if EMERGENCY_CONFIG.get("require_both_colors", True):
        return (red_percent > EMERGENCY_CONFIG["red_threshold"] and
                blue_percent > EMERGENCY_CONFIG["blue_threshold"])
    else:
        return (red_percent > EMERGENCY_CONFIG["red_threshold"] or
                blue_percent > EMERGENCY_CONFIG["blue_threshold"])


def count_people_on_vehicle(vehicle_roi, model):
    """Count people on a two-wheeler using YOLO"""
    if vehicle_roi is None or vehicle_roi.size == 0 or model is None:
        return 0

    try:
        results = model.predict(vehicle_roi, conf=0.4, classes=[0], verbose=False)  # class 0 = person
        if results and len(results) > 0:
            return len(results[0].boxes)
        return 0
    except Exception:
        return 0



def update_signal_automatic(int_id):
    """Automatically update traffic signal for an intersection"""
    idata = intersection_registry.get(int_id)
    if not idata or not idata["auto_control"]["enabled"]:
        return

    current_time = time.time()
    last_change = idata["auto_control"]["last_change_time"]
    current_signal = idata["signal"]

    # Use PCE density for smarter signal timing (accounts for vehicle size/type)
    pce_density = idata.get("pce_density", 0.0)

    # PCE-based thresholds (adjusted for weighted density)
    thresholds = idata["auto_control"]["vehicle_thresholds"]
    if pce_density <= thresholds["low"]:
        traffic_level = "low"
    elif pce_density <= thresholds["medium"]:
        traffic_level = "medium"
    else:
        traffic_level = "high"

    adjustment = idata["auto_control"]["cycle_adjustments"][traffic_level]
    base_time = get_adaptive_cycle_time(int_id, current_signal)
    adjusted_time = base_time * adjustment

    if current_time - last_change >= adjusted_time:
        if current_signal == "red":
            new_signal = "green"
            idata["vehicles_crossed_stop_line"].clear()
        elif current_signal == "green":
            new_signal = "yellow"
        else:
            new_signal = "red"

        old_signal = idata["signal"]
        idata["signal"] = new_signal
        idata["auto_control"]["last_change_time"] = current_time

        # Log signal change and send to physical controller
        log_signal_change(int_id, old_signal, new_signal, "auto_pce_based")

        # Coordinate: when this goes green, others go red
        if new_signal == "green":
            for other_id, other_data in intersection_registry.items():
                if other_id != int_id and other_data["auto_control"]["enabled"]:
                    if other_data["signal"] != "yellow":
                        old_other = other_data["signal"]
                        other_data["signal"] = "red"
                        if old_other != "red":
                            log_signal_change(other_id, old_other, "red", "coordination")

        elif new_signal == "red":
            # Find next intersection that should get green (round-robin within zone or all)
            zone_id = idata.get("zone_id")
            if zone_id and zone_id in zone_registry:
                candidate_ids = zone_registry[zone_id].get("intersection_ids", [])
            else:
                candidate_ids = list(intersection_registry.keys())

            idx = candidate_ids.index(int_id) if int_id in candidate_ids else -1
            if idx >= 0 and len(candidate_ids) > 1:
                next_idx = (idx + 1) % len(candidate_ids)
                next_id = candidate_ids[next_idx]
                next_data = intersection_registry.get(next_id)
                if next_data and next_data["auto_control"]["enabled"] and next_data["signal"] == "red":
                    if current_time - next_data["auto_control"]["last_change_time"] > 5:
                        next_data["signal"] = "green"
                        next_data["auto_control"]["last_change_time"] = current_time
                        next_data["vehicles_crossed_stop_line"].clear()
                        log_signal_change(next_id, "red", "green", "coordination")


# ============= PATTERN LEARNING THREAD =============

def pattern_learning_thread():
    """Background thread for periodic pattern updates"""
    while True:
        try:
            with data_lock:
                for int_id, idata in intersection_registry.items():
                    vehicle_count = idata["vehicle_count"]
                    update_traffic_pattern(int_id, vehicle_count)

                # Save to DB
                if db is not None and patterns_collection is not None:
                    for int_id, idata in intersection_registry.items():
                        try:
                            patterns_collection.update_one(
                                {"intersection_id": int_id},
                                {"$set": {
                                    "patterns": {str(k): v for k, v in idata["patterns"].items()},
                                    "predictions": idata["predictions"],
                                    "updated_at": datetime.now().isoformat()
                                }},
                                upsert=True
                            )
                        except Exception as e:
                            print(f"Error saving patterns: {e}")

            time.sleep(PATTERN_UPDATE_INTERVAL)
        except Exception as e:
            print(f"Error in pattern learning: {e}")
            time.sleep(10)


# ============= VEHICLE DETECTION (YOLOv11) =============

def match_vehicle_id(int_id, center_x, center_y, threshold=60):
    """Match a detected vehicle to a known vehicle ID using IoU-like distance"""
    idata = intersection_registry[int_id]
    best_id = None
    best_dist = threshold

    for known_id, (kx, ky) in list(idata["last_vehicle_positions"].items()):
        dist = np.sqrt((center_x - kx) ** 2 + (center_y - ky) ** 2)
        if dist < best_dist:
            best_dist = dist
            best_id = known_id

    if best_id is None:
        best_id = f"v-{idata['next_vehicle_id']}"
        idata["next_vehicle_id"] += 1

    idata["last_vehicle_positions"][best_id] = (center_x, center_y)
    return best_id


def detect_vehicles(int_id):
    """Main detection loop for an intersection using YOLOv11"""
    model = load_yolo_model()
    if model is None:
        print(f"Cannot start detection for {int_id}: YOLO model not available")
        return

    idata = intersection_registry.get(int_id)
    if not idata:
        print(f"Intersection {int_id} not found in registry")
        return

    camera_source = idata["camera_source"]
    camera_type = idata["camera_type"]

    # Determine camera input
    if camera_type == "usb":
        try:
            cam_input = int(camera_source)
        except ValueError:
            cam_input = 0
    else:
        cam_input = camera_source  # IP/RTSP URL string

    print(f"Starting detection for {int_id} ({idata['name']}) - Camera: {camera_type}:{camera_source}")

    # Initialize video capture with retries
    cap = None
    max_retries = 5

    for attempt in range(max_retries):
        try:
            print(f"  Attempt {attempt + 1}/{max_retries} to connect camera for {int_id}")
            cap = cv2.VideoCapture(cam_input)

            if camera_type == "usb":
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 800)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 600)
                cap.set(cv2.CAP_PROP_FPS, 30)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Reduce buffer for lower latency

            if cap.isOpened():
                ret, test_frame = cap.read()
                if ret and test_frame is not None:
                    print(f"  Camera connected for {int_id}: {test_frame.shape}")
                    idata["camera_status"] = "active"
                    break
                else:
                    cap.release()
                    cap = None
            else:
                cap = None

        except Exception as e:
            print(f"  Camera connection error for {int_id}: {e}")
            if cap:
                cap.release()
            cap = None

        time.sleep(2)

    if cap is None or not cap.isOpened():
        print(f"Could not open camera for {int_id} after {max_retries} attempts")
        idata["camera_status"] = "failed"
        idata["timestamp"] = datetime.now().isoformat()

        # Keep trying periodically
        while idata["running"]:
            time.sleep(10)
            try:
                cap = cv2.VideoCapture(cam_input)
                if cap.isOpened():
                    ret, frame = cap.read()
                    if ret and frame is not None:
                        print(f"Reconnected camera for {int_id}")
                        idata["camera_status"] = "active"
                        break
                    cap.release()
            except Exception:
                pass
            cap = None

        if cap is None:
            return

    # Main detection loop
    frame_count = 0
    process_every_n = FRAME_CONFIG["skip_frames"]
    last_auto_update = time.time()
    idata["running"] = True

    # Get class names from model
    class_names = model.names  # {0: 'person', 1: 'bicycle', 2: 'car', ...}

    while idata["running"]:
        try:
            loop_start = time.time()

            # Auto signal update
            if time.time() - last_auto_update >= 1.0:
                with data_lock:
                    update_signal_automatic(int_id)
                last_auto_update = time.time()

            ret, frame = cap.read()
            if not ret or frame is None:
                print(f"Frame read failed for {int_id}, reconnecting...")
                cap.release()
                time.sleep(1)
                cap = cv2.VideoCapture(cam_input)
                if camera_type == "usb":
                    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                if not cap.isOpened():
                    idata["camera_status"] = "reconnecting"
                    time.sleep(3)
                continue

            frame_count += 1

            # Build display frame with overlays
            display_frame = frame.copy()
            h_frame, w_frame = frame.shape[:2]

            # Add timestamp, intersection name, signal status
            ts_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cv2.putText(display_frame, f"{idata['name']} | {ts_str}", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

            signal_status = idata["signal"]
            signal_colors = {"red": (0, 0, 255), "yellow": (0, 255, 255), "green": (0, 255, 0)}
            sig_color = signal_colors.get(signal_status, (128, 128, 128))

            cv2.putText(display_frame, f"Signal: {signal_status.upper()}", (10, 60),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, sig_color, 2)

            auto_enabled = idata["auto_control"]["enabled"]
            cv2.putText(display_frame, f"Auto: {'ON' if auto_enabled else 'OFF'}", (10, 85),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                        (0, 200, 0) if auto_enabled else (128, 128, 128), 2)

            # Draw stop line
            stop_y = idata["stop_line"]["y_position"]
            if stop_y < h_frame:
                cv2.line(display_frame, (0, stop_y), (w_frame, stop_y), (0, 255, 255), 2)
                cv2.putText(display_frame, "STOP LINE", (10, stop_y - 8),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1)

            # Full YOLO detection on selected frames
            if frame_count % process_every_n == 0:
                current_time = time.time()

                # Run YOLOv11 inference
                results = model.predict(
                    frame,
                    conf=CONFIDENCE_THRESHOLD,
                    iou=IOU_THRESHOLD,
                    imgsz=FRAME_CONFIG["detection_size"],
                    verbose=False,
                    device="0" if _has_cuda() else "cpu",
                )

                vehicle_count = 0
                has_emergency = False
                current_vehicles = []

                if results and len(results) > 0:
                    boxes = results[0].boxes

                    for box in boxes:
                        cls_id = int(box.cls[0])
                        conf = float(box.conf[0])
                        cls_name = class_names.get(cls_id, "unknown")

                        if cls_name not in VEHICLE_CLASSES:
                            continue

                        vehicle_count += 1

                        # Get bounding box coordinates
                        x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                        w = x2 - x1
                        h = y2 - y1
                        center_x = (x1 + x2) // 2
                        center_y = (y1 + y2) // 2

                        # Match/assign vehicle ID
                        vehicle_id = match_vehicle_id(int_id, center_x, center_y)

                        # Calculate speed
                        speed = calculate_vehicle_speed(int_id, vehicle_id, (center_x, center_y), current_time)
                        is_speeding, actual_speed = detect_speeding(int_id, vehicle_id)

                        # Red light violation
                        is_red_violation, violation_reason = detect_red_light_violation(
                            int_id, vehicle_id, (center_x, center_y)
                        )

                        # Emergency vehicle detection
                        is_emergency = detect_emergency_vehicle(frame, x1, y1, w, h)
                        if is_emergency:
                            has_emergency = True

                        # Two-wheeler violations
                        helmet_violation = False
                        passenger_violation = False

                        if cls_name in ("motorcycle", "bicycle"):
                            if x1 >= 0 and y1 >= 0 and x2 < w_frame and y2 < h_frame:
                                vehicle_roi = frame[y1:y2, x1:x2]
                                person_count = count_people_on_vehicle(vehicle_roi, model)

                                if person_count > TWO_WHEELER_CONFIG["person_count_threshold"]:
                                    passenger_violation = True

                                if person_count > 0:
                                    if not detect_helmet(vehicle_roi):
                                        helmet_violation = True

                        vehicle_data = {
                            "id": vehicle_id,
                            "type": cls_name,
                            "confidence": round(conf, 2),
                            "position": (center_x, center_y),
                            "bbox": (x1, y1, x2, y2),
                            "size": (w, h),
                            "is_emergency": is_emergency,
                            "license_plate": generate_vehicle_plate_id(),
                            "helmet_violation": helmet_violation,
                            "passenger_violation": passenger_violation,
                            "speed_kmh": actual_speed,
                            "is_speeding": is_speeding,
                            "red_light_violation": is_red_violation,
                        }
                        current_vehicles.append(vehicle_data)

                        # Draw bounding box on display frame
                        if is_emergency:
                            box_color = (0, 0, 255)
                            label = f"EMERGENCY {cls_name}"
                        elif is_red_violation or helmet_violation or passenger_violation:
                            box_color = (0, 0, 255)
                            label = f"{cls_name} {vehicle_id} VIOLATION"
                        elif is_speeding:
                            box_color = (0, 165, 255)
                            label = f"{cls_name} {vehicle_id} SPEEDING"
                        else:
                            box_color = (0, 255, 0)
                            label = f"{cls_name} {vehicle_id} {conf:.0%}"

                        cv2.rectangle(display_frame, (x1, y1), (x2, y2), box_color, 2)
                        cv2.putText(display_frame, label, (x1, y1 - 8),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, box_color, 2)

                        if actual_speed > 0:
                            speed_color = (0, 0, 255) if is_speeding else (0, 255, 0)
                            cv2.putText(display_frame, f"{actual_speed:.0f} km/h",
                                        (x1, y2 + 15), cv2.FONT_HERSHEY_SIMPLEX, 0.4, speed_color, 1)

                        if is_red_violation:
                            cv2.putText(display_frame, "RED LIGHT!", (x1, y1 - 25),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)

                # Calculate PCE-weighted traffic density
                pce_density = 0.0
                type_counts = {}
                for v in current_vehicles:
                    vtype = v["type"]
                    type_counts[vtype] = type_counts.get(vtype, 0) + 1
                    pce_density += PCE_VALUES.get(vtype, 1.0)

                # Update shared state
                with data_lock:
                    idata["detected_vehicles"] = current_vehicles
                    idata["vehicle_count"] = vehicle_count
                    idata["pce_density"] = round(pce_density, 1)
                    idata["vehicle_type_counts"] = type_counts
                    idata["has_emergency"] = has_emergency
                    idata["timestamp"] = datetime.now().isoformat()

                    # Emergency priority - green corridor creation
                    if has_emergency:
                        idata["emergency_count"] = sum(1 for v in current_vehicles if v.get("is_emergency"))
                        if idata["signal"] != "green":
                            old_sig = idata["signal"]
                            idata["signal"] = "green"
                            idata["auto_control"]["last_change_time"] = time.time()
                            idata["vehicles_crossed_stop_line"].clear()
                            log_signal_change(int_id, old_sig, "green", "emergency")
                            log_emergency_event(int_id, "emergency_vehicle_detected", {
                                "vehicle_count": idata["emergency_count"],
                                "corridor": "activated",
                            })

                            for other_id, other_data in intersection_registry.items():
                                if other_id != int_id and other_data["signal"] != "yellow":
                                    old_other = other_data["signal"]
                                    other_data["signal"] = "red"
                                    if old_other != "red":
                                        log_signal_change(other_id, old_other, "red", "emergency_priority")
                    else:
                        idata["emergency_count"] = 0

                # Vehicle count and PCE density overlay
                cv2.putText(display_frame, f"Vehicles: {vehicle_count} | PCE: {pce_density:.1f}", (10, h_frame - 15),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

                # Clean up old vehicle positions (remove stale entries)
                if frame_count % (process_every_n * 20) == 0:
                    current_ids = {v["id"] for v in current_vehicles}
                    stale_ids = [vid for vid in idata["last_vehicle_positions"] if vid not in current_ids]
                    for vid in stale_ids[:len(stale_ids) // 2]:  # Remove half of stale entries
                        idata["last_vehicle_positions"].pop(vid, None)
                        idata["vehicle_tracking_history"].pop(vid, None)
                        idata["vehicle_speeds"].pop(vid, None)

            else:
                # Non-detection frame: show vehicle count from last detection
                cv2.putText(display_frame, f"Vehicles: {idata['vehicle_count']}", (10, h_frame - 15),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

            # Store processed frame for streaming
            with frame_lock:
                idata["processed_frame"] = display_frame

            # Frame rate control
            elapsed = time.time() - loop_start
            target_interval = 1.0 / FRAME_CONFIG["stream_fps"]
            sleep_time = max(0.001, target_interval - elapsed)
            time.sleep(sleep_time)

        except Exception as e:
            print(f"Error in detection for {int_id}: {e}")
            import traceback
            traceback.print_exc()
            time.sleep(0.1)

    # Cleanup
    if cap is not None:
        cap.release()
    print(f"Detection stopped for {int_id}")


def generate_vehicle_plate_id():
    """Generate a tracking ID for vehicles without ANPR.
    Returns 'N/A' to indicate no real plate recognition is available.
    In production, integrate an ANPR/OCR module here.
    """
    return "N/A"


def check_for_violations(int_id):
    """Check for traffic violations at intersection"""
    violations_count = 0

    with data_lock:
        idata = intersection_registry.get(int_id)
        if not idata:
            return 0

        vehicles = idata.get("detected_vehicles", [])

        for vehicle in vehicles:
            violation_type = None
            details = ""

            if vehicle.get("red_light_violation"):
                violation_type = "red_light"
                details = "Vehicle crossed stop line during red signal"
            elif vehicle.get("is_speeding"):
                violation_type = "speeding"
                speed = vehicle.get("speed_kmh", 0)
                details = f"Speeding at {speed:.0f} km/h (limit: {SPEED_LIMIT} km/h)"
            elif vehicle.get("type") in ("motorcycle", "bicycle"):
                if vehicle.get("helmet_violation"):
                    violation_type = "no_helmet"
                    details = "Riding without helmet"
                elif vehicle.get("passenger_violation"):
                    violation_type = "excess_passengers"
                    details = "Too many passengers on two-wheeler"

            if violation_type:
                violations_count += 1
                violation_data = {
                    "vehicleNumber": vehicle.get("license_plate", "Unknown"),
                    "type": violation_type,
                    "timestamp": datetime.now().isoformat(),
                    "location": idata["name"],
                    "details": details,
                    "speed": vehicle.get("speed_kmh"),
                    "imageUrl": None
                }

                if db is not None and violations_collection is not None:
                    try:
                        violations_collection.insert_one(violation_data)
                    except Exception as e:
                        print(f"Error saving violation: {e}")

    return violations_count


# ============= VIDEO STREAMING =============

def generate_frames(int_id, fps_requested=15):
    """Generator for MJPEG video streaming - optimized for performance"""
    fps_limit = min(fps_requested, FRAME_CONFIG["stream_fps"])
    interval = 1.0 / max(1, fps_limit)
    last_frame_time = 0

    while True:
        current_time = time.time()
        if current_time - last_frame_time < interval:
            time.sleep(0.005)  # Small sleep to prevent busy-waiting
            continue

        last_frame_time = current_time

        idata = intersection_registry.get(int_id)
        if not idata:
            time.sleep(0.1)
            continue

        with frame_lock:
            frame = idata.get("processed_frame")
            if frame is None:
                continue
            frame = frame.copy()

        # Resize if needed
        if frame.shape[1] > FRAME_CONFIG["max_width"]:
            scale = FRAME_CONFIG["max_width"] / frame.shape[1]
            new_w = FRAME_CONFIG["max_width"]
            new_h = int(frame.shape[0] * scale)
            frame = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

        # Encode to JPEG
        ret, buffer = cv2.imencode('.jpg', frame,
                                   [int(cv2.IMWRITE_JPEG_QUALITY), FRAME_CONFIG["frame_quality"]])
        if not ret:
            continue

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')


# ============= START/STOP DETECTION THREADS =============

def start_detection_thread(int_id):
    """Start detection thread for an intersection"""
    idata = intersection_registry.get(int_id)
    if not idata:
        return False

    if idata["detection_thread"] is not None and idata["detection_thread"].is_alive():
        return True  # Already running

    idata["running"] = True
    thread = threading.Thread(target=detect_vehicles, args=(int_id,), daemon=True)
    thread.start()
    idata["detection_thread"] = thread
    print(f"Started detection thread for {int_id}")
    return True


def stop_detection_thread(int_id):
    """Stop detection thread for an intersection"""
    idata = intersection_registry.get(int_id)
    if not idata:
        return

    idata["running"] = False
    if idata["detection_thread"] is not None:
        idata["detection_thread"].join(timeout=5)
        idata["detection_thread"] = None
    print(f"Stopped detection thread for {int_id}")


# ============= API ENDPOINTS =============

@app.route('/api/traffic', methods=['GET'])
def get_traffic_data():
    """Return current traffic data for all intersections"""
    result = []
    with data_lock:
        for int_id, idata in intersection_registry.items():
            result.append({
                "intersectionId": int_id,
                "name": idata["name"],
                "vehicleCount": idata["vehicle_count"],
                "pceDensity": idata.get("pce_density", 0.0),
                "vehicleTypeCounts": idata.get("vehicle_type_counts", {}),
                "hasEmergencyVehicle": idata["has_emergency"],
                "emergencyCount": idata.get("emergency_count", 0),
                "timestamp": idata["timestamp"],
                "status": idata["signal"],
                "autoMode": idata["auto_control"]["enabled"],
                "cameraStatus": idata["camera_status"],
                "zoneId": idata.get("zone_id"),
            })
    return jsonify(result)


@app.route('/api/traffic/signal', methods=['POST'])
@require_api_key
def update_signal():
    """Update traffic signal status"""
    data = request.json
    int_id = data.get('intersectionId')
    status = data.get('status')

    if not int_id or status not in ("red", "yellow", "green"):
        return jsonify({"success": False, "error": "Invalid parameters"}), 400

    with data_lock:
        idata = intersection_registry.get(int_id)
        if not idata:
            return jsonify({"success": False, "error": "Unknown intersection"}), 404

        if idata["auto_control"]["enabled"]:
            return jsonify({"success": False, "error": "Cannot change signal while auto mode is enabled"}), 400

        old_signal = idata["signal"]
        idata["signal"] = status
        if status == "green":
            idata["vehicles_crossed_stop_line"].clear()

    # Log and send to physical signal controller
    log_signal_change(int_id, old_signal, status, "manual")

    return jsonify({"success": True})


@app.route('/api/traffic/auto_control', methods=['POST'])
@require_api_key
def toggle_auto_control():
    """Toggle automatic signal control"""
    data = request.json
    int_id = data.get('intersectionId')
    enabled = data.get('enabled')

    if not int_id or enabled is None:
        return jsonify({"success": False, "error": "Invalid parameters"}), 400

    with data_lock:
        idata = intersection_registry.get(int_id)
        if not idata:
            return jsonify({"success": False, "error": "Unknown intersection"}), 404

        idata["auto_control"]["enabled"] = enabled
        idata["auto_control"]["last_change_time"] = time.time()

    return jsonify({"success": True})


@app.route('/api/traffic/check_violations', methods=['POST'])
def check_violations_endpoint():
    """Check for violations at an intersection"""
    data = request.json
    int_id = data.get('intersectionId')

    if not int_id:
        return jsonify({"success": False, "error": "Invalid intersection ID"}), 400

    violations = check_for_violations(int_id)
    return jsonify({"success": True, "violations": violations})


@app.route('/api/traffic/violations', methods=['GET'])
def get_violations():
    """Get recorded violations"""
    if db is not None and violations_collection is not None:
        try:
            cursor = violations_collection.find().sort("timestamp", -1).limit(50)
            violations = []
            for doc in cursor:
                doc["id"] = str(doc.pop("_id"))
                violations.append(doc)
            return jsonify(violations)
        except Exception as e:
            print(f"Error retrieving violations: {e}")
            return jsonify([])
    else:
        # Simulated violations when no DB
        return jsonify([
            {
                "id": f"sim-{i}",
                "vehicleNumber": f"SIM-{random.randint(1000,9999)}",
                "type": random.choice(["red_light", "speeding", "no_helmet", "excess_passengers"]),
                "timestamp": (datetime.now() - timedelta(minutes=i)).isoformat(),
                "location": random.choice([d["name"] for d in intersection_registry.values()] or ["Unknown"]),
                "details": "Simulated violation (no database)",
                "imageUrl": None
            }
            for i in range(1, 6)
        ])


@app.route('/api/traffic/patterns', methods=['GET'])
def get_traffic_patterns():
    """Get learned traffic patterns and predictions"""
    result = {}
    with data_lock:
        for int_id, idata in intersection_registry.items():
            result[int_id] = {
                "patterns": {str(k): v for k, v in idata["patterns"].items()},
                "predictions": idata["predictions"],
                "current_hour": datetime.now().hour,
            }
    return jsonify(result)


@app.route('/api/traffic/speeds', methods=['GET'])
def get_vehicle_speeds():
    """Get current vehicle speed data"""
    result = {}
    with data_lock:
        for int_id, idata in intersection_registry.items():
            speeds = idata.get("vehicle_speeds", {})
            speed_values = list(speeds.values())
            result[int_id] = {
                "vehicles": [{"id": k, "speed": v} for k, v in speeds.items()],
                "average_speed": round(sum(speed_values) / len(speed_values), 1) if speed_values else 0,
                "max_speed": round(max(speed_values), 1) if speed_values else 0,
                "speeding_count": sum(1 for v in speed_values if v > SPEED_LIMIT),
                "speed_limit": SPEED_LIMIT,
            }
    return jsonify(result)


@app.route('/api/traffic/learning_logs', methods=['GET'])
def get_learning_logs():
    """Get recent learning logs"""
    if db is not None and learning_logs_collection is not None:
        try:
            cursor = learning_logs_collection.find().sort("timestamp", -1).limit(100)
            logs = []
            for doc in cursor:
                doc["id"] = str(doc.pop("_id"))
                logs.append(doc)
            return jsonify(logs)
        except Exception as e:
            print(f"Error retrieving learning logs: {e}")
            return jsonify([])
    return jsonify([])


@app.route('/api/video_feed/<int_id>')
def video_feed(int_id):
    """MJPEG video streaming endpoint"""
    with data_lock:
        if int_id not in intersection_registry:
            return "Invalid intersection ID", 404

    fps = request.args.get('fps', 15, type=float)
    return Response(
        generate_frames(int_id, fps),
        mimetype='multipart/x-mixed-replace; boundary=frame',
        headers={
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'Pragma': 'no-cache',
            'Expires': '0',
            'Connection': 'keep-alive',
        }
    )


@app.route('/api/stream_status')
def stream_status():
    """Stream diagnostics"""
    return jsonify({
        "stream_fps": FRAME_CONFIG["stream_fps"],
        "process_skip_frames": FRAME_CONFIG["skip_frames"],
        "frame_quality": FRAME_CONFIG["frame_quality"],
        "detection_size": FRAME_CONFIG["detection_size"],
        "yolo_model": YOLO_MODEL_NAME,
        "cuda_available": _has_cuda(),
    })


# ============= CAMERA / INTERSECTION MANAGEMENT =============

@app.route('/api/traffic/cameras', methods=['GET'])
def get_camera_configs():
    """Get all camera configurations"""
    result = []
    with data_lock:
        for int_id, idata in intersection_registry.items():
            result.append({
                "intersection_id": int_id,
                "name": idata["name"],
                "camera_source": idata["camera_source"],
                "camera_type": idata["camera_type"],
                "status": idata["camera_status"],
            })
    return jsonify(result)


@app.route('/api/traffic/configure_camera', methods=['POST'])
def configure_camera():
    """Configure camera for an intersection (or update existing)"""
    data = request.json
    int_id = data.get('intersectionId')
    camera_source = data.get('cameraSource')
    camera_type = data.get('cameraType', 'usb')

    if not int_id or camera_source is None:
        return jsonify({"success": False, "error": "Invalid parameters"}), 400

    with data_lock:
        idata = intersection_registry.get(int_id)
        if idata:
            # Update existing - stop old thread, update config
            idata["camera_source"] = str(camera_source)
            idata["camera_type"] = camera_type
            idata["camera_status"] = "configured"
        else:
            return jsonify({"success": False, "error": "Intersection not found. Use /api/traffic/intersections to add."}), 404

    # Restart detection thread with new camera
    stop_detection_thread(int_id)
    time.sleep(1)
    start_detection_thread(int_id)

    return jsonify({"success": True, "message": "Camera configured and detection restarted."})


@app.route('/api/traffic/intersections', methods=['POST'])
@require_api_key
def add_intersection():
    """Add a new intersection/camera"""
    data = request.json
    int_id = data.get('intersectionId')
    name = data.get('name', f'Intersection {int_id}')
    camera_source = data.get('cameraSource', '0')
    camera_type = data.get('cameraType', 'usb')

    if not int_id:
        return jsonify({"success": False, "error": "intersectionId required"}), 400

    # Optional: signal controller, location, zone
    signal_ctrl = data.get('signalController', {})
    latitude = data.get('latitude', 0.0)
    longitude = data.get('longitude', 0.0)
    zone_id = data.get('zoneId')

    with data_lock:
        if int_id in intersection_registry:
            return jsonify({"success": False, "error": f"Intersection {int_id} already exists"}), 409

        idata = create_intersection_data(int_id, name, str(camera_source), camera_type)
        idata['latitude'] = latitude
        idata['longitude'] = longitude
        idata['zone_id'] = zone_id
        if signal_ctrl:
            idata['signal_controller'] = signal_ctrl
        intersection_registry[int_id] = idata

    # Register signal controller if configured
    if signal_ctrl and signal_ctrl.get('type') and signal_ctrl.get('type') != 'mock':
        signal_controller.register_controller(int_id, signal_ctrl)

    # Add to zone if specified
    if zone_id:
        with zone_lock:
            zone = zone_registry.get(zone_id)
            if zone and int_id not in zone['intersection_ids']:
                zone['intersection_ids'].append(int_id)

    # Persist to database
    save_intersection_to_db(int_id)

    # Start detection
    start_detection_thread(int_id)

    return jsonify({"success": True, "message": f"Intersection {int_id} added and detection started."})


@app.route('/api/traffic/intersections/<int_id>', methods=['DELETE'])
@require_api_key
def remove_intersection(int_id):
    """Remove an intersection"""
    with data_lock:
        if int_id not in intersection_registry:
            return jsonify({"success": False, "error": "Intersection not found"}), 404

    stop_detection_thread(int_id)

    with data_lock:
        del intersection_registry[int_id]

    remove_intersection_from_db(int_id)

    return jsonify({"success": True, "message": f"Intersection {int_id} removed."})


@app.route('/api/traffic/intersections', methods=['GET'])
def list_intersections():
    """List all intersections"""
    result = []
    with data_lock:
        for int_id, idata in intersection_registry.items():
            result.append({
                "id": int_id,
                "name": idata["name"],
                "camera_source": idata["camera_source"],
                "camera_type": idata["camera_type"],
                "camera_status": idata["camera_status"],
                "signal": idata["signal"],
                "vehicle_count": idata["vehicle_count"],
                "auto_mode": idata["auto_control"]["enabled"],
            })
    return jsonify(result)


@app.route('/api/traffic/congestion', methods=['GET'])
def get_congestion():
    """Get congestion summary"""
    result = {}
    with data_lock:
        for int_id, idata in intersection_registry.items():
            count = idata["vehicle_count"]
            pce = idata.get("pce_density", 0.0)
            level = "high" if pce > 15 else "medium" if pce > 8 else "low"
            result[int_id] = {
                "vehicle_count": count,
                "pce_density": pce,
                "vehicle_type_counts": idata.get("vehicle_type_counts", {}),
                "congestion_level": level,
                "trend": idata["predictions"].get("trend", "stable"),
                "confidence": idata["predictions"].get("confidence", 0),
                "is_peak_hour": idata["predictions"].get("is_peak_hour", False),
            }
    return jsonify(result)


@app.route('/api/traffic/calibration/<int_id>', methods=['POST'])
@require_api_key
def set_speed_calibration(int_id):
    """Set per-intersection speed calibration (pixels_per_meter)"""
    data = request.json
    ppm = data.get('pixels_per_meter')

    if ppm is None or not isinstance(ppm, (int, float)) or ppm <= 0:
        return jsonify({"success": False, "error": "pixels_per_meter must be a positive number"}), 400

    with data_lock:
        idata = intersection_registry.get(int_id)
        if not idata:
            return jsonify({"success": False, "error": "Intersection not found"}), 404
        idata['pixels_per_meter'] = float(ppm)

    save_intersection_to_db(int_id)
    return jsonify({"success": True, "message": f"Speed calibration set to {ppm} px/m for {int_id}"})


# ============= ZONE MANAGEMENT APIs =============

@app.route('/api/zones', methods=['GET'])
def list_zones():
    """List all traffic management zones"""
    with zone_lock:
        result = []
        for zid, zone in zone_registry.items():
            result.append({
                'id': zid,
                'name': zone['name'],
                'intersection_count': len(zone['intersection_ids']),
                'intersection_ids': zone['intersection_ids'],
                'emergency_corridor_active': zone['emergency_corridor']['active'],
                'green_wave_enabled': zone['green_wave']['enabled'],
            })
    return jsonify(result)


@app.route('/api/zones', methods=['POST'])
@require_api_key
def create_zone_endpoint():
    """Create a new zone"""
    data = request.json
    zone_id = data.get('zoneId')
    name = data.get('name', f'Zone {zone_id}')
    intersection_ids = data.get('intersectionIds', [])

    if not zone_id:
        return jsonify({"success": False, "error": "zoneId required"}), 400

    with zone_lock:
        if zone_id in zone_registry:
            return jsonify({"success": False, "error": "Zone already exists"}), 409

    create_zone(zone_id, name, intersection_ids)

    # Update intersection zone assignments
    with data_lock:
        for int_id in intersection_ids:
            idata = intersection_registry.get(int_id)
            if idata:
                idata['zone_id'] = zone_id

    save_zone_to_db(zone_id)

    return jsonify({"success": True, "message": f"Zone {zone_id} created"})


@app.route('/api/zones/<zone_id>', methods=['DELETE'])
@require_api_key
def delete_zone(zone_id):
    """Delete a zone"""
    with zone_lock:
        if zone_id not in zone_registry:
            return jsonify({"success": False, "error": "Zone not found"}), 404
        zone = zone_registry.pop(zone_id)

    # Clear zone assignment from intersections
    with data_lock:
        for int_id in zone.get('intersection_ids', []):
            idata = intersection_registry.get(int_id)
            if idata:
                idata['zone_id'] = None

    remove_zone_from_db(zone_id)

    return jsonify({"success": True})


@app.route('/api/zones/<zone_id>/intersections', methods=['POST'])
def add_intersection_to_zone(zone_id):
    """Add an intersection to a zone"""
    data = request.json
    int_id = data.get('intersectionId')

    with zone_lock:
        zone = zone_registry.get(zone_id)
        if not zone:
            return jsonify({"success": False, "error": "Zone not found"}), 404
        if int_id not in zone['intersection_ids']:
            zone['intersection_ids'].append(int_id)

    with data_lock:
        idata = intersection_registry.get(int_id)
        if idata:
            idata['zone_id'] = zone_id

    return jsonify({"success": True})


@app.route('/api/zones/<zone_id>/emergency_corridor', methods=['POST'])
def activate_corridor_endpoint(zone_id):
    """Activate emergency green corridor across a zone"""
    data = request.json
    path = data.get('path', [])
    vehicle_id = data.get('vehicleId')

    if not path:
        # Default: use all intersections in zone
        with zone_lock:
            zone = zone_registry.get(zone_id)
            if zone:
                path = zone['intersection_ids']

    success = activate_emergency_corridor(zone_id, path, vehicle_id)
    return jsonify({"success": success})


@app.route('/api/zones/<zone_id>/emergency_corridor', methods=['DELETE'])
def deactivate_corridor_endpoint(zone_id):
    """Deactivate emergency corridor"""
    success = deactivate_emergency_corridor(zone_id)
    return jsonify({"success": success})


# ============= SIGNAL CONTROLLER APIs =============

@app.route('/api/signal_controllers', methods=['GET'])
def get_signal_controllers():
    """Get status of all signal controllers"""
    return jsonify(signal_controller.get_status())


@app.route('/api/signal_controllers/<int_id>', methods=['POST'])
@require_api_key
def configure_signal_controller(int_id):
    """Register/update a signal controller for an intersection"""
    data = request.json
    config = {
        'type': data.get('type', 'http'),
        'endpoint': data.get('endpoint', ''),
        'auth_token': data.get('authToken', ''),
        'timeout': data.get('timeout', 5),
        'retry_count': data.get('retryCount', 3),
        'broker': data.get('broker', 'localhost'),
        'port': data.get('port', 1883),
        'topic': data.get('topic', f'traffic/signals/{int_id}'),
        'pins': data.get('pins', {'red': 17, 'yellow': 27, 'green': 22}),
    }

    signal_controller.register_controller(int_id, config)

    # Also save to intersection data
    with data_lock:
        idata = intersection_registry.get(int_id)
        if idata:
            idata['signal_controller'] = config

    return jsonify({"success": True, "message": f"Signal controller configured for {int_id}"})


@app.route('/api/signal_controllers/<int_id>', methods=['DELETE'])
def remove_signal_controller(int_id):
    """Remove a signal controller"""
    signal_controller.unregister_controller(int_id)
    return jsonify({"success": True})


@app.route('/api/signal_controllers/history', methods=['GET'])
def get_signal_command_history():
    """Get recent signal command history"""
    limit = request.args.get('limit', 50, type=int)
    return jsonify(signal_controller.get_command_history(limit))


@app.route('/api/signal_controllers/<int_id>/test', methods=['POST'])
def test_signal_controller(int_id):
    """Test a signal controller by sending a test command"""
    data = request.json or {}
    test_signal = data.get('signal', 'green')

    signal_controller.send_signal(int_id, test_signal, priority='test')
    return jsonify({"success": True, "message": f"Test command sent: {test_signal}"})


# ============= BULK OPERATIONS (City-Scale) =============

@app.route('/api/bulk/signals', methods=['POST'])
@require_api_key
def bulk_signal_update():
    """Bulk update signals across multiple intersections"""
    data = request.json
    updates = data.get('updates', [])  # [{intersectionId, signal}]
    results = []

    with data_lock:
        for update in updates:
            int_id = update.get('intersectionId')
            new_signal = update.get('signal')
            idata = intersection_registry.get(int_id)

            if idata and new_signal in ("red", "yellow", "green"):
                old_signal = idata['signal']
                idata['signal'] = new_signal
                log_signal_change(int_id, old_signal, new_signal, "bulk_manual")
                results.append({"intersectionId": int_id, "success": True})
            else:
                results.append({"intersectionId": int_id, "success": False, "error": "Invalid"})

    return jsonify({"success": True, "results": results})


@app.route('/api/bulk/auto_control', methods=['POST'])
@require_api_key
def bulk_auto_control():
    """Bulk enable/disable auto control"""
    data = request.json
    intersection_ids = data.get('intersectionIds', [])
    enabled = data.get('enabled', True)

    with data_lock:
        for int_id in intersection_ids:
            idata = intersection_registry.get(int_id)
            if idata:
                idata['auto_control']['enabled'] = enabled
                idata['auto_control']['last_change_time'] = time.time()

    return jsonify({"success": True, "updated": len(intersection_ids)})


@app.route('/api/stats/overview', methods=['GET'])
def get_system_overview():
    """Get system-wide statistics for dashboard"""
    with data_lock:
        total_vehicles = sum(d['vehicle_count'] for d in intersection_registry.values())
        total_pce = sum(d.get('pce_density', 0) for d in intersection_registry.values())
        emergency_count = sum(1 for d in intersection_registry.values() if d['has_emergency'])
        total_emergency_vehicles = sum(d.get('emergency_count', 0) for d in intersection_registry.values())
        active_cameras = sum(1 for d in intersection_registry.values() if d['camera_status'] == 'active')
        auto_mode_count = sum(1 for d in intersection_registry.values() if d['auto_control']['enabled'])

    with zone_lock:
        active_corridors = sum(1 for z in zone_registry.values() if z['emergency_corridor']['active'])

    return jsonify({
        'monitored_intersections': len(intersection_registry),
        'total_vehicles': total_vehicles,
        'total_pce_density': round(total_pce, 1),
        'emergency_vehicles': total_emergency_vehicles,
        'emergency_intersections': emergency_count,
        'active_cameras': active_cameras,
        'auto_mode_count': auto_mode_count,
        'total_zones': len(zone_registry),
        'active_emergency_corridors': active_corridors,
        'signal_controllers': len(signal_controller.controllers),
        'yolo_model': YOLO_MODEL_NAME,
        'cuda_available': _has_cuda(),
    })


@app.route('/api/emergency_events', methods=['GET'])
def get_emergency_events():
    """Get recent emergency events"""
    if emergency_events_collection is not None:
        try:
            limit = request.args.get('limit', 50, type=int)
            cursor = emergency_events_collection.find().sort("timestamp", -1).limit(limit)
            events = []
            for doc in cursor:
                doc['id'] = str(doc.pop('_id'))
                events.append(doc)
            return jsonify(events)
        except Exception as e:
            logger.error(f"Error getting emergency events: {e}")
    return jsonify([])


@app.route('/api/signal_history', methods=['GET'])
def get_signal_history():
    """Get signal change history"""
    if signal_history_collection is not None:
        try:
            limit = request.args.get('limit', 100, type=int)
            int_id = request.args.get('intersectionId')
            query = {"intersection_id": int_id} if int_id else {}
            cursor = signal_history_collection.find(query).sort("timestamp", -1).limit(limit)
            history = []
            for doc in cursor:
                doc['id'] = str(doc.pop('_id'))
                history.append(doc)
            return jsonify(history)
        except Exception as e:
            logger.error(f"Error getting signal history: {e}")
    return jsonify([])


# ============= SIMULATION APIs =============

from simulation import sim_manager

@app.route('/api/simulation', methods=['GET'])
def list_simulations():
    """List all active simulations."""
    return jsonify(sim_manager.list_simulations())


@app.route('/api/simulation/<int_id>', methods=['POST'])
def create_simulation(int_id):
    """Create and start a simulation for an intersection."""
    data = request.json or {}
    name = data.get('name', f'Simulation {int_id}')

    # Ensure intersection exists in registry
    with data_lock:
        if int_id not in intersection_registry:
            idata = create_intersection_data(int_id, name, "simulation", "simulation")
            idata["camera_status"] = "active"
            intersection_registry[int_id] = idata

    sim = sim_manager.create_simulation(int_id, name)
    sim.update_config(data)
    sim.start()

    # Start feeding simulation data into the main system
    sim_manager.start_feed_to_system(intersection_registry, data_lock, frame_lock)

    return jsonify({"success": True, "message": f"Simulation started for {int_id}", "config": sim.get_config()})


@app.route('/api/simulation/<int_id>', methods=['PUT'])
def update_simulation(int_id):
    """Update simulation configuration."""
    sim = sim_manager.get_simulation(int_id)
    if not sim:
        return jsonify({"success": False, "error": "Simulation not found"}), 404

    data = request.json or {}
    sim.update_config(data)
    return jsonify({"success": True, "config": sim.get_config()})


@app.route('/api/simulation/<int_id>', methods=['DELETE'])
def delete_simulation(int_id):
    """Stop and remove a simulation."""
    sim_manager.remove_simulation(int_id)
    return jsonify({"success": True})


@app.route('/api/simulation/<int_id>/spawn', methods=['POST'])
def spawn_vehicle(int_id):
    """Spawn a vehicle in the simulation."""
    sim = sim_manager.get_simulation(int_id)
    if not sim:
        return jsonify({"success": False, "error": "Simulation not found"}), 404

    data = request.json or {}
    vid = sim.spawn_vehicle(
        vehicle_type=data.get('type'),
        direction=data.get('direction'),
        speed=data.get('speed'),
        lane=data.get('lane'),
        is_violator=data.get('is_violator'),
        helmet_violation=data.get('helmet_violation'),
    )
    return jsonify({"success": True, "vehicleId": vid})


@app.route('/api/simulation/<int_id>/remove_vehicle', methods=['POST'])
def remove_sim_vehicle(int_id):
    """Remove a specific vehicle from the simulation."""
    sim = sim_manager.get_simulation(int_id)
    if not sim:
        return jsonify({"success": False, "error": "Simulation not found"}), 404

    data = request.json or {}
    vid = data.get('vehicleId')
    if vid:
        sim.remove_vehicle(vid)
    return jsonify({"success": True})


@app.route('/api/simulation/<int_id>/clear', methods=['POST'])
def clear_sim_vehicles(int_id):
    """Remove all vehicles from simulation."""
    sim = sim_manager.get_simulation(int_id)
    if not sim:
        return jsonify({"success": False, "error": "Simulation not found"}), 404

    sim.clear_vehicles()
    return jsonify({"success": True})


@app.route('/api/simulation/<int_id>/status', methods=['GET'])
def get_simulation_status(int_id):
    """Get simulation status and vehicle list."""
    sim = sim_manager.get_simulation(int_id)
    if not sim:
        return jsonify({"success": False, "error": "Simulation not found"}), 404

    det = sim.get_detection_results()
    config = sim.get_config()
    return jsonify({**config, "detection": det})


# ============= MAIN =============

if __name__ == '__main__':
    print("=" * 60)
    print("Smart Signal Sentinel - Traffic Management System")
    print("YOLOv11 + Dynamic Multi-Camera Support")
    print("=" * 60)

    # Check dependencies
    if not YOLO_AVAILABLE:
        print("\nERROR: ultralytics is required. Install with:")
        print("  pip install ultralytics")
        print("\nThe YOLOv11 model will be downloaded automatically on first run.\n")

    # Pre-load the YOLO model
    print("\nLoading YOLOv11 model...")
    model = load_yolo_model()
    if model:
        print(f"Model ready: {YOLO_MODEL_NAME}")
    else:
        print("WARNING: Model loading failed. Detection will not work.")

    # Load persisted data from MongoDB, then init defaults if empty
    load_persisted_data()
    init_default_intersections()

    # Start pattern learning thread
    learn_thread = threading.Thread(target=pattern_learning_thread, daemon=True)
    learn_thread.start()
    print("Started pattern learning thread")

    # Start detection threads for all configured intersections
    with data_lock:
        for int_id in list(intersection_registry.keys()):
            start_detection_thread(int_id)

    print(f"\nActive intersections: {list(intersection_registry.keys())}")
    print("Starting Flask server on http://0.0.0.0:5000")
    print("=" * 60)

    app.run(debug=False, threaded=True, host='0.0.0.0', port=5000)
