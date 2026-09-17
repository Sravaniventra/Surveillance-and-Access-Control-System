import os
import sys

# Ensure project root is in sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import json
import datetime
import numpy as np
import cv2
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database import engine, Base, SessionLocal
from backend.models import User, Camera, Identity, AccessLog, SecurityAlert
from backend.auth import hash_password
from backend.ml_engine.face_engine import face_engine


def seed():
    print("[Seed] Creating database tables...")
    Base.metadata.create_all(bind=engine)

    db: Session = SessionLocal()
    try:
        # 1. Seed Admin User
        admin_user = db.query(User).filter(User.username == "admin").first()
        if not admin_user:
            admin_user = User(
                username="admin",
                password_hash=hash_password("admin123"),
                full_name="Chief Security Officer",
                role="admin",
                is_active=True
            )
            db.add(admin_user)
            print("[Seed] Admin user created: admin / admin123")

        # 2. Seed Cameras
        camera_configs = [
            {"id": "cam_01", "name": "CAM 01", "location": "Main Entrance", "restricted": False, "clearance": "Level 1", "online": True},
            {"id": "cam_02", "name": "CAM 02", "location": "Reception", "restricted": False, "clearance": "Level 1", "online": True},
            {"id": "cam_03", "name": "CAM 03", "location": "R&D Laboratory", "restricted": True, "clearance": "Level 2", "online": True},
            {"id": "cam_04", "name": "CAM 04", "location": "Side Gate", "restricted": True, "clearance": "Level 2", "online": False},
        ]
        for cfg in camera_configs:
            cam = db.query(Camera).filter(Camera.camera_id == cfg["id"]).first()
            if not cam:
                cam = Camera(
                    camera_id=cfg["id"],
                    name=cfg["name"],
                    location=cfg["location"],
                    is_restricted=cfg["restricted"],
                    required_clearance=cfg["clearance"],
                    source_type="cctv_dataset",
                    is_online=cfg["online"]
                )
                db.add(cam)
        print("[Seed] Cameras verified.")

        # 3. Seed Identities with face embeddings
        identities_data = [
            {
                "code": "EMP-1027",
                "name": "Sarah Jenkins",
                "type": "EMPLOYEE",
                "dept": "Engineering",
                "desig": "Software Engineer",
                "level": "Level 2",
                "cams": "cam_01,cam_02,cam_03,cam_04",
                "color": (200, 160, 120)
            },
            {
                "code": "EMP-1042",
                "name": "Marcus Vance",
                "type": "EMPLOYEE",
                "dept": "Security Ops",
                "desig": "Lead Officer",
                "level": "Level 3",
                "cams": "cam_01,cam_02,cam_03,cam_04",
                "color": (160, 180, 210)
            },
            {
                "code": "VIS-2001",
                "name": "David Miller",
                "type": "VISITOR",
                "dept": "Guest / Logistics",
                "desig": "Auditor",
                "level": "Level 1",
                "cams": "cam_01,cam_02",
                "color": (180, 190, 170)
            }
        ]

        for item in identities_data:
            existing = db.query(Identity).filter(Identity.identity_code == item["code"]).first()
            if not existing:
                # Create a sample portrait face image for enrollment
                img_path = os.path.join(settings.ENROLLED_DIR, f"{item['code']}.jpg")
                portrait = np.zeros((200, 200, 3), dtype=np.uint8)
                # Background
                portrait[:] = (25, 35, 45)
                # Head oval
                cv2.ellipse(portrait, (100, 95), (55, 75), 0, 0, 360, item["color"], -1)
                # Eyes
                cv2.circle(portrait, (80, 85), 6, (40, 30, 20), -1)
                cv2.circle(portrait, (120, 85), 6, (40, 30, 20), -1)
                # Mouth
                cv2.ellipse(portrait, (100, 125), (20, 8), 0, 0, 180, (50, 40, 80), 2)
                cv2.imwrite(img_path, portrait)

                # Extract embedding from the synthetic portrait
                # Use the full image as the face region [x, y, w, h]
                embedding = face_engine.extract_embedding(portrait, raw_face=None, box=[20, 10, 160, 180])
                if embedding is None or (hasattr(embedding, '__len__') and len(embedding) == 0):
                    # Deterministic normalized random 128-d vector seeded by identity code
                    rng = np.random.RandomState(abs(hash(item["code"])) % (2**32))
                    vec = rng.randn(128).astype(np.float32)
                    embedding = (vec / np.linalg.norm(vec)).tolist()
                else:
                    embedding = embedding.tolist()

                ident = Identity(
                    identity_code=item["code"],
                    name=item["name"],
                    identity_type=item["type"],
                    department=item["dept"],
                    designation=item["desig"],
                    access_level=item["level"],
                    allowed_cameras=item["cams"],
                    face_embedding=json.dumps(embedding),
                    photo_path=f"/static/enrolled/{item['code']}.jpg",
                    is_active=True
                )
                db.add(ident)
        print("[Seed] Identities seeded.")

        # 4. Seed initial Access Logs
        if db.query(AccessLog).count() == 0:
            now = datetime.datetime.utcnow()
            logs = [
                AccessLog(
                    timestamp=now - datetime.timedelta(minutes=2),
                    identity_code="EMP-1027",
                    identity_name="Sarah Jenkins",
                    identity_type="EMPLOYEE",
                    camera_id="cam_01",
                    camera_name="CAM 01",
                    location="Main Entrance",
                    status="GRANTED",
                    reason="Biometric identity verified"
                ),
                AccessLog(
                    timestamp=now - datetime.timedelta(minutes=6),
                    identity_code="UNKNOWN",
                    identity_name="Unknown Person",
                    identity_type="UNAUTHORIZED",
                    camera_id="cam_01",
                    camera_name="CAM 01",
                    location="Main Entrance",
                    status="DENIED",
                    reason="Unregistered face detected"
                ),
                AccessLog(
                    timestamp=now - datetime.timedelta(minutes=13),
                    identity_code="VIS-2001",
                    identity_name="David Miller",
                    identity_type="VISITOR",
                    camera_id="cam_02",
                    camera_name="CAM 02",
                    location="Reception",
                    status="CHECKED IN",
                    reason="Visitor badge checked in"
                ),
                AccessLog(
                    timestamp=now - datetime.timedelta(minutes=20),
                    identity_code="EMP-1027",
                    identity_name="Sarah Jenkins",
                    identity_type="EMPLOYEE",
                    camera_id="cam_03",
                    camera_name="CAM 03",
                    location="R&D Laboratory",
                    status="GRANTED",
                    reason="Level 2 clearance verified"
                )
            ]
            db.add_all(logs)
            print("[Seed] Initial access logs seeded.")

        # 5. Seed initial Security Alerts
        if db.query(SecurityAlert).count() == 0:
            now = datetime.datetime.utcnow()
            alerts = [
                SecurityAlert(
                    timestamp=now - datetime.timedelta(minutes=6),
                    alert_type="UNAUTHORIZED_ACCESS",
                    severity="CRITICAL",
                    camera_id="cam_01",
                    camera_name="CAM 01",
                    location="Main Entrance",
                    identity_name="Unknown Individual",
                    description="Unknown face detected at Main Entrance. Access was automatically denied.",
                    status="NEW"
                ),
                SecurityAlert(
                    timestamp=now - datetime.timedelta(minutes=18),
                    alert_type="RESTRICTED_BREACH",
                    severity="WARNING",
                    camera_id="cam_04",
                    camera_name="CAM 04",
                    location="Side Gate",
                    identity_name="Unknown Individual",
                    description="Movement detected in perimeter perimeter zone while camera was unattended.",
                    status="INVESTIGATING"
                ),
                SecurityAlert(
                    timestamp=now - datetime.timedelta(minutes=35),
                    alert_type="SPOOF_ATTEMPT",
                    severity="WARNING",
                    camera_id="cam_02",
                    camera_name="CAM 02",
                    location="Reception",
                    identity_name="Unverified Photo",
                    description="Anti-spoofing algorithm flagged low texture frequency replay attempt.",
                    status="RESOLVED",
                    resolution_notes="Guard confirmed visitor was showing screen badge. Identity checked manually."
                )
            ]
            db.add_all(alerts)
            print("[Seed] Initial security alerts seeded.")

        db.commit()
        print("[Seed] Seeding completed successfully!")

    except Exception as e:
        db.rollback()
        print(f"[Seed] Error: {e}")
        raise e
    finally:
        db.close()

if __name__ == "__main__":
    seed()
