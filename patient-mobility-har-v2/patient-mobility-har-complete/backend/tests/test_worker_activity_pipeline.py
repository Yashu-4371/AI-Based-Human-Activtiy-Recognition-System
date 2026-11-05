"""Drives MonitoringWorker._process_frame with a mocked pose + stub classifier (no camera, no DB)."""

import numpy as np
import pytest

from app.ml.feature_extractor import FeatureExtractor
from app.pipeline import monitoring_worker as mw
from tests.test_activity_recognition import _landmarks, _p


class StubClassifier:
    def __init__(self):
        self.label = "standing"

    def predict_proba(self, _vec):
        return _p(self.label, 0.9)


class SpyFallDetector:
    def __init__(self):
        self.calls = []

    def update(self, **kw):
        self.calls.append(kw)
        return False

    def is_in_confirmed_fall_state(self):
        return False


class QuietInactivity:
    def update(self, **_kw):
        return False

    def is_warning_active(self):
        return False


class FakePose:
    def __init__(self):
        self.landmarks = None

    def process(self, _frame):
        return self.landmarks


@pytest.fixture
def worker(monkeypatch):
    stub = StubClassifier()
    monkeypatch.setattr(mw, "activity_classifier", stub)
    captured = {}
    monkeypatch.setattr(mw.live_frame_buffer, "update", lambda **kw: captured.update(kw))
    w = mw.MonitoringWorker()
    monkeypatch.setattr(w, "_sync_activity_segment", lambda *a, **k: captured.setdefault("synced", []).append(a))
    monkeypatch.setattr(w, "_raise_alert", lambda *a, **k: None)
    return w, stub, captured


def test_smoothed_label_reaches_live_buffer_and_fall_signals_are_unchanged(worker, monkeypatch):
    w, stub, captured = worker
    clock = {"t": 1000.0}
    monkeypatch.setattr(mw.time, "time", lambda: clock["t"])
    pose, extractor, fall = FakePose(), FeatureExtractor(), SpyFallDetector()
    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    pose.landmarks = _landmarks(aspect=640 / 480)
    for _ in range(12):
        w._process_frame(frame, pose, extractor, fall, QuietInactivity())
        clock["t"] += 0.1
    assert captured["activity_label"] == "standing" and captured["confidence"] > 0.6
    assert captured["synced"], "activity segment should be recorded once confident"

    # person lies down: the label follows within about one smoothing window, not instantly
    stub.label = "lying"
    pose.landmarks = _landmarks(rotate_deg=90, aspect=640 / 480)
    labels = []
    for _ in range(15):
        w._process_frame(frame, pose, extractor, fall, QuietInactivity())
        labels.append(captured["activity_label"])
        clock["t"] += 0.1
    assert labels[0] == "standing" and labels[-1] == "lying"
    assert labels.index("lying") <= 8  # switches in <= ~0.8 s

    last = fall.calls[-1]
    assert set(last) == {"torso_inclination_deg", "vertical_velocity", "bbox_aspect_ratio",
                         "centroid_velocity", "timestamp_sec"}
    assert last["torso_inclination_deg"] > 80  # lying torso, original unscaled definition


def test_no_person_resets_state_and_shows_no_activity(worker, monkeypatch):
    w, stub, captured = worker
    pose, extractor = FakePose(), FeatureExtractor()
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    pose.landmarks = None
    w._process_frame(frame, pose, extractor, SpyFallDetector(), QuietInactivity())
    assert captured["activity_label"] is None and captured["skeleton_points"] == []
