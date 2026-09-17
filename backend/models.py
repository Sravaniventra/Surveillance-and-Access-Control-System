import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, Float
from backend.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(64), unique=True, index=True, nullable=False)
    password_hash = Column(String(256), nullable=False)
    full_name = Column(String(128), default="Administrator")
    role = Column(String(32), default="admin")  # admin, supervisor
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class Identity(Base):
    __tablename__ = "identities"

    id = Column(Integer, primary_key=True, index=True)
    identity_code = Column(String(64), unique=True, index=True, nullable=False)  # e.g. EMP-1027, VIS-2001
    name = Column(String(128), nullable=False)
    identity_type = Column(String(32), default="EMPLOYEE", nullable=False)  # EMPLOYEE, VISITOR
    department = Column(String(128), default="General")
    designation = Column(String(128), default="Staff")
    access_level = Column(String(32), default="Level 1")  # Level 1, Level 2, Level 3
    allowed_cameras = Column(String(256), default="cam_01,cam_02,cam_03,cam_04")  # comma-separated camera_ids
    face_embedding = Column(Text, nullable=True)  # JSON array of 128 float numbers
    photo_path = Column(String(256), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class Camera(Base):
    __tablename__ = "cameras"

    camera_id = Column(String(32), primary_key=True, index=True)  # cam_01, cam_02, cam_03, cam_04
    name = Column(String(64), nullable=False)                     # CAM 01, CAM 02, etc.
    location = Column(String(128), nullable=False)                 # Main Entrance, Reception, etc.
    is_restricted = Column(Boolean, default=False)                # True for high-security zones (e.g. R&D Lab)
    required_clearance = Column(String(32), default="Level 1")     # Minimum access level needed
    source_type = Column(String(32), default="cctv_dataset")      # webcam, cctv_dataset, video, offline
    source_url = Column(String(256), default="0")
    is_online = Column(Boolean, default=True)


class AccessLog(Base):
    __tablename__ = "access_logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, index=True)
    identity_code = Column(String(64), default="UNKNOWN")
    identity_name = Column(String(128), default="Unknown Person")
    identity_type = Column(String(32), default="UNAUTHORIZED")  # EMPLOYEE, VISITOR, UNAUTHORIZED
    camera_id = Column(String(32), nullable=False)
    camera_name = Column(String(64), default="CAM 01")
    location = Column(String(128), default="Main Entrance")
    status = Column(String(32), default="GRANTED")  # GRANTED, DENIED, CHECKED IN
    reason = Column(String(256), default="Verification successful")
    snapshot_path = Column(String(256), nullable=True)


class SecurityAlert(Base):
    __tablename__ = "security_alerts"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, index=True)
    alert_type = Column(String(64), nullable=False)  # UNAUTHORIZED_ACCESS, RESTRICTED_BREACH, TAILGATING, LOITERING, SPOOF_ATTEMPT
    severity = Column(String(32), default="CRITICAL")  # CRITICAL, WARNING, INFO
    camera_id = Column(String(32), nullable=False)
    camera_name = Column(String(64), default="CAM 01")
    location = Column(String(128), default="Main Entrance")
    identity_name = Column(String(128), default="Unknown Individual")
    description = Column(String(512), nullable=False)
    status = Column(String(32), default="NEW", index=True)  # NEW, INVESTIGATING, RESOLVED
    resolution_notes = Column(Text, nullable=True)
    snapshot_path = Column(String(256), nullable=True)
