"""
download_models.py
Downloads the required ONNX face model files (YuNet + SFace) from
the official OpenCV model zoo GitHub releases.

Run once before starting the server:
    python download_models.py
"""
import os
import sys
import hashlib
import requests
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
MODELS_DIR = BASE_DIR / "models"
MODELS_DIR.mkdir(exist_ok=True)

# Official OpenCV model zoo URLs (GitHub releases / raw)
MODELS = [
    {
        "name": "YuNet Face Detector",
        "filename": "face_detection_yunet.onnx",
        "url": (
            "https://github.com/opencv/opencv_zoo/raw/main/models/"
            "face_detection_yunet/face_detection_yunet_2023mar.onnx"
        ),
        "min_size_kb": 200,
    },
    {
        "name": "SFace Face Recognizer",
        "filename": "face_recognition_sface.onnx",
        "url": (
            "https://github.com/opencv/opencv_zoo/raw/main/models/"
            "face_recognition_sface/face_recognition_sface_2021dec.onnx"
        ),
        "min_size_kb": 30,
    },
]

def download_file(name: str, url: str, dest: Path, min_size_kb: int) -> bool:
    """Download a file with progress display. Returns True on success."""
    if dest.exists() and dest.stat().st_size > min_size_kb * 1024:
        print(f"  [OK]  {name} already present: {dest.name}  ({dest.stat().st_size // 1024} KB)")
        return True

    print(f"  [DL]  Downloading {name}...")
    print(f"        URL: {url}")
    try:
        response = requests.get(url, stream=True, timeout=60)
        response.raise_for_status()

        total = int(response.headers.get("content-length", 0))
        downloaded = 0
        chunk_size = 8192

        with open(dest, "wb") as f:
            for chunk in response.iter_content(chunk_size=chunk_size):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total > 0:
                        pct = int(downloaded * 50 / total)
                        bar = "=" * pct + ">" + " " * (50 - pct)
                        print(f"\r        [{bar}] {downloaded // 1024}/{total // 1024} KB", end="", flush=True)

        print()
        size_kb = dest.stat().st_size // 1024
        if size_kb < min_size_kb:
            print(f"  [WARN] {name}: downloaded file is unexpectedly small ({size_kb} KB). Check URL.")
            return False

        print(f"  [OK]  {name} saved: {dest.name} ({size_kb} KB)")
        return True

    except requests.exceptions.RequestException as e:
        print(f"\n  [ERR] Failed to download {name}: {e}")
        return False


def check_yolo_model():
    """Ensure yolov8n.pt exists - ultralytics downloads it automatically but we verify."""
    yolo_path = BASE_DIR / "yolov8n.pt"
    if yolo_path.exists():
        print(f"  [OK]  YOLOv8n base model present: yolov8n.pt  ({yolo_path.stat().st_size // 1024} KB)")
    else:
        print("  [INFO] yolov8n.pt not found locally. Ultralytics will auto-download it on first run.")
        print("         (Requires ~6 MB internet access)")


def main():
    print("=" * 60)
    print("  SecureVision - Model Downloader")
    print("=" * 60)
    print(f"  Models directory: {MODELS_DIR}\n")

    all_ok = True
    for model in MODELS:
        dest = MODELS_DIR / model["filename"]
        ok = download_file(model["name"], model["url"], dest, model["min_size_kb"])
        if not ok:
            all_ok = False

    print()
    check_yolo_model()

    print()
    if all_ok:
        print("  All face models are ready.")
        print("  Next step: python run.py")
    else:
        print("  One or more downloads failed.")
        print("  Manual fallback: Download the .onnx files from the OpenCV model zoo")
        print("  and place them in the 'models/' folder.")
        print()
        print("  YuNet:  https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet")
        print("  SFace:  https://github.com/opencv/opencv_zoo/tree/main/models/face_recognition_sface")
        sys.exit(1)


if __name__ == "__main__":
    main()
