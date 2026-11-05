"""
Converts 2D skeleton keypoints from other pose estimators into the 33-point
MediaPipe/BlazePose landmark list that FeatureExtractor expects, so public
skeleton-only datasets can be used WITHOUT a second feature representation.

Compatibility notes (documented conversion, not a claim of equivalence):

* The 13 "core" joints that all classifier features are computed from
  (nose, shoulders, elbows, wrists, hips, knees, ankles) exist in every
  supported format, so the 14 training features are computed from them by
  the same code as live inference.
* Landmarks that other formats lack (eyes/ears/mouth, fingers, heels, toes)
  are filled with the nearest available joint. The classifier features never
  read them; only the fall detector's all-landmark bounding box does, and the
  fall detector is not fed by training data.
* Different pose estimators have different keypoint noise/bias than
  MediaPipe. A model trained on converted skeletons is therefore trained on
  a slightly different noise distribution than it sees live. Mixing such data
  with real MediaPipe-extracted clips (and evaluating on MediaPipe-extracted
  held-out subjects) is the way to measure whether that matters.
* Formats with a neck but no shoulders-midpoint issue: shoulders are used
  directly; the neck is ignored. BODY_25 mid-hip is ignored (real hips used).
"""

from typing import Dict, List, Optional

import numpy as np

from app.ml.feature_extractor import CORE_JOINTS
from app.ml.pose_estimator import Landmark

# MediaPipe index -> keypoint index in the source format, for the 13 core joints.
_FORMATS: Dict[str, Dict[int, int]] = {
    "coco17": {0: 0, 11: 5, 12: 6, 13: 7, 14: 8, 15: 9, 16: 10, 23: 11, 24: 12, 25: 13, 26: 14, 27: 15, 28: 16},
    "openpose_coco18": {0: 0, 12: 2, 11: 5, 14: 3, 13: 6, 16: 4, 15: 7, 24: 8, 26: 9, 28: 10, 23: 11, 25: 12, 27: 13},
    "openpose_body25": {0: 0, 12: 2, 11: 5, 14: 3, 13: 6, 16: 4, 15: 7, 24: 9, 26: 10, 28: 11, 23: 12, 25: 13, 27: 14},
    "mediapipe33": {i: i for i in range(33)},
}
SUPPORTED_FORMATS = list(_FORMATS)
NUM_KEYPOINTS = {"coco17": 17, "openpose_coco18": 18, "openpose_body25": 25, "mediapipe33": 33}

# Filler landmarks (MediaPipe index -> core joint it copies).
_FILL = {**{i: 0 for i in range(1, 11)},           # eyes, ears, mouth -> nose
         **{i: 15 for i in (17, 19, 21)},          # left hand points -> left wrist
         **{i: 16 for i in (18, 20, 22)},          # right hand points -> right wrist
         **{i: 27 for i in (29, 31)},              # left heel/toe -> left ankle
         **{i: 28 for i in (30, 32)}}              # right heel/toe -> right ankle


def to_mediapipe_landmarks(
    keypoints: np.ndarray,
    fmt: str,
    width: float,
    height: float,
    normalized: bool = False,
    min_confidence: float = 0.1,
) -> Optional[List[Landmark]]:
    """
    keypoints: array (K, 2) or (K, 3) [x, y(, confidence)] for one person/frame.
    Returns None when any of the 13 core joints is missing (NaN, non-positive
    confidence below min_confidence, or exactly (0, 0) as OpenPose writes for
    undetected joints), because a partially-visible skeleton would yield
    garbage features.
    """
    if fmt not in _FORMATS:
        raise ValueError(f"Unsupported format {fmt!r}; choose from {SUPPORTED_FORMATS}")
    mapping = _FORMATS[fmt]
    kp = np.asarray(keypoints, dtype=float)
    if kp.ndim != 2 or kp.shape[0] < NUM_KEYPOINTS[fmt] or kp.shape[1] < 2:
        raise ValueError(f"Expected keypoints shape (>= {NUM_KEYPOINTS[fmt]}, >=2) for {fmt}, got {kp.shape}")

    landmarks: List[Optional[Landmark]] = [None] * 33
    for mp_idx in CORE_JOINTS:
        x, y = kp[mapping[mp_idx], 0], kp[mapping[mp_idx], 1]
        conf = kp[mapping[mp_idx], 2] if kp.shape[1] > 2 else 1.0
        if np.isnan(x) or np.isnan(y) or np.isnan(conf) or conf < min_confidence or (x == 0 and y == 0):
            return None
        nx, ny = (x, y) if normalized else (x / width, y / height)
        landmarks[mp_idx] = Landmark(x=float(nx), y=float(ny), z=0.0, visibility=float(min(conf, 1.0)))

    for mp_idx in range(33):
        if landmarks[mp_idx] is None:
            landmarks[mp_idx] = landmarks[_FILL.get(mp_idx, 0)]
    return landmarks  # type: ignore[return-value]
