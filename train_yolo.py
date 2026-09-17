"""
Training & Fine-Tuning Script for YOLO Person Detection
Project: Intelligent Enterprise Surveillance and Access Control System
Dataset: CCTV Indoor Person Detection.v4i.yolov8-obb
"""
import os
import sys
import argparse
from pathlib import Path
import yaml
from ultralytics import YOLO

def train():
    parser = argparse.ArgumentParser(description="Train YOLOv8 on CCTV Indoor Person Detection Dataset")
    parser.add_argument("--epochs", type=int, default=10, help="Number of training epochs (default: 10)")
    parser.add_argument("--batch", type=int, default=8, help="Batch size (default: 8 for laptop CPUs)")
    parser.add_argument("--imgsz", type=int, default=640, help="Input image resolution (default: 640)")
    parser.add_argument("--device", type=str, default="cpu", help="Device to use: 'cpu' or '0' for CUDA GPU")
    parser.add_argument("--model", type=str, default="yolov8n.pt",
                        help="Pretrained base model — use 'yolov8n.pt' (standard) or 'yolov8n-obb.pt' (oriented bbox)")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent
    dataset_dir = project_root / "CCTV Indoor Person Detection.v4i.yolov8-obb"
    original_yaml = dataset_dir / "data.yaml"

    if not original_yaml.exists():
        print(f"[Error] Dataset configuration not found at {original_yaml}")
        sys.exit(1)

    print("=" * 70)
    print("  INTELLIGENT ENTERPRISE SURVEILLANCE - YOLO TRAINING PIPELINE")
    print("=" * 70)
    print(f"Dataset directory : {dataset_dir}")
    print(f"Base model        : {args.model}")
    print(f"Epochs            : {args.epochs}")
    print(f"Batch size        : {args.batch}")
    print(f"Image size        : {args.imgsz}")
    print(f"Compute device    : {args.device}")

    # Read and prepare runtime YAML with absolute path so YOLO finds it everywhere
    with open(original_yaml, "r") as f:
        data_cfg = yaml.safe_load(f)

    data_cfg["path"] = str(dataset_dir.as_posix())

    # Ensure 'nc' (number of classes) is present — required by Ultralytics
    names = data_cfg.get("names", {0: "person"})
    if isinstance(names, dict):
        data_cfg["nc"] = len(names)
        data_cfg["names"] = list(names.values())
    elif isinstance(names, list):
        data_cfg["nc"] = len(names)
    else:
        data_cfg["nc"] = 1
        data_cfg["names"] = ["person"]

    runtime_yaml = dataset_dir / "runtime_data.yaml"
    with open(runtime_yaml, "w") as f:
        yaml.safe_dump(data_cfg, f)

    print(f"Runtime YAML generated: {runtime_yaml}")

    # Initialize model
    print(f"\n[1/3] Initializing {args.model}...")
    model = YOLO(args.model)

    # Train
    print(f"\n[2/3] Starting training on {data_cfg.get('names', {0: 'person'})}...")
    try:
        results = model.train(
            data=str(runtime_yaml),
            epochs=args.epochs,
            batch=args.batch,
            imgsz=args.imgsz,
            device=args.device,
            project=str(project_root / "runs"),
            name="train",
            exist_ok=True,
            verbose=True
        )
        print("\n[3/3] Training completed successfully!")
        best_weights = project_root / "runs" / "train" / "weights" / "best.pt"
        if best_weights.exists():
            print(f"\n>>> Best trained model saved to: {best_weights}")
        else:
            print(f"\n>>> Model checkpoints saved under: {project_root / 'runs' / 'train'}")
    except Exception as e:
        print(f"\n[Training Error] {e}")
        print("Note: The surveillance backend is already configured to seamlessly use pretrained yolov8n.pt out of the box.")

if __name__ == "__main__":
    train()
