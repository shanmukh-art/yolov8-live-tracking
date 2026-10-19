# YOLOv8 Live Object Tracking & Telemetry Dashboard 🚀

A high-performance, real-time Computer Vision system combining **YOLOv8** deep learning detection with **ByteTrack**, **BotSORT**, and **DeepSORT** association filters, paired with a React TypeScript glassmorphism telemetry dashboard.

---

## ✨ Features

- **Real-Time Object Detection**: Powered by Ultralytics YOLOv8 (Nano, Small, Medium models supported).
- **Multiple Tracking Algorithms**:
  - **ByteTrack**: High-speed, lightweight association (YOLOv8 Native).
  - **BotSORT**: Camera motion compensation tracking (YOLOv8 Native).
  - **DeepSORT**: Deep appearance feature embedding association engine.
- **Multiple Input Sources**:
  - Simulated Mock Feed (automated object bounce physics for offline testing).
  - Host System Webcam (`cv2.VideoCapture`).
  - Web Browser Camera Streaming over binary WebSockets.
  - Video File Uploads (`mp4`, `avi`, `mov`).
  - RTSP / IP Camera Network Streams.
- **Interactive React Telemetry Dashboard**:
  - Glass-morphism futuristic UI with responsive controls.
  - Real-time FPS metrics, active object counters, and unique ID tracking.
  - SVG Historical Density Line Chart & Class Distribution Progress Bars.
  - Event Activity Terminal console logging target entrances & exits.
- **Live Visual Overlays**:
  - Glow & solid rounded bounding boxes.
  - Object motion trails (historical center-point tracking paths).
  - Dynamic score & class label badges.
- **On-the-Fly Configuration**:
  - Adjust Confidence Limits & IoU thresholds via sliders.
  - Category class filtering (select individual COCO classes or popular presets).
- **PDF Report Generation**: Automated project documentation generator using `reportlab`.

---

## 🛠️ System Architecture

```
yolov8-live-tracking/
│
├── backend/
│   └── server.py              # FastAPI server (MJPEG stream, WebSockets, Settings API)
│
├── frontend/                  # React + TypeScript + Vite Dashboard
│   ├── src/
│   │   ├── App.tsx            # Telemetry UI & WebCam WebSocket streamer
│   │   ├── App.css            # Glassmorphism styling tokens & themes
│   │   └── index.css          # Base CSS reset & typography
│   ├── package.json           # Frontend dependencies (lucide-react, axios, vite)
│   └── vite.config.ts         # Vite server proxy configuration
│
├── uploads/                   # Uploaded video files storage
├── generate_report.py         # Automated PDF project report generator
├── kill_port_8000.py          # Port 8000 process cleanup script
├── requirements.txt           # Python dependency requirements
├── yolov8n.pt                 # YOLOv8 Nano pre-trained weights
├── yolov8s.pt                 # YOLOv8 Small pre-trained weights
├── yolov8m.pt                 # YOLOv8 Medium pre-trained weights
└── README.md                  # Project documentation
```

---

## 🚀 Getting Started

### 1. Prerequisites
- **Python**: 3.8 or higher
- **Node.js**: 16+ & `npm`

### 2. Install Python Dependencies
```bash
pip install -r requirements.txt
```

### 3. Build Frontend (Production Mode)
```bash
cd frontend
npm install
npm run build
cd ..
```

### 4. Launch the System

#### Option A: Production Server (FastAPI + Embedded React Frontend)
Run the backend server, which will automatically host the built React dashboard:
```bash
python backend/server.py
```
Open **[http://localhost:8000](http://localhost:8000)** in your browser.

#### Option B: Development Mode (Hot-Reloading)
Start the FastAPI backend:
```bash
python backend/server.py
```
In a second terminal, start the Vite dev server:
```bash
cd frontend
npm run dev
```
Open **[http://localhost:5173](http://localhost:5173)** in your browser.

---

## 🌐 Deploy to Vercel (Frontend Live Dashboard)

The frontend is fully configured for deployment on **Vercel** with automatic SPA routing and dynamic backend URL connectivity.

### Method 1: Deploy with Vercel CLI
```bash
cd frontend
npx vercel
```
Follow the interactive prompts to link your Vercel account and deploy. For production:
```bash
npx vercel --prod
```

### Method 2: Deploy with GitHub & Vercel Dashboard
1. Push your repository to **GitHub**.
2. Go to **[vercel.com/new](https://vercel.com/new)** and import your repository.
3. Vercel will automatically detect `vercel.json` and build settings.
4. *(Optional)* Add the environment variable `VITE_BACKEND_URL` pointing to your deployed backend (e.g., `https://yolov8-tracking-backend.onrender.com`).
5. Click **Deploy**!

> **💡 Connecting Backend to Live Vercel App**:
> Because YOLOv8, OpenCV, and WebSockets require a persistent runtime (beyond serverless timeouts), host your backend on **Render**, **Railway**, **Fly.io**, or **Hugging Face Spaces** (using the included `Dockerfile`). Alternatively, run it locally with an **ngrok** tunnel (`ngrok http 8000`). Then paste your backend URL directly into the **"Connect Backend"** button in the dashboard header!

---

## ⚡ Utility Scripts

### Process Port Cleanup
If port 8000 is occupied by a stuck process:
```bash
python kill_port_8000.py
```

### PDF Report Generator
Generate a PDF report summarizing system performance, architecture, and benchmark metrics:
```bash
python generate_report.py
```

---

## 📊 Performance Benchmarks

| Model Name | Parameters | Typical CPU FPS | Typical GPU FPS | Memory Footprint |
| :--- | :--- | :--- | :--- | :--- |
| **YOLOv8 Nano** | 3.2M | 15 - 20 FPS | 60 - 80 FPS | ~12 MB |
| **YOLOv8 Small** | 11.2M | 8 - 12 FPS | 45 - 60 FPS | ~30 MB |
| **YOLOv8 Medium**| 25.9M | 3 - 5 FPS | 25 - 35 FPS | ~78 MB |

---

## 👥 Author & Credits

- **Developer**: Gollavilli Shanmukh Vardhan Sai
- **Contact**: [shannuvardhan802@gmail.com](mailto:shannuvardhan802@gmail.com)

---
*Built for High-Performance Intelligent Computer Vision & Surveillance Operations.*
