
import cv2
import numpy as np
from flask import Flask, jsonify, request, Response
from flask_cors import CORS
import time
import threading
import os
from datetime import datetime, timedelta
import random
import pymongo
from bson import ObjectId
from collections import deque
import json

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# MongoDB setup - connect to local MongoDB or skip if not available
mongo_client = None
db = None
try:
    mongo_client = pymongo.MongoClient("mongodb://localhost:27017/", serverSelectionTimeoutMS=2000)
    mongo_client.server_info()  # Will raise exception if connection fails
    db = mongo_client["traffic_management"]
    violations_collection = db["violations"]
    patterns_collection = db["traffic_patterns"]
    learning_logs_collection = db["learning_logs"]
    print("Successfully connected to MongoDB")
except Exception as e:
    print(f"Warning: Could not connect to MongoDB: {e}")
    print("Vehicle violations will not be stored in database")

# Store the latest traffic data
traffic_data = {
    "int-001": {"vehicleCount": 0, "hasEmergencyVehicle": False, "timestamp": ""},
    "int-002": {"vehicleCount": 0, "hasEmergencyVehicle": False, "timestamp": ""},
}

# Traffic signal status
traffic_signals = {
    "int-001": "red",
    "int-002": "green",
}

# ============= ONLINE LEARNING: Traffic Pattern Memory =============
# Store traffic patterns by hour of day and day of week
traffic_patterns = {
    "int-001": {hour: {"avg_count": 0, "samples": 0, "peak_detected": False} for hour in range(24)},
    "int-002": {hour: {"avg_count": 0, "samples": 0, "peak_detected": False} for hour in range(24)},
}

# Pattern predictions based on learned data
traffic_predictions = {
    "int-001": {"next_hour_prediction": 0, "trend": "stable", "confidence": 0.0},
    "int-002": {"next_hour_prediction": 0, "trend": "stable", "confidence": 0.0},
}

# Learning rate for online updates
LEARNING_RATE = 0.1
PATTERN_UPDATE_INTERVAL = 60  # Update patterns every 60 seconds

# ============= SPEED TRACKING =============
# Store vehicle positions with timestamps for speed calculation
vehicle_tracking_history = {
    "int-001": {},  # {vehicle_id: deque([(x, y, timestamp), ...])}
    "int-002": {},
}

# Speed data storage
vehicle_speeds = {
    "int-001": {},  # {vehicle_id: speed_kmh}
    "int-002": {},
}

# Speed limit configuration (km/h)
SPEED_LIMIT = 40
PIXELS_PER_METER = 10  # Calibration factor - adjust based on camera setup

# ============= RED LIGHT VIOLATION DETECTION =============
# Stop line positions for each intersection (y-coordinate in pixels)
stop_line_config = {
    "int-001": {"y_position": 350, "tolerance": 20},  # Adjust based on camera view
    "int-002": {"y_position": 350, "tolerance": 20},
}

# Track vehicles that have crossed the stop line
vehicles_crossed_stop_line = {
    "int-001": set(),
    "int-002": set(),
}

# Automatic control configuration
auto_control = {
    "int-001": {
        "enabled": False,
        "last_change_time": time.time(),
        "cycle_times": {
            "red": 30,
            "yellow": 5,
            "green": 30,
        },
        "vehicle_thresholds": {
            "low": 5,
            "medium": 15,
            "high": 99999
        },
        "cycle_adjustments": {
            "low": 0.7,
            "medium": 1.0,
            "high": 1.3,
        },
        "use_predictions": True  # Enable predictive signal timing
    },
    "int-002": {
        "enabled": False,
        "last_change_time": time.time(),
        "cycle_times": {
            "red": 30,
            "yellow": 5,
            "green": 30,
        },
        "vehicle_thresholds": {
            "low": 5,
            "medium": 15,
            "high": 99999
        },
        "cycle_adjustments": {
            "low": 0.7,
            "medium": 1.0,
            "high": 1.3,
        },
        "use_predictions": True
    }
}

# Configuration for emergency vehicle detection
emergency_config = {
    "min_size": 80,
    "confidence_threshold": 0.5,
}

# Two-wheeler violation detection configuration
two_wheeler_config = {
    "confidence_threshold": 0.6,
    "helmet_detection_threshold": 0.5,
    "person_count_threshold": 2,
    "helmet_color_ranges": {
        # Typical helmet colors in HSV
        "black": [(0, 0, 0), (180, 255, 50)],
        "white": [(0, 0, 200), (180, 30, 255)],
        "red": [(0, 100, 100), (10, 255, 255)],
        "blue": [(100, 100, 100), (130, 255, 255)],
        "yellow": [(20, 100, 100), (35, 255, 255)],
    }
}

# Store detected vehicle information
detected_vehicles = {
    "int-001": [],
    "int-002": []
}

# Last stored vehicle positions for speed estimation
last_vehicle_positions = {
    "int-001": {},
    "int-002": {}
}

# Vehicle ID counter
next_vehicle_id = 1

# Lock for thread-safe access to shared data
data_lock = threading.Lock()

# Latest frames for video streaming
latest_frames = {
    "int-001": None,
    "int-002": None
}
processed_frames = {
    "int-001": None,
    "int-002": None
}
frame_lock = threading.Lock()

# Frame processing configuration
frame_processing = {
    "skip_frames": 5,
    "last_full_process_time": 0,
    "frame_quality": 70,
    "max_width": 640,
    "stream_fps": 15
}

# ============= ONLINE LEARNING FUNCTIONS =============

def update_traffic_pattern(intersection_id, vehicle_count):
    """
    Update traffic patterns with new observation (Online Learning)
    Uses exponential moving average for smooth updates
    """
    current_hour = datetime.now().hour
    
    with data_lock:
        pattern = traffic_patterns[intersection_id][current_hour]
        
        # Exponential moving average update
        if pattern["samples"] == 0:
            pattern["avg_count"] = vehicle_count
        else:
            pattern["avg_count"] = (1 - LEARNING_RATE) * pattern["avg_count"] + LEARNING_RATE * vehicle_count
        
        pattern["samples"] += 1
        
        # Detect peak hours (above average)
        all_hours_avg = sum(p["avg_count"] for p in traffic_patterns[intersection_id].values()) / 24
        pattern["peak_detected"] = pattern["avg_count"] > all_hours_avg * 1.3
        
        # Update predictions
        update_traffic_predictions(intersection_id)
        
        # Log learning event
        log_learning_event(intersection_id, "pattern_update", {
            "hour": current_hour,
            "vehicle_count": vehicle_count,
            "new_avg": pattern["avg_count"],
            "samples": pattern["samples"]
        })

def update_traffic_predictions(intersection_id):
    """
    Generate predictions based on learned patterns (Continual Learning)
    """
    current_hour = datetime.now().hour
    next_hour = (current_hour + 1) % 24
    
    pattern = traffic_patterns[intersection_id]
    current_avg = pattern[current_hour]["avg_count"]
    next_avg = pattern[next_hour]["avg_count"]
    samples = pattern[current_hour]["samples"]
    
    # Calculate confidence based on number of samples
    confidence = min(1.0, samples / 100)  # Max confidence after 100 samples
    
    # Determine trend
    if next_avg > current_avg * 1.1:
        trend = "increasing"
    elif next_avg < current_avg * 0.9:
        trend = "decreasing"
    else:
        trend = "stable"
    
    traffic_predictions[intersection_id] = {
        "next_hour_prediction": next_avg,
        "trend": trend,
        "confidence": confidence,
        "current_hour_avg": current_avg,
        "is_peak_hour": pattern[current_hour]["peak_detected"]
    }

def log_learning_event(intersection_id, event_type, data):
    """
    Log learning events to database for analysis
    """
    if db is not None:
        try:
            learning_logs_collection.insert_one({
                "intersection_id": intersection_id,
                "event_type": event_type,
                "data": data,
                "timestamp": datetime.now().isoformat()
            })
        except Exception as e:
            print(f"Error logging learning event: {e}")

def get_adaptive_cycle_time(intersection_id, signal_type):
    """
    Get adaptive signal cycle time based on predictions and current conditions
    """
    base_time = auto_control[intersection_id]["cycle_times"][signal_type]
    
    if not auto_control[intersection_id].get("use_predictions", False):
        return base_time
    
    prediction = traffic_predictions[intersection_id]
    
    # Adjust based on predicted trend
    if prediction["trend"] == "increasing" and prediction["confidence"] > 0.5:
        # If traffic is predicted to increase, extend green time
        if signal_type == "green":
            return base_time * 1.2
        elif signal_type == "red":
            return base_time * 0.8
    elif prediction["trend"] == "decreasing" and prediction["confidence"] > 0.5:
        # If traffic is predicted to decrease, reduce green time
        if signal_type == "green":
            return base_time * 0.8
        elif signal_type == "red":
            return base_time * 1.2
    
    return base_time

# ============= SPEED TRACKING FUNCTIONS =============

def calculate_vehicle_speed(intersection_id, vehicle_id, current_position, current_time):
    """
    Calculate vehicle speed based on position history
    Uses displacement over time to estimate speed
    """
    global vehicle_tracking_history, vehicle_speeds
    
    # Initialize tracking history if needed
    if vehicle_id not in vehicle_tracking_history[intersection_id]:
        vehicle_tracking_history[intersection_id][vehicle_id] = deque(maxlen=10)
    
    history = vehicle_tracking_history[intersection_id][vehicle_id]
    history.append((current_position[0], current_position[1], current_time))
    
    # Need at least 2 points to calculate speed
    if len(history) < 2:
        return 0
    
    # Calculate speed using oldest and newest positions
    old_x, old_y, old_time = history[0]
    new_x, new_y, new_time = history[-1]
    
    # Calculate displacement in pixels
    displacement_pixels = np.sqrt((new_x - old_x)**2 + (new_y - old_y)**2)
    
    # Calculate time difference
    time_diff = new_time - old_time
    
    if time_diff <= 0:
        return 0
    
    # Convert to real-world speed (pixels/second -> km/h)
    # Assuming PIXELS_PER_METER calibration
    displacement_meters = displacement_pixels / PIXELS_PER_METER
    speed_mps = displacement_meters / time_diff  # meters per second
    speed_kmh = speed_mps * 3.6  # Convert to km/h
    
    # Store the calculated speed
    vehicle_speeds[intersection_id][vehicle_id] = round(speed_kmh, 1)
    
    return speed_kmh

def detect_speeding_violation(intersection_id, vehicle_id, vehicle_data):
    """
    Detect if a vehicle is speeding based on calculated speed
    """
    speed = vehicle_speeds[intersection_id].get(vehicle_id, 0)
    
    if speed > SPEED_LIMIT:
        return True, speed
    return False, speed

# ============= RED LIGHT VIOLATION DETECTION =============

def detect_red_light_violation(intersection_id, vehicle_id, vehicle_position, vehicle_data):
    """
    Detect red light violations by tracking vehicle position relative to stop line
    """
    global vehicles_crossed_stop_line
    
    with data_lock:
        current_signal = traffic_signals.get(intersection_id, "unknown")
    
    stop_line = stop_line_config[intersection_id]
    vehicle_y = vehicle_position[1]
    
    # Check if vehicle has crossed the stop line
    crossed_line = vehicle_y > stop_line["y_position"] - stop_line["tolerance"]
    
    # Track vehicles that cross the stop line
    if crossed_line:
        was_already_crossed = vehicle_id in vehicles_crossed_stop_line[intersection_id]
        
        if not was_already_crossed:
            # Vehicle just crossed the stop line
            vehicles_crossed_stop_line[intersection_id].add(vehicle_id)
            
            # If signal is red when crossing, it's a violation
            if current_signal == "red":
                return True, "Vehicle crossed stop line during red signal"
    
    return False, None

def reset_stop_line_tracking(intersection_id):
    """
    Reset stop line tracking when signal changes to green
    """
    vehicles_crossed_stop_line[intersection_id].clear()

# ============= IMPROVED HELMET DETECTION =============

def detect_helmet_improved(person_roi):
    """
    Improved helmet detection using color and shape analysis
    Since COCO doesn't have helmet class, we use computer vision techniques
    """
    if person_roi is None or person_roi.size == 0:
        return True  # Assume helmet present if can't analyze
    
    try:
        height, width = person_roi.shape[:2]
        
        # Focus on the upper portion of the person (head area)
        head_region = person_roi[0:int(height * 0.3), :]
        
        if head_region.size == 0:
            return True
        
        # Convert to HSV for color analysis
        hsv = cv2.cvtColor(head_region, cv2.COLOR_BGR2HSV)
        
        # Check for common helmet colors
        helmet_detected = False
        
        for color_name, (lower, upper) in two_wheeler_config["helmet_color_ranges"].items():
            lower_bound = np.array(lower)
            upper_bound = np.array(upper)
            mask = cv2.inRange(hsv, lower_bound, upper_bound)
            
            # Calculate percentage of helmet-colored pixels
            helmet_ratio = cv2.countNonZero(mask) / (head_region.shape[0] * head_region.shape[1])
            
            if helmet_ratio > 0.15:  # At least 15% of head region has helmet color
                helmet_detected = True
                break
        
        # Additional check: Look for rounded shape in head region (helmet shape)
        gray = cv2.cvtColor(head_region, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        circles = cv2.HoughCircles(blurred, cv2.HOUGH_GRADIENT, 1, 20,
                                   param1=50, param2=30, minRadius=10, maxRadius=50)
        
        if circles is not None:
            helmet_detected = True
        
        return helmet_detected
        
    except Exception as e:
        print(f"Error in helmet detection: {e}")
        return True  # Assume helmet present on error

def count_people_on_vehicle_improved(vehicle_roi, net, classes, output_layers):
    """
    Improved person counting on two-wheelers
    """
    if vehicle_roi is None or vehicle_roi.size == 0:
        return 0
    
    try:
        height, width, _ = vehicle_roi.shape
        blob = cv2.dnn.blobFromImage(vehicle_roi, 1/255.0, (416, 416), swapRB=True, crop=False)
        net.setInput(blob)
        outputs = net.forward(output_layers)
        
        person_count = 0
        person_boxes = []
        
        for output in outputs:
            for detection in output:
                scores = detection[5:]
                class_id = np.argmax(scores)
                confidence = scores[class_id]
                
                if confidence > two_wheeler_config["confidence_threshold"]:
                    if classes[class_id] == "person":
                        # Get bounding box
                        center_x = int(detection[0] * width)
                        center_y = int(detection[1] * height)
                        w = int(detection[2] * width)
                        h = int(detection[3] * height)
                        
                        # Non-maximum suppression check
                        is_duplicate = False
                        for (px, py, pw, ph) in person_boxes:
                            if abs(center_x - px) < 30 and abs(center_y - py) < 30:
                                is_duplicate = True
                                break
                        
                        if not is_duplicate:
                            person_count += 1
                            person_boxes.append((center_x, center_y, w, h))
        
        return person_count
        
    except Exception as e:
        print(f"Error counting people: {e}")
        return 0

# ============= SIGNAL COORDINATION =============

def coordinate_traffic_signals():
    """
    Coordinates traffic signals between intersections to optimize traffic flow
    """
    while True:
        try:
            with data_lock:
                if (auto_control["int-001"]["enabled"] and 
                    auto_control["int-002"]["enabled"]):
                    
                    signal_1 = traffic_signals["int-001"]
                    signal_2 = traffic_signals["int-002"]
                    
                    if signal_1 == "green" and signal_2 != "yellow":
                        traffic_signals["int-002"] = "red"
                    elif signal_2 == "green" and signal_1 != "yellow":
                        traffic_signals["int-001"] = "red"
            
            time.sleep(1)
        except Exception as e:
            print(f"Error in signal coordination: {e}")
            time.sleep(1)

def update_traffic_signal_automatic(intersection_id):
    """
    Automatically update the traffic signal based on time, vehicle count, and predictions
    """
    if not auto_control[intersection_id]["enabled"]:
        return
        
    current_time = time.time()
    last_change_time = auto_control[intersection_id]["last_change_time"]
    current_signal = traffic_signals[intersection_id]
    
    vehicle_count = traffic_data[intersection_id]["vehicleCount"]
    
    # Determine traffic level
    thresholds = auto_control[intersection_id]["vehicle_thresholds"]
    if vehicle_count <= thresholds["low"]:
        traffic_level = "low"
    elif vehicle_count <= thresholds["medium"]:
        traffic_level = "medium"
    else:
        traffic_level = "high"
    
    adjustment = auto_control[intersection_id]["cycle_adjustments"][traffic_level]
    
    # Get adaptive cycle time (uses predictions)
    base_time = get_adaptive_cycle_time(intersection_id, current_signal)
    adjusted_time = base_time * adjustment
    
    if current_time - last_change_time >= adjusted_time:
        if current_signal == "red":
            new_signal = "green"
            reset_stop_line_tracking(intersection_id)  # Reset tracking on green
        elif current_signal == "green":
            new_signal = "yellow"
        else:
            new_signal = "red"
            
        with data_lock:
            traffic_signals[intersection_id] = new_signal
            auto_control[intersection_id]["last_change_time"] = current_time
            
        print(f"Auto mode: Changed signal at {intersection_id} from {current_signal} to {new_signal} (Traffic: {traffic_level})")

        other_id = "int-002" if intersection_id == "int-001" else "int-001"
        if auto_control[other_id]["enabled"]:
            if new_signal == "green":
                if traffic_signals[other_id] != "yellow":
                    traffic_signals[other_id] = "red"
                    print(f"Coordinated: Setting {other_id} to red")
            elif new_signal == "red" and traffic_signals[other_id] == "red":
                if time.time() - auto_control[other_id]["last_change_time"] > 5:
                    traffic_signals[other_id] = "green"
                    auto_control[other_id]["last_change_time"] = time.time()
                    reset_stop_line_tracking(other_id)
                    print(f"Coordinated: Setting {other_id} to green after mutual red period")

# ============= PATTERN LEARNING THREAD =============

def pattern_learning_thread():
    """
    Background thread for updating traffic patterns periodically
    """
    while True:
        try:
            for intersection_id in ["int-001", "int-002"]:
                vehicle_count = traffic_data[intersection_id].get("vehicleCount", 0)
                update_traffic_pattern(intersection_id, vehicle_count)
            
            # Save patterns to database periodically
            if db is not None:
                try:
                    for intersection_id in ["int-001", "int-002"]:
                        patterns_collection.update_one(
                            {"intersection_id": intersection_id},
                            {"$set": {
                                "patterns": traffic_patterns[intersection_id],
                                "predictions": traffic_predictions[intersection_id],
                                "updated_at": datetime.now().isoformat()
                            }},
                            upsert=True
                        )
                except Exception as e:
                    print(f"Error saving patterns: {e}")
            
            time.sleep(PATTERN_UPDATE_INTERVAL)
            
        except Exception as e:
            print(f"Error in pattern learning thread: {e}")
            time.sleep(10)

# ============= VEHICLE DETECTION =============

def detect_vehicles(camera_index, intersection_id):
    """
    Process video feed to count vehicles and detect emergency vehicles
    """
    global latest_frames, processed_frames, next_vehicle_id
    print(f"Starting vehicle detection for intersection {intersection_id} using camera index {camera_index}")
    
    # Load YOLO model
    try:
        yolo_dir = os.path.join(os.path.dirname(__file__), 'yolo')
        
        config_path = os.path.join(yolo_dir, 'yolov4.cfg')
        weights_path = os.path.join(yolo_dir, 'yolov4.weights')
        classes_path = os.path.join(yolo_dir, 'coco.names')
        
        if not os.path.exists(config_path) or not os.path.exists(weights_path) or not os.path.exists(classes_path):
            print(f"YOLO files not found at {yolo_dir}. Please download them as mentioned in README.md")
            raise FileNotFoundError(f"Required YOLO files not found in {yolo_dir}")
            
        net = cv2.dnn.readNetFromDarknet(config_path, weights_path)
        with open(classes_path, "r") as f:
            classes = [line.strip() for line in f.readlines()]
        
        net.setPreferableBackend(cv2.dnn.DNN_BACKEND_DEFAULT)
        try:
            if cv2.ocl.haveOpenCL():
                cv2.ocl.setUseOpenCL(True)
                net.setPreferableTarget(cv2.dnn.DNN_TARGET_OPENCL)
                print("Using OpenCL acceleration")
            else:
                net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
                print("Using CPU for inference")
        except:
            net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
            print("Fallback to CPU for inference")
        
        layer_names = net.getLayerNames()
        output_layers = [layer_names[i - 1] for i in net.getUnconnectedOutLayers()]
        
        print(f"Successfully loaded YOLO model for {intersection_id}")
    except Exception as e:
        print(f"Error loading YOLO model: {e}")
        raise
    
    # Initialize video capture
    cap = None
    max_retries = 5
    retry_count = 0
    
    while cap is None or not cap.isOpened():
        try:
            print(f"Attempt {retry_count + 1}/{max_retries} to connect to camera {camera_index}")
            cap = cv2.VideoCapture(camera_index)
            
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            cap.set(cv2.CAP_PROP_FPS, 30)
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
            
            if not cap.isOpened():
                print(f"Failed to open camera {camera_index}. Retrying...")
                time.sleep(1)
                retry_count += 1
                if retry_count >= max_retries:
                    print(f"Could not open camera {camera_index} after {max_retries} attempts")
                    raise IOError(f"Could not open camera {camera_index}")
                continue
            
            print(f"Successfully connected to camera {camera_index} for {intersection_id}")
            ret, test_frame = cap.read()
            if not ret or test_frame is None:
                print(f"Camera {camera_index} opened but could not read frame. Retrying...")
                cap.release()
                cap = None
                retry_count += 1
                time.sleep(1)
                continue
                
        except Exception as e:
            print(f"Error connecting to camera {camera_index}: {e}")
            retry_count += 1
            time.sleep(1)
            if retry_count >= max_retries:
                print(f"Giving up on camera {camera_index} after {max_retries} attempts")
                with data_lock:
                    traffic_data[intersection_id] = {
                        "vehicleCount": 0,
                        "hasEmergencyVehicle": False,
                        "timestamp": datetime.now().isoformat(),
                        "error": f"Failed to connect to camera {camera_index}: {str(e)}"
                    }
                while True:
                    time.sleep(10)
                    try:
                        print(f"Periodic retry: Attempting to connect to camera {camera_index}")
                        cap = cv2.VideoCapture(camera_index)
                        if cap.isOpened():
                            print(f"Successfully reconnected to camera {camera_index}")
                            break
                        cap.release()
                    except Exception as retry_e:
                        print(f"Periodic retry failed: {retry_e}")
    
    print(f"Starting main detection loop for {intersection_id} with camera {camera_index}")
    
    frame_count = 0
    process_every_n_frames = frame_processing["skip_frames"]
    last_auto_control_update = time.time()
    
    while True:
        try:
            start_time = time.time()
            
            current_time = time.time()
            if current_time - last_auto_control_update >= 1.0:
                update_traffic_signal_automatic(intersection_id)
                last_auto_control_update = current_time
            
            ret, frame = cap.read()
            
            if not ret or frame is None:
                print(f"Error reading frame from camera {camera_index}. Reconnecting...")
                cap.release()
                time.sleep(1)
                cap = cv2.VideoCapture(camera_index)
                if not cap.isOpened():
                    print(f"Failed to reconnect to camera {camera_index}")
                    time.sleep(5)
                continue
            
            with frame_lock:
                latest_frames[intersection_id] = frame.copy()
            
            frame_count += 1
            process_frame = frame.copy()
            full_processing = (frame_count % process_every_n_frames == 0)
            
            # Add timestamp and info
            current_time_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            intersection_name = "Main Street Intersection" if intersection_id == "int-001" else "Park Avenue Intersection"
            cv2.putText(process_frame, f"Traffic Camera: {current_time_str}", (10, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            cv2.putText(process_frame, intersection_name, (10, 60), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            
            # Draw stop line
            stop_line_y = stop_line_config[intersection_id]["y_position"]
            cv2.line(process_frame, (0, stop_line_y), (frame.shape[1], stop_line_y), (0, 255, 255), 2)
            cv2.putText(process_frame, "STOP LINE", (10, stop_line_y - 10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
            
            with data_lock:
                signal_status = traffic_signals.get(intersection_id, "unknown")
                auto_enabled = auto_control.get(intersection_id, {}).get("enabled", False)
            
            signal_color = (0, 0, 255)
            if signal_status == "green":
                signal_color = (0, 255, 0)
            elif signal_status == "yellow":
                signal_color = (0, 255, 255)
                
            cv2.putText(process_frame, f"Signal: {signal_status.upper()}", (10, 90), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, signal_color, 2)
            cv2.putText(process_frame, f"Auto Mode: {('ON' if auto_enabled else 'OFF')}", (10, 120), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 165, 0) if auto_enabled else (128, 128, 128), 2)
            
            # Display prediction info
            pred = traffic_predictions[intersection_id]
            cv2.putText(process_frame, f"Trend: {pred['trend']} ({pred['confidence']*100:.0f}% conf)", 
                       (10, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            with frame_lock:
                processed_frames[intersection_id] = process_frame.copy()
            
            if not full_processing:
                elapsed = time.time() - start_time
                sleep_time = max(0.001, (1.0/frame_processing["stream_fps"]) - elapsed)
                time.sleep(sleep_time)
                continue
                
            frame_processing["last_full_process_time"] = time.time()
                
            # YOLO detection
            height, width, channels = frame.shape
            blob = cv2.dnn.blobFromImage(frame, 1/255.0, (416, 416), swapRB=True, crop=False)
            net.setInput(blob)
            outputs = net.forward(output_layers)
            
            vehicle_count = 0
            has_emergency = False
            current_vehicles = []
            current_timestamp = time.time()
            
            for output in outputs:
                for detection in output:
                    scores = detection[5:]
                    class_id = np.argmax(scores)
                    confidence = scores[class_id]
                    
                    if confidence > emergency_config["confidence_threshold"]:
                        if classes[class_id] in ["car", "truck", "bus", "motorcycle", "bicycle"]:
                            vehicle_count += 1
                            
                            center_x = int(detection[0] * width)
                            center_y = int(detection[1] * height)
                            w = int(detection[2] * width)
                            h = int(detection[3] * height)
                            
                            x = int(center_x - w / 2)
                            y = int(center_y - h / 2)
                            
                            vehicle_position = (center_x, center_y)
                            vehicle_id = None
                            
                            for known_id, known_pos in list(last_vehicle_positions.get(intersection_id, {}).items()):
                                known_x, known_y = known_pos
                                distance = ((center_x - known_x) ** 2 + (center_y - known_y) ** 2) ** 0.5
                                if distance < 50:
                                    vehicle_id = known_id
                                    break
                            
                            if vehicle_id is None:
                                vehicle_id = f"v-{next_vehicle_id}"
                                next_vehicle_id += 1
                            
                            if intersection_id not in last_vehicle_positions:
                                last_vehicle_positions[intersection_id] = {}
                            last_vehicle_positions[intersection_id][vehicle_id] = vehicle_position
                            
                            # Calculate speed
                            speed = calculate_vehicle_speed(intersection_id, vehicle_id, vehicle_position, current_timestamp)
                            is_speeding, actual_speed = detect_speeding_violation(intersection_id, vehicle_id, None)
                            
                            # Check red light violation
                            is_red_light_violation, violation_reason = detect_red_light_violation(
                                intersection_id, vehicle_id, vehicle_position, None
                            )
                            
                            # Check for emergency vehicles
                            is_emergency = False
                            if w > emergency_config["min_size"] and h > emergency_config["min_size"]:
                                if x >= 0 and y >= 0 and x+w < width and y+h < height:
                                    vehicle_roi = frame[y:y+h, x:x+w]
                                    hsv = cv2.cvtColor(vehicle_roi, cv2.COLOR_BGR2HSV)
                                    
                                    lower_red = np.array([0, 120, 70])
                                    upper_red = np.array([10, 255, 255])
                                    lower_blue = np.array([110, 50, 50])
                                    upper_blue = np.array([130, 255, 255])
                                    
                                    mask_red = cv2.inRange(hsv, lower_red, upper_red)
                                    mask_blue = cv2.inRange(hsv, lower_blue, upper_blue)
                                    
                                    red_percent = cv2.countNonZero(mask_red) / (w * h) * 100
                                    blue_percent = cv2.countNonZero(mask_blue) / (w * h) * 100
                                    
                                    if red_percent > 5 or blue_percent > 5:
                                        is_emergency = True
                                        has_emergency = True
                                        print(f"Emergency vehicle detected at {intersection_id}!")
                                        
                                        with frame_lock:
                                            cv2.rectangle(processed_frames[intersection_id], (x, y), (x + w, y + h), (0, 0, 255), 2)
                                            cv2.putText(processed_frames[intersection_id], "EMERGENCY VEHICLE", (x, y - 10), 
                                                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
                            
                            # Two-wheeler violations
                            helmet_violation = False
                            passenger_violation = False
                            
                            if classes[class_id] in ["motorcycle", "bicycle"] and x >= 0 and y >= 0 and x+w < width and y+h < height:
                                vehicle_roi = frame[y:y+h, x:x+w]
                                
                                person_count = count_people_on_vehicle_improved(vehicle_roi, net, classes, output_layers)
                                
                                if person_count > two_wheeler_config["person_count_threshold"]:
                                    passenger_violation = True
                                    print(f"Passenger violation detected: {person_count} people on two-wheeler")
                                    
                                    with frame_lock:
                                        cv2.putText(processed_frames[intersection_id], 
                                                  f"VIOLATION: {person_count} PASSENGERS", 
                                                  (x, y + h + 30), 
                                                  cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
                                
                                if person_count > 0:
                                    has_helmet = detect_helmet_improved(vehicle_roi)
                                    if not has_helmet:
                                        helmet_violation = True
                                        print(f"Helmet violation detected on two-wheeler")
                                        
                                        with frame_lock:
                                            cv2.putText(processed_frames[intersection_id], 
                                                      "VIOLATION: NO HELMET", 
                                                      (x, y + h + 15), 
                                                      cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
                            
                            vehicle_data = {
                                "id": vehicle_id,
                                "type": classes[class_id],
                                "position": vehicle_position,
                                "size": (w, h),
                                "is_emergency": is_emergency,
                                "license_plate": generate_random_license_plate() if random.random() < 0.8 else None,
                                "helmet_violation": helmet_violation,
                                "passenger_violation": passenger_violation,
                                "speed_kmh": actual_speed,
                                "is_speeding": is_speeding,
                                "red_light_violation": is_red_light_violation
                            }
                            current_vehicles.append(vehicle_data)
                            
                            # Draw bounding box
                            with frame_lock:
                                box_color = (0, 0, 255) if is_emergency else (255, 0, 0)
                                if helmet_violation or passenger_violation or is_red_light_violation:
                                    box_color = (0, 0, 255)  # Red for violations
                                elif is_speeding:
                                    box_color = (0, 165, 255)  # Orange for speeding
                                
                                cv2.rectangle(processed_frames[intersection_id], (x, y), (x + w, y + h), box_color, 2)
                                label = f"{classes[class_id]} {vehicle_id}"
                                cv2.putText(processed_frames[intersection_id], label, (x, y - 5), 
                                          cv2.FONT_HERSHEY_SIMPLEX, 0.5, box_color, 2)
                                
                                # Display speed
                                if actual_speed > 0:
                                    speed_color = (0, 0, 255) if is_speeding else (0, 255, 0)
                                    cv2.putText(processed_frames[intersection_id], f"{actual_speed:.0f} km/h", 
                                              (x, y + h + 15), cv2.FONT_HERSHEY_SIMPLEX, 0.5, speed_color, 2)
                                
                                # Red light violation marker
                                if is_red_light_violation:
                                    cv2.putText(processed_frames[intersection_id], "RED LIGHT!", 
                                              (x, y - 25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
                                
                                if vehicle_data["license_plate"]:
                                    cv2.putText(processed_frames[intersection_id], vehicle_data["license_plate"], 
                                              (x + w + 5, y + 15), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 0), 1)
            
            with data_lock:
                detected_vehicles[intersection_id] = current_vehicles
            
            with data_lock:
                if has_emergency and traffic_signals[intersection_id] != "green":
                    traffic_signals[intersection_id] = "green"
                    auto_control[intersection_id]["last_change_time"] = time.time()
                    reset_stop_line_tracking(intersection_id)
                    print(f"Emergency vehicle detected at {intersection_id}. Setting signal to green.")
                    
                    other_id = "int-002" if intersection_id == "int-001" else "int-001"
                    if traffic_signals[other_id] != "yellow":
                        traffic_signals[other_id] = "red"
                        print(f"Setting {other_id} to red for emergency priority")
                    
                traffic_data[intersection_id] = {
                    "vehicleCount": vehicle_count,
                    "hasEmergencyVehicle": has_emergency,
                    "timestamp": datetime.now().isoformat(),
                    "autoMode": auto_control[intersection_id]["enabled"]
                }
            
            if frame_count % 100 == 0:
                print(f"Intersection {intersection_id}: {vehicle_count} vehicles, Emergency: {has_emergency}")
                
            elapsed = time.time() - start_time
            sleep_time = max(0.001, (1.0/frame_processing["stream_fps"]) - elapsed)
            time.sleep(sleep_time)
                
        except Exception as e:
            print(f"Error in video processing for {intersection_id}: {e}")
            time.sleep(0.1)
        
    if cap is not None:
        cap.release()
    cv2.destroyAllWindows()

def generate_random_license_plate():
    """Generate random license plate number for simulation"""
    letters = "ABCDEFGHJKLMNPQRSTUVWXYZ"
    numbers = "0123456789"
    
    license_plate = ''.join(random.choice(letters) for _ in range(2))
    license_plate += ''.join(random.choice(numbers) for _ in range(2))
    license_plate += ''.join(random.choice(letters) for _ in range(3))
    
    return license_plate

def check_for_violations(intersection_id):
    """
    Check for traffic violations based on current state
    Returns the number of violations detected
    """
    violations_count = 0
    with data_lock:
        current_signal = traffic_signals.get(intersection_id)
        vehicles = detected_vehicles.get(intersection_id, [])
        
        for vehicle in vehicles:
            violation_type = None
            details = ""
            
            # Real red light violation detection
            if vehicle.get("red_light_violation"):
                violation_type = "red_light"
                details = f"Vehicle crossed stop line during red signal"
            
            # Real speeding detection
            elif vehicle.get("is_speeding"):
                violation_type = "speeding"
                speed = vehicle.get("speed_kmh", 0)
                details = f"Speeding at {speed:.0f} km/h (limit: {SPEED_LIMIT} km/h)"
                
            # Two-wheeler violations
            elif vehicle.get("type") in ["motorcycle", "bicycle"]:
                if vehicle.get("helmet_violation"):
                    violation_type = "no_helmet"
                    details = "Riding without helmet"
                elif vehicle.get("passenger_violation"):
                    violation_type = "excess_passengers"
                    details = "Too many passengers on two-wheeler"
            
            if violation_type:
                violations_count += 1
                intersection_name = "Main Street Intersection" if intersection_id == "int-001" else "Park Avenue Intersection"
                violation_data = {
                    "vehicleNumber": vehicle.get("license_plate", "Unknown"),
                    "type": violation_type,
                    "timestamp": datetime.now().isoformat(),
                    "location": intersection_name,
                    "details": details,
                    "speed": vehicle.get("speed_kmh"),
                    "imageUrl": None
                }
                
                if db is not None:
                    try:
                        result = violations_collection.insert_one(violation_data)
                        print(f"Violation recorded in database with ID: {result.inserted_id}")
                    except Exception as e:
                        print(f"Error saving violation to database: {e}")
    
    return violations_count

def generate_frames(intersection_id, fps_requested=1):
    """
    Generator function for video streaming with adjustable quality
    """
    global processed_frames
    
    fps_limit = min(fps_requested, frame_processing["stream_fps"])
    interval = 1.0 / max(0.5, fps_limit)
    last_frame_time = 0
    
    while True:
        current_time = time.time()
        elapsed = current_time - last_frame_time
        if elapsed < interval:
            time.sleep(0.01)
            continue
            
        last_frame_time = current_time
        
        if processed_frames.get(intersection_id) is None:
            time.sleep(0.1)
            continue
            
        with frame_lock:
            if processed_frames.get(intersection_id) is not None:
                frame = processed_frames[intersection_id].copy()
            else:
                continue
        
        if frame_processing["max_width"] < frame.shape[1]:
            scale = frame_processing["max_width"] / frame.shape[1]
            new_width = frame_processing["max_width"]
            new_height = int(frame.shape[0] * scale)
            frame = cv2.resize(frame, (new_width, new_height))
                
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), frame_processing["frame_quality"]]
        ret, buffer = cv2.imencode('.jpg', frame, encode_param)
        if not ret:
            continue
            
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

# ============= API ENDPOINTS =============

@app.route('/api/traffic', methods=['GET'])
def get_traffic_data():
    """Return the current traffic data for all intersections"""
    result = []
    with data_lock:
        for intersection_id, data in traffic_data.items():
            result.append({
                "intersectionId": intersection_id,
                "vehicleCount": data["vehicleCount"],
                "hasEmergencyVehicle": data["hasEmergencyVehicle"],
                "timestamp": data["timestamp"],
                "status": traffic_signals[intersection_id],
                "autoMode": auto_control[intersection_id]["enabled"]
            })
    return jsonify(result)

@app.route('/api/traffic/signal', methods=['POST'])
def update_signal():
    """Update the traffic signal status"""
    data = request.json
    intersection_id = data.get('intersectionId')
    status = data.get('status')
    
    if not intersection_id or not status or status not in ["red", "yellow", "green"]:
        return jsonify({"success": False, "error": "Invalid request parameters"}), 400
    
    with data_lock:
        if auto_control[intersection_id]["enabled"]:
            return jsonify({"success": False, "error": "Cannot change signal manually while auto mode is enabled"}), 400
            
        traffic_signals[intersection_id] = status
        if status == "green":
            reset_stop_line_tracking(intersection_id)
    
    print(f"Changing traffic signal at {intersection_id} to {status}")
    return jsonify({"success": True})

@app.route('/api/traffic/auto_control', methods=['POST'])
def toggle_auto_control():
    """Toggle automatic traffic signal control"""
    data = request.json
    intersection_id = data.get('intersectionId')
    enabled = data.get('enabled')
    
    if not intersection_id or enabled is None:
        return jsonify({"success": False, "error": "Invalid request parameters"}), 400
    
    with data_lock:
        auto_control[intersection_id]["enabled"] = enabled
        auto_control[intersection_id]["last_change_time"] = time.time()
    
    print(f"{'Enabling' if enabled else 'Disabling'} auto control for {intersection_id}")
    return jsonify({"success": True})

@app.route('/api/traffic/check_violations', methods=['POST'])
def check_violations():
    """Check for traffic violations at a specific intersection"""
    data = request.json
    intersection_id = data.get('intersectionId')
    
    if not intersection_id:
        return jsonify({"success": False, "error": "Invalid intersection ID"}), 400
    
    violations = check_for_violations(intersection_id)
    
    return jsonify({
        "success": True,
        "violations": violations
    })

@app.route('/api/traffic/violations', methods=['GET'])
def get_violations():
    """Get all recorded traffic violations"""
    if db is not None:
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
        return jsonify([
            {
                "id": f"sim-violation-{i}",
                "vehicleNumber": generate_random_license_plate(),
                "type": random.choice(["red_light", "speeding", "no_helmet", "excess_passengers"]),
                "timestamp": (datetime.now().replace(minute=datetime.now().minute-i)).isoformat(),
                "location": "Main Street Intersection" if i % 2 == 0 else "Park Avenue Intersection",
                "details": "Simulated violation (no database connection)",
                "imageUrl": None
            }
            for i in range(1, 6)
        ])

@app.route('/api/traffic/patterns', methods=['GET'])
def get_traffic_patterns():
    """Get learned traffic patterns and predictions"""
    result = {}
    for intersection_id in ["int-001", "int-002"]:
        result[intersection_id] = {
            "patterns": {str(k): v for k, v in traffic_patterns[intersection_id].items()},
            "predictions": traffic_predictions[intersection_id],
            "current_hour": datetime.now().hour
        }
    return jsonify(result)

@app.route('/api/traffic/speeds', methods=['GET'])
def get_vehicle_speeds():
    """Get current vehicle speeds at intersections"""
    result = {}
    for intersection_id in ["int-001", "int-002"]:
        speeds = vehicle_speeds.get(intersection_id, {})
        result[intersection_id] = {
            "vehicles": [{"id": k, "speed": v} for k, v in speeds.items()],
            "average_speed": sum(speeds.values()) / len(speeds) if speeds else 0,
            "max_speed": max(speeds.values()) if speeds else 0,
            "speeding_count": sum(1 for v in speeds.values() if v > SPEED_LIMIT),
            "speed_limit": SPEED_LIMIT
        }
    return jsonify(result)

@app.route('/api/traffic/learning_logs', methods=['GET'])
def get_learning_logs():
    """Get recent learning logs for analysis"""
    if db is not None:
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

@app.route('/api/video_feed/<intersection_id>')
def video_feed(intersection_id):
    """Video streaming route for the camera feed"""
    if intersection_id not in ["int-001", "int-002"]:
        return "Invalid intersection ID", 400
        
    fps = request.args.get('fps', 1, type=float)
    if fps <= 0.5:
        frame_processing["frame_quality"] = 75
    elif fps <= 1:
        frame_processing["frame_quality"] = 70
    else:
        frame_processing["frame_quality"] = 65
    
    return Response(generate_frames(intersection_id, fps),
                   mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/api/stream_status')
def stream_status():
    """Return stream status information for diagnostics"""
    return jsonify({
        "stream_fps": frame_processing["stream_fps"],
        "process_skip_frames": frame_processing["skip_frames"],
        "frame_quality": frame_processing["frame_quality"],
        "last_processed": time.time() - frame_processing["last_full_process_time"]
    })

if __name__ == '__main__':
    yolo_dir = os.path.join(os.path.dirname(__file__), 'yolo')
    if not os.path.exists(yolo_dir):
        os.makedirs(yolo_dir)
        print(f"Created directory {yolo_dir} for YOLO model files")
        print("Please download the following files to the 'yolo' directory:")
        print("1. yolov4.cfg: https://raw.githubusercontent.com/AlexeyAB/darknet/master/cfg/yolov4.cfg")
        print("2. yolov4.weights: https://github.com/AlexeyAB/darknet/releases/download/darknet_yolo_v3_optimal/yolov4.weights")
        print("3. coco.names: https://raw.githubusercontent.com/AlexeyAB/darknet/master/data/coco.names")
    
    # Start signal coordination thread
    coord_thread = threading.Thread(
        target=coordinate_traffic_signals,
        daemon=True
    )
    coord_thread.start()
    print("Started signal coordination thread")
    
    # Start pattern learning thread
    learning_thread = threading.Thread(
        target=pattern_learning_thread,
        daemon=True
    )
    learning_thread.start()
    print("Started pattern learning thread (Online Learning)")
    
    # Start video processing threads
    thread1 = threading.Thread(
        target=detect_vehicles, 
        args=(0, "int-001"),
        daemon=True
    )
    thread1.start()
    print(f"Started detection thread for int-001 with laptop camera (index 0)")
    
    thread2 = threading.Thread(
        target=detect_vehicles, 
        args=(1, "int-002"),
        daemon=True
    )
    thread2.start()
    print(f"Started detection thread for int-002 with external webcam (index 1)")
    
    print("Starting Flask server on http://0.0.0.0:5000")
    app.run(debug=False, threaded=True, host='0.0.0.0', port=5000)
