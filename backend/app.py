
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
        
        if not os.path.exists(config_path) or not os.path.exists(weights_path) or not os.path.exists(classes_path):
            print(f"YOLO files not found at {yolo_dir}. Please download them as mentioned in README.md")
            raise FileNotFoundError(f"Required YOLO files not found in {yolo_dir}")
            
        net = cv2.dnn.readNetFromDarknet(config_path, weights_path)
        with open(classes_path, "r") as f:
            classes = [line.strip() for line in f.readlines()]
        
        # Configure the network
        net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
        net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
        
        # Get output layer names
        layer_names = net.getLayerNames()
        output_layers = [layer_names[i - 1] for i in net.getUnconnectedOutLayers()]
        
        print(f"Successfully loaded YOLO model for {intersection_id}")
    except Exception as e:
        print(f"Error loading YOLO model: {e}")
        print(f"Cannot proceed without object detection model")
        raise
    
    # Initialize video capture - retry up to 3 times if it fails
    camera_opened = False
    retry_count = 0
    max_retries = 3
    
    while not camera_opened and retry_count < max_retries:
        try:
            print(f"Attempt {retry_count + 1}/{max_retries} to connect to camera source {video_source}")
            cap = cv2.VideoCapture(video_source)
            
            if not cap.isOpened():
                print(f"Failed to open camera. Retrying in 2 seconds...")
                time.sleep(2)
                retry_count += 1
                if retry_count == max_retries:
                    print(f"Could not open camera after {max_retries} attempts")
                    raise IOError(f"Could not open camera source {video_source}")
            else:
                camera_opened = True
                print(f"Successfully connected to camera for {intersection_id}")
        except Exception as e:
            print(f"Error connecting to camera: {e}")
            retry_count += 1
            time.sleep(2)
            if retry_count == max_retries:
                raise IOError(f"Failed to connect to camera: {e}")
    
    print(f"Starting main detection loop for {intersection_id}")
    # Main processing loop
    while True:
        # Real video processing mode
        try:
            ret, frame = cap.read()
            if not ret:
                print(f"Error reading frame from {video_source}. Reconnecting...")
                cap.release()
                time.sleep(1)
                cap = cv2.VideoCapture(video_source)
                if not cap.isOpened():
                    print(f"Failed to reconnect to camera {video_source}")
                    time.sleep(5)  # Wait longer before retry
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
                                        print(f"Emergency vehicle detected at {intersection_id}!")
                        
                        # Optional: Draw detection boxes on frame for monitoring
                        # if classes[class_id] in ["car", "truck", "bus", "motorcycle", "ambulance"]:
                        #     center_x = int(detection[0] * width)
                        #     center_y = int(detection[1] * height)
                        #     w = int(detection[2] * width)
                        #     h = int(detection[3] * height)
                        #     x = int(center_x - w / 2)
                        #     y = int(center_y - h / 2)
                        #     cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
            
            # Optional: Display the processed frame with detections
            # cv2.imshow(f"Traffic Camera - {intersection_id}", frame)
            # if cv2.waitKey(1) & 0xFF == ord('q'):
            #     break
            
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
            
            # Print status update every 30 seconds
            if int(time.time()) % 30 == 0:
                print(f"Intersection {intersection_id}: {vehicle_count} vehicles, Emergency: {has_emergency}")
                
        except Exception as e:
            print(f"Error in video processing for {intersection_id}: {e}")
            # Try to reconnect to the camera
            try:
                if 'cap' in locals() and cap is not None:
                    cap.release()
                time.sleep(3)
                cap = cv2.VideoCapture(video_source)
                if not cap.isOpened():
                    print(f"Failed to reconnect to camera. Will retry...")
                    time.sleep(5)
            except Exception as reconnect_error:
                print(f"Error reconnecting to camera: {reconnect_error}")
                time.sleep(5)
        
        # Sleep briefly to reduce CPU usage
        time.sleep(0.05)
    
    # Cleanup
    if 'cap' in locals() and cap is not None:
        cap.release()
    cv2.destroyAllWindows()

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
    # Create directory for YOLO files if it doesn't exist
    yolo_dir = os.path.join(os.path.dirname(__file__), 'yolo')
    if not os.path.exists(yolo_dir):
        os.makedirs(yolo_dir)
        print(f"Created directory {yolo_dir} for YOLO model files")
        print("Please download the following files to the 'yolo' directory:")
        print("1. yolov4.cfg: https://raw.githubusercontent.com/AlexeyAB/darknet/master/cfg/yolov4.cfg")
        print("2. yolov4.weights: https://github.com/AlexeyAB/darknet/releases/download/darknet_yolo_v3_optimal/yolov4.weights")
        print("3. coco.names: https://raw.githubusercontent.com/AlexeyAB/darknet/master/data/coco.names")
    
    # Define video sources for each intersection
    # Use camera indexes (0, 1, 2...) or RTSP/IP camera URLs
    video_sources = {
        "int-001": 0,  # Main camera (default webcam)
        "int-002": 0,  # Using same camera for testing, replace with different cameras or sources
        "int-003": 0,  # Using same camera for testing, replace with different cameras or sources 
        "int-004": 0,  # Using same camera for testing, replace with different cameras or sources
    }
    
    print("Starting traffic monitoring with the following camera sources:")
    for intersection, source in video_sources.items():
        print(f"- {intersection}: {source}")
    
    # Start video processing in background threads
    threads = []
    for intersection_id, source in video_sources.items():
        thread = threading.Thread(
            target=detect_vehicles, 
            args=(source, intersection_id),
            daemon=True
        )
        thread.start()
        threads.append(thread)
        print(f"Started detection thread for {intersection_id}")
    
    # Start the Flask app
    print("Starting Flask server on http://0.0.0.0:5000")
    app.run(debug=False, host='0.0.0.0', port=5000)
