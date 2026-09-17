# SecureVision — Enterprise AI Surveillance & Access Control

Real-time CCTV monitoring with YOLO person detection, face recognition,
access control, alerting, and a dark-theme dashboard — all running locally
on a Windows laptop.

---

## Architecture at a Glance

```
CCTV / Webcam
    │
    ▼
YOLOv8 Person Detection  (ultralytics, your dataset)
    │
    ▼
Multi-Person IoU Tracker  (dwell time, tailgating)
    │
    ▼
YuNet Face Detector  →  SFace 128-d Embedding
    │                         │
    ▼                         ▼
Liveness / Anti-Spoof   Cosine Match vs DB
    │                         │
    ▼                         ▼
Classification:  EMPLOYEE (green) | VISITOR (yellow) | UNAUTHORIZED (red)
    │
    ▼
Access Control  →  Restricted Zone check  →  Tailgating / Loitering analytics
    │
    ▼
SQLite DB  ←→  FastAPI REST + WebSocket  ←→  Browser Dashboard
```

---

## Requirements

- Windows 10 / 11
- Python 3.10 or 3.11 (recommended)
- ~3 GB disk space (models + venv)
- Webcam optional (dataset demo mode works without one)

---

## Installation

### 1 — Clone / open the project folder

```powershell
cd "Access control surveilliance"
```

### 2 — Create and activate a virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

> If PowerShell blocks scripts: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

### 3 — Install all dependencies

```powershell
pip install -r requirements.txt
```

> **Critical:** `requirements.txt` uses `opencv-contrib-python`. Do **not** mix it
> with plain `opencv-python` — they conflict and the face API will be missing.

### 4 — Download face ONNX models

```powershell
python download_models.py
```

This fetches `face_detection_yunet.onnx` (~350 KB) and
`face_recognition_sface.onnx` (~38 KB) from the official OpenCV model zoo
and saves them to `models/`.

If your models folder already has both files (>200 KB and >30 KB), this step
is a no-op.

---

## Starting the Server

### One-command launch (recommended)

```powershell
python run.py
```

`run.py` will:
1. Check ONNX models (offer to download if missing)
2. Create `static/snapshots` and `static/enrolled` directories
3. Create all database tables
4. Seed admin user, 4 cameras, 3 sample identities, and initial logs
5. Start Uvicorn on **http://localhost:8000**

### Development mode (auto-reload on code changes)

```powershell
python run.py --dev
```

### Custom port or host

```powershell
python run.py --port 9000 --host 127.0.0.1
```

### Manual Uvicorn start (without seeding)

```powershell
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## Admin Login

Open **http://localhost:8000** in your browser.

| Field    | Value      |
|----------|------------|
| Username | `admin`    |
| Password | `admin123` |

Click the **A** avatar button (top right) to open the login modal.

---

## Database Setup & Seeding

Run once (also called automatically by `run.py`):

```powershell
python backend/seed_data.py
```

Seeds:
- Admin user (`admin` / `admin123`)
- 4 cameras (CAM 01–04)
- 3 sample identities with synthetic face embeddings (replace with real photos via enrollment)
- Initial access logs and security alerts

---

## Face Enrollment (Adding Real Identities)

### Via the Web UI (recommended)

1. Click the **A** avatar → Login
2. Click **Enroll Identity** (or the 👤➕ button in the camera toolbar)
3. Fill in: Identity Code, Name, Type (Employee/Visitor), Department, Clearance Level
4. Upload a clear front-facing portrait photo (JPG/PNG, good lighting)
5. Click **Extract & Enroll** — the backend runs YuNet + SFace to extract the
   128-d biometric embedding and stores it encrypted in SQLite

### Via cURL (for scripted bulk enrollment)

```powershell
curl -X POST http://localhost:8000/api/enroll `
  -F "identity_code=EMP-1099" `
  -F "name=Jane Smith" `
  -F "identity_type=EMPLOYEE" `
  -F "department=Engineering" `
  -F "designation=Senior Developer" `
  -F "access_level=Level 2" `
  -F "allowed_cameras=cam_01,cam_02,cam_03,cam_04" `
  -F "photo=@C:\path\to\jane.jpg"
```

---

## YOLO Training (Fine-tune on Your Dataset)

The system ships with `yolov8n.pt` (pre-trained on COCO person class) and
works out of the box. Fine-tune on your indoor CCTV dataset for better
accuracy in your specific environment:

```powershell
# Quick test (10 epochs, CPU)
python train_yolo.py --epochs 10 --batch 8 --device cpu

# Better quality (50 epochs, GPU if available)
python train_yolo.py --epochs 50 --batch 16 --device 0

# OBB (oriented bounding boxes) — matches your Roboflow dataset format
python train_yolo.py --epochs 30 --model yolov8n-obb.pt --batch 8
```

After training, the best weights are saved to:
`runs/train/weights/best.pt`

The YOLO loader in `backend/ml_engine/yolo_detector.py` automatically
picks up `runs/train/weights/best.pt` if it exists.

---

## System Self-Test

Run this before the server to verify everything is wired up correctly:

```powershell
python test_system.py
```

Runs 10 check sections: Python env → packages → OpenCV contrib → project
structure → dataset → model integrity → config/DB → ML engine → auth →
seed data.

Test face recognition on a specific image:

```powershell
python test_system.py --image "path\to\face_photo.jpg"
```

---

## API Reference

All endpoints are documented at **http://localhost:8000/docs** (Swagger UI).

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/auth/login` | Admin login → JWT token |
| `GET`  | `/api/auth/me` | Current user profile |
| `GET`  | `/api/dashboard/stats` | Live security metrics |
| `GET`  | `/api/cameras` | List all cameras + online status |
| `GET`  | `/api/video_feed/{camera_id}` | MJPEG stream (multipart) |
| `POST` | `/api/cameras/{id}/toggle` | Online ↔ Offline toggle |
| `POST` | `/api/cameras/{id}/source` | Switch webcam ↔ dataset feed |
| `POST` | `/api/recognize` | Upload image → face recognition result |
| `POST` | `/api/enroll` | Enroll new identity with face photo |
| `GET`  | `/api/identities` | List enrolled identities |
| `GET`  | `/api/records` | Access logs (filter + search) |
| `GET`  | `/api/records/export` | Download CSV or JSON audit report |
| `GET`  | `/api/access_logs` | Recent access timeline |
| `GET`  | `/api/alerts` | Security alerts list |
| `PATCH`| `/api/alerts/{id}/status` | Update alert: NEW → INVESTIGATING → RESOLVED |
| `WS`   | `/ws` | Real-time WebSocket event stream |

---

## Complete Workflow Test (Manual)

After `python run.py`:

1. **Open** http://localhost:8000 — dashboard loads with live camera feeds
2. **Login** — click A → `admin` / `admin123` → verify "Admin Control Portal" shows
3. **Live stream** — CAM 01 cycles through dataset images with YOLO person detection
   boxes and face classification overlays visible
4. **Enroll a face** — click 👤➕ → upload a clear photo → confirm green success message
5. **Face recognition** — go to **Recognition** tab → upload any face image →
   click "Run Face Recognition" → verify identity panel shows real result
6. **Access logs** — go to **Records** tab → real DB entries appear
7. **Alerts** — go to **Alerts** tab → click "REVIEW EVENT" → change status to
   INVESTIGATING → click "Update Status" → confirm badge updates in real time
8. **Camera controls** — click the 🔄 button to switch CAM 01 to webcam;
   click ⏻ to take it offline (shows "SIGNAL LOST" overlay)
9. **Export** — Records tab → click CSV or JSON button → file downloads
10. **Real-time** — open browser console → Network tab → `/ws` WebSocket
    connection should show `connection_established` message

---

## Project Structure

```
Access control surveilliance/
├── index.html                          # Frontend (unchanged)
├── style.css                           # Styles (unchanged)
├── script.js                           # Frontend JS (unchanged)
├── run.py                              # One-command launcher
├── train_yolo.py                       # YOLO fine-tuning script
├── download_models.py                  # ONNX model downloader
├── test_system.py                      # End-to-end offline validator
├── requirements.txt                    # Python dependencies
├── .env                                # Local config (not committed)
├── .env.example                        # Config template
├── surveillance.db                     # SQLite database (auto-created)
├── yolov8n.pt                          # YOLOv8 base weights
├── models/
│   ├── face_detection_yunet.onnx       # YuNet face detector
│   └── face_recognition_sface.onnx    # SFace recognizer
├── static/
│   ├── snapshots/                      # Auto-saved alert/recognition frames
│   └── enrolled/                       # Enrollment photos
├── backend/
│   ├── main.py                         # FastAPI app + all endpoints
│   ├── config.py                       # Settings (pydantic-settings)
│   ├── database.py                     # SQLAlchemy engine + session
│   ├── models.py                       # ORM: User, Identity, Camera, AccessLog, Alert
│   ├── schemas.py                      # Pydantic request/response models
│   ├── auth.py                         # PBKDF2 password hash, JWT
│   ├── seed_data.py                    # DB bootstrap script
│   ├── camera_manager.py               # Multi-threaded MJPEG stream workers
│   └── ml_engine/
│       ├── face_engine.py              # YuNet + SFace + cosine matching
│       ├── yolo_detector.py            # YOLOv8 person detection (OBB + standard)
│       ├── liveness.py                 # Anti-spoofing (Laplacian + saturation)
│       ├── tracker.py                  # IoU-based multi-person tracker
│       └── analytics.py               # Tailgating, loitering, access rules
└── CCTV Indoor Person Detection.v4i.yolov8-obb/
    ├── data.yaml
    ├── train/images/  (labels/)
    ├── valid/images/  (labels/)
    └── test/images/   (labels/)
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `cv2.FaceDetectorYN not found` | Uninstall `opencv-python`, install `opencv-contrib-python==4.10.0.84` |
| `No module named 'backend'` | Run all commands from the project root folder, not inside `backend/` |
| Port 8000 already in use | `python run.py --port 8001` |
| Camera stream blank/frozen | Click ⏻ to toggle online; refresh the page |
| Webcam not opening | Switch back to dataset mode (click 🔄); check Device Manager |
| `yolov8n.pt` not found | Ultralytics downloads it automatically on first inference (~6 MB) |
| Models download fails | Download manually from [OpenCV model zoo](https://github.com/opencv/opencv_zoo) and place in `models/` |
| `surveillance.db` locked | Stop all running `python run.py` / `uvicorn` processes |
| Face not recognized after enrollment | Ensure good lighting in enrollment photo; confidence threshold is 0.363 (adjustable in `.env`) |

---

## Security Notes

- Change `SECRET_KEY` in `.env` before deploying anywhere
- The admin password `admin123` is for local development only
- Face embeddings are stored as JSON in SQLite — suitable for local/LAN use
- For production: use PostgreSQL, HTTPS, and a proper secret manager

---

## License

MIT — see LICENSE file.
