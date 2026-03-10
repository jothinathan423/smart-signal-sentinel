
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

# ============= MONGODB SETUP =============
mongo_client = None
db = None
violations_collection = None
patterns_collection = None
learning_logs_collection = None

if PYMONGO_AVAILABLE:
    try:
        mongo_client = pymongo.MongoClient("mongodb://localhost:27017/", serverSelectionTimeoutMS=2000)
        mongo_client.server_info()
        db = mongo_client["traffic_management"]
        violations_collection = db["violations"]
        patterns_collection = db["traffic_patterns"]
        learning_logs_collection = db["learning_logs"]
        print("Successfully connected to MongoDB")
    except Exception as e:
        print(f"Warning: Could not connect to MongoDB: {e}")
        print("Vehicle violations will not be stored in database")

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
    "min_size": 60,
    "red_threshold": 4.0,
    "blue_threshold": 4.0,
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

        # Traffic data
        "vehicle_count": 0,
        "pce_density": 0.0,  # PCE-weighted traffic density
        "vehicle_type_counts": {},  # {type: count} for PCE breakdown
        "has_emergency": False,
        "timestamp": "",

        # Signal
        "signal": "red",
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

        # Stop line / violations
        "stop_line": {"y_position": 350, "tolerance": 20},
        "vehicles_crossed_stop_line": set(),

        # Frames
        "latest_frame": None,
        "processed_frame": None,

        # Thread control
        "detection_thread": None,
        "running": False,
    }


def init_default_intersections():
    """Initialize default intersections"""
    with data_lock:
        if "int-001" not in intersection_registry:
            intersection_registry["int-001"] = create_intersection_data(
                "int-001", "Main Street Intersection", "0", "usb"
            )
            intersection_registry["int-001"]["signal"] = "red"
        if "int-002" not in intersection_registry:
            intersection_registry["int-002"] = create_intersection_data(
                "int-002", "Park Avenue Intersection", "1", "usb"
            )
            intersection_registry["int-002"]["signal"] = "green"


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

    displacement_meters = displacement_pixels / PIXELS_PER_METER
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
            idata["vehicles_crossed_stop_line"].add(vehicle_id)
            if current_signal == "red":
                return True, "Vehicle crossed stop line during red signal"

    return False, None


def detect_speeding(int_id, vehicle_id):
    """Check if vehicle is speeding"""
    idata = intersection_registry[int_id]
    speed = idata["vehicle_speeds"].get(vehicle_id, 0)
    return (speed > SPEED_LIMIT, speed)


def detect_helmet(person_roi):
    """Helmet detection using color and shape analysis"""
    if person_roi is None or person_roi.size == 0:
        return True

    try:
        height, width = person_roi.shape[:2]
        head_region = person_roi[0:int(height * 0.3), :]

        if head_region.size == 0:
            return True

        hsv = cv2.cvtColor(head_region, cv2.COLOR_BGR2HSV)
        helmet_detected = False

        for color_name, (lower, upper) in TWO_WHEELER_CONFIG["helmet_color_ranges"].items():
            mask = cv2.inRange(hsv, np.array(lower), np.array(upper))
            helmet_ratio = cv2.countNonZero(mask) / (head_region.shape[0] * head_region.shape[1])

            if helmet_ratio > 0.15:
                helmet_detected = True
                break

        if not helmet_detected:
            gray = cv2.cvtColor(head_region, cv2.COLOR_BGR2GRAY)
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            circles = cv2.HoughCircles(blurred, cv2.HOUGH_GRADIENT, 1, 20,
                                       param1=50, param2=30, minRadius=10, maxRadius=50)
            if circles is not None:
                helmet_detected = True

        return helmet_detected
    except Exception:
        return True


def detect_emergency_vehicle(frame, x, y, w, h):
    """Detect emergency vehicle by red/blue color analysis"""
    if w < EMERGENCY_CONFIG["min_size"] or h < EMERGENCY_CONFIG["min_size"]:
        return False

    height, width = frame.shape[:2]
    if x < 0 or y < 0 or x + w >= width or y + h >= height:
        return False

    vehicle_roi = frame[y:y + h, x:x + w]
    hsv = cv2.cvtColor(vehicle_roi, cv2.COLOR_BGR2HSV)

    # Red detection (two ranges for red hue wrap-around)
    mask_red1 = cv2.inRange(hsv, np.array([0, 120, 70]), np.array([10, 255, 255]))
    mask_red2 = cv2.inRange(hsv, np.array([170, 120, 70]), np.array([180, 255, 255]))
    mask_red = mask_red1 | mask_red2

    # Blue detection
    mask_blue = cv2.inRange(hsv, np.array([100, 50, 50]), np.array([130, 255, 255]))

    total_pixels = w * h
    red_percent = cv2.countNonZero(mask_red) / total_pixels * 100
    blue_percent = cv2.countNonZero(mask_blue) / total_pixels * 100

    return red_percent > EMERGENCY_CONFIG["red_threshold"] or blue_percent > EMERGENCY_CONFIG["blue_threshold"]


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


# ============= SIGNAL COORDINATION =============

def coordinate_traffic_signals():
    """Coordinate signals across all intersections"""
    while True:
        try:
            with data_lock:
                int_ids = list(intersection_registry.keys())
                auto_ids = [iid for iid in int_ids if intersection_registry[iid]["auto_control"]["enabled"]]

                if len(auto_ids) >= 2:
                    # Ensure only one intersection has green at a time
                    green_ids = [iid for iid in auto_ids if intersection_registry[iid]["signal"] == "green"]
                    if len(green_ids) > 1:
                        # Keep only the first green, set others to red
                        for iid in green_ids[1:]:
                            if intersection_registry[iid]["signal"] != "yellow":
                                intersection_registry[iid]["signal"] = "red"

            time.sleep(1)
        except Exception as e:
            print(f"Error in signal coordination: {e}")
            time.sleep(1)


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

        idata["signal"] = new_signal
        idata["auto_control"]["last_change_time"] = current_time

        # Coordinate: when this goes green, others go red
        if new_signal == "green":
            for other_id, other_data in intersection_registry.items():
                if other_id != int_id and other_data["auto_control"]["enabled"]:
                    if other_data["signal"] != "yellow":
                        other_data["signal"] = "red"

        elif new_signal == "red":
            # Find next intersection that should get green
            all_ids = list(intersection_registry.keys())
            idx = all_ids.index(int_id) if int_id in all_ids else -1
            if idx >= 0:
                next_idx = (idx + 1) % len(all_ids)
                next_id = all_ids[next_idx]
                next_data = intersection_registry[next_id]
                if next_data["auto_control"]["enabled"] and next_data["signal"] == "red":
                    if current_time - next_data["auto_control"]["last_change_time"] > 5:
                        next_data["signal"] = "green"
                        next_data["auto_control"]["last_change_time"] = current_time
                        next_data["vehicles_crossed_stop_line"].clear()


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
                            "license_plate": generate_license_plate() if random.random() < 0.8 else None,
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

                    # Emergency priority
                    if has_emergency and idata["signal"] != "green":
                        idata["signal"] = "green"
                        idata["auto_control"]["last_change_time"] = time.time()
                        idata["vehicles_crossed_stop_line"].clear()

                        for other_id, other_data in intersection_registry.items():
                            if other_id != int_id and other_data["signal"] != "yellow":
                                other_data["signal"] = "red"

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


def _has_cuda():
    """Check if CUDA is available"""
    try:
        import torch
        return torch.cuda.is_available()
    except ImportError:
        return False


def generate_license_plate():
    """Generate random license plate"""
    letters = "ABCDEFGHJKLMNPQRSTUVWXYZ"
    numbers = "0123456789"
    return (''.join(random.choice(letters) for _ in range(2)) +
            ''.join(random.choice(numbers) for _ in range(2)) +
            ''.join(random.choice(letters) for _ in range(3)))


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
                "timestamp": idata["timestamp"],
                "status": idata["signal"],
                "autoMode": idata["auto_control"]["enabled"],
                "cameraStatus": idata["camera_status"],
            })
    return jsonify(result)


@app.route('/api/traffic/signal', methods=['POST'])
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

        idata["signal"] = status
        if status == "green":
            idata["vehicles_crossed_stop_line"].clear()

    return jsonify({"success": True})


@app.route('/api/traffic/auto_control', methods=['POST'])
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
                "vehicleNumber": generate_license_plate(),
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
def add_intersection():
    """Add a new intersection/camera"""
    data = request.json
    int_id = data.get('intersectionId')
    name = data.get('name', f'Intersection {int_id}')
    camera_source = data.get('cameraSource', '0')
    camera_type = data.get('cameraType', 'usb')

    if not int_id:
        return jsonify({"success": False, "error": "intersectionId required"}), 400

    with data_lock:
        if int_id in intersection_registry:
            return jsonify({"success": False, "error": f"Intersection {int_id} already exists"}), 409

        intersection_registry[int_id] = create_intersection_data(int_id, name, str(camera_source), camera_type)

    # Start detection
    start_detection_thread(int_id)

    return jsonify({"success": True, "message": f"Intersection {int_id} added and detection started."})


@app.route('/api/traffic/intersections/<int_id>', methods=['DELETE'])
def remove_intersection(int_id):
    """Remove an intersection"""
    with data_lock:
        if int_id not in intersection_registry:
            return jsonify({"success": False, "error": "Intersection not found"}), 404

    stop_detection_thread(int_id)

    with data_lock:
        del intersection_registry[int_id]

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

    # Initialize default intersections
    init_default_intersections()

    # Start signal coordination thread
    coord_thread = threading.Thread(target=coordinate_traffic_signals, daemon=True)
    coord_thread.start()
    print("Started signal coordination thread")

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
