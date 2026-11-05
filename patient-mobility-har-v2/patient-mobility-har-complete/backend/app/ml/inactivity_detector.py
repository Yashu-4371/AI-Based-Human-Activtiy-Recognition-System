"""
Tracks time since the patient's last significant movement and raises a
warning once the configurable threshold (30/60/90s, etc.) is exceeded.
Separate from fall detection: lying still is expected/normal (e.g.
sleeping), so this only warns when NOT classified as lying, or can be
configured to warn regardless via `warn_during_lying`.
"""

from typing import Optional

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

_STILLNESS_VELOCITY_THRESHOLD = 0.03


class InactivityDetector:
    def __init__(self, threshold_sec: float = None, warn_during_lying: bool = False):
        self.threshold_sec = threshold_sec or settings.INACTIVITY_THRESHOLD_SEC
        self.warn_during_lying = warn_during_lying

        self._last_movement_timestamp: Optional[float] = None
        self._warning_already_raised = False

    def reset(self) -> None:
        self._last_movement_timestamp = None
        self._warning_already_raised = False

    def update(self, centroid_velocity: float, activity_label: str, timestamp_sec: float) -> bool:
        """
        Call once per processed frame. Returns True exactly once, on the
        frame where the inactivity warning is newly raised.
        """
        if self._last_movement_timestamp is None:
            self._last_movement_timestamp = timestamp_sec

        is_moving = centroid_velocity >= _STILLNESS_VELOCITY_THRESHOLD
        if is_moving:
            self._last_movement_timestamp = timestamp_sec
            self._warning_already_raised = False
            return False

        if activity_label == "lying" and not self.warn_during_lying:
            # Expected stillness (e.g. sleeping) — don't count toward inactivity warning.
            self._last_movement_timestamp = timestamp_sec
            return False

        elapsed_still = timestamp_sec - self._last_movement_timestamp
        if elapsed_still >= self.threshold_sec and not self._warning_already_raised:
            self._warning_already_raised = True
            logger.warning("Prolonged inactivity detected: %.0fs without significant movement.", elapsed_still)
            return True

        return False

    def is_warning_active(self) -> bool:
        return self._warning_already_raised
