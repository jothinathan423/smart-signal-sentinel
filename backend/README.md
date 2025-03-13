
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

## Configuration

- By default, the application will use your webcam (index 0) for the first intersection and simulation for the others.
- To use different video sources, modify the `video_sources` dictionary in the `app.py` file.
- You can use video files, IP camera streams, or other video inputs supported by OpenCV.

## API Endpoints

- `GET /api/traffic` - Get current traffic data for all intersections
- `POST /api/traffic/signal` - Update traffic signal status
  - Request body: `{ "intersectionId": "int-001", "status": "green" }`

## Simulation Mode

If YOLO model files are not found or there's an issue with the video source, the system will fall back to simulation mode, which generates random traffic data.
