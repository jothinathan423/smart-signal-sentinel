
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

4. Download YOLO model files and place them in the `yolo` directory:
   - yolov4.cfg
   - yolov4.weights
   - coco.names

   You can download these files from:
   - https://github.com/AlexeyAB/darknet/releases/download/darknet_yolo_v3_optimal/yolov4.weights
   - https://raw.githubusercontent.com/AlexeyAB/darknet/master/cfg/yolov4.cfg
   - https://raw.githubusercontent.com/AlexeyAB/darknet/master/data/coco.names

5. Run the application:
   ```
   python app.py
   ```

## System Details

This simplified version uses:
- A single traffic intersection monitored by your laptop's webcam
- YOLO object detection to count vehicles and detect emergency vehicles
- Automatic traffic light state changes when emergency vehicles are detected
- A REST API for monitoring and controlling the traffic light status

## API Endpoints

- `GET /api/traffic` - Get current traffic data for the intersection
- `POST /api/traffic/signal` - Update traffic signal status
  - Request body: `{ "intersectionId": "int-001", "status": "green" }`

## Troubleshooting

- If your laptop camera is not detected, check that it's not being used by another application
- If you get "YOLO files not found" error, make sure you've downloaded the required files to the 'yolo' directory
- For better performance on low-power devices, you might want to use smaller YOLO models like YOLOv4-tiny
