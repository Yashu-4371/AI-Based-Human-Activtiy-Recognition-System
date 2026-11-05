"""
PLACEHOLDER ONLY - synthetic feature rows, NOT real people.

This exists so the application can start and be demonstrated before real
multi-subject data has been collected/ingested. The per-class value ranges
below are hand-written approximations of the feature definitions in
app/ml/feature_extractor.py (they were NOT measured from real MediaPipe
output). A model trained on this data:
  * has no subjects, so it cannot be evaluated subject-wise;
  * scores ~100% on its own random split because the classes are generated
    to be separable - that number says NOTHING about real-world accuracy.
Train on real data (docs/activity_recognition.md) before trusting predictions.

Use:  python -m app.ml.train_model --synthetic
"""

import numpy as np
import pandas as pd

from app.ml.feature_extractor import FEATURE_NAMES

RANDOM_SEED = 42
SAMPLES_PER_CLASS = 1500


def _n(rng, mean, std, low, high, size):
    return np.clip(rng.normal(mean, std, size), low, high)


def _generate(rng, n, spec) -> pd.DataFrame:
    return pd.DataFrame({name: _n(rng, *spec[name], n) for name in FEATURE_NAMES})


# (mean, std, low, high) per feature. Wide stds on purpose (arms/legs vary a lot).
_SPECS = {
    "walking": {
        "left_elbow_angle": (140, 25, 60, 180), "right_elbow_angle": (140, 25, 60, 180),
        "left_knee_angle": (140, 25, 80, 180), "right_knee_angle": (140, 25, 80, 180),
        "left_hip_angle": (165, 12, 120, 180), "right_hip_angle": (165, 12, 120, 180),
        "torso_inclination_deg": (8, 6, 0, 30), "hip_ankle_distance_norm": (1.8, 0.25, 1.2, 2.5),
        "knee_hip_vertical_norm": (0.95, 0.2, 0.3, 1.5), "nose_hip_vertical_norm": (1.3, 0.2, 0.7, 1.9),
        "shoulder_width_norm": (0.9, 0.3, 0.2, 1.7), "ankle_spread_norm": (0.9, 0.4, 0.05, 2.0),
        "bbox_aspect_ratio": (2.5, 0.4, 1.5, 4.0), "centroid_velocity_norm": (1.0, 0.7, 0.1, 3.5),
    },
    "standing": {
        "left_elbow_angle": (160, 25, 60, 180), "right_elbow_angle": (160, 25, 60, 180),
        "left_knee_angle": (173, 7, 150, 180), "right_knee_angle": (173, 7, 150, 180),
        "left_hip_angle": (173, 7, 150, 180), "right_hip_angle": (173, 7, 150, 180),
        "torso_inclination_deg": (4, 4, 0, 20), "hip_ankle_distance_norm": (2.0, 0.2, 1.4, 2.6),
        "knee_hip_vertical_norm": (1.05, 0.15, 0.5, 1.5), "nose_hip_vertical_norm": (1.35, 0.2, 0.8, 1.9),
        "shoulder_width_norm": (0.9, 0.3, 0.2, 1.7), "ankle_spread_norm": (0.35, 0.2, 0.02, 1.2),
        "bbox_aspect_ratio": (2.8, 0.4, 1.7, 4.0), "centroid_velocity_norm": (0.06, 0.05, 0.0, 0.3),
    },
    "sitting": {
        "left_elbow_angle": (120, 35, 40, 180), "right_elbow_angle": (120, 35, 40, 180),
        "left_knee_angle": (100, 20, 60, 165), "right_knee_angle": (100, 20, 60, 165),
        "left_hip_angle": (105, 20, 60, 165), "right_hip_angle": (105, 20, 60, 165),
        "torso_inclination_deg": (14, 10, 0, 45), "hip_ankle_distance_norm": (1.2, 0.3, 0.5, 2.0),
        "knee_hip_vertical_norm": (0.2, 0.3, -0.5, 0.9), "nose_hip_vertical_norm": (1.25, 0.25, 0.6, 1.9),
        "shoulder_width_norm": (0.9, 0.3, 0.2, 1.7), "ankle_spread_norm": (0.45, 0.3, 0.02, 1.4),
        "bbox_aspect_ratio": (1.5, 0.35, 0.8, 2.6), "centroid_velocity_norm": (0.06, 0.05, 0.0, 0.3),
    },
    "lying": {
        "left_elbow_angle": (140, 35, 40, 180), "right_elbow_angle": (140, 35, 40, 180),
        "left_knee_angle": (150, 30, 50, 180), "right_knee_angle": (150, 30, 50, 180),
        "left_hip_angle": (160, 25, 60, 180), "right_hip_angle": (160, 25, 60, 180),
        "torso_inclination_deg": (75, 15, 30, 90), "hip_ankle_distance_norm": (1.8, 0.35, 0.6, 2.6),
        "knee_hip_vertical_norm": (0.0, 0.5, -1.2, 1.2), "nose_hip_vertical_norm": (0.0, 0.6, -1.5, 1.5),
        "shoulder_width_norm": (0.9, 0.35, 0.1, 1.9), "ankle_spread_norm": (0.5, 0.35, 0.02, 1.6),
        "bbox_aspect_ratio": (0.6, 0.3, 0.15, 1.6), "centroid_velocity_norm": (0.04, 0.04, 0.0, 0.25),
    },
}


def generate_dataset(samples_per_class: int = SAMPLES_PER_CLASS, seed: int = RANDOM_SEED) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    frames = []
    for label, spec in _SPECS.items():
        df = _generate(rng, samples_per_class, spec)
        df["activity_label"] = label
        frames.append(df)
    dataset = pd.concat(frames, ignore_index=True)[FEATURE_NAMES + ["activity_label"]]
    return dataset.sample(frac=1, random_state=seed).reset_index(drop=True)
