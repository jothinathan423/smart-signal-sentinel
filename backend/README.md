
# Smart Traffic Management System - Backend

This is the Python backend for the Smart Traffic Management System.

## Setup

1. Create a virtual environment:
   ```
   python -m venv venv
   ```

2. Activate the virtual environment:
   - Windows: `venv\Scripts\activate`
   - Linux/Mac: `source venv/bin/activate`

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Install MongoDB (optional):
   - The system can run without MongoDB, but traffic violations won't be stored persistently
   - Install MongoDB from https://www.mongodb.com/try/download/community
   - Start MongoDB service on default port (27017)

5. Download YOLO model files and place them in the `yolo` directory:
   - yolov4.cfg
   - yolov4.weights
   - coco.names

   You can download these files from:
   - https://github.com/AlexeyAB/darknet/releases/download/darknet_yolo_v3_optimal/yolov4.weights
   - https://raw.githubusercontent.com/AlexeyAB/darknet/master/cfg/yolov4.cfg
   - https://raw.githubusercontent.com/AlexeyAB/darknet/master/data/coco.names

6. Connect your webcams:
   - The system uses two cameras:
     - Camera 0: Laptop built-in camera (first intersection)
     - Camera 1: External webcam (second intersection)
   - Make sure both cameras are connected and not in use by other applications

7. Run the application:
   ```
   python app.py
   ```

## System Features

- Dual intersection monitoring with coordinated traffic signals
- Automatic traffic signal control based on vehicle count and timing
- Emergency vehicle detection with automatic signal prioritization
- Traffic violation detection:
  - Red light running
  - Speeding
  - Two-wheeler violations:
    - Riding without helmet
    - Excess passengers (more than allowed limit)
- Vehicle license plate recognition
- MongoDB integration for storing violation records
- Responsive camera feeds with quality optimization

## API Endpoints

- `GET /api/traffic` - Get current traffic data for all intersections
- `POST /api/traffic/signal` - Update traffic signal status
  - Request body: `{ "intersectionId": "int-001", "status": "green" }`
- `POST /api/traffic/auto_control` - Toggle automatic traffic control
  - Request body: `{ "intersectionId": "int-001", "enabled": true }`
- `POST /api/traffic/check_violations` - Check for traffic violations
  - Request body: `{ "intersectionId": "int-001" }`
- `GET /api/traffic/violations` - Get list of recorded violations
- `GET /api/video_feed/<intersection_id>` - Camera video stream for specific intersection
  - Example: `/api/video_feed/int-001` for the first intersection
  - Query param: `fps` (e.g., `?fps=1` for 1 frame per second)

## Two-Wheeler Violation Detection

The system can detect two types of two-wheeler violations:
1. **Helmet Violations**: Riders not wearing helmets
2. **Passenger Violations**: More than allowed number of passengers on a two-wheeler (typically >2)

When a violation is detected:
- The vehicle is highlighted in the video feed
- The violation type is displayed on the video
- The license plate is recorded (simulated)
- The violation is stored in MongoDB if available

## Coordinated Traffic Signals

The system automatically coordinates traffic signals between intersections:
- When one intersection has a green signal, the other will have red
- Emergency vehicles override this coordination
- Signals are timed based on traffic density at each intersection

## Troubleshooting

- If your cameras are not detected, check that they're not being used by another application
- If you get "YOLO files not found" error, make sure you've downloaded the required files to the 'yolo' directory
- For better performance on low-power devices, you might want to use smaller YOLO models like YOLOv4-tiny
- If MongoDB connection fails, the system will still work but violations won't be stored persistently
- If you have only one camera, you can modify the code to use a simulated feed for the second intersection
