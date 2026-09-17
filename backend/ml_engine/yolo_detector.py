import os
from typing import List, Dict, Any
import numpy as np
import cv2
from ultralytics import YOLO
from backend.config import settings

class YOLOPersonDetector:
    def __init__(self, model_path: str = None, conf_threshold: float = None):
        self.model_path = model_path or settings.YOLO_MODEL_PATH
        self.conf_threshold = conf_threshold or settings.PERSON_CONFIDENCE_THRESHOLD
        self.model = None
        self._load_model()

    def _load_model(self):
        """Loads or downloads the YOLO model."""
        try:
            # If a custom fine-tuned model exists, use it; otherwise default to base yolov8n
            custom_path = os.path.join(settings.BASE_DIR, "runs", "detect", "train", "weights", "best.pt")
            if os.path.exists(custom_path):
                print(f"[YOLO] Loading custom fine-tuned weights: {custom_path}")
                self.model = YOLO(custom_path)
            else:
                print(f"[YOLO] Loading model from: {self.model_path}")
                self.model = YOLO(self.model_path)
        except Exception as e:
            print(f"[YOLO] Error loading model, falling back to yolov8n.pt: {e}")
            self.model = YOLO("yolov8n.pt")

    def detect(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """
        Run person detection on an input BGR frame.
        Returns a list of dicts:
        [{'box': [x1, y1, x2, y2], 'conf': 0.85, 'class': 'person'}]
        """
        if self.model is None or frame is None or frame.size == 0:
            return []

        try:
            # Run inference with person class (0) or all classes if fine-tuned
            results = self.model(frame, conf=self.conf_threshold, verbose=False)
            detections = []

            for result in results:
                # 1. Standard bounding boxes
                if hasattr(result, "boxes") and result.boxes is not None and len(result.boxes) > 0:
                    boxes = result.boxes
                    for i in range(len(boxes)):
                        cls_id = int(boxes.cls[i].item())
                        conf = float(boxes.conf[i].item())
                        
                        # In standard COCO, class 0 is person. In single-class Roboflow dataset, class 0 is person.
                        if cls_id == 0:
                            xyxy = boxes.xyxy[i].cpu().numpy().astype(int).tolist()
                            x1, y1, x2, y2 = xyxy
                            
                            # Boundary clamping
                            h, w = frame.shape[:2]
                            x1 = max(0, min(x1, w - 1))
                            y1 = max(0, min(y1, h - 1))
                            x2 = max(x1 + 1, min(x2, w))
                            y2 = max(y1 + 1, min(y2, h))

                            detections.append({
                                "box": [x1, y1, x2, y2],
                                "conf": round(conf, 3),
                                "class": "person"
                            })

                # 2. Support for Oriented Bounding Boxes (OBB) if model is OBB
                elif hasattr(result, "obb") and result.obb is not None and len(result.obb) > 0:
                    obb = result.obb
                    for i in range(len(obb)):
                        cls_id = int(obb.cls[i].item())
                        conf = float(obb.conf[i].item())
                        if cls_id == 0:
                            # Convert 4 corner points to enclosing axis-aligned bbox
                            xyxyxyxy = obb.xyxyxyxy[i].cpu().numpy()
                            x_coords = xyxyxyxy[:, 0]
                            y_coords = xyxyxyxy[:, 1]
                            x1, y1 = int(np.min(x_coords)), int(np.min(y_coords))
                            x2, y2 = int(np.max(x_coords)), int(np.max(y_coords))
                            
                            h, w = frame.shape[:2]
                            x1 = max(0, min(x1, w - 1))
                            y1 = max(0, min(y1, h - 1))
                            x2 = max(x1 + 1, min(x2, w))
                            y2 = max(y1 + 1, min(y2, h))

                            detections.append({
                                "box": [x1, y1, x2, y2],
                                "conf": round(conf, 3),
                                "class": "person"
                            })

            return detections
        except Exception as e:
            print(f"[YOLO] Inference error: {e}")
            return []

# Singleton instance
yolo_detector = YOLOPersonDetector()
