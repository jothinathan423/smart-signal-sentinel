
import cv2
import numpy as np
from flask import Flask, jsonify, request, Response
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
}

# Traffic signal status
traffic_signals = {
    "int-001": "red",
}

# Configuration for emergency vehicle detection
emergency_config = {
    "min_size": 80,  # Minimum size of emergency vehicle to detect
    "confidence_threshold": 0.5,  # Confidence threshold for detection
}

# Lock for thread-safe access to shared data
data_lock = threading.Lock()
# Latest frame for video streaming
latest_frame = None
processed_frame = None  # Store the processed frame separately
frame_lock = threading.Lock()

# Frame processing configuration
frame_processing = {
    "skip_frames": 5,  # Process only every Nth frame
    "last_full_process_time": 0,
    "frame_quality": 70,  # JPEG quality for streaming (0-100)
    "max_width": 640,  # Maximum width for streaming
    "stream_fps": 15  # Target FPS for streaming
}

def detect_vehicles(video_source, intersection_id):
    """
    Process video feed to count vehicles and detect emergency vehicles
    """
    global latest_frame, processed_frame
    print(f"Starting vehicle detection for intersection {intersection_id} using laptop camera")
    
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
            print(f"Attempt {retry_count + 1}/{max_retries} to connect to laptop camera")
            cap = cv2.VideoCapture(0)  # Use laptop camera (index 0)
            
            # Set camera properties for better performance
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            cap.set(cv2.CAP_PROP_FPS, 30)  # Request 30 FPS
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))  # Use MJPG codec for better speed
            
            if not cap.isOpened():
                print(f"Failed to open camera. Retrying...")
                time.sleep(1)
                retry_count += 1
                if retry_count >= max_retries:
                    print(f"Could not open laptop camera after {max_retries} attempts")
                    raise IOError(f"Could not open laptop camera")
                continue
            
            print(f"Successfully connected to laptop camera for {intersection_id}")
            # Read a test frame to verify camera is working
            ret, test_frame = cap.read()
            if not ret or test_frame is None:
                print("Camera opened but could not read frame. Retrying...")
                cap.release()
                cap = None
                retry_count += 1
                time.sleep(1)
                continue
                
        except Exception as e:
            print(f"Error connecting to laptop camera: {e}")
            retry_count += 1
            time.sleep(1)
            if retry_count >= max_retries:
                print(f"Giving up on laptop camera after {max_retries} attempts")
                # Update traffic data to indicate camera failure
                with data_lock:
                    traffic_data[intersection_id] = {
                        "vehicleCount": 0,
                        "hasEmergencyVehicle": False,
                        "timestamp": datetime.now().isoformat(),
                        "error": f"Failed to connect to laptop camera: {str(e)}"
                    }
                # Keep trying periodically
                while True:
                    time.sleep(10)
                    try:
                        print(f"Periodic retry: Attempting to connect to laptop camera")
                        cap = cv2.VideoCapture(0)
                        if cap.isOpened():
                            print(f"Successfully reconnected to laptop camera")
                            break
                        cap.release()
                    except Exception as retry_e:
                        print(f"Periodic retry failed: {retry_e}")
    
    print(f"Starting main detection loop for {intersection_id}")
    
    # Main processing loop
    frame_count = 0
    process_every_n_frames = frame_processing["skip_frames"]  # Process every Nth frame to reduce CPU usage
    
    while True:
        try:
            start_time = time.time()
            
            # Read a frame from the camera
            ret, frame = cap.read()
            
            if not ret or frame is None:
                print(f"Error reading frame from laptop camera. Reconnecting...")
                cap.release()
                time.sleep(1)
                cap = cv2.VideoCapture(0)
                if not cap.isOpened():
                    print(f"Failed to reconnect to laptop camera")
                    time.sleep(5)  # Wait longer before retry
                continue
            
            # Update the latest frame for video streaming (unprocessed)
            with frame_lock:
                latest_frame = frame.copy()
            
            # Only process every nth frame to improve performance
            frame_count += 1
            
            # Create a copy for processing
            process_frame = frame.copy()
            
            # Full processing (object detection) only on every nth frame
            full_processing = (frame_count % process_every_n_frames == 0)
            
            # Always add timestamp and basic info to the frame
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cv2.putText(process_frame, f"Traffic Camera: {current_time}", (10, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            cv2.putText(process_frame, "Main Street Intersection", (10, 60), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            
            # Add the current signal status
            with data_lock:
                signal_status = traffic_signals.get(intersection_id, "unknown")
            
            signal_color = (0, 0, 255)  # red
            if signal_status == "green":
                signal_color = (0, 255, 0)
            elif signal_status == "yellow":
                signal_color = (0, 255, 255)
                
            cv2.putText(process_frame, f"Signal: {signal_status.upper()}", (10, 90), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, signal_color, 2)
            
            # Update processed frame that will be used for streaming
            with frame_lock:
                processed_frame = process_frame.copy()
            
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
                                        
                                        # Draw box around emergency vehicle in the processed frame
                                        with frame_lock:
                                            cv2.rectangle(processed_frame, (x, y), (x + w, y + h), (0, 0, 255), 2)
                                            cv2.putText(processed_frame, "EMERGENCY VEHICLE", (x, y - 10), 
                                                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
                            
                            # Draw bounding box for each vehicle in the processed frame
                            with frame_lock:
                                x = int(center_x - w / 2)
                                y = int(center_y - h / 2)
                                cv2.rectangle(processed_frame, (x, y), (x + w, y + h), (255, 0, 0), 2)
                                cv2.putText(processed_frame, classes[class_id], (x, y - 5), 
                                          cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)
            
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

def generate_frames(fps_requested=1):
    """
    Generator function for video streaming with adjustable quality
    """
    global processed_frame
    
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
        if processed_frame is None:
            time.sleep(0.1)
            continue
            
        # Use processed frame with annotations
        with frame_lock:
            if processed_frame is not None:
                frame = processed_frame.copy()
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

@app.route('/api/video_feed')
def video_feed():
    """
    Video streaming route for the camera feed with quality parameter
    """
    # Get requested FPS from query parameter
    fps = request.args.get('fps', 1, type=float)
    # Update frame quality based on FPS (higher FPS = lower quality to maintain performance)
    if fps <= 0.5:
        frame_processing["frame_quality"] = 75  # Higher quality for low FPS
    elif fps <= 1:
        frame_processing["frame_quality"] = 70  # Medium quality
    else:
        frame_processing["frame_quality"] = 65  # Lower quality for high FPS
    
    return Response(generate_frames(fps),
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
    
    # Define the single intersection with laptop camera
    intersection_id = "int-001"
    
    print("Starting traffic monitoring with laptop camera")
    
    # Start video processing in background thread
    thread = threading.Thread(
        target=detect_vehicles, 
        args=(0, intersection_id),  # 0 is the index for laptop camera
        daemon=True
    )
    thread.start()
    print(f"Started detection thread for {intersection_id}")
    
    # Start the Flask app
    print("Starting Flask server on http://0.0.0.0:5000")
    app.run(debug=False, threaded=True, host='0.0.0.0', port=5000)
