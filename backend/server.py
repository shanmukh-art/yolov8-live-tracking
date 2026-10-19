import sys
import os
import asyncio
import time
import json
import cv2
import shutil
import numpy as np
from collections import deque
from fastapi import FastAPI, WebSocket, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

# Setup base directories dynamically
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
DIST_DIR = os.path.join(BASE_DIR, "frontend", "dist")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(DIST_DIR, exist_ok=True)

try:
    from ultralytics import YOLO
    HAS_YOLO = True
except ImportError:
    HAS_YOLO = False
    print("[!] YOLOv8 not found. Running in MOCK mode.")

try:
    from deep_sort_realtime.deepsort_tracker import DeepSort
    HAS_DEEPSORT = True
except ImportError:
    HAS_DEEPSORT = False
    print("[!] deep-sort-realtime not found.")

app = FastAPI()

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Global Configurations ---
current_model_name = "yolov8n"
current_tracker_type = "bytetrack"  # "bytetrack", "botsort", "deepsort"
conf_threshold = 0.25
iou_threshold = 0.45
active_classes = []  # Empty means all classes
show_boxes = True
show_labels = True
show_scores = True
show_trails = True

# Active video source settings
current_source_type = "mock"  # "mock", "webcam", "file", "url"
current_webcam_id = 0
current_file_path = ""
current_url_stream = ""

# Telemetry stats
live_fps = 0
active_object_count = 0
unique_object_count = 0
class_counts = {}
event_logs = []

# Tracker instances
model = None
deepsort_tracker = None
track_trails = {}  # track_id -> deque of center points
prev_track_ids = set()

# COCO Dataset Classes
COCO_CLASSES = [
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck", "boat",
    "traffic light", "fire hydrant", "stop sign", "parking meter", "bench", "bird", "cat",
    "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe", "backpack",
    "umbrella", "handbag", "tie", "suitcase", "frisbee", "skis", "snowboard", "sports ball",
    "kite", "baseball bat", "baseball glove", "skateboard", "surfboard", "tennis racket",
    "bottle", "wine glass", "cup", "fork", "knife", "spoon", "bowl", "banana", "apple",
    "sandwich", "orange", "broccoli", "carrot", "hot dog", "pizza", "donut", "cake",
    "chair", "couch", "potted plant", "bed", "dining table", "toilet", "tv", "laptop",
    "mouse", "remote", "keyboard", "cell phone", "microwave", "oven", "toaster", "sink",
    "refrigerator", "book", "clock", "vase", "scissors", "teddy bear", "hair drier", "toothbrush"
]

# Vibrant colors for tracking overlays (BGR format)
TRACK_COLORS = [
    (153, 51, 255),   # Vibrant Purple
    (51, 153, 255),   # Bright Cyan-Blue
    (51, 255, 153),   # Electric Mint
    (255, 255, 51),   # Neon Yellow
    (255, 153, 51),   # Electric Orange
    (255, 51, 153),   # Neon Pink
    (255, 51, 51),    # Neon Red
    (51, 255, 255),   # Cyan
    (153, 255, 51),   # Lime Green
]

# Load YOLO model
if HAS_YOLO:
    try:
        model = YOLO(f"{current_model_name}.pt")
    except Exception as e:
        HAS_YOLO = False
        print(f"[!] Error loading YOLO: {e}. Switching to MOCK mode.")

# --- Mock Object Simulation (when YOLO is missing or Source is Mock) ---
class MockTracker:
    def __init__(self):
        self.objects = []
        self.next_id = 1
        
    def step(self, width=640, height=480):
        # Move existing objects
        for obj in self.objects:
            obj["pos"][0] += obj["vel"][0]
            obj["pos"][1] += obj["vel"][1]
            obj["age"] += 1
            
            # Bounce off walls
            if obj["pos"][0] - obj["size"][0]//2 < 0 or obj["pos"][0] + obj["size"][0]//2 > width:
                obj["vel"][0] = -obj["vel"][0]
            if obj["pos"][1] - obj["size"][1]//2 < 0 or obj["pos"][1] + obj["size"][1]//2 > height:
                obj["vel"][1] = -obj["vel"][1]
                
        # Randomly remove objects (1% chance if old enough)
        self.objects = [obj for obj in self.objects if not (obj["age"] > 120 and np.random.rand() < 0.008)]
        
        # Randomly add new objects if count < 5
        if len(self.objects) < 6 and np.random.rand() < 0.04:
            # Classes: person (0), bicycle (1), car (2), dog (16), cat (15), backpack (24)
            classes = [0, 1, 2, 15, 16, 24]
            cls_id = int(np.random.choice(classes))
            w = int(60 + np.random.rand() * 40)
            h = int(100 + np.random.rand() * 50) if cls_id == 0 else int(60 + np.random.rand() * 30)
            self.objects.append({
                "id": self.next_id,
                "pos": [float(np.random.randint(100, width-100)), float(np.random.randint(100, height-100))],
                "vel": [float(np.random.choice([-4, -3, -2, 2, 3, 4])), float(np.random.choice([-4, -3, -2, 2, 3, 4]))],
                "size": [w, h],
                "class_id": cls_id,
                "age": 0
            })
            self.next_id += 1
            
        return self.objects

mock_tracker = MockTracker()

# --- Custom Visualization Drawing Helpers ---
def draw_rounded_rect(img, pt1, pt2, color, thickness=1, r=8):
    x1, y1 = pt1
    x2, y2 = pt2
    w = x2 - x1
    h = y2 - y1
    r = max(1, min(r, w // 2, h // 2))
    
    # Draw corners
    cv2.ellipse(img, (x1 + r, y1 + r), (r, r), 180, 0, 90, color, thickness, cv2.LINE_AA)
    cv2.ellipse(img, (x2 - r, y1 + r), (r, r), 270, 0, 90, color, thickness, cv2.LINE_AA)
    cv2.ellipse(img, (x1 + r, y2 - r), (r, r), 90, 0, 90, color, thickness, cv2.LINE_AA)
    cv2.ellipse(img, (x2 - r, y2 - r), (r, r), 0, 0, 90, color, thickness, cv2.LINE_AA)
    
    # Draw lines
    cv2.line(img, (x1 + r, y1), (x2 - r, y1), color, thickness, cv2.LINE_AA)
    cv2.line(img, (x1 + r, y2), (x2 - r, y2), color, thickness, cv2.LINE_AA)
    cv2.line(img, (x1, y1 + r), (x1, y2 - r), color, thickness, cv2.LINE_AA)
    cv2.line(img, (x2, y1 + r), (x2, y2 - r), color, thickness, cv2.LINE_AA)

def get_color(track_id):
    return TRACK_COLORS[int(track_id) % len(TRACK_COLORS)]

def render_predictions(frame, track_ids, boxes, scores, classes):
    global track_trails, active_object_count, class_counts
    
    h_img, w_img = frame.shape[:2]
    active_ids = set()
    current_class_counts = {}
    
    for i, raw_track_id in enumerate(track_ids):
        try:
            track_id = int(raw_track_id)
        except (ValueError, TypeError):
            track_id = raw_track_id
            
        active_ids.add(track_id)
        box = boxes[i]
        score = scores[i]
        cls_id = int(classes[i])
        class_name = COCO_CLASSES[cls_id] if 0 <= cls_id < len(COCO_CLASSES) else f"Class {cls_id}"
        
        # Update class distribution counts
        current_class_counts[class_name] = current_class_counts.get(class_name, 0) + 1
        
        color = get_color(track_id)
        x1, y1, x2, y2 = map(int, box)
        
        # Calculate center point
        cx, cy = int((x1 + x2) / 2), int((y1 + y2) / 2)
        
        # 1. Draw trails
        if show_trails:
            if track_id not in track_trails:
                track_trails[track_id] = deque(maxlen=25)
            track_trails[track_id].append((cx, cy))
            
            trail_points = list(track_trails[track_id])
            for idx in range(1, len(trail_points)):
                pt1 = trail_points[idx-1]
                pt2 = trail_points[idx]
                alpha = idx / len(trail_points)
                thickness = int(1.5 + 2.0 * alpha)
                
                overlay = frame.copy()
                cv2.line(overlay, pt1, pt2, color, thickness, cv2.LINE_AA)
                cv2.addWeighted(overlay, alpha * 0.7, frame, 1.0 - (alpha * 0.7), 0, frame)
        
        # 2. Draw boxes
        if show_boxes:
            # Draw glow overlay
            overlay = frame.copy()
            draw_rounded_rect(overlay, (x1, y1), (x2, y2), color, thickness=4, r=8)
            cv2.addWeighted(overlay, 0.25, frame, 0.75, 0, frame)
            # Solid box border
            draw_rounded_rect(frame, (x1, y1), (x2, y2), color, thickness=2, r=8)
            
        # 3. Draw Labels & Scores
        if show_labels:
            label_text = f"ID {track_id} | {class_name.upper()}"
            if show_scores:
                label_text += f" {score:.2f}"
                
            # Text Badge background overlay
            text_size = cv2.getTextSize(label_text, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)[0]
            badge_w, badge_h = text_size[0] + 12, text_size[1] + 10
            badge_y1 = max(0, y1 - badge_h)
            badge_y2 = y1
            
            badge_overlay = frame.copy()
            cv2.rectangle(badge_overlay, (x1, badge_y1), (x1 + badge_w, badge_y2), color, -1)
            cv2.addWeighted(badge_overlay, 0.35, frame, 0.65, 0, frame)
            
            # White text on colored badge
            cv2.putText(frame, label_text, (x1 + 6, badge_y2 - 6), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)
            
    # Clean up stale trails
    for tid in list(track_trails.keys()):
        if tid not in active_ids:
            del track_trails[tid]
            
    active_object_count = len(track_ids)
    class_counts = current_class_counts
    
    # Update event logs
    normalized_track_ids = []
    for tid in track_ids:
        try:
            normalized_track_ids.append(int(tid))
        except (ValueError, TypeError):
            normalized_track_ids.append(tid)
    update_event_logs(active_ids, dict(zip(normalized_track_ids, classes)))

def update_event_logs(current_track_ids, current_classes_dict):
    global prev_track_ids, unique_object_count, event_logs
    
    # Entities entered
    entered = current_track_ids - prev_track_ids
    for tid in entered:
        cls_id = current_classes_dict.get(tid, 0)
        try:
            cls_id = int(cls_id)
        except (ValueError, TypeError):
            cls_id = 0
        cls_name = COCO_CLASSES[cls_id] if 0 <= cls_id < len(COCO_CLASSES) else "object"
        timestamp = time.strftime("%H:%M:%S")
        event_logs.append({
            "time": timestamp,
            "event": f"Entered: {cls_name.upper()} (ID {tid})",
            "type": "entry",
            "id": tid,
            "class": cls_name
        })
        unique_object_count += 1
        
    # Entities exited
    exited = prev_track_ids - current_track_ids
    for tid in exited:
        timestamp = time.strftime("%H:%M:%S")
        event_logs.append({
            "time": timestamp,
            "event": f"Exited: Object ID {tid}",
            "type": "exit",
            "id": tid
        })
        
    prev_track_ids = current_track_ids
    if len(event_logs) > 40:
        event_logs = event_logs[-40:]

# --- Video Stream Capture Wrapper ---
class VideoStreamer:
    def __init__(self):
        self.cap = None
        self.is_running = True
        self.reset_source()

    def reset_source(self):
        if self.cap and self.cap.isOpened():
            self.cap.release()
        self.cap = None
        
        if current_source_type == "webcam":
            self.cap = cv2.VideoCapture(current_webcam_id, cv2.CAP_DSHOW if os.name == 'nt' else cv2.CAP_ANY)
        elif current_source_type == "file":
            if os.path.exists(current_file_path):
                self.cap = cv2.VideoCapture(current_file_path)
            else:
                print(f"[!] Video file not found: {current_file_path}. Falling back to mock.")
        elif current_source_type == "url":
            if current_url_stream:
                self.cap = cv2.VideoCapture(current_url_stream)

    def set_source(self, source_type, details=None):
        global current_source_type, current_webcam_id, current_file_path, current_url_stream
        current_source_type = source_type
        if source_type == "webcam":
            current_webcam_id = int(details) if details is not None else 0
        elif source_type == "file":
            current_file_path = str(details)
        elif source_type == "url":
            current_url_stream = str(details)
            
        self.reset_source()

    async def get_frames(self):
        global live_fps, HAS_YOLO, deepsort_tracker
        
        prev_time = time.time()
        
        while self.is_running:
            success = False
            frame = None
            
            if current_source_type != "mock" and self.cap:
                success, frame = self.cap.read()
                
                # Loop video files automatically
                if not success and current_source_type == "file":
                    self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    success, frame = self.cap.read()
                    
            if not success or frame is None:
                # Mock Mode Frame Generation
                frame = np.zeros((480, 640, 3), dtype=np.uint8)
                # Create sleek neon grid background
                for y in range(0, 480, 40):
                    cv2.line(frame, (0, y), (640, y), (20, 20, 25), 1)
                for x in range(0, 640, 40):
                    cv2.line(frame, (x, 0), (x, 480), (20, 20, 25), 1)
                
                # Write Mock Status Header
                cv2.putText(frame, "SIMULATED FEED (NO DEVICE CONNECTED)", (140, 30), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 153, 51), 1, cv2.LINE_AA)
                
                # Run Mock Tracking Movement
                mock_objects = mock_tracker.step(640, 480)
                track_ids, boxes, scores, classes = [], [], [], []
                for obj in mock_objects:
                    if active_classes and obj["class_id"] not in active_classes:
                        continue
                    # Conf score bounces slightly
                    score = 0.82 + 0.12 * np.sin(time.time() + obj["id"])
                    if score < conf_threshold:
                        continue
                    
                    x, y = obj["pos"]
                    w, h = obj["size"]
                    
                    track_ids.append(obj["id"])
                    boxes.append([x - w/2, y - h/2, x + w/2, y + h/2])
                    scores.append(score)
                    classes.append(obj["class_id"])
                    
                render_predictions(frame, track_ids, boxes, scores, classes)
            else:
                # Real Tracking Execution
                if HAS_YOLO and model is not None:
                    h_f, w_f = frame.shape[:2]
                    
                    # 1. DeepSORT tracker
                    if current_tracker_type == "deepsort" and HAS_DEEPSORT:
                        if deepsort_tracker is None:
                            deepsort_tracker = DeepSort(max_age=30, n_init=3, nms_max_overlap=1.0, max_cosine_distance=0.2)
                            
                        # Run YOLO prediction
                        predict_args = {"conf": conf_threshold, "iou": iou_threshold, "verbose": False}
                        if active_classes:
                            predict_args["classes"] = active_classes
                            
                        results = model.predict(frame, **predict_args)[0]
                        
                        detections = []
                        if results.boxes is not None:
                            for box in results.boxes:
                                x1, y1, x2, y2 = box.xyxy[0].tolist()
                                conf = float(box.conf[0])
                                cls = int(box.cls[0])
                                detections.append(([x1, y1, x2 - x1, y2 - y1], conf, str(cls)))
                                
                        # Update tracker
                        tracks = deepsort_tracker.update_tracks(detections, frame=frame)
                        
                        track_ids, boxes, scores, classes = [], [], [], []
                        for track in tracks:
                            if not track.is_confirmed():
                                continue
                            track_ids.append(int(track.track_id))
                            boxes.append(track.to_ltrb())
                            scores.append(track.get_det_conf() or 1.0)
                            classes.append(int(track.get_class()))
                            
                        render_predictions(frame, track_ids, boxes, scores, classes)
                        
                    # 2. Native YOLOv8 Trackers (ByteTrack or BotSORT)
                    else:
                        tracker_name = current_tracker_type if current_tracker_type in ["bytetrack", "botsort"] else "bytetrack"
                        track_args = {
                            "persist": True,
                            "tracker": f"{tracker_name}.yaml",
                            "conf": conf_threshold,
                            "iou": iou_threshold,
                            "verbose": False
                        }
                        if active_classes:
                            track_args["classes"] = active_classes
                            
                        try:
                            results = model.track(frame, **track_args)[0]
                            
                            track_ids, boxes, scores, classes = [], [], [], []
                            if results.boxes is not None and results.boxes.id is not None:
                                track_ids = results.boxes.id.int().tolist()
                                boxes = results.boxes.xyxy.tolist()
                                scores = results.boxes.conf.tolist()
                                classes = results.boxes.cls.int().tolist()
                                
                            render_predictions(frame, track_ids, boxes, scores, classes)
                        except Exception as tracking_error:
                            # Print and draw tracking error
                            cv2.putText(frame, f"Tracking Engine Error: {str(tracking_error)}", (20, 40), 
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (51, 51, 255), 1, cv2.LINE_AA)
                else:
                    # Fallback message
                    cv2.putText(frame, "YOLO SYSTEM NOT CONFIGURED", (20, 40), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (51, 51, 255), 1, cv2.LINE_AA)
            
            # FPS Calculation
            curr_time = time.time()
            time_diff = curr_time - prev_time
            live_fps = int(1.0 / time_diff) if time_diff > 0 else 30
            prev_time = curr_time
            
            # Encode frame to JPEG
            _, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
            frame_bytes = buffer.tobytes()
            
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            
            await asyncio.sleep(0.01)

streamer = VideoStreamer()

# --- FastAPI API Endpoints ---
@app.get("/video_feed")
async def video_feed():
    return StreamingResponse(streamer.get_frames(), media_type="multipart/x-mixed-replace; boundary=frame")

@app.post("/upload_video")
async def upload_video(file: UploadFile = File(...)):
    # Save the file to local workspace
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    # Update streamer source
    streamer.set_source("file", file_path)
    
    return {"status": "success", "file_path": file_path, "filename": file.filename}

@app.post("/settings")
async def update_settings(settings: dict):
    global current_tracker_type, current_model_name, conf_threshold, iou_threshold
    global active_classes, show_boxes, show_labels, show_scores, show_trails, model, deepsort_tracker
    
    if "tracker" in settings:
        t_type = settings["tracker"]
        if t_type in ["bytetrack", "botsort", "deepsort"]:
            if t_type == "deepsort" and not HAS_DEEPSORT:
                print("[!] DeepSORT requested but not installed. Falling back to ByteTrack.")
                t_type = "bytetrack"
            current_tracker_type = t_type
            if t_type == "deepsort":
                deepsort_tracker = None  # Force re-instantiation
                
    if "model" in settings:
        m_name = settings["model"]
        if m_name in ["yolov8n", "yolov8s", "yolov8m"] and m_name != current_model_name:
            current_model_name = m_name
            if HAS_YOLO:
                try:
                    model = YOLO(f"{m_name}.pt")
                except Exception as e:
                    print(f"Failed to load model {m_name}: {e}")
                    
    if "conf_threshold" in settings:
        conf_threshold = float(settings["conf_threshold"])
        
    if "iou_threshold" in settings:
        iou_threshold = float(settings["iou_threshold"])
        
    if "active_classes" in settings:
        active_classes = [int(cid) for cid in settings["active_classes"]]
        
    if "show_boxes" in settings:
        show_boxes = bool(settings["show_boxes"])
        
    if "show_labels" in settings:
        show_labels = bool(settings["show_labels"])
        
    if "show_scores" in settings:
        show_scores = bool(settings["show_scores"])
        
    if "show_trails" in settings:
        show_trails = bool(settings["show_trails"])
        
    if "source_type" in settings:
        src_type = settings["source_type"]
        details = settings.get("source_details", None)
        streamer.set_source(src_type, details)
        
    return {
        "status": "success",
        "settings": {
            "model": current_model_name,
            "tracker": current_tracker_type,
            "conf_threshold": conf_threshold,
            "iou_threshold": iou_threshold,
            "active_classes": active_classes,
            "show_boxes": show_boxes,
            "show_labels": show_labels,
            "show_scores": show_scores,
            "show_trails": show_trails,
            "source_type": current_source_type
        }
    }

@app.get("/settings")
async def get_settings():
    return {
        "model": current_model_name,
        "tracker": current_tracker_type,
        "conf_threshold": conf_threshold,
        "iou_threshold": iou_threshold,
        "active_classes": active_classes,
        "show_boxes": show_boxes,
        "show_labels": show_labels,
        "show_scores": show_scores,
        "show_trails": show_trails,
        "source_type": current_source_type,
        "available_classes": [{"id": idx, "name": name} for idx, name in enumerate(COCO_CLASSES)]
    }

# --- WebSocket server for real-time telemetry stats ---
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            # Build current telemetry packet
            stats = {
                "fps": live_fps,
                "count": active_object_count,
                "total_unique": unique_object_count,
                "model": current_model_name,
                "tracker": current_tracker_type,
                "classes": class_counts,
                "logs": event_logs[-15:] if event_logs else []  # Send last 15 entries
            }
            await websocket.send_text(json.dumps(stats))
            await asyncio.sleep(0.5)
    except Exception as e:
        print(f"[!] Telemetry WebSocket disconnected: {e}")

# --- WebSocket for receiving client browser camera frames and streaming back tracked output ---
@app.websocket("/ws/browser_stream")
async def browser_stream_endpoint(websocket: WebSocket):
    global live_fps, deepsort_tracker
    await websocket.accept()
    prev_time = time.time()
    
    try:
        while True:
            # Receive binary frame (JPEG) from browser webcam
            data = await websocket.receive_bytes()
            if not data:
                continue
                
            nparr = np.frombuffer(data, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if frame is None:
                continue
                
            # Process using the active tracker/YOLO configuration
            if HAS_YOLO and model is not None:
                # 1. DeepSORT tracker
                if current_tracker_type == "deepsort" and HAS_DEEPSORT:
                    if deepsort_tracker is None:
                        deepsort_tracker = DeepSort(max_age=30, n_init=3, nms_max_overlap=1.0, max_cosine_distance=0.2)
                        
                    predict_args = {"conf": conf_threshold, "iou": iou_threshold, "verbose": False}
                    if active_classes:
                        predict_args["classes"] = active_classes
                        
                    results = model.predict(frame, **predict_args)[0]
                    detections = []
                    if results.boxes is not None:
                        for box in results.boxes:
                            x1, y1, x2, y2 = box.xyxy[0].tolist()
                            conf = float(box.conf[0])
                            cls = int(box.cls[0])
                            detections.append(([x1, y1, x2 - x1, y2 - y1], conf, str(cls)))
                            
                    tracks = deepsort_tracker.update_tracks(detections, frame=frame)
                    
                    track_ids, boxes, scores, classes = [], [], [], []
                    for track in tracks:
                        if not track.is_confirmed():
                            continue
                        track_ids.append(int(track.track_id))
                        boxes.append(track.to_ltrb())
                        scores.append(track.get_det_conf() or 1.0)
                        classes.append(int(track.get_class()))
                        
                    render_predictions(frame, track_ids, boxes, scores, classes)
                    
                # 2. Native trackers (ByteTrack / BotSORT)
                else:
                    tracker_name = current_tracker_type if current_tracker_type in ["bytetrack", "botsort"] else "bytetrack"
                    track_args = {
                        "persist": True,
                        "tracker": f"{tracker_name}.yaml",
                        "conf": conf_threshold,
                        "iou": iou_threshold,
                        "verbose": False
                    }
                    if active_classes:
                        track_args["classes"] = active_classes
                        
                    try:
                        results = model.track(frame, **track_args)[0]
                        
                        track_ids, boxes, scores, classes = [], [], [], []
                        if results.boxes is not None and results.boxes.id is not None:
                            track_ids = results.boxes.id.int().tolist()
                            boxes = results.boxes.xyxy.tolist()
                            scores = results.boxes.conf.tolist()
                            classes = results.boxes.cls.int().tolist()
                            
                        render_predictions(frame, track_ids, boxes, scores, classes)
                    except Exception as e:
                        cv2.putText(frame, f"Tracking Error: {str(e)}", (20, 40), 
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (51, 51, 255), 1, cv2.LINE_AA)
            else:
                # Mock Mode processing for Browser Webcam if YOLO is not initialized
                mock_objects = mock_tracker.step(frame.shape[1], frame.shape[0])
                track_ids, boxes, scores, classes = [], [], [], []
                for obj in mock_objects:
                    if active_classes and obj["class_id"] not in active_classes:
                        continue
                    score = 0.85 + 0.1 * np.sin(time.time() + obj["id"])
                    if score < conf_threshold:
                        continue
                    x, y = obj["pos"]
                    w, h = obj["size"]
                    track_ids.append(obj["id"])
                    boxes.append([x - w/2, y - h/2, x + w/2, y + h/2])
                    scores.append(score)
                    classes.append(obj["class_id"])
                    
                render_predictions(frame, track_ids, boxes, scores, classes)
                
            # Recalculate FPS for streaming
            curr_time = time.time()
            time_diff = curr_time - prev_time
            live_fps = int(1.0 / time_diff) if time_diff > 0 else 30
            prev_time = curr_time
            
            # Send back annotated frame
            _, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
            await websocket.send_bytes(buffer.tobytes())
            
    except Exception as e:
        print(f"[!] Browser stream WebSocket disconnected: {e}")

# Serve static React frontend files (mount at bottom to prevent route hijacking)
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

if os.path.exists(DIST_DIR):
    app.mount("/assets", StaticFiles(directory=os.path.join(DIST_DIR, "assets")), name="static_assets")

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "yolov8-live-tracking-backend"}

@app.get("/{catchall:path}")
async def serve_react(catchall: str):
    file_path = os.path.join(DIST_DIR, catchall)
    if os.path.isfile(file_path):
        return FileResponse(file_path)
    index_path = os.path.join(DIST_DIR, "index.html")
    if os.path.isfile(index_path):
        return FileResponse(index_path)
    return {"status": "active", "message": "YOLOv8 Backend Running. Connect from frontend dashboard."}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
