import time
from typing import List, Dict, Any, Tuple
import numpy as np

def calculate_iou(boxA: List[int], boxB: List[int]) -> float:
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2])
    yB = min(boxA[3], boxB[3])

    interArea = max(0, xB - xA) * max(0, yB - yA)
    boxAArea = max(1, (boxA[2] - boxA[0]) * (boxA[3] - boxA[1]))
    boxBArea = max(1, (boxB[2] - boxB[0]) * (boxB[3] - boxB[1]))

    return interArea / float(boxAArea + boxBArea - interArea)

class MultiPersonTracker:
    def __init__(self, max_disappeared: int = 15, iou_threshold: float = 0.3):
        self.next_track_id = 1
        self.tracks: Dict[int, Dict[str, Any]] = {}
        self.disappeared: Dict[int, int] = {}
        self.max_disappeared = max_disappeared
        self.iou_threshold = iou_threshold

    def update(self, detected_boxes: List[List[int]]) -> List[Dict[str, Any]]:
        """
        Update tracker with detected bounding boxes [x1, y1, x2, y2].
        Returns list of active tracked objects:
        [{'track_id': 1, 'box': [...], 'centroid': (cx, cy), 'dwell_seconds': 4.2}]
        """
        current_time = time.time()

        # If no detections, increment disappeared count
        if len(detected_boxes) == 0:
            for track_id in list(self.disappeared.keys()):
                self.disappeared[track_id] += 1
                if self.disappeared[track_id] > self.max_disappeared:
                    self._deregister(track_id)
            return self._get_active_tracks()

        # If no existing tracks, register all detections as new
        if len(self.tracks) == 0:
            for box in detected_boxes:
                self._register(box, current_time)
            return self._get_active_tracks()

        # Match existing tracks to detections using IoU
        track_ids = list(self.tracks.keys())
        track_boxes = [self.tracks[tid]["box"] for tid in track_ids]

        iou_matrix = np.zeros((len(track_boxes), len(detected_boxes)), dtype=np.float32)
        for i, tbox in enumerate(track_boxes):
            for j, dbox in enumerate(detected_boxes):
                iou_matrix[i, j] = calculate_iou(tbox, dbox)

        matched_tracks = set()
        matched_detections = set()

        if iou_matrix.size > 0:
            row_indices = iou_matrix.max(axis=1).argsort()[::-1]
            for row in row_indices:
                col = int(iou_matrix[row].argmax())
                if col in matched_detections:
                    continue
                if iou_matrix[row, col] >= self.iou_threshold:
                    tid = track_ids[row]
                    box = detected_boxes[col]
                    cx = (box[0] + box[2]) // 2
                    cy = (box[1] + box[3]) // 2
                    
                    self.tracks[tid]["box"] = box
                    self.tracks[tid]["centroid"] = (cx, cy)
                    self.tracks[tid]["last_seen"] = current_time
                    self.tracks[tid]["history"].append((cx, cy))
                    if len(self.tracks[tid]["history"]) > 30:
                        self.tracks[tid]["history"].pop(0)
                    self.disappeared[tid] = 0

                    matched_tracks.add(tid)
                    matched_detections.add(col)

        # Handle unmatched existing tracks
        for tid in track_ids:
            if tid not in matched_tracks:
                self.disappeared[tid] += 1
                if self.disappeared[tid] > self.max_disappeared:
                    self._deregister(tid)

        # Register unmatched detections as new tracks
        for j, box in enumerate(detected_boxes):
            if j not in matched_detections:
                self._register(box, current_time)

        return self._get_active_tracks()

    def _register(self, box: List[int], current_time: float):
        cx = (box[0] + box[2]) // 2
        cy = (box[1] + box[3]) // 2
        self.tracks[self.next_track_id] = {
            "track_id": self.next_track_id,
            "box": box,
            "centroid": (cx, cy),
            "start_time": current_time,
            "last_seen": current_time,
            "history": [(cx, cy)],
            "authorized": False,
            "identity": None
        }
        self.disappeared[self.next_track_id] = 0
        self.next_track_id += 1

    def _deregister(self, track_id: int):
        if track_id in self.tracks:
            del self.tracks[track_id]
        if track_id in self.disappeared:
            del self.disappeared[track_id]

    def _get_active_tracks(self) -> List[Dict[str, Any]]:
        current_time = time.time()
        active = []
        for tid, track in self.tracks.items():
            if self.disappeared.get(tid, 0) == 0:
                dwell = round(current_time - track["start_time"], 1)
                active.append({
                    "track_id": tid,
                    "box": track["box"],
                    "centroid": track["centroid"],
                    "dwell_seconds": dwell,
                    "history": track["history"]
                })
        return active
