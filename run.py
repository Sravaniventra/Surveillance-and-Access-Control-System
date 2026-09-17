"""
run.py  —  SecureVision Enterprise Surveillance — One-Command Launcher
======================================================================
Handles:
  1. Model file presence check (offers to download if missing)
  2. Database table creation
  3. Admin + camera + seed data bootstrap
  4. Starts Uvicorn ASGI server

Usage:
    python run.py               # production-like (reload=False)
    python run.py --dev         # auto-reload on code changes
    python run.py --port 9000   # custom port
    python run.py --host 127.0.0.1  # localhost only
"""
import os
import sys
import argparse
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# ── Ensure project root is importable ─────────────────────────────────────────
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))


def banner():
    print("""
╔══════════════════════════════════════════════════════════════╗
║          SECUREVISION  Enterprise Surveillance               ║
║          AI-Powered Access Control & CCTV Monitoring         ║
╚══════════════════════════════════════════════════════════════╝
""")


def check_models() -> bool:
    """Return True if both ONNX model files are present and non-empty."""
    models_dir = BASE_DIR / "models"
    yunet  = models_dir / "face_detection_yunet.onnx"
    sface  = models_dir / "face_recognition_sface.onnx"

    missing = []
    for p, min_kb in [(yunet, 200), (sface, 30)]:
        if not p.exists() or p.stat().st_size < min_kb * 1024:
            missing.append(p.name)

    if missing:
        print(f"  [WARN]  Missing/incomplete ONNX models: {', '.join(missing)}")
        print("          Face recognition will fall back to Haar cascade only.")
        answer = input("  Download models now? [Y/n]: ").strip().lower()
        if answer in ("", "y", "yes"):
            result = subprocess.run(
                [sys.executable, str(BASE_DIR / "download_models.py")],
                check=False
            )
            return result.returncode == 0
        else:
            print("  [INFO]  Skipping download. System will use Haar cascade fallback.")
            return False
    else:
        print("  [OK]    Face ONNX models present.")
        return True


def ensure_static_dirs():
    """Create static output directories if they don't exist."""
    for subdir in ("static/snapshots", "static/enrolled"):
        d = BASE_DIR / subdir
        d.mkdir(parents=True, exist_ok=True)
    print("  [OK]    Static directories ready.")


def init_database():
    """Create all DB tables and run seed data."""
    print("  [DB]    Initialising database...")
    try:
        from backend.database import engine, Base
        Base.metadata.create_all(bind=engine)
        print("  [OK]    Database tables created/verified.")
    except Exception as e:
        print(f"  [ERR]   Database table creation failed: {e}")
        sys.exit(1)

    print("  [DB]    Running seed data...")
    try:
        from backend.seed_data import seed
        seed()
    except Exception as e:
        print(f"  [WARN]  Seed data error (non-fatal): {e}")


def start_server(host: str, port: int, dev: bool):
    """Launch uvicorn."""
    import uvicorn
    print(f"\n  [SERVER]  Starting SecureVision on http://{host}:{port}")
    print(f"  [SERVER]  Open your browser: http://localhost:{port}")
    print(f"  [SERVER]  Admin login:  username=admin  password=admin123")
    print(f"  [SERVER]  Press Ctrl+C to stop.\n")

    uvicorn.run(
        "backend.main:app",
        host=host,
        port=port,
        reload=dev,
        log_level="info",
        access_log=True,
    )


def main():
    banner()

    parser = argparse.ArgumentParser(description="SecureVision launcher")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="Port (default: 8000)")
    parser.add_argument("--dev",  action="store_true", help="Enable auto-reload for development")
    parser.add_argument("--skip-seed", action="store_true", help="Skip database seeding")
    parser.add_argument("--skip-models", action="store_true", help="Skip ONNX model check")
    args = parser.parse_args()

    print("  Startup checks...")
    print()

    if not args.skip_models:
        check_models()

    ensure_static_dirs()

    if not args.skip_seed:
        init_database()
    else:
        print("  [SKIP]  Database seeding skipped (--skip-seed).")

    start_server(args.host, args.port, args.dev)


if __name__ == "__main__":
    main()
