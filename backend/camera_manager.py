import os
import time
import glob
import threading
from typing import Dict, Any, Optional, Generator, List
import numpy as np
import cv2
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database import SessionLocal
from backend.models import Camera, Identity, AccessLog, SecurityAlert
from backend.ml_engine.yolo_detector import yolo_detector
from backend.ml_engine.face_engine import face_engine
from backend.ml_engine.tracker import MultiPersonTracker
from backend.ml_engine.liveness import liveness_detector
from backend.ml_engine.analytics import security_analytics

# Global broadcast callback for WebSocket notifications
_ws_broadcast_callback = None

def set_ws_broadcast_callback(cb):
    global _ws_broadcast_callback
    _ws_broadcast_callback = cb

def broadcast_event(event_type: str, data: dict):
    if _ws_broadcast_callback is not None:
        try:
            _ws_broadcast_callback({"type": event_type, "data": data})
        except Exception as e:
            pass

class CameraStreamWorker:
    def __init__(
        self,
        camera_id: str,
        name: str,
        location: str,
        source_type: str = "cctv_dataset",
        source_url: str = "0",
        is_restricted: bool = False,
        required_clearance: str = "Level 1"
    ):
        self.camera_id = camera_id
        self.name = name
        self.location = location
        self.source_type = source_type
        self.source_url = source_url
        self.is_restricted = is_restricted
        self.required_clearance = required_clearance
        self.is_online = True

        self.cap = None
        self.dataset_images: List[str] = []
        self.dataset_index = 0
        self.tracker = MultiPersonTracker()
        self.last_alert_time: Dict[str, float] = {}

        self.last_frame_bytes: Optional[bytes] = None
        self.lock = threading.Lock()
        self.running = False
        self.thread = None

        self._load_dataset_images()

    def _load_dataset_images(self):
        """Find CCTV dataset images for demo replay."""
        test_dir = os.path.join(settings.DATASET_DIR, "test", "images")
        if os.path.exists(test_dir):
            images = glob.glob(os.path.join(test_dir, "*.jpg")) + glob.glob(os.path.join(test_dir, "*.png"))
            if images:
                # Distribute different subsets of images across cameras
                step = 4
                offset = {"cam_01": 0, "cam_02": 1, "cam_03": 2, "cam_04": 3}.get(self.camera_id, 0)
                self.dataset_images = images[offset::step]
                if not self.dataset_images:
                    self.dataset_images = images

    def start(self):
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._capture_loop, daemon=True)
            self.thread.start()

    def stop(self):
        self.running = False
        if self.cap is not None:
            try:
                self.cap.release()
            except Exception:
                pass

    def switch_source(self, source_type: str, source_url: str = "0"):
        with self.lock:
            if self.cap is not None:
                self.cap.release()
                self.cap = None
            self.source_type = source_type
            self.source_url = source_url

    def toggle_online(self, status: Optional[bool] = None):
        with self.lock:
            if status is not None:
                self.is_online = status
            else:
                self.is_online = not self.is_online

    def _get_raw_frame(self) -> Optional[np.ndarray]:
        """Fetch next frame from webcam or dataset loop."""
        if not self.is_online:
            return None

        # 1. Webcam capture
        if self.source_type == "webcam":
            if self.cap is None or not self.cap.isOpened():
                try:
                    idx = int(self.source_url) if self.source_url.isdigit() else 0
                    self.cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW if os.name == 'nt' else cv2.CAP_ANY)
                except Exception as e:
                    print(f"[{self.name}] Webcam open failed: {e}")
                    return None

            if self.cap is not None and self.cap.isOpened():
                ret, frame = self.cap.read()
                if ret and frame is not None:
                    return frame
                else:
                    # Webcam read failed
                    return None

        # 2. CCTV Dataset sequence
        if self.dataset_images:
            img_path = self.dataset_images[self.dataset_index % len(self.dataset_images)]
            frame = cv2.imread(img_path)
            # Advance every 12 frames for smooth presentation
            self.dataset_index += 1
            if frame is not None:
                return cv2.resize(frame, (800, 480))

        # 3. Default synthetic CCTV background if no dataset images
        frame = np.zeros((480, 800, 3), dtype=np.uint8)
        frame[:] = (18, 26, 31)
        cv2.putText(frame, f"FEED: {self.name}", (50, 240), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (70, 140, 255), 2)
        return frame

    def _generate_offline_frame(self) -> np.ndarray:
        """Render offline / signal lost screen."""
        frame = np.zeros((480, 800, 3), dtype=np.uint8)
        frame[:] = (10, 15, 20)
        # Scanlines effect
        for y in range(0, 480, 4):
            frame[y:y+1, :] = (15, 20, 26)
        
        cv2.putText(frame, "[ SIGNAL LOST - CAMERA OFFLINE ]", (180, 220), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (77, 77, 255), 2)
        cv2.putText(frame, f"{self.name} • {self.location}", (260, 260), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (147, 135, 113), 1)
        timestamp_str = time.strftime("%d-%m-%Y %I:%M:%S %p")
        cv2.putText(frame, timestamp_str, (280, 290), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (100, 100, 100), 1)
        return frame

    def _capture_loop(self):
        """Worker thread processing frames and running deep learning."""
        while self.running:
            try:
                frame = self._get_raw_frame()
                if frame is None or not self.is_online:
                    annotated_frame = self._generate_offline_frame()
                else:
                    annotated_frame = self._process_frame(frame)

                # JPEG encode
                ret, buffer = cv2.imencode(".jpg", annotated_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
                if ret:
                    with self.lock:
                        self.last_frame_bytes = buffer.tobytes()

                # Control frame rate (~12-15 FPS to keep CPU utilization moderate)
                time.sleep(0.07)

            except Exception as e:
                print(f"[{self.name}] Stream processing error: {e}")
                time.sleep(0.2)

    def _process_frame(self, frame: np.ndarray) -> np.ndarray:
        """Run YOLO Person Detection -> Face Detection -> Classification -> Analytics -> HUD overlay."""
        display = frame.copy()
        h, w = display.shape[:2]

        # 1. YOLO Person Detection
        person_detections = yolo_detector.detect(frame)
        person_boxes = [d["box"] for d in person_detections]

        # 2. Multi-Person Tracking
        active_tracks = self.tracker.update(person_boxes)

        # Database session for identity queries and event logging
        db: Session = SessionLocal()
        try:
            enrolled = db.query(Identity).filter(Identity.is_active == True).all()

            # 3. Process each tracked person
            for track in active_tracks:
                px1, py1, px2, py2 = track["box"]
                track_id = track["track_id"]
                dwell = track["dwell_seconds"]

                # Extract upper body / person crop for face search
                pw, ph = px2 - px1, py2 - py1
                face_search_crop = frame[py1:min(h, py1 + int(ph * 0.55)), px1:px2]

                matched_identity = None
                similarity = 0.0
                classification = "UNAUTHORIZED"
                badge_color_bgr = (77, 77, 255)  # RED (BGR)
                name_label = f"Track #{track_id} (Unknown)"
                status_label = "UNAUTHORIZED"

                if face_search_crop.size > 0:
                    faces = face_engine.detect_faces(face_search_crop)
                    if faces:
                        best_face = faces[0]
                        fx, fy, fw_box, fh_box = best_face["box"]

                        # Global coordinates of face
                        gfx, gfy = px1 + fx, py1 + fy

                        # Anti-spoofing check
                        is_live, live_score, live_reason = liveness_detector.check_liveness(best_face["face_crop"])

                        # Deep feature extraction
                        emb = face_engine.extract_embedding(face_search_crop, best_face.get("raw_face"), best_face.get("box"))
                        if emb is not None:
                            matched_identity, similarity, classification, badge_hex = face_engine.match_against_identities(
                                emb, enrolled
                            )

                        if not is_live:
                            classification = "UNAUTHORIZED"
                            badge_color_bgr = (77, 77, 255)
                            name_label = "SPOOF ATTACK DETECTED"
                            status_label = "REPLAY/PRINT SPOOF"
                        elif classification == "EMPLOYEE" and matched_identity is not None:
                            badge_color_bgr = (107, 217, 66)  # GREEN (#42d96b BGR)
                            name_label = f"{matched_identity.identity_code} • {matched_identity.name}"
                            status_label = f"EMPLOYEE ({matched_identity.access_level})"
                        elif classification == "VISITOR" and matched_identity is not None:
                            badge_color_bgr = (56, 190, 255)  # YELLOW (#ffbe38 BGR: 56, 190, 255)
                            name_label = f"{matched_identity.identity_code} • {matched_identity.name}"
                            status_label = "VISITOR"
                        else:
                            badge_color_bgr = (77, 77, 255)  # RED (#ff4d4d BGR)
                            name_label = f"UNAUTHORIZED (Conf: {int(similarity * 100)}%)"
                            status_label = "ACCESS DENIED"

                        # Draw face box inside upper body
                        cv2.rectangle(display, (gfx, gfy), (gfx + fw_box, gfy + fh_box), badge_color_bgr, 1)

                # Access clearance check
                access_granted, access_reason, alert_type = security_analytics.check_access(
                    self.camera_id, self.name, self.is_restricted, self.required_clearance,
                    matched_identity, classification
                )

                # Draw Person Bounding Box & HUD
                # Corner styling matching SecureVision theme
                self._draw_corners(display, px1, py1, px2, py2, badge_color_bgr)

                # Top info tag
                label_text = f"{name_label} [{status_label}]"
                cv2.rectangle(display, (px1, max(0, py1 - 24)), (px1 + min(w - px1, len(label_text) * 9 + 10), py1), (12, 23, 30), -1)
                cv2.putText(display, label_text, (px1 + 4, max(12, py1 - 7)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, badge_color_bgr, 1)

                # Dwell time indicator
                dwell_text = f"T#{track_id} | Dwell: {dwell}s"
                cv2.putText(display, dwell_text, (px1 + 4, py2 - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)

                # 4. Trigger alert if unauthorized or breach detected
                if alert_type is not None:
                    self._record_alert(db, frame, alert_type, self.name, name_label, access_reason)

            # 5. Tailgating & Loitering Analytics
            tailgate_alerts = security_analytics.check_tailgating(self.camera_id, self.name, active_tracks)
            for ta in tailgate_alerts:
                self._record_alert(db, frame, ta["alert_type"], self.name, "Multiple Individuals", ta["description"])

            loiter_alerts = security_analytics.check_loitering(self.camera_id, self.name, self.is_restricted, active_tracks)
            for la in loiter_alerts:
                self._record_alert(db, frame, la["alert_type"], self.name, f"Track #{la['track_id']}", la["description"])

        finally:
            db.close()

        # HUD Top Banner
        self._draw_hud(display)

        return display

    def _draw_corners(self, img: np.ndarray, x1: int, y1: int, x2: int, y2: int, color: tuple, length: int = 15, thickness: int = 2):
        # Bounding box border
        cv2.rectangle(img, (x1, y1), (x2, y2), color, 1)
        # Top-left
        cv2.line(img, (x1, y1), (x1 + length, y1), color, thickness)
        cv2.line(img, (x1, y1), (x1, y1 + length), color, thickness)
        # Top-right
        cv2.line(img, (x2, y1), (x2 - length, y1), color, thickness)
        cv2.line(img, (x2, y1), (x2, y1 + length), color, thickness)
        # Bottom-left
        cv2.line(img, (x1, y2), (x1 + length, y2), color, thickness)
        cv2.line(img, (x1, y2), (x1, y2 - length), color, thickness)
        # Bottom-right
        cv2.line(img, (x2, y2), (x2 - length, y2), color, thickness)
        cv2.line(img, (x2, y2), (x2, y2 - length), color, thickness)

    def _draw_hud(self, img: np.ndarray):
        h, w = img.shape[:2]
        # Top HUD Bar
        cv2.rectangle(img, (0, 0), (w, 30), (9, 20, 27), -1)
        cv2.line(img, (0, 30), (w, 30), (27, 48, 60), 1)

        # Status dot
        cv2.circle(img, (15, 15), 4, (66, 217, 107), -1)
        cam_info = f"LIVE • {self.name.upper()} - {self.location.upper()}"
        if self.is_restricted:
            cam_info += " [RESTRICTED]"
        cv2.putText(img, cam_info, (28, 19), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (229, 237, 242), 1)

        time_str = time.strftime("%H:%M:%S")
        cv2.putText(img, time_str, (w - 75, 19), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (56, 160, 255), 1)

    def _record_alert(self, db: Session, frame: np.ndarray, alert_type: str, cam_name: str, identity_name: str, desc: str):
        """Save snapshot and write alert + access log to database, broadcasting via WebSocket."""
        now = time.time()
        cooldown_key = f"{self.camera_id}_{alert_type}"
        # 12-second rate-limiting cooldown per camera and alert type
        if now - self.last_alert_time.get(cooldown_key, 0.0) < 12.0:
            return
        self.last_alert_time[cooldown_key] = now

        snapshot_filename = f"alert_{int(now * 1000)}.jpg"
        snapshot_path = os.path.join(settings.SNAPSHOTS_DIR, snapshot_filename)
        cv2.imwrite(snapshot_path, frame)

        rel_snapshot_path = f"/static/snapshots/{snapshot_filename}"

        # Create alert record
        alert = SecurityAlert(
            alert_type=alert_type,
            severity="CRITICAL" if "BREACH" in alert_type or "TAILGATING" in alert_type else "WARNING",
            camera_id=self.camera_id,
            camera_name=self.name,
            location=self.location,
            identity_name=identity_name,
            description=desc,
            status="NEW",
            snapshot_path=rel_snapshot_path
        )
        db.add(alert)

        # Create access log entry
        access_status = "DENIED" if "UNAUTHORIZED" in alert_type or "BREACH" in alert_type else "WARNING"
        log = AccessLog(
            identity_code="UNKNOWN",
            identity_name=identity_name,
            identity_type="UNAUTHORIZED",
            camera_id=self.camera_id,
            camera_name=self.name,
            location=self.location,
            status=access_status,
            reason=desc,
            snapshot_path=rel_snapshot_path
        )
        db.add(log)
        db.commit()
        db.refresh(alert)
        db.refresh(log)

        # Broadcast via WebSocket
        broadcast_event("new_alert", {
            "id": alert.id,
            "type": alert.alert_type,
            "severity": alert.severity,
            "camera": alert.camera_name,
            "location": alert.location,
            "identity": alert.identity_name,
            "description": alert.description,
            "status": alert.status,
            "time": alert.timestamp.strftime("%I:%M:%S %p"),
            "snapshot": rel_snapshot_path
        })

        broadcast_event("new_activity", {
            "id": log.id,
            "time": log.timestamp.strftime("%H:%M"),
            "identity": log.identity_name,
            "type": log.identity_type,
            "location": f"{log.location} • {log.camera_name}",
            "status": log.status
        })

    def get_stream(self) -> Generator[bytes, None, None]:
        """Yield multipart MJPEG stream frames."""
        while self.running:
            with self.lock:
                frame_data = self.last_frame_bytes

            if frame_data is not None:
                yield (
                    b'--frame\r\n'
                    b'Content-Type: image/jpeg\r\n\r\n' + frame_data + b'\r\n'
                )
            time.sleep(0.06)

class CameraManager:
    def __init__(self):
        self.cameras: Dict[str, CameraStreamWorker] = {}
        self._init_cameras()

    def _init_cameras(self):
        # 4 predefined cameras matching the UI
        self.cameras["cam_01"] = CameraStreamWorker(
            camera_id="cam_01",
            name="CAM 01",
            location="Main Entrance",
            source_type="cctv_dataset",  # Can switch to webcam on button click
            is_restricted=False,
            required_clearance="Level 1"
        )
        self.cameras["cam_02"] = CameraStreamWorker(
            camera_id="cam_02",
            name="CAM 02",
            location="Reception",
            source_type="cctv_dataset",
            is_restricted=False,
            required_clearance="Level 1"
        )
        self.cameras["cam_03"] = CameraStreamWorker(
            camera_id="cam_03",
            name="CAM 03",
            location="R&D Laboratory",
            source_type="cctv_dataset",
            is_restricted=True,
            required_clearance="Level 2"
        )
        self.cameras["cam_04"] = CameraStreamWorker(
            camera_id="cam_04",
            name="CAM 04",
            location="Side Gate",
            source_type="cctv_dataset",
            is_restricted=True,
            required_clearance="Level 2"
        )
        # Start CAM 04 as offline initially to match existing UI
        self.cameras["cam_04"].is_online = False

    def start_all(self):
        for cam in self.cameras.values():
            cam.start()

    def stop_all(self):
        for cam in self.cameras.values():
            cam.stop()

    def get_camera(self, camera_id: str) -> Optional[CameraStreamWorker]:
        return self.cameras.get(camera_id)

camera_manager = CameraManager()
