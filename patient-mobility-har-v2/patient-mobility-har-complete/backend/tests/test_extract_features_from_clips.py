"""
Verifies the clip -> training_features.csv pipeline end-to-end
(clip discovery, subject parsing, CSV/JSON output) without needing a
real camera or a real detectable person in the test video — MediaPipe
pose detection itself is monkeypatched to return a fixed, valid
landmark set, since that part is already covered by
test_feature_extractor.py and pose_estimator.py has no branching logic
worth re-testing here.
"""

import csv
import json

import cv2
import numpy as np
import pytest

from app.ml.data import extract_features_from_clips as pipeline
from app.ml.pose_estimator import Landmark


def _make_standing_landmarks():
    """33 landmarks in a rough standing pose (indices per pose_estimator.py)."""
    landmarks = [Landmark(x=0.5, y=0.5, z=0.0, visibility=1.0) for _ in range(33)]
    coords = {
        0: (0.5, 0.1),    # nose
        11: (0.45, 0.3), 12: (0.55, 0.3),   # shoulders
        13: (0.43, 0.45), 14: (0.57, 0.45),  # elbows
        15: (0.42, 0.6), 16: (0.58, 0.6),   # wrists
        23: (0.47, 0.55), 24: (0.53, 0.55),  # hips
        25: (0.47, 0.75), 26: (0.53, 0.75),  # knees
        27: (0.47, 0.95), 28: (0.53, 0.95),  # ankles
    }
    for idx, (x, y) in coords.items():
        landmarks[idx] = Landmark(x=x, y=y, z=0.0, visibility=1.0)
    return landmarks


def _write_dummy_clip(path, num_frames=6):
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 10, (64, 64))
    for _ in range(num_frames):
        writer.write(np.zeros((64, 64, 3), dtype=np.uint8))
    writer.release()


@pytest.fixture(autouse=True)
def _mock_pose_detection(monkeypatch):
    """Every frame 'detects' the same standing pose, regardless of pixel content."""
    landmarks = _make_standing_landmarks()
    monkeypatch.setattr(pipeline.PoseEstimator, "__init__", lambda self, **kwargs: None)
    monkeypatch.setattr(pipeline.PoseEstimator, "process", lambda self, frame_bgr: landmarks)
    monkeypatch.setattr(pipeline.PoseEstimator, "close", lambda self: None)


def test_build_dataset_end_to_end(tmp_path, monkeypatch):
    raw_clips_dir = tmp_path / "raw_clips"
    (raw_clips_dir / "standing").mkdir(parents=True)
    (raw_clips_dir / "walking").mkdir(parents=True)

    _write_dummy_clip(raw_clips_dir / "standing" / "s1_clip0.mp4")
    _write_dummy_clip(raw_clips_dir / "standing" / "s2_clip0.mp4")
    _write_dummy_clip(raw_clips_dir / "walking" / "s1_clip0.mp4")

    output_csv = tmp_path / "training_features.csv"
    dataset_info_json = tmp_path / "dataset_info.json"

    monkeypatch.setattr(pipeline, "RAW_CLIPS_DIR", raw_clips_dir)
    monkeypatch.setattr(pipeline, "OUTPUT_CSV", output_csv)
    monkeypatch.setattr(pipeline, "DATASET_INFO_JSON", dataset_info_json)

    pipeline.build_dataset(frame_stride=1)

    assert output_csv.exists()
    with open(output_csv, newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) > 0
    assert {row["activity_label"] for row in rows} == {"standing", "walking"}
    assert {row["subject_id"] for row in rows} == {"s1", "s2"}
    assert "left_elbow_angle" in rows[0]

    info = json.loads(dataset_info_json.read_text())
    assert info["num_clips"] == 3
    assert info["num_subjects"] == 2
    assert info["frames_per_label"]["standing"] > 0
    assert info["frames_per_label"]["walking"] > 0


def test_build_dataset_raises_when_no_clips(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, "RAW_CLIPS_DIR", tmp_path / "empty")
    with pytest.raises(SystemExit):
        pipeline.build_dataset()
