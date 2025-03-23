
import cv2
import numpy as np
from flask import Flask, jsonify, request, Response
from flask_cors import CORS
import time
import threading
import os
from datetime import datetime
import random
import pymongo
from bson import ObjectId

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

# Automatic control configuration
auto_control = {
    "int-001": {
        "enabled": False,
        "last_change_time": time.time(),
        "cycle_times": {
            "red": 30,  # 30 seconds for red
            "yellow": 5,  # 5 seconds for yellow
            "green": 30,  # 30 seconds for green
        },
        "vehicle_thresholds": {
            "low": 5,    # 0-5 vehicles
            "medium": 15,  # 6-15 vehicles
            "high": 99999  # >15 vehicles
        },
        "cycle_adjustments": {
            "low": 0.7,     # Reduce times by 30%
            "medium": 1.0,  # Normal times
            "high": 1.3,    # Increase times by 30%
        }
    },
    "int-002": {
        "enabled": False,
        "last_change_time": time.time(),
        "cycle_times": {
            "red": 30,  # 30 seconds for red
            "yellow": 5,  # 5 seconds for yellow
            "green": 30,  # 30 seconds for green
        },
        "vehicle_thresholds": {
            "low": 5,    # 0-5 vehicles
            "medium": 15,  # 6-15 vehicles
            "high": 99999  # >15 vehicles
        },
        "cycle_adjustments": {
            "low": 0.7,     # Reduce times by 30%
            "medium": 1.0,  # Normal times
            "high": 1.3,    # Increase times by 30%
        }
    }
}

# Configuration for emergency vehicle detection
emergency_config = {
    "min_size": 80,  # Minimum size of emergency vehicle to detect
    "confidence_threshold": 0.5,  # Confidence threshold for detection
}

# Two-wheeler violation detection configuration
two_wheeler_config = {
    "confidence_threshold": 0.6,  # Confidence threshold for detection
    "helmet_detection_threshold": 0.5,  # Confidence threshold for helmet detection
    "person_count_threshold": 2  # Maximum allowed people on a two-wheeler
}

# Store detected vehicle information
detected_vehicles = {
    "int-001": [],  # List to store vehicle data like position, speed, etc.
    "int-002": []   # List to store vehicle data for the second intersection
}

# Last stored vehicle positions for speed estimation
last_vehicle_positions = {
    "int-001": {},  # Dictionary of vehicle IDs to positions
    "int-002": {}   # Dictionary of vehicle IDs to positions for the second intersection
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
}  # Store the processed frames separately
frame_lock = threading.Lock()

# Frame processing configuration
frame_processing = {
    "skip_frames": 5,  # Process only every Nth frame
    "last_full_process_time": 0,
    "frame_quality": 70,  # JPEG quality for streaming (0-100)
    "max_width": 640,  # Maximum width for streaming
    "stream_fps": 15  # Target FPS for streaming
}

def coordinate_traffic_signals():
    """
    Coordinates traffic signals between intersections to optimize traffic flow
    """
    while True:
        try:
            with data_lock:
                # If both intersections are in auto mode, coordinate their signals
                if (auto_control["int-001"]["enabled"] and 
                    auto_control["int-002"]["enabled"]):
                    
                    # Get current signals
                    signal_1 = traffic_signals["int-001"]
                    signal_2 = traffic_signals["int-002"]
                    
                    # If one is green, make sure the other is red (unless transitioning through yellow)
                    if signal_1 == "green" and signal_2 != "yellow":
                        traffic_signals["int-002"] = "red"
                    elif signal_2 == "green" and signal_1 != "yellow":
                        traffic_signals["int-001"] = "red"
            
            # Run at a reasonable interval
            time.sleep(1)
        except Exception as e:
            print(f"Error in signal coordination: {e}")
            time.sleep(1)

def update_traffic_signal_automatic(intersection_id):
    """
    Automatically update the traffic signal based on time and vehicle count
    """
    # Skip if auto mode is not enabled
    if not auto_control[intersection_id]["enabled"]:
        return
        
    current_time = time.time()
    last_change_time = auto_control[intersection_id]["last_change_time"]
    current_signal = traffic_signals[intersection_id]
    
    # Get current vehicle count
    vehicle_count = traffic_data[intersection_id]["vehicleCount"]
    
    # Determine traffic level
    thresholds = auto_control[intersection_id]["vehicle_thresholds"]
    if vehicle_count <= thresholds["low"]:
        traffic_level = "low"
    elif vehicle_count <= thresholds["medium"]:
        traffic_level = "medium"
    else:
        traffic_level = "high"
    
    # Adjust cycle times based on traffic
    adjustment = auto_control[intersection_id]["cycle_adjustments"][traffic_level]
    
    # Get time for current phase
    cycle_times = auto_control[intersection_id]["cycle_times"]
    adjusted_time = cycle_times[current_signal] * adjustment
    
    # Check if we need to change the signal
    if current_time - last_change_time >= adjusted_time:
        # Change to next signal
        if current_signal == "red":
            new_signal = "green"
        elif current_signal == "green":
            new_signal = "yellow"
        else:  # yellow
            new_signal = "red"
            
        # Update signal
        with data_lock:
            traffic_signals[intersection_id] = new_signal
            auto_control[intersection_id]["last_change_time"] = current_time
            
        print(f"Auto mode: Changed signal at {intersection_id} from {current_signal} to {new_signal} (Traffic: {traffic_level})")

        # If both intersections are in auto mode, coordinate the other intersection's signal
        other_id = "int-002" if intersection_id == "int-001" else "int-001"
        if auto_control[other_id]["enabled"]:
            # Make sure the other signal is complementary
            if new_signal == "green":
                # If this signal is green, other should be red unless it's currently yellow
                if traffic_signals[other_id] != "yellow":
                    traffic_signals[other_id] = "red"
                    print(f"Coordinated: Setting {other_id} to red")
            elif new_signal == "red" and traffic_signals[other_id] == "red":
                # Both shouldn't be red for too long (unless transitioning)
                # If the other has been red longer, make it green
                if time.time() - auto_control[other_id]["last_change_time"] > 5:
                    traffic_signals[other_id] = "green"
                    auto_control[other_id]["last_change_time"] = time.time()
                    print(f"Coordinated: Setting {other_id} to green after mutual red period")

def detect_helmet(person_roi, net, classes, output_layers):
    """
    Detect if a person is wearing a helmet
    """
    # Basic helmet detection using YOLO
    height, width, _ = person_roi.shape
    blob = cv2.dnn.blobFromImage(person_roi, 1/255.0, (416, 416), swapRB=True, crop=False)
    net.setInput(blob)
    outputs = net.forward(output_layers)
    
    # Look for helmet class or similar
    for output in outputs:
        for detection in output:
            scores = detection[5:]
            class_id = np.argmax(scores)
            confidence = scores[class_id]
            
            if confidence > two_wheeler_config["helmet_detection_threshold"]:
                # Check if class is a helmet or similar (helmet might not be in COCO dataset)
                # We'll check for "helmet" in the class name or use a similar class like "cap"
                if classes[class_id].lower() in ["helmet", "cap", "hat"]:
                    return True
    
    return False

def count_people_on_vehicle(vehicle_roi, net, classes, output_layers):
    """
    Count the number of people on a vehicle
    """
    height, width, _ = vehicle_roi.shape
    blob = cv2.dnn.blobFromImage(vehicle_roi, 1/255.0, (416, 416), swapRB=True, crop=False)
    net.setInput(blob)
    outputs = net.forward(output_layers)
    
    person_count = 0
    
    for output in outputs:
        for detection in output:
            scores = detection[5:]
            class_id = np.argmax(scores)
            confidence = scores[class_id]
            
            if confidence > two_wheeler_config["confidence_threshold"]:
                if classes[class_id] == "person":
                    person_count += 1
    
    return person_count

def detect_vehicles(camera_index, intersection_id):
    """
    Process video feed to count vehicles and detect emergency vehicles
    """
    global latest_frames, processed_frames, next_vehicle_id
    print(f"Starting vehicle detection for intersection {intersection_id} using camera index {camera_index}")
    
    # Load pre-trained vehicle detection model (using YOLO)
    try:
        # Check if we're running in development or production
        yolo_dir = os.path.join(os.path.dirname(__file__), 'yolo')
        
        # Try to load YOLO model - make sure these files exist in your backend/yolo directory
        config_path = os.path.join(yolo_dir, 'yolov4.cfg')
        weights_path = os.path.join(yolo_dir, 'yolov4.weights')
        classes_path = os.path.join(yolo_dir, 'coco.names')
        
        if not os.path.exists(config_path) or not os.path.exists(weights_path) or not os.path.exists(classes_path):
            print(f"YOLO files not found at {yolo_dir}. Please download them as mentioned in README.md")
            raise FileNotFoundError(f"Required YOLO files not found in {yolo_dir}")
            
        net = cv2.dnn.readNetFromDarknet(config_path, weights_path)
        with open(classes_path, "r") as f:
            classes = [line.strip() for line in f.readlines()]
        
        # Configure the network to use available hardware acceleration
        net.setPreferableBackend(cv2.dnn.DNN_BACKEND_DEFAULT)
        try:
            # Try to use OpenCL acceleration if available
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
        
        # Get output layer names
        layer_names = net.getLayerNames()
        output_layers = [layer_names[i - 1] for i in net.getUnconnectedOutLayers()]
        
        print(f"Successfully loaded YOLO model for {intersection_id}")
    except Exception as e:
        print(f"Error loading YOLO model: {e}")
        print(f"Cannot proceed without object detection model")
        raise
    
    # Initialize video capture with explicit retry logic
    cap = None
    max_retries = 5
    retry_count = 0
    
    while cap is None or not cap.isOpened():
        try:
            print(f"Attempt {retry_count + 1}/{max_retries} to connect to camera {camera_index}")
            cap = cv2.VideoCapture(camera_index)  # Use the camera index provided
            
            # Set camera properties for better performance
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            cap.set(cv2.CAP_PROP_FPS, 30)  # Request 30 FPS
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))  # Use MJPG codec for better speed
            
            if not cap.isOpened():
                print(f"Failed to open camera {camera_index}. Retrying...")
                time.sleep(1)
                retry_count += 1
                if retry_count >= max_retries:
                    print(f"Could not open camera {camera_index} after {max_retries} attempts")
                    raise IOError(f"Could not open camera {camera_index}")
                continue
            
            print(f"Successfully connected to camera {camera_index} for {intersection_id}")
            # Read a test frame to verify camera is working
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
                # Update traffic data to indicate camera failure
                with data_lock:
                    traffic_data[intersection_id] = {
                        "vehicleCount": 0,
                        "hasEmergencyVehicle": False,
                        "timestamp": datetime.now().isoformat(),
                        "error": f"Failed to connect to camera {camera_index}: {str(e)}"
                    }
                # Keep trying periodically
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
    
    # Main processing loop
    frame_count = 0
    process_every_n_frames = frame_processing["skip_frames"]  # Process every Nth frame to reduce CPU usage
    last_auto_control_update = time.time()
    
    while True:
        try:
            start_time = time.time()
            
            # Check if we need to update auto traffic control
            current_time = time.time()
            if current_time - last_auto_control_update >= 1.0:  # Check every second
                update_traffic_signal_automatic(intersection_id)
                last_auto_control_update = current_time
            
            # Read a frame from the camera
            ret, frame = cap.read()
            
            if not ret or frame is None:
                print(f"Error reading frame from camera {camera_index}. Reconnecting...")
                cap.release()
                time.sleep(1)
                cap = cv2.VideoCapture(camera_index)
                if not cap.isOpened():
                    print(f"Failed to reconnect to camera {camera_index}")
                    time.sleep(5)  # Wait longer before retry
                continue
            
            # Update the latest frame for video streaming (unprocessed)
            with frame_lock:
                latest_frames[intersection_id] = frame.copy()
            
            # Only process every nth frame to improve performance
            frame_count += 1
            
            # Create a copy for processing
            process_frame = frame.copy()
            
            # Full processing (object detection) only on every nth frame
            full_processing = (frame_count % process_every_n_frames == 0)
            
            # Always add timestamp and basic info to the frame
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            intersection_name = "Main Street Intersection" if intersection_id == "int-001" else "Park Avenue Intersection"
            cv2.putText(process_frame, f"Traffic Camera: {current_time}", (10, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            cv2.putText(process_frame, intersection_name, (10, 60), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            
            # Add the current signal status
            with data_lock:
                signal_status = traffic_signals.get(intersection_id, "unknown")
                auto_enabled = auto_control.get(intersection_id, {}).get("enabled", False)
            
            signal_color = (0, 0, 255)  # red
            if signal_status == "green":
                signal_color = (0, 255, 0)
            elif signal_status == "yellow":
                signal_color = (0, 255, 255)
                
            cv2.putText(process_frame, f"Signal: {signal_status.upper()}", (10, 90), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, signal_color, 2)
                       
            cv2.putText(process_frame, f"Auto Mode: {('ON' if auto_enabled else 'OFF')}", (10, 120), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 165, 0) if auto_enabled else (128, 128, 128), 2)
            
            # Update processed frame that will be used for streaming
            with frame_lock:
                processed_frames[intersection_id] = process_frame.copy()
            
            # Skip full processing if not needed this frame
            if not full_processing:
                elapsed = time.time() - start_time
                sleep_time = max(0.001, (1.0/frame_processing["stream_fps"]) - elapsed)
                time.sleep(sleep_time)  # Control the loop speed
                continue
                
            # Record time of full processing
            frame_processing["last_full_process_time"] = time.time()
                
            # Preprocess the frame
            height, width, channels = frame.shape
            blob = cv2.dnn.blobFromImage(frame, 1/255.0, (416, 416), swapRB=True, crop=False)
            net.setInput(blob)
            
            # Get detections
            outputs = net.forward(output_layers)
            
            # Process detections
            vehicle_count = 0
            has_emergency = False
            current_vehicles = []
            
            for output in outputs:
                for detection in output:
                    scores = detection[5:]
                    class_id = np.argmax(scores)
                    confidence = scores[class_id]
                    
                    if confidence > emergency_config["confidence_threshold"]:
                        # Check if the detected object is a vehicle
                        if classes[class_id] in ["car", "truck", "bus", "motorcycle", "bicycle"]:
                            vehicle_count += 1
                            
                            # Get bounding box dimensions
                            center_x = int(detection[0] * width)
                            center_y = int(detection[1] * height)
                            w = int(detection[2] * width)
                            h = int(detection[3] * height)
                            
                            # Calculate position
                            x = int(center_x - w / 2)
                            y = int(center_y - h / 2)
                            
                            # Generate vehicle ID if new, track if existing
                            vehicle_position = (center_x, center_y)
                            vehicle_id = None
                            
                            # Check if this is a vehicle we're already tracking
                            for known_id, known_pos in list(last_vehicle_positions.get(intersection_id, {}).items()):
                                known_x, known_y = known_pos
                                # If the center is close enough to a known vehicle, consider it the same one
                                distance = ((center_x - known_x) ** 2 + (center_y - known_y) ** 2) ** 0.5
                                if distance < 50:  # Threshold for considering it the same vehicle
                                    vehicle_id = known_id
                                    break
                            
                            # If no matching vehicle, create new ID
                            if vehicle_id is None:
                                vehicle_id = f"v-{next_vehicle_id}"
                                next_vehicle_id += 1
                            
                            # Update position
                            if intersection_id not in last_vehicle_positions:
                                last_vehicle_positions[intersection_id] = {}
                            last_vehicle_positions[intersection_id][vehicle_id] = vehicle_position
                            
                            # Check for emergency vehicles (ambulances, police cars)
                            is_emergency = False
                            if w > emergency_config["min_size"] and h > emergency_config["min_size"]:
                                # Extract vehicle region
                                if x >= 0 and y >= 0 and x+w < width and y+h < height:
                                    vehicle_roi = frame[y:y+h, x:x+w]
                                    
                                    # Convert to HSV color space
                                    hsv = cv2.cvtColor(vehicle_roi, cv2.COLOR_BGR2HSV)
                                    
                                    # Define color ranges for red and blue emergency lights
                                    lower_red = np.array([0, 120, 70])
                                    upper_red = np.array([10, 255, 255])
                                    lower_blue = np.array([110, 50, 50])
                                    upper_blue = np.array([130, 255, 255])
                                    
                                    # Create masks for red and blue colors
                                    mask_red = cv2.inRange(hsv, lower_red, upper_red)
                                    mask_blue = cv2.inRange(hsv, lower_blue, upper_blue)
                                    
                                    # Calculate the percentage of emergency colors
                                    red_percent = cv2.countNonZero(mask_red) / (w * h) * 100
                                    blue_percent = cv2.countNonZero(mask_blue) / (w * h) * 100
                                    
                                    # If enough red or blue pixels are detected, classify as emergency vehicle
                                    if red_percent > 5 or blue_percent > 5:
                                        is_emergency = True
                                        has_emergency = True
                                        print(f"Emergency vehicle detected at {intersection_id}!")
                                        
                                        # Draw box around emergency vehicle in the processed frame
                                        with frame_lock:
                                            cv2.rectangle(processed_frames[intersection_id], (x, y), (x + w, y + h), (0, 0, 255), 2)
                                            cv2.putText(processed_frames[intersection_id], "EMERGENCY VEHICLE", (x, y - 10), 
                                                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
                            
                            # Add two-wheeler detection with helmet and passenger violations
                            helmet_violation = False
                            passenger_violation = False
                            
                            if classes[class_id] in ["motorcycle", "bicycle"] and x >= 0 and y >= 0 and x+w < width and y+h < height:
                                vehicle_roi = frame[y:y+h, x:x+w]
                                
                                # Count people on the bike
                                person_count = count_people_on_vehicle(vehicle_roi, net, classes, output_layers)
                                
                                # Check if the count exceeds the limit
                                if person_count > two_wheeler_config["person_count_threshold"]:
                                    passenger_violation = True
                                    print(f"Passenger violation detected: {person_count} people on two-wheeler")
                                    
                                    # Add to processed frame
                                    with frame_lock:
                                        cv2.putText(processed_frames[intersection_id], 
                                                  f"VIOLATION: {person_count} PASSENGERS", 
                                                  (x, y + h + 30), 
                                                  cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
                                
                                # Check for helmet
                                if person_count > 0:
                                    has_helmet = detect_helmet(vehicle_roi, net, classes, output_layers)
                                    if not has_helmet:
                                        helmet_violation = True
                                        print(f"Helmet violation detected on two-wheeler")
                                        
                                        # Add to processed frame
                                        with frame_lock:
                                            cv2.putText(processed_frames[intersection_id], 
                                                      "VIOLATION: NO HELMET", 
                                                      (x, y + h + 15), 
                                                      cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
                            
                            # Store vehicle data
                            vehicle_data = {
                                "id": vehicle_id,
                                "type": classes[class_id],
                                "position": vehicle_position,
                                "size": (w, h),
                                "is_emergency": is_emergency,
                                "license_plate": generate_random_license_plate() if random.random() < 0.8 else None,
                                "helmet_violation": helmet_violation,
                                "passenger_violation": passenger_violation
                            }
                            current_vehicles.append(vehicle_data)
                            
                            # Draw bounding box for each vehicle in the processed frame
                            with frame_lock:
                                box_color = (0, 0, 255) if is_emergency else (255, 0, 0)
                                if helmet_violation or passenger_violation:
                                    box_color = (0, 165, 255)  # Orange for violations
                                
                                cv2.rectangle(processed_frames[intersection_id], (x, y), (x + w, y + h), box_color, 2)
                                label = f"{classes[class_id]} {vehicle_id}"
                                cv2.putText(processed_frames[intersection_id], label, (x, y - 5), 
                                          cv2.FONT_HERSHEY_SIMPLEX, 0.5, box_color, 2)
                                
                                # Add license plate if available
                                if vehicle_data["license_plate"]:
                                    cv2.putText(processed_frames[intersection_id], vehicle_data["license_plate"], (x, y + h + 15), 
                                              cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 2)
            
            # Update the detected vehicles list
            with data_lock:
                detected_vehicles[intersection_id] = current_vehicles
            
            # Update traffic data with thread safety
            with data_lock:
                # If emergency is detected, automatically set signal to green
                if has_emergency and traffic_signals[intersection_id] != "green":
                    traffic_signals[intersection_id] = "green"
                    auto_control[intersection_id]["last_change_time"] = time.time()
                    print(f"Emergency vehicle detected at {intersection_id}. Setting signal to green.")
                    
                    # Set the other intersection to red for emergency priority
                    other_id = "int-002" if intersection_id == "int-001" else "int-001"
                    if traffic_signals[other_id] != "yellow":  # Don't interrupt yellow phase
                        traffic_signals[other_id] = "red"
                        print(f"Setting {other_id} to red for emergency priority")
                    
                traffic_data[intersection_id] = {
                    "vehicleCount": vehicle_count,
                    "hasEmergencyVehicle": has_emergency,
                    "timestamp": datetime.now().isoformat(),
                    "autoMode": auto_control[intersection_id]["enabled"]
                }
            
            # Print status update periodically
            if frame_count % 100 == 0:
                print(f"Intersection {intersection_id}: {vehicle_count} vehicles, Emergency: {has_emergency}")
                
            # Control the loop speed based on target FPS
            elapsed = time.time() - start_time
            sleep_time = max(0.001, (1.0/frame_processing["stream_fps"]) - elapsed)
            time.sleep(sleep_time)
                
        except Exception as e:
            print(f"Error in video processing for {intersection_id}: {e}")
            time.sleep(0.1)
        
    # Cleanup (this will only execute if we break the loop)
    if cap is not None:
        cap.release()
    cv2.destroyAllWindows()

def generate_random_license_plate():
    """Generate random license plate number for simulation"""
    letters = "ABCDEFGHJKLMNPQRSTUVWXYZ"
    numbers = "0123456789"
    
    # State/prefix (2 letters) + 2 numbers + 3 letters
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
        
        # Store violations
        for vehicle in vehicles:
            violation_type = None
            details = ""
            
            # Red light violation (simulated for demonstration)
            if current_signal == "red" and random.random() < 0.2:  # 20% chance
                violation_type = "red_light"
                details = "Running a red light"
                
            # Speeding violation (simulated for demonstration)  
            elif random.random() < 0.1:  # 10% chance
                violation_type = "speeding"
                details = "Exceeding speed limit"
                
            # Two-wheeler violations (actual detection)
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
                    "imageUrl": f"https://example.com/violations/{violation_type}_{random.randint(1, 10)}.jpg"  # Fake URL for demo
                }
                
                # Store in MongoDB if available
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
    interval = 1.0 / max(0.5, fps_limit)  # At least 0.5 FPS, but limit to requested FPS
    last_frame_time = 0
    
    while True:
        # Respect requested FPS
        current_time = time.time()
        elapsed = current_time - last_frame_time
        if elapsed < interval:
            time.sleep(0.01)  # Small sleep to prevent CPU hogging
            continue
            
        last_frame_time = current_time
        
        # Wait until we have a frame
        if processed_frames.get(intersection_id) is None:
            time.sleep(0.1)
            continue
            
        # Use processed frame with annotations
        with frame_lock:
            if processed_frames.get(intersection_id) is not None:
                frame = processed_frames[intersection_id].copy()
            else:
                continue
        
        # Resize for streaming if needed
        if frame_processing["max_width"] < frame.shape[1]:
            scale = frame_processing["max_width"] / frame.shape[1]
            new_width = frame_processing["max_width"]
            new_height = int(frame.shape[0] * scale)
            frame = cv2.resize(frame, (new_width, new_height))
                
        # Encode the frame as JPEG with quality setting
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), frame_processing["frame_quality"]]
        ret, buffer = cv2.imencode('.jpg', frame, encode_param)
        if not ret:
            continue
            
        # Yield the frame in the multipart response format
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

@app.route('/api/traffic', methods=['GET'])
def get_traffic_data():
    """
    Return the current traffic data for all intersections
    """
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
    """
    Update the traffic signal status
    """
    data = request.json
    intersection_id = data.get('intersectionId')
    status = data.get('status')
    
    if not intersection_id or not status or status not in ["red", "yellow", "green"]:
        return jsonify({"success": False, "error": "Invalid request parameters"}), 400
    
    with data_lock:
        # Only allow manual changes if auto mode is disabled
        if auto_control[intersection_id]["enabled"]:
            return jsonify({"success": False, "error": "Cannot change signal manually while auto mode is enabled"}), 400
            
        traffic_signals[intersection_id] = status
    
    print(f"Changing traffic signal at {intersection_id} to {status}")
    return jsonify({"success": True})

@app.route('/api/traffic/auto_control', methods=['POST'])
def toggle_auto_control():
    """
    Toggle automatic traffic signal control
    """
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
    """
    Check for traffic violations at a specific intersection
    """
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
    """
    Get all recorded traffic violations
    """
    if db is not None:
        try:
            # Get violations from MongoDB
            cursor = violations_collection.find().sort("timestamp", -1).limit(50)
            violations = []
            
            for doc in cursor:
                doc["id"] = str(doc.pop("_id"))  # Convert ObjectId to string
                violations.append(doc)
                
            return jsonify(violations)
        except Exception as e:
            print(f"Error retrieving violations: {e}")
            return jsonify([])
    else:
        # Return simulated violations if no database
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

@app.route('/api/video_feed/<intersection_id>')
def video_feed(intersection_id):
    """
    Video streaming route for the camera feed with quality parameter
    """
    if intersection_id not in ["int-001", "int-002"]:
        return "Invalid intersection ID", 400
        
    # Get requested FPS from query parameter
    fps = request.args.get('fps', 1, type=float)
    # Update frame quality based on FPS (higher FPS = lower quality to maintain performance)
    if fps <= 0.5:
        frame_processing["frame_quality"] = 75  # Higher quality for low FPS
    elif fps <= 1:
        frame_processing["frame_quality"] = 70  # Medium quality
    else:
        frame_processing["frame_quality"] = 65  # Lower quality for high FPS
    
    return Response(generate_frames(intersection_id, fps),
                   mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/api/stream_status')
def stream_status():
    """
    Return stream status information for diagnostics
    """
    return jsonify({
        "stream_fps": frame_processing["stream_fps"],
        "process_skip_frames": frame_processing["skip_frames"],
        "frame_quality": frame_processing["frame_quality"],
        "last_processed": time.time() - frame_processing["last_full_process_time"]
    })

if __name__ == '__main__':
    # Create directory for YOLO files if it doesn't exist
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
    
    # Start video processing for each intersection in background threads
    thread1 = threading.Thread(
        target=detect_vehicles, 
        args=(0, "int-001"),  # 0 is the index for laptop camera
        daemon=True
    )
    thread1.start()
    print(f"Started detection thread for int-001 with laptop camera (index 0)")
    
    thread2 = threading.Thread(
        target=detect_vehicles, 
        args=(1, "int-002"),  # 1 is the index for external webcam
        daemon=True
    )
    thread2.start()
    print(f"Started detection thread for int-002 with external webcam (index 1)")
    
    # Start the Flask app
    print("Starting Flask server on http://0.0.0.0:5000")
    app.run(debug=False, threaded=True, host='0.0.0.0', port=5000)
