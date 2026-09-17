import os
from pathlib import Path
from pydantic_settings import BaseSettings

# Project Root Directory
BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    BASE_DIR: Path = BASE_DIR
    APP_NAME: str = "SecureVision Enterprise Surveillance"
    DEBUG: bool = False
    PORT: int = 8000
    HOST: str = "0.0.0.0"

    # Security
    SECRET_KEY: str = "super-secret-enterprise-surveillance-jwt-key-998811"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    # Database — absolute path prevents CWD-relative resolution issues
    DATABASE_URL: str = f"sqlite:///{BASE_DIR}/surveillance.db".replace("\\", "/")

    # Model paths — absolute so they resolve regardless of working directory
    YOLO_MODEL_PATH: str = str(BASE_DIR / "yolov8n.pt")
    YUNET_MODEL_PATH: str = str(BASE_DIR / "models" / "face_detection_yunet.onnx")
    SFACE_MODEL_PATH: str = str(BASE_DIR / "models" / "face_recognition_sface.onnx")

    # Thresholds
    PERSON_CONFIDENCE_THRESHOLD: float = 0.35
    FACE_CONFIDENCE_THRESHOLD: float = 0.60
    FACE_MATCH_THRESHOLD: float = 0.363  # Standard OpenCV SFace cosine similarity threshold
    LIVENESS_LAPLACIAN_THRESHOLD: float = 35.0

    # Security Rules
    LOITERING_TIME_SECONDS: float = 10.0
    TAILGATING_TIME_SECONDS: float = 2.5

    # Dataset path for demo feed
    DATASET_DIR: str = str(BASE_DIR / "CCTV Indoor Person Detection.v4i.yolov8-obb")
    SNAPSHOTS_DIR: str = str(BASE_DIR / "static" / "snapshots")
    ENROLLED_DIR: str = str(BASE_DIR / "static" / "enrolled")

    class Config:
        env_file = str(BASE_DIR / ".env")
        extra = "ignore"

settings = Settings()

# Ensure required directories exist
os.makedirs(settings.SNAPSHOTS_DIR, exist_ok=True)
os.makedirs(settings.ENROLLED_DIR, exist_ok=True)
os.makedirs(BASE_DIR / "models", exist_ok=True)
