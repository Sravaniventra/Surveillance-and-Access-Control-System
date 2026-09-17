import os
import json
import threading
from typing import List, Dict, Any, Tuple, Optional
import numpy as np
import cv2
from backend.config import settings

class FaceEngine:
    def __init__(
        self,
        detector_path: str = None,
        recognizer_path: str = None,
        conf_threshold: float = None,
        match_threshold: float = None
    ):
        self.detector_path = detector_path or settings.YUNET_MODEL_PATH
        self.recognizer_path = recognizer_path or settings.SFACE_MODEL_PATH
        self.conf_threshold = conf_threshold or settings.FACE_CONFIDENCE_THRESHOLD
        self.match_threshold = match_threshold or settings.FACE_MATCH_THRESHOLD

        self.lock = threading.Lock()
        self.detector = None
        self.recognizer = None
        self.haar_cascade = None
        self._init_models()

    def _init_models(self):
        """Initialize YuNet detector and SFace recognizer."""
        try:
            if os.path.exists(self.detector_path) and os.path.exists(self.recognizer_path):
                print(f"[FaceEngine] Initializing YuNet: {self.detector_path}")
                self.detector = cv2.FaceDetectorYN.create(
                    self.detector_path,
                    "",
                    (320, 320),
                    self.conf_threshold,
                    0.3,
                    5000
                )
                print(f"[FaceEngine] Initializing SFace: {self.recognizer_path}")
                self.recognizer = cv2.FaceRecognizerSF.create(self.recognizer_path, "")
            else:
                print("[FaceEngine] Model files missing. Will initialize Haar Cascade fallback.")
        except Exception as e:
            print(f"[FaceEngine] Failed to initialize YuNet/SFace: {e}")

        # Fallback Haar cascade
        try:
            cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            self.haar_cascade = cv2.CascadeClassifier(cascade_path)
        except Exception as e:
            print(f"[FaceEngine] Haar cascade fallback error: {e}")

    def detect_faces(self, image: np.ndarray) -> List[Dict[str, Any]]:
        """
        Detect faces in image.
        Returns list of dicts:
        {
            'box': [x, y, w, h],
            'confidence': float,
            'raw_face': np.ndarray, # YuNet 15-dim landmark array
            'face_crop': np.ndarray
        }
        """
        if image is None or image.size == 0:
            return []

        h, w = image.shape[:2]
        detected = []

        with self.lock:
            if self.detector is not None:
                try:
                    self.detector.setInputSize((w, h))
                    ret, faces = self.detector.detect(image)
                    if faces is not None and len(faces) > 0:
                        for face in faces:
                            conf = float(face[-1])
                            if conf < self.conf_threshold or np.isnan(conf):
                                continue

                            raw_x = float(np.nan_to_num(face[0], nan=0.0))
                            raw_y = float(np.nan_to_num(face[1], nan=0.0))
                            raw_w = float(np.nan_to_num(face[2], nan=1.0))
                            raw_h = float(np.nan_to_num(face[3], nan=1.0))

                            x = max(0, min(int(raw_x), w - 1))
                            y = max(0, min(int(raw_y), h - 1))
                            fw = max(1, min(int(raw_w), w - x))
                            fh = max(1, min(int(raw_h), h - y))

                            face_crop = image[y:y+fh, x:x+fw]
                            detected.append({
                                "box": [x, y, fw, fh],
                                "confidence": round(conf, 3),
                                "raw_face": face,
                                "face_crop": face_crop
                            })
                    return detected
                except Exception as e:
                    print(f"[FaceEngine] YuNet detection error: {e}")

        # Haar cascade fallback if YuNet fails or is unavailable
        if self.haar_cascade is not None:
            try:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
                faces = self.haar_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
                for (x, y, fw, fh) in faces:
                    face_crop = image[y:y+fh, x:x+fw]
                    detected.append({
                        "box": [int(x), int(y), int(fw), int(fh)],
                        "confidence": 0.85,
                        "raw_face": None,
                        "face_crop": face_crop
                    })
            except Exception as e:
                print(f"[FaceEngine] Haar detection error: {e}")

        return detected

    def extract_embedding(self, image: np.ndarray, raw_face: Optional[np.ndarray] = None, box: Optional[List[int]] = None) -> Optional[np.ndarray]:
        """
        Extract 128-dimensional deep face embedding using SFace.
        Returns normalized 128-d numpy array or None.
        """
        if self.recognizer is None or image is None or image.size == 0:
            return None

        with self.lock:
            try:
                feature = None
                if raw_face is not None:
                    # Align face with YuNet 5 landmarks
                    aligned = self.recognizer.alignCrop(image, raw_face)
                    feature = self.recognizer.feature(aligned)
                elif box is not None:
                    # Approximate aligned face from box
                    x, y, fw, fh = box
                    face_crop = image[y:y+fh, x:x+fw]
                    if face_crop.size == 0:
                        return None
                    resized = cv2.resize(face_crop, (112, 112))
                    feature = self.recognizer.feature(resized)
                else:
                    resized = cv2.resize(image, (112, 112))
                    feature = self.recognizer.feature(resized)

                if feature is not None and feature.size > 0:
                    # L2 normalize
                    norm = np.linalg.norm(feature)
                    if norm > 1e-6:
                        feature = feature / norm
                    return feature.flatten()
            except Exception as e:
                print(f"[FaceEngine] Feature extraction error: {e}")

        return None

    def match_against_identities(
        self,
        query_embedding: np.ndarray,
        enrolled_identities: List[Any]
    ) -> Tuple[Optional[Any], float, str, str]:
        """
        Match a query embedding against enrolled identities.
        Returns:
            (matched_identity, similarity_score, classification, badge_color)
            Classification is one of: 'EMPLOYEE', 'VISITOR', 'UNAUTHORIZED'
            badge_color: '#42d96b' (green), '#ffbe38' (yellow), '#ff4d4d' (red)
        """
        if query_embedding is None or not enrolled_identities:
            return None, 0.0, "UNAUTHORIZED", "#ff4d4d"

        best_score = -1.0
        best_identity = None

        query_vec = np.array(query_embedding, dtype=np.float32).flatten()
        q_norm = np.linalg.norm(query_vec)
        if q_norm > 1e-6:
            query_vec = query_vec / q_norm

        for identity in enrolled_identities:
            if not identity.face_embedding:
                continue
            try:
                enrolled_vec = np.array(json.loads(identity.face_embedding), dtype=np.float32).flatten()
                e_norm = np.linalg.norm(enrolled_vec)
                if e_norm > 1e-6:
                    enrolled_vec = enrolled_vec / e_norm

                # Cosine similarity is dot product of normalized vectors
                cosine_sim = float(np.dot(query_vec, enrolled_vec))
                if cosine_sim > best_score:
                    best_score = cosine_sim
                    best_identity = identity
            except Exception as e:
                continue

        best_score = round(max(0.0, min(1.0, best_score)), 3)

        # Threshold check: strictly unauthorized if below match_threshold
        if best_identity is not None and best_score >= self.match_threshold:
            itype = getattr(best_identity, "identity_type", "EMPLOYEE").upper()
            if itype == "EMPLOYEE":
                return best_identity, best_score, "EMPLOYEE", "#42d96b"
            else:
                return best_identity, best_score, "VISITOR", "#ffbe38"
        else:
            return None, best_score, "UNAUTHORIZED", "#ff4d4d"

# Singleton instance
face_engine = FaceEngine()
