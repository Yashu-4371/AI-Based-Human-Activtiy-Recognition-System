"""
Fall detection rule engine, implementing the logic formalized in the
architecture doc:

  possible_fall  IF torso_angle > threshold
                 AND vertical_velocity > threshold
                 AND bbox_aspect_ratio < 1.0 (person is wider than tall)

  confirmed_fall IF possible_fall AND the patient remains in a fallen
                 posture with no significant movement for
                 FALL_CONFIRMATION_WINDOW_SEC afterwards.

This two-stage design avoids false alarms from someone quickly sitting
down or bending over by requiring sustained fallen-posture + stillness
before escalating.

IMPORTANT: the TRIGGER condition (torso_angle + vertical_velocity +
bbox_ratio) is checked only once, to enter the "possible fall" state.
vertical_velocity is an instantaneous frame-to-frame quantity (see
feature_extractor.vertical_velocity) that spikes for essentially one
frame during the drop and returns to ~0 immediately afterward, by
design — that's what makes it useful for detecting sudden onset.
Re-checking the full trigger signature (including vertical_velocity)
on every frame of the confirmation window would therefore always fail
the instant the person stops moving, i.e. exactly when a real fall
victim is lying still — making confirmation impossible. So once
"possible fall" is entered, the window instead checks POSTURE
(torso_angle, bbox_ratio) and STILLNESS (centroid_velocity) — not
vertical_velocity — to decide whether to confirm or reset.
"""

from typing import Optional

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

_STILLNESS_VELOCITY_THRESHOLD = 0.05  # normalized units/sec; below this counts as "not moving"
_RECOVERY_ANGLE_FACTOR = 0.7  # posture must relax below this fraction of the trigger angle to count as "got up"
_RECOVERY_BBOX_RATIO = 1.0  # bbox must widen back out to at least this ratio to count as "got up"


class FallDetector:
    def __init__(
        self,
        torso_angle_threshold_deg: float = None,
        vertical_velocity_threshold: float = None,
        confirmation_window_sec: float = None,
    ):
        self.torso_angle_threshold_deg = torso_angle_threshold_deg or settings.FALL_TORSO_ANGLE_THRESHOLD_DEG
        self.vertical_velocity_threshold = vertical_velocity_threshold or settings.FALL_VERTICAL_VELOCITY_THRESHOLD
        self.confirmation_window_sec = confirmation_window_sec or settings.FALL_CONFIRMATION_WINDOW_SEC

        self._possible_fall_active = False
        self._possible_fall_started_at: Optional[float] = None
        self._already_confirmed = False

    def reset(self) -> None:
        self._possible_fall_active = False
        self._possible_fall_started_at = None
        self._already_confirmed = False

    def _is_fallen_posture(self, torso_inclination_deg: float, bbox_aspect_ratio: float) -> bool:
        return (
            torso_inclination_deg > self.torso_angle_threshold_deg * _RECOVERY_ANGLE_FACTOR
            and bbox_aspect_ratio < _RECOVERY_BBOX_RATIO
        )

    def update(
        self,
        torso_inclination_deg: float,
        vertical_velocity: float,
        bbox_aspect_ratio: float,
        centroid_velocity: float,
        timestamp_sec: float,
    ) -> bool:
        """
        Call once per processed frame. Returns True exactly once, on the
        frame where a fall is newly confirmed (so callers don't create
        duplicate alerts on every subsequent frame while the patient
        remains on the ground).
        """
        if self._already_confirmed:
            return False

        if not self._possible_fall_active:
            trigger_signature = (
                torso_inclination_deg > self.torso_angle_threshold_deg
                and vertical_velocity > self.vertical_velocity_threshold
                and bbox_aspect_ratio < 1.0
            )
            if trigger_signature:
                self._possible_fall_active = True
                self._possible_fall_started_at = timestamp_sec
                logger.info("Possible fall detected — starting confirmation window.")
            return False

        # We're inside the confirmation window: judge by posture + stillness,
        # not by re-checking the (instantaneous, single-frame) trigger signature.
        started_at = self._possible_fall_started_at if self._possible_fall_started_at is not None else timestamp_sec
        elapsed = timestamp_sec - started_at
        fallen_posture = self._is_fallen_posture(torso_inclination_deg, bbox_aspect_ratio)

        if not fallen_posture:
            # Posture relaxed back toward upright before confirmation — patient got up. Not a fall.
            logger.info("Possible fall recovered before confirmation — resetting.")
            self.reset()
            return False

        if elapsed >= self.confirmation_window_sec:
            is_still = centroid_velocity < _STILLNESS_VELOCITY_THRESHOLD
            if is_still:
                self._already_confirmed = True
                logger.warning("FALL CONFIRMED after %.1fs in fallen posture with no movement.", elapsed)
                return True
            else:
                # Still in a fallen-looking posture but actively moving (e.g. crawling,
                # repositioning) — not treated as a confirmed immobilizing fall yet.
                self.reset()
                return False

        return False

    def is_in_confirmed_fall_state(self) -> bool:
        return self._already_confirmed
