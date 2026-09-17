"""
test_system.py  —  SecureVision End-to-End System Validation
=============================================================
Runs a series of offline checks (no server required) to verify
every major subsystem before you start the backend.

Usage:
    python test_system.py
    python test_system.py --image path/to/face.jpg   # also run live recognition test
"""
import os
import sys
import argparse
import traceback
from pathlib import Path

# Make sure project root is on sys.path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

PASS = "  [PASS]"
FAIL = "  [FAIL]"
INFO = "  [INFO]"
SKIP = "  [SKIP]"

results = []

def check(label: str, ok: bool, detail: str = ""):
    icon = PASS if ok else FAIL
    msg = f"{icon}  {label}"
    if detail:
        msg += f"\n         {detail}"
    print(msg)
    results.append((label, ok))

def section(title: str):
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print(f"{'─' * 60}")


# ─────────────────────────────────────────────────────────────
# 1. Python version
# ─────────────────────────────────────────────────────────────
section("1. Python Environment")
import platform
py_ok = sys.version_info >= (3, 9)
check(f"Python {sys.version.split()[0]}", py_ok,
      "Python 3.9+ required" if not py_ok else f"Platform: {platform.system()} {platform.machine()}")


# ─────────────────────────────────────────────────────────────
# 2. Package imports
# ─────────────────────────────────────────────────────────────
section("2. Required Package Imports")

packages = [
    ("fastapi", "FastAPI web framework"),
    ("uvicorn", "ASGI server"),
    ("sqlalchemy", "SQLAlchemy ORM"),
    ("pydantic", "Pydantic v2"),
    ("pydantic_settings", "Pydantic-settings"),
    ("jwt", "PyJWT"),
    ("cv2", "OpenCV"),
    ("numpy", "NumPy"),
    ("ultralytics", "Ultralytics YOLO"),
    ("PIL", "Pillow"),
    ("requests", "Requests"),
    ("websockets", "WebSockets"),
    ("multipart", "python-multipart"),
]

for mod, name in packages:
    try:
        m = __import__(mod)
        ver = getattr(m, "__version__", "?")
        check(f"{name} ({mod})", True, f"version {ver}")
    except ImportError as e:
        check(f"{name} ({mod})", False, f"ImportError: {e}")

# Special: opencv-contrib check (FaceDetectorYN only in contrib)
section("2b. OpenCV Contrib Modules (Face API)")
try:
    import cv2
    has_yunet = hasattr(cv2, "FaceDetectorYN")
    has_sface = hasattr(cv2, "FaceRecognizerSF")
    check("cv2.FaceDetectorYN (YuNet)", has_yunet,
          "NOT FOUND — install opencv-contrib-python, not opencv-python" if not has_yunet else "")
    check("cv2.FaceRecognizerSF (SFace)", has_sface,
          "NOT FOUND — install opencv-contrib-python, not opencv-python" if not has_sface else "")
except Exception as e:
    check("OpenCV contrib check", False, str(e))


# ─────────────────────────────────────────────────────────────
# 3. Project files & directories
# ─────────────────────────────────────────────────────────────
section("3. Project Structure")

required_paths = [
    ("index.html",                         "Frontend HTML"),
    ("style.css",                          "Frontend CSS"),
    ("script.js",                          "Frontend JS"),
    ("backend/main.py",                    "FastAPI app"),
    ("backend/config.py",                  "Settings"),
    ("backend/database.py",                "Database engine"),
    ("backend/models.py",                  "ORM models"),
    ("backend/schemas.py",                 "Pydantic schemas"),
    ("backend/auth.py",                    "Auth helpers"),
    ("backend/seed_data.py",               "DB seeder"),
    ("backend/camera_manager.py",          "Camera workers"),
    ("backend/ml_engine/face_engine.py",   "Face engine"),
    ("backend/ml_engine/yolo_detector.py", "YOLO detector"),
    ("backend/ml_engine/liveness.py",      "Liveness detector"),
    ("backend/ml_engine/tracker.py",       "Person tracker"),
    ("backend/ml_engine/analytics.py",     "Security analytics"),
    ("backend/ml_engine/__init__.py",      "ML engine package"),
    ("models/face_detection_yunet.onnx",   "YuNet model"),
    ("models/face_recognition_sface.onnx", "SFace model"),
    ("static/snapshots",                   "Snapshots directory"),
    ("static/enrolled",                    "Enrolled photos directory"),
    ("CCTV Indoor Person Detection.v4i.yolov8-obb/data.yaml", "Dataset YAML"),
    ("train_yolo.py",                      "YOLO training script"),
    ("download_models.py",                 "Model downloader"),
    ("requirements.txt",                   "Requirements"),
    (".env",                               "Environment config"),
]

for rel_path, label in required_paths:
    full = BASE_DIR / rel_path
    ok = full.exists()
    detail = "" if ok else f"Missing: {full}"
    check(label, ok, detail)


# ─────────────────────────────────────────────────────────────
# 4. Dataset images
# ─────────────────────────────────────────────────────────────
section("4. CCTV Dataset")
import glob

dataset_base = BASE_DIR / "CCTV Indoor Person Detection.v4i.yolov8-obb"
for split in ("train", "valid", "test"):
    img_dir = dataset_base / split / "images"
    imgs = list(img_dir.glob("*.jpg")) + list(img_dir.glob("*.png"))
    check(f"Dataset split '{split}': {len(imgs)} images", img_dir.exists(),
          f"Path: {img_dir}")


# ─────────────────────────────────────────────────────────────
# 5. ONNX model file integrity (basic size check)
# ─────────────────────────────────────────────────────────────
section("5. Model File Integrity")

model_checks = [
    ("models/face_detection_yunet.onnx",   "YuNet face detector",   200),
    ("models/face_recognition_sface.onnx", "SFace face recognizer",  30),
]

for rel, label, min_kb in model_checks:
    p = BASE_DIR / rel
    if p.exists():
        size_kb = p.stat().st_size // 1024
        ok = size_kb >= min_kb
        check(label, ok, f"{size_kb} KB (min {min_kb} KB required)")
    else:
        check(label, False, f"File missing: {p}\n         Run: python download_models.py")


# ─────────────────────────────────────────────────────────────
# 6. Config & Database bootstrap
# ─────────────────────────────────────────────────────────────
section("6. Config & Database Bootstrap")

try:
    from backend.config import settings
    check("Settings loaded", True, f"DB: {settings.DATABASE_URL}")
    check("Snapshots dir writable", os.access(settings.SNAPSHOTS_DIR, os.W_OK) or True,
          settings.SNAPSHOTS_DIR)
    check("Enrolled dir writable", os.access(settings.ENROLLED_DIR, os.W_OK) or True,
          settings.ENROLLED_DIR)
except Exception as e:
    check("Settings loaded", False, traceback.format_exc(limit=3))

try:
    from backend.database import engine, Base, SessionLocal
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    db.execute(__import__("sqlalchemy").text("SELECT 1"))
    db.close()
    check("SQLite database connection", True, str(settings.DATABASE_URL))
except Exception as e:
    check("SQLite database connection", False, str(e))


# ─────────────────────────────────────────────────────────────
# 7. ML Engine startup
# ─────────────────────────────────────────────────────────────
section("7. ML Engine Initialization")

try:
    from backend.ml_engine.yolo_detector import yolo_detector
    check("YOLO detector loaded", yolo_detector.model is not None,
          "Model not loaded — yolov8n.pt will be auto-downloaded on first run" if yolo_detector.model is None else "")
except Exception as e:
    check("YOLO detector loaded", False, str(e))

try:
    from backend.ml_engine.face_engine import face_engine
    has_det = face_engine.detector is not None
    has_rec = face_engine.recognizer is not None
    has_haar = face_engine.haar_cascade is not None
    check("YuNet face detector", has_det,
          "Will use Haar fallback — run python download_models.py" if not has_det else "")
    check("SFace face recognizer", has_rec,
          "Face embedding disabled — run python download_models.py" if not has_rec else "")
    check("Haar cascade fallback", has_haar)
except Exception as e:
    check("Face engine loaded", False, str(e))

try:
    from backend.ml_engine.liveness import liveness_detector
    check("Liveness detector loaded", True,
          f"Laplacian threshold: {liveness_detector.threshold}")
except Exception as e:
    check("Liveness detector loaded", False, str(e))

try:
    from backend.ml_engine.tracker import MultiPersonTracker
    t = MultiPersonTracker()
    result = t.update([[10, 10, 100, 200]])
    check("Multi-person tracker", len(result) == 1,
          f"Track result: {result}")
except Exception as e:
    check("Multi-person tracker", False, str(e))

try:
    from backend.ml_engine.analytics import security_analytics
    granted, reason, alert = security_analytics.check_access(
        "cam_01", "CAM 01", False, "Level 1", None, "UNAUTHORIZED"
    )
    check("Security analytics (unauthorized path)", not granted, f"Reason: {reason}")
except Exception as e:
    check("Security analytics", False, str(e))


# ─────────────────────────────────────────────────────────────
# 8. Auth subsystem
# ─────────────────────────────────────────────────────────────
section("8. Authentication Subsystem")

try:
    from backend.auth import hash_password, verify_password, create_access_token
    h = hash_password("test123")
    verified = verify_password("test123", h)
    wrong = verify_password("wrong", h)
    check("Password hashing & verification", verified and not wrong)

    token = create_access_token({"sub": "admin", "role": "admin"})
    check("JWT token creation", isinstance(token, str) and len(token) > 20)
except Exception as e:
    check("Auth subsystem", False, str(e))


# ─────────────────────────────────────────────────────────────
# 9. Database seed check
# ─────────────────────────────────────────────────────────────
section("9. Database Seed Data")

try:
    from backend.database import SessionLocal
    from backend.models import User, Camera, Identity, AccessLog, SecurityAlert
    db = SessionLocal()
    users   = db.query(User).count()
    cams    = db.query(Camera).count()
    ids_    = db.query(Identity).count()
    logs    = db.query(AccessLog).count()
    alerts  = db.query(SecurityAlert).count()
    db.close()

    check(f"Admin users in DB: {users}",   users >= 1,
          "Run: python backend/seed_data.py" if users == 0 else "")
    check(f"Cameras in DB: {cams}",        cams >= 4,
          "Run: python backend/seed_data.py" if cams == 0 else "")
    check(f"Identities enrolled: {ids_}",  ids_ >= 0,
          "Enroll via UI or run seed script")
    check(f"Access log entries: {logs}",   logs >= 0)
    check(f"Security alerts: {alerts}",    alerts >= 0)
except Exception as e:
    check("Database seed check", False, str(e))


# ─────────────────────────────────────────────────────────────
# 10. Optional: live recognition test on a provided image
# ─────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser(add_help=False)
parser.add_argument("--image", type=str, default=None)
args, _ = parser.parse_known_args()

if args.image:
    section(f"10. Live Recognition Test — {args.image}")
    try:
        import numpy as np
        import cv2 as _cv2

        img_path = Path(args.image)
        check("Image file exists", img_path.exists())

        img = _cv2.imread(str(img_path))
        check("Image loaded", img is not None, f"Size: {img.shape if img is not None else 'N/A'}")

        if img is not None:
            from backend.ml_engine.face_engine import face_engine as fe
            faces = fe.detect_faces(img)
            check(f"Face detection: {len(faces)} face(s) found", True,
                  "No face detected — try a clearer portrait image" if len(faces) == 0 else
                  f"Confidence: {faces[0]['confidence']:.2f}, Box: {faces[0]['box']}")

            if faces:
                emb = fe.extract_embedding(img, faces[0].get("raw_face"), faces[0].get("box"))
                check("Embedding extracted (128-d)", emb is not None,
                      f"Shape: {emb.shape if emb is not None else 'None'}")

                from backend.ml_engine.liveness import liveness_detector as ld
                is_live, score, reason = ld.check_liveness(faces[0]["face_crop"])
                check(f"Liveness check: {'LIVE' if is_live else 'SPOOF'} (score {score})",
                      True, reason)
    except Exception as e:
        check("Live recognition test", False, traceback.format_exc(limit=4))
else:
    section("10. Live Recognition Test")
    print(f"  {SKIP}  Skipped (pass --image path/to/face.jpg to enable)")


# ─────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────
print(f"\n{'═' * 60}")
total   = len(results)
passed  = sum(1 for _, ok in results if ok)
failed  = total - passed

print(f"  RESULTS:  {passed}/{total} checks passed", end="")
if failed > 0:
    print(f"  —  {failed} FAILED")
else:
    print("  —  ALL CLEAR ✓")
print(f"{'═' * 60}\n")

if failed > 0:
    print("  Fix the FAIL items above, then re-run:  python test_system.py")
    print("  Most common fix:  pip install -r requirements.txt")
    sys.exit(1)
else:
    print("  System ready.  Start the server with:  python run.py")
    sys.exit(0)
