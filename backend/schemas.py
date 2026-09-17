import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict

# Token & Auth
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    username: str
    role: str

class LoginRequest(BaseModel):
    username: str
    password: str

# Identity
class IdentityCreate(BaseModel):
    identity_code: str
    name: str
    identity_type: str = "EMPLOYEE"  # EMPLOYEE or VISITOR
    department: str = "Engineering"
    designation: str = "Software Engineer"
    access_level: str = "Level 1"
    allowed_cameras: str = "cam_01,cam_02,cam_03,cam_04"

class IdentityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    identity_code: str
    name: str
    identity_type: str
    department: str
    designation: str
    access_level: str
    allowed_cameras: str
    photo_path: Optional[str] = None
    is_active: bool
    created_at: datetime.datetime

# Camera
class CameraOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    camera_id: str
    name: str
    location: str
    is_restricted: bool
    required_clearance: str
    source_type: str
    is_online: bool

# Access Log
class AccessLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    timestamp: datetime.datetime
    identity_code: str
    identity_name: str
    identity_type: str
    camera_id: str
    camera_name: str
    location: str
    status: str
    reason: str
    snapshot_path: Optional[str] = None

# Alert
class AlertStatusUpdate(BaseModel):
    status: str  # NEW, INVESTIGATING, RESOLVED
    resolution_notes: Optional[str] = None

class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    timestamp: datetime.datetime
    alert_type: str
    severity: str
    camera_id: str
    camera_name: str
    location: str
    identity_name: str
    description: str
    status: str
    resolution_notes: Optional[str] = None
    snapshot_path: Optional[str] = None

# Dashboard Stats
class DashboardStats(BaseModel):
    total_cameras: int
    cameras_online: int
    total_identities: int
    active_visitors: int
    today_alerts: int
    today_access_count: int
    today_blocked_count: int
    security_score: int
    system_status: str

# Recognition Response
class RecognitionResponse(BaseModel):
    success: bool
    face_detected: bool
    authorized: bool
    classification: str  # EMPLOYEE, VISITOR, UNAUTHORIZED
    badge_color: str     # GREEN (#42d96b), YELLOW (#ffbe38), RED (#ff4d4d)
    similarity_score: float
    is_live: bool
    liveness_score: float
    identity: Optional[dict] = None
    box: Optional[List[int]] = None  # [x, y, w, h]
    timestamp: str
    message: str
