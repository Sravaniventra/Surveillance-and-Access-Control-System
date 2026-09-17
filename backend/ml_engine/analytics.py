import time
from typing import Dict, Any, Optional, Tuple, List
from backend.config import settings

class SecurityAnalytics:
    def __init__(self):
        # camera_id -> list of recent access timestamps: [{'timestamp': float, 'identity_code': str}]
        self.recent_authorizations: Dict[str, List[Dict[str, Any]]] = {}
        # track_id -> timestamp when loitering alert was fired (to prevent duplicate spam)
        self.loitering_alerted: Dict[int, float] = {}
        # track_id -> timestamp when tailgating alert was fired
        self.tailgating_alerted: Dict[int, float] = {}

    def check_access(
        self,
        camera_id: str,
        camera_name: str,
        is_restricted: bool,
        required_clearance: str,
        identity: Optional[Any],
        classification: str
    ) -> Tuple[bool, str, str]:
        """
        Evaluate access decision and determine if alert is needed.
        Returns:
            (access_granted: bool, reason: str, alert_type: Optional[str])
        """
        if classification == "UNAUTHORIZED" or identity is None:
            if is_restricted:
                return False, f"Unauthorized individual in restricted zone ({camera_name})", "RESTRICTED_BREACH"
            else:
                return False, f"Unregistered identity detected at {camera_name}", "UNAUTHORIZED_ACCESS"

        # Check camera permissions
        allowed_cams = getattr(identity, "allowed_cameras", "") or ""
        allowed_list = [c.strip().lower() for c in allowed_cams.split(",") if c.strip()]
        if allowed_list and camera_id.lower() not in allowed_list and "*" not in allowed_list:
            return False, f"Access level insufficient for {camera_name}", "RESTRICTED_BREACH"

        # Check restricted clearance levels
        if is_restricted:
            clearance = getattr(identity, "access_level", "Level 1")
            # Order: Level 1 < Level 2 < Level 3
            level_rank = {"Level 1": 1, "Level 2": 2, "Level 3": 3}
            user_rank = level_rank.get(clearance, 1)
            req_rank = level_rank.get(required_clearance, 2)

            if user_rank < req_rank:
                return False, f"Clearance required: {required_clearance} (Holder has: {clearance})", "RESTRICTED_BREACH"

        # If visitor, check check-in status
        if classification == "VISITOR":
            return True, f"Visitor authorized for {camera_name}", None

        # Employee authorized
        now = time.time()
        if camera_id not in self.recent_authorizations:
            self.recent_authorizations[camera_id] = []
        self.recent_authorizations[camera_id].append({
            "timestamp": now,
            "identity_code": getattr(identity, "identity_code", "EMP")
        })
        # Clean authorizations older than 10 seconds
        self.recent_authorizations[camera_id] = [
            a for a in self.recent_authorizations[camera_id] if now - a["timestamp"] < 10.0
        ]

        return True, "Access Granted", None

    def check_tailgating(
        self,
        camera_id: str,
        camera_name: str,
        active_tracks: List[Dict[str, Any]],
        portal_line_y: int = 240
    ) -> List[Dict[str, Any]]:
        """
        Detect tailgating at access points (e.g. Main Entrance).
        If multiple persons pass entry threshold within quick succession without separate auth.
        """
        now = time.time()
        alerts = []

        if len(active_tracks) >= 2:
            # Check for two people moving together through entrance
            auths = self.recent_authorizations.get(camera_id, [])
            valid_auths = [a for a in auths if now - a["timestamp"] <= settings.TAILGATING_TIME_SECONDS]

            # If there are multiple people but fewer authorizations than people
            if len(active_tracks) > max(1, len(valid_auths)):
                for track in active_tracks:
                    tid = track["track_id"]
                    if tid not in self.tailgating_alerted or (now - self.tailgating_alerted[tid] > 15.0):
                        self.tailgating_alerted[tid] = now
                        alerts.append({
                            "alert_type": "TAILGATING",
                            "severity": "CRITICAL",
                            "camera_id": camera_id,
                            "camera_name": camera_name,
                            "description": f"Tailgating violation detected at {camera_name}: multiple persons entering on single access grant.",
                            "track_id": tid
                        })
                        break
        return alerts

    def check_loitering(
        self,
        camera_id: str,
        camera_name: str,
        is_restricted: bool,
        active_tracks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Detect prolonged presence (loitering) in restricted zones.
        """
        now = time.time()
        alerts = []

        if is_restricted:
            for track in active_tracks:
                dwell = track.get("dwell_seconds", 0.0)
                tid = track["track_id"]

                if dwell >= settings.LOITERING_TIME_SECONDS:
                    # Check if already alerted recently
                    if tid not in self.loitering_alerted or (now - self.loitering_alerted[tid] > 20.0):
                        self.loitering_alerted[tid] = now
                        alerts.append({
                            "alert_type": "LOITERING",
                            "severity": "WARNING",
                            "camera_id": camera_id,
                            "camera_name": camera_name,
                            "description": f"Suspicious loitering detected at {camera_name} (dwell time: {dwell}s in restricted zone).",
                            "track_id": tid
                        })
        return alerts

security_analytics = SecurityAnalytics()
