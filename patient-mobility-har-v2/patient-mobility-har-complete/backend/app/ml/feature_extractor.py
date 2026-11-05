"""
Converts raw MediaPipe landmarks into a fixed-length feature vector for
the Random Forest activity classifier.

Design goals of FEATURE_SCHEMA_VERSION 2 (generalization to unseen people,
camera distances and viewpoints):

* Everything is expressed relative to the person's own torso length, never
  in absolute image coordinates, so it does not depend on where the person
  stands in the frame or how far they are from the camera.
* Landmark x is multiplied by the frame aspect ratio (width/height) so
  angles/distances are computed in a square pixel space instead of the
  anisotropic normalized [0,1] space.
* Movement speed is measured over a fixed TIME window (not a fixed number
  of samples), in torso-lengths per second, so training clips (frame
  stride) and live camera (wall-clock fps) produce comparable values.

Feature order is fixed in FEATURE_NAMES; the trained model stores the list
and the classifier refuses to use a model trained on a different schema.

The fall/inactivity detectors are NOT affected by these feature changes:
they read the *_for_fall_detector signals below, which keep the original
definitions (unscaled coordinates, all-landmark bounding box).
"""

import math
from collections import deque
from typing import Deque, List, Optional, Tuple

import numpy as np

from app.ml.pose_estimator import (
    Landmark,
    LEFT_SHOULDER, RIGHT_SHOULDER,
    LEFT_ELBOW, RIGHT_ELBOW,
    LEFT_WRIST, RIGHT_WRIST,
    LEFT_HIP, RIGHT_HIP,
    LEFT_KNEE, RIGHT_KNEE,
    LEFT_ANKLE, RIGHT_ANKLE,
    NOSE,
)

FEATURE_SCHEMA_VERSION = 2

FEATURE_NAMES = [
    "left_elbow_angle", "right_elbow_angle",
    "left_knee_angle", "right_knee_angle",
    "left_hip_angle", "right_hip_angle",
    "torso_inclination_deg",
    "hip_ankle_distance_norm",
    "knee_hip_vertical_norm",     # (knee_y - hip_y) / torso_len: ~+1 standing, ~0 thighs horizontal (sitting)
    "nose_hip_vertical_norm",     # (hip_y - nose_y) / torso_len: >0 head above hips, ~0 when lying
    "shoulder_width_norm",        # shoulder width / torso_len: viewing-angle (front vs side) cue
    "ankle_spread_norm",          # ankle-to-ankle distance / torso_len: stride / leg-spread cue
    "bbox_aspect_ratio",          # height/width of the 13 core joints (not hands/feet/face points)
    "centroid_velocity_norm",     # hip-centre speed over last VELOCITY_WINDOW_SEC, in torso-lengths/sec
]
FEATURE_INDEX = {name: i for i, name in enumerate(FEATURE_NAMES)}

VELOCITY_WINDOW_SEC = 0.6
_MIN_TORSO_LEN = 1e-3
_MAX_BBOX_ASPECT = 10.0

CORE_JOINTS = [
    NOSE, LEFT_SHOULDER, RIGHT_SHOULDER, LEFT_ELBOW, RIGHT_ELBOW, LEFT_WRIST, RIGHT_WRIST,
    LEFT_HIP, RIGHT_HIP, LEFT_KNEE, RIGHT_KNEE, LEFT_ANKLE, RIGHT_ANKLE,
]


def _angle_between(a: Landmark, b: Landmark, c: Landmark) -> float:
    """Angle at vertex b, formed by points a-b-c, in degrees."""
    ba = np.array([a.x - b.x, a.y - b.y])
    bc = np.array([c.x - b.x, c.y - b.y])
    norm_product = (np.linalg.norm(ba) * np.linalg.norm(bc)) or 1e-6
    cosine_angle = np.clip(np.dot(ba, bc) / norm_product, -1.0, 1.0)
    return float(np.degrees(np.arccos(cosine_angle)))


def _euclidean(a: Landmark, b: Landmark) -> float:
    return float(math.hypot(a.x - b.x, a.y - b.y))


def _midpoint(a: Landmark, b: Landmark) -> Tuple[float, float]:
    return (a.x + b.x) / 2.0, (a.y + b.y) / 2.0


class FeatureExtractor:
    """
    Stateful per-track extractor. Keeps short rolling histories of the hip
    centroid so it can compute movement speed (inherently multi-frame).
    """

    def __init__(self, history_len: int = 5, velocity_window_sec: float = VELOCITY_WINDOW_SEC):
        # Original raw-coordinate history: used ONLY by the fall/inactivity signals below.
        self._centroid_history: Deque[Tuple[float, float, float]] = deque(maxlen=history_len)  # (x, y, t)
        # Aspect-corrected history used for the classifier's velocity feature (time-window based).
        self._velocity_window_sec = velocity_window_sec
        self._scaled_history: Deque[Tuple[float, float, float]] = deque(maxlen=256)
        # Signals for the (unchanged) fall detector; refreshed on every successful extract().
        self.torso_inclination_for_fall_detector: float = 0.0
        self.bbox_aspect_ratio_for_fall_detector: float = 1.0

    def reset(self) -> None:
        self._centroid_history.clear()
        self._scaled_history.clear()

    def extract(
        self, landmarks: List[Landmark], timestamp_sec: float, aspect_ratio: float = 1.0
    ) -> Optional[np.ndarray]:
        """
        aspect_ratio = frame_width / frame_height of the image the landmarks
        were detected in (1.0 if unknown). Live camera, video extraction and
        skeleton-dataset conversion must all pass the true value.
        """
        try:
            self._update_fall_signals(landmarks, timestamp_sec)

            lms = [Landmark(x=lm.x * aspect_ratio, y=lm.y, z=lm.z, visibility=lm.visibility) for lm in landmarks]

            left_elbow_angle = _angle_between(lms[LEFT_SHOULDER], lms[LEFT_ELBOW], lms[LEFT_WRIST])
            right_elbow_angle = _angle_between(lms[RIGHT_SHOULDER], lms[RIGHT_ELBOW], lms[RIGHT_WRIST])
            left_knee_angle = _angle_between(lms[LEFT_HIP], lms[LEFT_KNEE], lms[LEFT_ANKLE])
            right_knee_angle = _angle_between(lms[RIGHT_HIP], lms[RIGHT_KNEE], lms[RIGHT_ANKLE])
            left_hip_angle = _angle_between(lms[LEFT_SHOULDER], lms[LEFT_HIP], lms[LEFT_KNEE])
            right_hip_angle = _angle_between(lms[RIGHT_SHOULDER], lms[RIGHT_HIP], lms[RIGHT_KNEE])

            shoulder_mid = _midpoint(lms[LEFT_SHOULDER], lms[RIGHT_SHOULDER])
            hip_mid = _midpoint(lms[LEFT_HIP], lms[RIGHT_HIP])
            ankle_mid = _midpoint(lms[LEFT_ANKLE], lms[RIGHT_ANKLE])

            torso_len = math.hypot(shoulder_mid[0] - hip_mid[0], shoulder_mid[1] - hip_mid[1])
            if torso_len < _MIN_TORSO_LEN:
                return None  # degenerate / unreliable detection

            torso_dx = shoulder_mid[0] - hip_mid[0]
            torso_dy = shoulder_mid[1] - hip_mid[1]
            torso_inclination_deg = float(np.degrees(np.arctan2(abs(torso_dx), abs(torso_dy) or 1e-6)))

            hip_ankle_distance_norm = math.hypot(hip_mid[0] - ankle_mid[0], hip_mid[1] - ankle_mid[1]) / torso_len
            knee_mid_y = (lms[LEFT_KNEE].y + lms[RIGHT_KNEE].y) / 2.0
            knee_hip_vertical_norm = (knee_mid_y - hip_mid[1]) / torso_len
            nose_hip_vertical_norm = (hip_mid[1] - lms[NOSE].y) / torso_len
            shoulder_width_norm = _euclidean(lms[LEFT_SHOULDER], lms[RIGHT_SHOULDER]) / torso_len
            ankle_spread_norm = _euclidean(lms[LEFT_ANKLE], lms[RIGHT_ANKLE]) / torso_len

            xs = [lms[i].x for i in CORE_JOINTS]
            ys = [lms[i].y for i in CORE_JOINTS]
            bbox_width = max((max(xs) - min(xs)), 1e-6)
            bbox_height = max((max(ys) - min(ys)), 1e-6)
            bbox_aspect_ratio = min(bbox_height / bbox_width, _MAX_BBOX_ASPECT)

            centroid_velocity_norm = self._compute_velocity_norm(hip_mid, torso_len, timestamp_sec)

            return np.array(
                [
                    left_elbow_angle, right_elbow_angle,
                    left_knee_angle, right_knee_angle,
                    left_hip_angle, right_hip_angle,
                    torso_inclination_deg,
                    hip_ankle_distance_norm,
                    knee_hip_vertical_norm,
                    nose_hip_vertical_norm,
                    shoulder_width_norm,
                    ankle_spread_norm,
                    bbox_aspect_ratio,
                    centroid_velocity_norm,
                ],
                dtype=np.float32,
            )
        except (IndexError, ZeroDivisionError):
            return None

    # ---- classifier velocity (time-window, torso-normalized) ----

    def _compute_velocity_norm(self, hip_mid: Tuple[float, float], torso_len: float, timestamp_sec: float) -> float:
        self._scaled_history.append((hip_mid[0], hip_mid[1], timestamp_sec))
        cutoff = timestamp_sec - self._velocity_window_sec
        while len(self._scaled_history) > 2 and self._scaled_history[1][2] <= cutoff:
            self._scaled_history.popleft()
        if len(self._scaled_history) < 2:
            return 0.0
        x_old, y_old, t_old = self._scaled_history[0]
        dt = max(timestamp_sec - t_old, 1e-3)
        return math.hypot(hip_mid[0] - x_old, hip_mid[1] - y_old) / dt / torso_len

    # ---- fall / inactivity signals: ORIGINAL definitions, kept unchanged ----

    def _update_fall_signals(self, landmarks: List[Landmark], timestamp_sec: float) -> None:
        shoulder_mid = _midpoint(landmarks[LEFT_SHOULDER], landmarks[RIGHT_SHOULDER])
        hip_mid = _midpoint(landmarks[LEFT_HIP], landmarks[RIGHT_HIP])
        torso_dx = shoulder_mid[0] - hip_mid[0]
        torso_dy = shoulder_mid[1] - hip_mid[1]
        self.torso_inclination_for_fall_detector = float(
            np.degrees(np.arctan2(abs(torso_dx), abs(torso_dy) or 1e-6))
        )
        xs = [lm.x for lm in landmarks]
        ys = [lm.y for lm in landmarks]
        bbox_width = (max(xs) - min(xs)) or 1e-6
        bbox_height = (max(ys) - min(ys)) or 1e-6
        self.bbox_aspect_ratio_for_fall_detector = bbox_height / bbox_width
        self._centroid_history.append((hip_mid[0], hip_mid[1], timestamp_sec))

    def vertical_velocity(self) -> float:
        """
        Signed vertical velocity (positive = moving downward in image space),
        used by fall_detector to catch SUDDEN onset. Uses only the two most
        recent samples: averaging a one-frame drop over a window dilutes it
        below threshold.
        """
        if len(self._centroid_history) < 2:
            return 0.0
        (_, y_prev, t_prev) = self._centroid_history[-2]
        (_, y_curr, t_curr) = self._centroid_history[-1]
        dt = max(t_curr - t_prev, 1e-3)
        return (y_curr - y_prev) / dt

    def instantaneous_speed(self) -> float:
        """
        Unsigned movement speed from the two most recent samples — the
        correct signal for "is the patient still right now" (fall
        confirmation stillness check, inactivity timer).
        """
        if len(self._centroid_history) < 2:
            return 0.0
        (x_prev, y_prev, t_prev) = self._centroid_history[-2]
        (x_curr, y_curr, t_curr) = self._centroid_history[-1]
        dt = max(t_curr - t_prev, 1e-3)
        return math.hypot(x_curr - x_prev, y_curr - y_prev) / dt
