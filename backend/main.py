import os
import sys
import io
import csv
import json
import time
import datetime
from contextlib import asynccontextmanager
from typing import Optional, List
import asyncio

# Ensure project root in sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import numpy as np
import cv2
from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File, Form, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse, Response, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import desc

from backend.config import settings
from backend.database import get_db, Base, engine
from backend.models import User, Identity, Camera, AccessLog, SecurityAlert
from backend.schemas import (
    Token, LoginRequest, IdentityCreate, IdentityOut,
    CameraOut, AccessLogOut, AlertOut, AlertStatusUpdate,
    DashboardStats, RecognitionResponse
)
from backend.auth import verify_password, create_access_token, get_current_user, require_admin
from backend.ml_engine.face_engine import face_engine
from backend.ml_engine.liveness import liveness_detector
from backend.ml_engine.analytics import security_analytics
from backend.camera_manager import camera_manager, set_ws_broadcast_callback

# Create database tables if not exist
Base.metadata.create_all(bind=engine)

# Active WebSocket connections
active_connections: List[WebSocket] = []

async def ws_broadcast(message: dict):
    """Send JSON message to all connected clients."""
    disconnected = []
    for conn in active_connections:
        try:
            await conn.send_json(message)
        except Exception:
            disconnected.append(conn)
    for conn in disconnected:
        if conn in active_connections:
            active_connections.remove(conn)

def sync_ws_broadcast(message: dict):
    """Bridge sync threads to async WebSocket broadcast loop."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.run_coroutine_threadsafe(ws_broadcast(message), loop)
    except Exception:
        pass

# Hook camera manager event broadcaster to WebSocket
set_ws_broadcast_callback(sync_ws_broadcast)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup → yield → shutdown."""
    print("[Server] Starting Camera Stream Workers...")
    camera_manager.start_all()
    yield
    print("[Server] Stopping Camera Stream Workers...")
    camera_manager.stop_all()


app = FastAPI(
    title=settings.APP_NAME,
    description="Intelligent Enterprise Surveillance and Access Control System API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =====================================================================
# FRONTEND STATIC ROUTES
# =====================================================================

app.mount("/static", StaticFiles(directory=str(settings.BASE_DIR / "static")), name="static")

@app.get("/")
def read_root():
    """Serve main index.html"""
    return FileResponse(os.path.join(settings.BASE_DIR, "index.html"))

@app.get("/style.css")
def read_css():
    return FileResponse(os.path.join(settings.BASE_DIR, "style.css"))

@app.get("/script.js")
def read_js():
    return FileResponse(os.path.join(settings.BASE_DIR, "script.js"))


# =====================================================================
# WEBSOCKET REAL-TIME ENDPOINT
# =====================================================================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    try:
        # Send initial connection confirmation
        await websocket.send_json({
            "type": "connection_established",
            "message": "Connected to SecureVision Real-Time Stream",
            "timestamp": datetime.datetime.now().strftime("%H:%M:%S")
        })
        while True:
            # Keep alive and listen for client heartbeats/messages
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in active_connections:
            active_connections.remove(websocket)
    except Exception:
        if websocket in active_connections:
            active_connections.remove(websocket)


# =====================================================================
# AUTHENTICATION
# =====================================================================

@app.post("/api/auth/login", response_model=Token)
def login(creds: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == creds.username).first()
    if not user or not verify_password(creds.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled")

    access_token = create_access_token(data={"sub": user.username, "role": user.role})
    return Token(
        access_token=access_token,
        token_type="bearer",
        user_id=user.id,
        username=user.username,
        role=user.role
    )

@app.get("/api/auth/me")
def get_current_user_profile(user: Optional[User] = Depends(get_current_user)):
    if not user:
        return {"authenticated": False}
    return {
        "authenticated": True,
        "username": user.username,
        "full_name": user.full_name,
        "role": user.role
    }


# =====================================================================
# DASHBOARD STATS
# =====================================================================

@app.get("/api/dashboard/stats", response_model=DashboardStats)
def get_dashboard_stats(db: Session = Depends(get_db)):
    total_cameras = db.query(Camera).count() or 4
    cameras_online = sum(1 for c in camera_manager.cameras.values() if c.is_online)
    total_identities = db.query(Identity).filter(Identity.is_active == True).count()
    active_visitors = db.query(Identity).filter(Identity.identity_type == "VISITOR", Identity.is_active == True).count()
    
    # Today's logs
    today_start = datetime.datetime.combine(datetime.date.today(), datetime.time.min)
    today_alerts = db.query(SecurityAlert).filter(SecurityAlert.timestamp >= today_start).count()
    today_access_count = db.query(AccessLog).filter(AccessLog.timestamp >= today_start).count()
    today_blocked_count = db.query(AccessLog).filter(
        AccessLog.timestamp >= today_start,
        AccessLog.status.in_(["DENIED", "BLOCKED"])
    ).count()

    score = max(70, min(100, 100 - (today_blocked_count * 2) - (today_alerts * 3)))
    sys_status = "SECURE" if today_alerts == 0 else ("INVESTIGATING" if today_alerts <= 2 else "ALERT ACTIVE")

    return DashboardStats(
        total_cameras=total_cameras,
        cameras_online=cameras_online,
        total_identities=total_identities,
        active_visitors=active_visitors,
        today_alerts=today_alerts,
        today_access_count=today_access_count,
        today_blocked_count=today_blocked_count,
        security_score=score,
        system_status=sys_status
    )


# =====================================================================
# CAMERA MANAGEMENT & STREAMING
# =====================================================================

@app.get("/api/cameras", response_model=List[CameraOut])
def list_cameras(db: Session = Depends(get_db)):
    cams = db.query(Camera).all()
    # Sync online status from camera_manager
    for c in cams:
        worker = camera_manager.get_camera(c.camera_id)
        if worker:
            c.is_online = worker.is_online
    return cams

@app.get("/api/video_feed/{camera_id}")
def video_feed(camera_id: str):
    worker = camera_manager.get_camera(camera_id)
    if not worker:
        raise HTTPException(status_code=404, detail="Camera not found")
    
    return StreamingResponse(
        worker.get_stream(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )

@app.post("/api/cameras/{camera_id}/toggle")
def toggle_camera(camera_id: str, db: Session = Depends(get_db)):
    worker = camera_manager.get_camera(camera_id)
    if not worker:
        raise HTTPException(status_code=404, detail="Camera not found")
    
    worker.toggle_online()
    cam = db.query(Camera).filter(Camera.camera_id == camera_id).first()
    if cam:
        cam.is_online = worker.is_online
        db.commit()

    sync_ws_broadcast({
        "type": "camera_status_change",
        "camera_id": camera_id,
        "is_online": worker.is_online
    })
    return {"camera_id": camera_id, "is_online": worker.is_online}

@app.post("/api/cameras/{camera_id}/source")
def switch_camera_source(camera_id: str, source_type: str = Query(..., enum=["webcam", "cctv_dataset"])):
    worker = camera_manager.get_camera(camera_id)
    if not worker:
        raise HTTPException(status_code=404, detail="Camera not found")
    
    worker.switch_source(source_type=source_type)
    return {"camera_id": camera_id, "source_type": source_type}


# =====================================================================
# FACE RECOGNITION (VERIFICATION ENDPOINT)
# =====================================================================

@app.post("/api/recognize", response_model=RecognitionResponse)
async def recognize_face(
    image: UploadFile = File(...),
    camera_id: str = Form("cam_01"),
    db: Session = Depends(get_db)
):
    """
    Process an uploaded CCTV/face image:
    1. YuNet Face Detection
    2. Anti-Spoofing / Liveness check
    3. SFace 128-d Feature Embedding
    4. Match against database enrolled identities
    5. Evaluate Access Control
    6. Record Access Log / Alert & return results
    """
    contents = await image.read()
    nparr = np.frombuffer(contents, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if img is None:
        raise HTTPException(status_code=400, detail="Invalid image format")

    now_str = datetime.datetime.now().strftime("%d-%m-%Y %I:%M:%S %p")
    cam = db.query(Camera).filter(Camera.camera_id == camera_id).first()
    cam_name = cam.name if cam else "CAM 01"
    location = cam.location if cam else "Main Entrance"
    is_restricted = cam.is_restricted if cam else False
    clearance_req = cam.required_clearance if cam else "Level 1"

    # 1. Face Detection
    faces = face_engine.detect_faces(img)
    if not faces:
        # No face detected
        return RecognitionResponse(
            success=False,
            face_detected=False,
            authorized=False,
            classification="UNAUTHORIZED",
            badge_color="#ff4d4d",
            similarity_score=0.0,
            is_live=False,
            liveness_score=0.0,
            identity=None,
            box=None,
            timestamp=now_str,
            message="No face detected in the image"
        )

    best_face = faces[0]
    box = best_face["box"]

    # 2. Anti-Spoofing / Liveness Check
    is_live, live_score, live_reason = liveness_detector.check_liveness(best_face["face_crop"])

    # 3. SFace 128-d Embedding Extraction
    query_emb = face_engine.extract_embedding(img, best_face.get("raw_face"), box)

    # 4. Match against DB Enrolled Identities
    enrolled = db.query(Identity).filter(Identity.is_active == True).all()
    matched_identity, similarity, classification, badge_color = face_engine.match_against_identities(
        query_emb, enrolled
    )

    # If spoof detected, force classification
    if not is_live:
        classification = "UNAUTHORIZED"
        badge_color = "#ff4d4d"

    # 5. Access Control Decision
    access_granted, access_reason, alert_type = security_analytics.check_access(
        camera_id, cam_name, is_restricted, clearance_req, matched_identity, classification
    )

    # 6. Save Snapshot & Log to Database
    snapshot_filename = f"rec_{int(time.time() * 1000)}.jpg"
    snapshot_path = os.path.join(settings.SNAPSHOTS_DIR, snapshot_filename)
    # Draw verification box
    bgr_color = (107, 217, 66) if badge_color == "#42d96b" else ((56, 190, 255) if badge_color == "#ffbe38" else (77, 77, 255))
    annotated = img.copy()
    x, y, w, h = box
    cv2.rectangle(annotated, (x, y), (x + w, y + h), bgr_color, 2)
    cv2.imwrite(snapshot_path, annotated)

    rel_snapshot = f"/static/snapshots/{snapshot_filename}"

    # Insert Access Log
    id_code = matched_identity.identity_code if matched_identity else "UNKNOWN"
    id_name = matched_identity.name if matched_identity else "Unknown Person"
    log_status = "GRANTED" if access_granted else "DENIED"

    access_log = AccessLog(
        identity_code=id_code,
        identity_name=id_name,
        identity_type=classification,
        camera_id=camera_id,
        camera_name=cam_name,
        location=location,
        status=log_status,
        reason=access_reason,
        snapshot_path=rel_snapshot
    )
    db.add(access_log)

    # Trigger alert if access denied or spoof
    if alert_type or not is_live:
        alt_type = "SPOOF_ATTEMPT" if not is_live else (alert_type or "UNAUTHORIZED_ACCESS")
        sec_alert = SecurityAlert(
            alert_type=alt_type,
            severity="CRITICAL" if "BREACH" in alt_type else "WARNING",
            camera_id=camera_id,
            camera_name=cam_name,
            location=location,
            identity_name=id_name,
            description=f"{alt_type}: {access_reason}" if is_live else f"Spoof Attempt: {live_reason}",
            status="NEW",
            snapshot_path=rel_snapshot
        )
        db.add(sec_alert)
        db.commit()
        db.refresh(sec_alert)

        sync_ws_broadcast({
            "type": "new_alert",
            "data": {
                "id": sec_alert.id,
                "type": sec_alert.alert_type,
                "severity": sec_alert.severity,
                "camera": sec_alert.camera_name,
                "location": sec_alert.location,
                "identity": sec_alert.identity_name,
                "description": sec_alert.description,
                "status": sec_alert.status,
                "time": sec_alert.timestamp.strftime("%I:%M:%S %p"),
                "snapshot": rel_snapshot
            }
        })
    else:
        db.commit()

    db.refresh(access_log)

    # Broadcast new activity
    sync_ws_broadcast({
        "type": "new_activity",
        "data": {
            "id": access_log.id,
            "time": access_log.timestamp.strftime("%H:%M"),
            "identity": access_log.identity_name,
            "type": access_log.identity_type,
            "location": f"{location} • {cam_name}",
            "status": access_log.status
        }
    })

    identity_info = None
    if matched_identity:
        identity_info = {
            "id": matched_identity.identity_code,
            "name": matched_identity.name,
            "department": matched_identity.department,
            "designation": matched_identity.designation,
            "access_level": matched_identity.access_level
        }

    return RecognitionResponse(
        success=True,
        face_detected=True,
        authorized=access_granted,
        classification=classification,
        badge_color=badge_color,
        similarity_score=similarity,
        is_live=is_live,
        liveness_score=live_score,
        identity=identity_info,
        box=box,
        timestamp=now_str,
        message=access_reason
    )


# =====================================================================
# ENROLLMENT & IDENTITY MANAGEMENT
# =====================================================================

@app.get("/api/identities", response_model=List[IdentityOut])
def list_identities(identity_type: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(Identity).filter(Identity.is_active == True)
    if identity_type:
        query = query.filter(Identity.identity_type == identity_type.upper())
    return query.order_by(desc(Identity.created_at)).all()

@app.post("/api/enroll", response_model=IdentityOut)
async def enroll_face(
    identity_code: str = Form(...),
    name: str = Form(...),
    identity_type: str = Form("EMPLOYEE"),
    department: str = Form("Engineering"),
    designation: str = Form("Software Engineer"),
    access_level: str = Form("Level 1"),
    allowed_cameras: str = Form("cam_01,cam_02,cam_03,cam_04"),
    photo: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Enroll a new identity with real face embedding."""
    # Check duplicate code
    existing = db.query(Identity).filter(Identity.identity_code == identity_code).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Identity code {identity_code} is already registered")

    contents = await photo.read()
    nparr = np.frombuffer(contents, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if img is None:
        raise HTTPException(status_code=400, detail="Invalid photo upload")

    # Detect face
    faces = face_engine.detect_faces(img)
    if not faces:
        raise HTTPException(status_code=400, detail="No clear face detected in the enrollment image. Please ensure good lighting and face the camera directly.")

    best_face = faces[0]
    emb = face_engine.extract_embedding(img, best_face.get("raw_face"), best_face.get("box"))
    if emb is None:
        raise HTTPException(status_code=400, detail="Could not extract biometric face embedding")

    # Save photo to static/enrolled
    photo_filename = f"{identity_code}_{int(time.time())}.jpg"
    photo_path = os.path.join(settings.ENROLLED_DIR, photo_filename)
    cv2.imwrite(photo_path, img)

    new_ident = Identity(
        identity_code=identity_code,
        name=name,
        identity_type=identity_type.upper(),
        department=department,
        designation=designation,
        access_level=access_level,
        allowed_cameras=allowed_cameras,
        face_embedding=json.dumps(emb.tolist()),
        photo_path=f"/static/enrolled/{photo_filename}",
        is_active=True
    )
    db.add(new_ident)
    db.commit()
    db.refresh(new_ident)

    sync_ws_broadcast({
        "type": "new_enrollment",
        "data": {
            "code": new_ident.identity_code,
            "name": new_ident.name,
            "type": new_ident.identity_type
        }
    })
    return new_ident


# =====================================================================
# RECORDS & ACCESS LOGS
# =====================================================================

@app.get("/api/records", response_model=List[AccessLogOut])
def get_records(
    filter_type: Optional[str] = Query("all", enum=["all", "employees", "visitors", "unauthorized"]),
    search: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    query = db.query(AccessLog)
    if filter_type == "employees":
        query = query.filter(AccessLog.identity_type == "EMPLOYEE")
    elif filter_type == "visitors":
        query = query.filter(AccessLog.identity_type == "VISITOR")
    elif filter_type == "unauthorized":
        query = query.filter(AccessLog.identity_type == "UNAUTHORIZED")

    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            (AccessLog.identity_name.ilike(search_pattern)) |
            (AccessLog.identity_code.ilike(search_pattern)) |
            (AccessLog.location.ilike(search_pattern))
        )

    return query.order_by(desc(AccessLog.timestamp)).limit(limit).all()

@app.get("/api/records/export")
def export_records(format: str = Query("csv", enum=["csv", "json"]), db: Session = Depends(get_db)):
    logs = db.query(AccessLog).order_by(desc(AccessLog.timestamp)).all()

    if format == "json":
        data = [
            {
                "id": l.id,
                "timestamp": l.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                "identity_code": l.identity_code,
                "identity_name": l.identity_name,
                "identity_type": l.identity_type,
                "location": l.location,
                "camera": l.camera_name,
                "status": l.status,
                "reason": l.reason
            }
            for l in logs
        ]
        return JSONResponse(
            content=data,
            headers={"Content-Disposition": "attachment; filename=security_records.json"}
        )

    # CSV format
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Timestamp", "Identity Code", "Name", "Type", "Camera", "Location", "Status", "Reason"])
    for l in logs:
        writer.writerow([
            l.id,
            l.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            l.identity_code,
            l.identity_name,
            l.identity_type,
            l.camera_name,
            l.location,
            l.status,
            l.reason
        ])

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=security_records.csv"}
    )

@app.get("/api/access_logs", response_model=List[AccessLogOut])
def get_access_timeline(limit: int = 20, db: Session = Depends(get_db)):
    return db.query(AccessLog).order_by(desc(AccessLog.timestamp)).limit(limit).all()


# =====================================================================
# SECURITY ALERTS & LIFECYCLE
# =====================================================================

@app.get("/api/alerts", response_model=List[AlertOut])
def get_alerts(status_filter: Optional[str] = None, limit: int = 50, db: Session = Depends(get_db)):
    query = db.query(SecurityAlert)
    if status_filter:
        query = query.filter(SecurityAlert.status == status_filter.upper())
    return query.order_by(desc(SecurityAlert.timestamp)).limit(limit).all()

@app.patch("/api/alerts/{alert_id}/status", response_model=AlertOut)
def update_alert_status(alert_id: int, update: AlertStatusUpdate, db: Session = Depends(get_db)):
    alert = db.query(SecurityAlert).filter(SecurityAlert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    valid_statuses = ["NEW", "INVESTIGATING", "RESOLVED"]
    if update.status.upper() not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Status must be one of {valid_statuses}")

    alert.status = update.status.upper()
    if update.resolution_notes is not None:
        alert.resolution_notes = update.resolution_notes

    db.commit()
    db.refresh(alert)

    sync_ws_broadcast({
        "type": "alert_status_update",
        "data": {
            "id": alert.id,
            "status": alert.status,
            "resolution_notes": alert.resolution_notes
        }
    })
    return alert

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
