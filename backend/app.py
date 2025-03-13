
import cv2
import numpy as np
from flask import Flask, jsonify, request
from flask_cors import CORS
import time
import threading
import os
from datetime import datetime

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Store the latest traffic data
traffic_data = {
    "int-001": {"vehicleCount": 0, "hasEmergencyVehicle": False, "timestamp": ""},
    "int-002": {"vehicleCount": 0, "hasEmergencyVehicle": False, "timestamp": ""},
    "int-003": {"vehicleCount": 0, "hasEmergencyVehicle": False, "timestamp": ""},
    "int-004": {"vehicleCount": 0, "hasEmergencyVehicle": False, "timestamp": ""},
}

# Traffic signal status
traffic_signals = {
    "int-001": "red",
    "int-002": "red",
    "int-003": "red",
    "int-004": "red",
}

# Configuration for emergency vehicle detection
emergency_config = {
    "min_size": 80,  # Minimum size of emergency vehicle to detect
    "confidence_threshold": 0.5,  # Confidence threshold for detection
}

# Lock for thread-safe access to shared data
data_lock = threading.Lock()

def detect_vehicles(video_source, intersection_id):
    """
    Process video feed to count vehicles and detect emergency vehicles
    """
    print(f"Starting vehicle detection for intersection {intersection_id} using source {video_source}")
    
    # Load pre-trained vehicle detection model (using YOLO)
    try:
        # Check if we're running in development or production
        yolo_dir = os.path.join(os.path.dirname(__file__), 'yolo')
        
        # Try to load YOLO model - make sure these files exist in your backend/yolo directory
        config_path = os.path.join(yolo_dir, 'yolov4.cfg')
        weights_path = os.path.join(yolo_dir, 'yolov4.weights')
        classes_path = os.path.join(yolo_dir, 'coco.names')
        
        if not os.path.exists(config_path) or not os.path.exists(weights_path):
            print(f"YOLO files not found. Using simulation mode for {intersection_id}")
            use_simulation = True
        else:
            net = cv2.dnn.readNetFromDarknet(config_path, weights_path)
            with open(classes_path, "r") as f:
                classes = [line.strip() for line in f.readlines()]
            
            # Configure the network
            net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
            net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
            use_simulation = False
            
            # Get output layer names
            layer_names = net.getLayerNames()
            output_layers = [layer_names[i - 1] for i in net.getUnconnectedOutLayers()]
    except Exception as e:
        print(f"Error loading YOLO model: {e}")
        print(f"Using simulation mode for {intersection_id}")
        use_simulation = True
    
    # Initialize video capture
    if not use_simulation:
        try:
            cap = cv2.VideoCapture(video_source)
            if not cap.isOpened():
                print(f"Error opening video source {video_source}. Using simulation mode.")
                use_simulation = True
        except Exception as e:
            print(f"Error with video capture: {e}")
            use_simulation = True
    
    # Main processing loop
    while True:
        if use_simulation:
            # Simulation mode - generate random data
            with data_lock:
                vehicle_count = np.random.randint(1, 20)
                has_emergency = np.random.random() < 0.1  # 10% chance of emergency
                
                # If emergency is detected, automatically set signal to green
                if has_emergency and traffic_signals[intersection_id] != "green":
                    traffic_signals[intersection_id] = "green"
                    print(f"Emergency vehicle detected at {intersection_id}. Setting signal to green.")
                
                traffic_data[intersection_id] = {
                    "vehicleCount": vehicle_count,
                    "hasEmergencyVehicle": has_emergency,
                    "timestamp": datetime.now().isoformat()
                }
            
            # Sleep longer in simulation mode
            time.sleep(2)
            continue
        
        # Real video processing mode
        ret, frame = cap.read()
        if not ret:
            print(f"Error reading frame from {video_source}. Restarting capture.")
            cap.release()
            time.sleep(1)
            try:
                cap = cv2.VideoCapture(video_source)
            except:
                print(f"Failed to restart capture. Using simulation.")
                use_simulation = True
                continue
        
        # Preprocess the frame
        height, width, channels = frame.shape
        blob = cv2.dnn.blobFromImage(frame, 1/255.0, (416, 416), swapRB=True, crop=False)
        net.setInput(blob)
        
        # Get detections
        outputs = net.forward(output_layers)
        
        # Process detections
        vehicle_count = 0
        has_emergency = False
        
        for output in outputs:
            for detection in output:
                scores = detection[5:]
                class_id = np.argmax(scores)
                confidence = scores[class_id]
                
                if confidence > emergency_config["confidence_threshold"]:
                    # Check if the detected object is a vehicle
                    if classes[class_id] in ["car", "truck", "bus", "motorcycle"]:
                        vehicle_count += 1
                        
                        # Get bounding box dimensions
                        center_x = int(detection[0] * width)
                        center_y = int(detection[1] * height)
                        w = int(detection[2] * width)
                        h = int(detection[3] * height)
                        
                        # Check for emergency vehicles (ambulances, police cars)
                        if w > emergency_config["min_size"] and h > emergency_config["min_size"]:
                            x = int(center_x - w / 2)
                            y = int(center_y - h / 2)
                            
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
                                    has_emergency = True
        
        # Update traffic data with thread safety
        with data_lock:
            # If emergency is detected, automatically set signal to green
            if has_emergency and traffic_signals[intersection_id] != "green":
                traffic_signals[intersection_id] = "green"
                print(f"Emergency vehicle detected at {intersection_id}. Setting signal to green.")
                
            traffic_data[intersection_id] = {
                "vehicleCount": vehicle_count,
                "hasEmergencyVehicle": has_emergency,
                "timestamp": datetime.now().isoformat()
            }
        
        # Sleep to reduce CPU usage
        time.sleep(0.1)
    
    if not use_simulation:
        cap.release()

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
                "status": traffic_signals[intersection_id]
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
        traffic_signals[intersection_id] = status
    
    print(f"Changing traffic signal at {intersection_id} to {status}")
    return jsonify({"success": True})

if __name__ == '__main__':
    # Start video processing in background threads
    video_sources = {
        "int-001": 0,  # Default webcam (or replace with video file or IP camera stream)
        "int-002": "simulation",  # You can use separate video files for each intersection
        "int-003": "simulation",  # Or use IP camera feeds
        "int-004": "simulation",  # Or just use simulation
    }
    
    for intersection_id, source in video_sources.items():
        video_source = 0 if source == 0 else "simulation"  # Default to simulation for this example
        thread = threading.Thread(
            target=detect_vehicles, 
            args=(video_source, intersection_id),
            daemon=True
        )
        thread.start()
    
    # Create directory for YOLO files if it doesn't exist
    yolo_dir = os.path.join(os.path.dirname(__file__), 'yolo')
    if not os.path.exists(yolo_dir):
        os.makedirs(yolo_dir)
        print(f"Created directory {yolo_dir} for YOLO model files")
        print("Place yolov4.cfg, yolov4.weights, and coco.names in this directory")
    
    # Start the Flask app
    app.run(debug=True, host='0.0.0.0', port=5000)
