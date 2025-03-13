
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

5. Configure your camera sources:
   - Open `app.py` and update the `video_sources` dictionary with your camera indexes or IP camera URLs
   - By default, all intersections use your default webcam (index 0)
   - For multiple cameras, set different indexes (1, 2, 3) or use RTSP URLs

6. Run the application:
   ```
   python app.py
   ```

## Camera Configuration

For each intersection, you can specify a different camera source:

- Webcam: Use index numbers (0, 1, 2, etc.)
- IP Camera: Use RTSP or HTTP URLs, e.g., `"rtsp://admin:password@192.168.1.100:554/cam/realmonitor"`
- Video File: Use file path, e.g., `"path/to/traffic_video.mp4"`

Example configuration in `app.py`:
```python
video_sources = {
    "int-001": 0,  # First webcam
    "int-002": 1,  # Second webcam
    "int-003": "rtsp://admin:password@192.168.1.100:554/cam/realmonitor",  # IP camera
    "int-004": "path/to/traffic_video.mp4",  # Video file
}
```

## API Endpoints

- `GET /api/traffic` - Get current traffic data for all intersections
- `POST /api/traffic/signal` - Update traffic signal status
  - Request body: `{ "intersectionId": "int-001", "status": "green" }`

## Troubleshooting

- If your camera is not detected, check that the index number is correct or the IP address is accessible
- If you get "YOLO files not found" error, make sure you've downloaded the required files to the 'yolo' directory
- For better performance on low-power devices, you might want to use smaller YOLO models like YOLOv4-tiny
