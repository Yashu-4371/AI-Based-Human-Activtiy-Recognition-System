"""
Wraps MediaPipe Pose. Given a BGR frame (as read by OpenCV), returns
the 33 body landmarks (x, y, z, visibility — x/y normalized to [0,1]
relative to image width/height) or None if no person is detected.
"""

from pathlib import Path
from typing import List, NamedTuple, Optional

import cv2
import mediapipe as mp
import numpy as np


class Landmark(NamedTuple):
    x: float
    y: float
    z: float
    visibility: float


# MediaPipe Pose landmark indices used throughout feature extraction.
LEFT_SHOULDER, RIGHT_SHOULDER = 11, 12
LEFT_ELBOW, RIGHT_ELBOW = 13, 14
LEFT_WRIST, RIGHT_WRIST = 15, 16
LEFT_HIP, RIGHT_HIP = 23, 24
LEFT_KNEE, RIGHT_KNEE = 25, 26
LEFT_ANKLE, RIGHT_ANKLE = 27, 28
NOSE = 0


POSE_LANDMARKER_MODEL_FILENAME = "pose_landmarker_full.task"
POSE_LANDMARKER_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
    "pose_landmarker_full/float16/latest/pose_landmarker_full.task"
)


def _resolve_pose_model_path() -> Path:
    from app.config import settings

    return settings.models_path / POSE_LANDMARKER_MODEL_FILENAME


def download_pose_model(target: Optional[Path] = None) -> Path:
    """Downloads the official MediaPipe pose_landmarker_full model (only needed for MediaPipe
    builds that no longer ship the legacy mp.solutions.pose model)."""
    import urllib.request

    target = target or _resolve_pose_model_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(POSE_LANDMARKER_MODEL_URL, target)
    return target


class PoseEstimator:
    """
    Two interchangeable MediaPipe backends producing the same 33 BlazePose
    landmarks:
      * legacy  mp.solutions.pose            (older mediapipe wheels, bundled model)
      * tasks   mediapipe.tasks PoseLandmarker (newer wheels; needs
                models_store/pose_landmarker_full.task, auto-downloaded on first use)
    Recent mediapipe releases (including the version pinned in requirements.txt)
    no longer expose mp.solutions, so the Tasks backend is required there.
    """

    def __init__(self, min_detection_confidence: float = 0.5, min_tracking_confidence: float = 0.5):
        self.drawing_utils = None
        self.pose_connections = None
        self._backend = None
        self._last_timestamp_ms = 0

        if hasattr(mp, "solutions") and hasattr(mp.solutions, "pose"):
            self._backend = "legacy"
            self._mp_pose = mp.solutions.pose
            self._pose = self._mp_pose.Pose(
                static_image_mode=False,
                model_complexity=1,
                min_detection_confidence=min_detection_confidence,
                min_tracking_confidence=min_tracking_confidence,
            )
            self.drawing_utils = mp.solutions.drawing_utils
            self.pose_connections = self._mp_pose.POSE_CONNECTIONS
            return

        from mediapipe.tasks import python as mp_tasks
        from mediapipe.tasks.python import vision

        model_path = _resolve_pose_model_path()
        if not model_path.exists():
            try:
                download_pose_model(model_path)
            except Exception as exc:  # network blocked, offline, etc.
                raise RuntimeError(
                    f"This mediapipe build has no mp.solutions.pose and the pose model {model_path} "
                    f"is missing and could not be downloaded ({exc}). Download {POSE_LANDMARKER_MODEL_URL} "
                    f"manually into that path, or `pip install mediapipe==0.10.14` to use the legacy backend."
                ) from exc

        self._backend = "tasks"
        options = vision.PoseLandmarkerOptions(
            base_options=mp_tasks.BaseOptions(model_asset_path=str(model_path)),
            running_mode=vision.RunningMode.VIDEO,
            num_poses=1,
            min_pose_detection_confidence=min_detection_confidence,
            min_pose_presence_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )
        self._pose = vision.PoseLandmarker.create_from_options(options)

    def process(self, frame_bgr: np.ndarray) -> Optional[List[Landmark]]:
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)

        if self._backend == "legacy":
            frame_rgb.flags.writeable = False
            results = self._pose.process(frame_rgb)
            if not results.pose_landmarks:
                return None
            return [
                Landmark(x=lm.x, y=lm.y, z=lm.z, visibility=lm.visibility)
                for lm in results.pose_landmarks.landmark
            ]

        # Tasks API requires strictly increasing timestamps in VIDEO mode.
        self._last_timestamp_ms += 33
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(frame_rgb))
        result = self._pose.detect_for_video(image, self._last_timestamp_ms)
        if not result.pose_landmarks:
            return None
        return [
            Landmark(x=lm.x, y=lm.y, z=lm.z, visibility=lm.visibility if lm.visibility is not None else 1.0)
            for lm in result.pose_landmarks[0]
        ]

    def close(self) -> None:
        self._pose.close()
