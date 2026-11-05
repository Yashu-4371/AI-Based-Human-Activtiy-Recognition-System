"""
Logic tests for the activity-recognition improvements. The skeletons built here are
geometric test fixtures used ONLY to verify code behaviour (invariances, splitting,
conversion). They are never written to the training set and prove nothing about
real-world accuracy.
"""

import json

import numpy as np
import pandas as pd
import pytest

from app.config import settings
from app.ml import train_model
from app.ml.activity_smoother import ActivitySmoother
from app.ml.data import dataset_io, ingest_skeleton_dataset as ingest
from app.ml.data.skeleton_adapters import to_mediapipe_landmarks
from app.ml.feature_extractor import FEATURE_INDEX, FEATURE_NAMES, FeatureExtractor
from app.ml.pose_estimator import (
    Landmark, NOSE, LEFT_SHOULDER, RIGHT_SHOULDER, LEFT_ELBOW, RIGHT_ELBOW, LEFT_WRIST, RIGHT_WRIST,
    LEFT_HIP, RIGHT_HIP, LEFT_KNEE, RIGHT_KNEE, LEFT_ANKLE, RIGHT_ANKLE,
)

JOINTS = {
    NOSE: (0.0, -1.35), LEFT_SHOULDER: (-0.5, -1.0), RIGHT_SHOULDER: (0.5, -1.0),
    LEFT_ELBOW: (-0.55, -0.5), RIGHT_ELBOW: (0.55, -0.5), LEFT_WRIST: (-0.55, 0.0), RIGHT_WRIST: (0.55, 0.0),
    LEFT_HIP: (-0.25, 0.0), RIGHT_HIP: (0.25, 0.0), LEFT_KNEE: (-0.25, 1.0), RIGHT_KNEE: (0.25, 1.0),
    LEFT_ANKLE: (-0.25, 2.0), RIGHT_ANKLE: (0.25, 2.0),
}


def _landmarks(scale=1.0, offset=(0.5, 0.4), rotate_deg=0.0, aspect=1.0):
    """Body-unit skeleton -> normalized landmarks of an image with the given aspect (w/h)."""
    th = np.radians(rotate_deg)
    rot = np.array([[np.cos(th), -np.sin(th)], [np.sin(th), np.cos(th)]])
    lms = [Landmark(0.5, 0.5, 0.0, 1.0)] * 33
    lms = list(lms)
    for idx, (x, y) in JOINTS.items():
        px, py = rot @ np.array([x, y]) * scale * 0.2
        lms[idx] = Landmark(offset[0] + px / aspect, offset[1] + py, 0.0, 1.0)
    return lms


def _feat(lms, t=0.0, aspect=1.0):
    return dict(zip(FEATURE_NAMES, FeatureExtractor().extract(lms, t, aspect)))


# ---------------- features ----------------

def test_features_invariant_to_distance_and_position():
    near = _feat(_landmarks(scale=1.4, offset=(0.4, 0.3)))
    far = _feat(_landmarks(scale=0.6, offset=(0.6, 0.5)))
    for name in FEATURE_NAMES:
        assert near[name] == pytest.approx(far[name], abs=1e-3), name


def test_aspect_ratio_correction_recovers_true_geometry():
    square = _feat(_landmarks(aspect=1.0), aspect=1.0)
    wide = _feat(_landmarks(aspect=16 / 9), aspect=16 / 9)
    for name in FEATURE_NAMES:
        assert square[name] == pytest.approx(wide[name], abs=1e-3), name


def test_lying_differs_from_standing_in_orientation_features():
    stand = _feat(_landmarks())
    lying = _feat(_landmarks(rotate_deg=90))
    assert stand["torso_inclination_deg"] < 5 and lying["torso_inclination_deg"] > 80
    assert stand["nose_hip_vertical_norm"] > 1.0 and abs(lying["nose_hip_vertical_norm"]) < 0.3
    assert stand["bbox_aspect_ratio"] > 1.0 > lying["bbox_aspect_ratio"]


def test_velocity_is_scale_and_fps_independent():
    def run(scale, dt):
        ex = FeatureExtractor()
        v = 0.0
        for i in range(30):  # person walks sideways at 2 torso-lengths / second
            t = i * dt
            torso = 1.0 * scale * 0.2
            lms = _landmarks(scale=scale, offset=(0.2 + 2.0 * torso * t, 0.4))
            v = ex.extract(lms, t)[FEATURE_INDEX["centroid_velocity_norm"]]
        return v

    assert run(1.0, 1 / 30) == pytest.approx(2.0, rel=0.05)
    assert run(0.5, 1 / 30) == pytest.approx(run(1.0, 1 / 15), rel=0.05)


def test_degenerate_torso_returns_none():
    lms = _landmarks()
    lms[LEFT_SHOULDER] = lms[LEFT_HIP]
    lms[RIGHT_SHOULDER] = lms[RIGHT_HIP]
    assert FeatureExtractor().extract(lms, 0.0) is None


def test_fall_detector_signals_keep_original_definitions():
    lms = _landmarks(rotate_deg=90)
    ex = FeatureExtractor()
    ex.extract(lms, 0.0, aspect_ratio=1.7)  # aspect correction must NOT leak into fall signals
    sh = ((lms[LEFT_SHOULDER].x + lms[RIGHT_SHOULDER].x) / 2, (lms[LEFT_SHOULDER].y + lms[RIGHT_SHOULDER].y) / 2)
    hp = ((lms[LEFT_HIP].x + lms[RIGHT_HIP].x) / 2, (lms[LEFT_HIP].y + lms[RIGHT_HIP].y) / 2)
    expected = np.degrees(np.arctan2(abs(sh[0] - hp[0]), abs(sh[1] - hp[1]) or 1e-6))
    assert ex.torso_inclination_for_fall_detector == pytest.approx(expected)
    xs, ys = [l.x for l in lms], [l.y for l in lms]
    assert ex.bbox_aspect_ratio_for_fall_detector == pytest.approx((max(ys) - min(ys)) / (max(xs) - min(xs)))


# ---------------- smoother ----------------

def _p(label, conf=0.9):
    others = [l for l in ("walking", "standing", "sitting", "lying") if l != label]
    return {label: conf, **{o: (1 - conf) / 3 for o in others}}


def test_smoother_ignores_single_frame_glitch_but_follows_sustained_change():
    s = ActivitySmoother(window_sec=1.0)
    t = 0.0
    for _ in range(15):
        out = s.update(_p("standing"), t); t += 0.1
    assert out[0] == "standing"
    assert s.update(_p("walking"), t)[0] == "standing"  # one-frame glitch ignored
    t += 0.1
    for _ in range(12):
        out = s.update(_p("walking"), t); t += 0.1
    assert out[0] == "walking"  # real change goes through within about a window


def test_smoother_returns_none_when_never_confident_and_resets_after_gap():
    s = ActivitySmoother(min_confidence=0.6)
    assert s.update({"walking": 0.3, "standing": 0.3, "sitting": 0.2, "lying": 0.2}, 0.0) is None
    for i in range(10):
        s.update(_p("sitting"), 1.0 + i * 0.1)
    assert s.update(_p("lying"), 10.0)[0] == "lying"  # gap > max_gap -> old state discarded


# ---------------- adapters / ingestion ----------------

def _coco_from_landmarks(lms, w, h):
    kp = np.zeros((17, 3))
    order = {0: NOSE, 5: LEFT_SHOULDER, 6: RIGHT_SHOULDER, 7: LEFT_ELBOW, 8: RIGHT_ELBOW, 9: LEFT_WRIST,
             10: RIGHT_WRIST, 11: LEFT_HIP, 12: RIGHT_HIP, 13: LEFT_KNEE, 14: RIGHT_KNEE, 15: LEFT_ANKLE,
             16: RIGHT_ANKLE}
    for k, mp_i in order.items():
        kp[k] = (lms[mp_i].x * w, lms[mp_i].y * h, 0.9)
    return kp


def test_coco17_conversion_gives_same_features_as_native_landmarks():
    w, h = 640, 480
    native = _landmarks(aspect=w / h)
    converted = to_mediapipe_landmarks(_coco_from_landmarks(native, w, h), "coco17", w, h)
    a, b = _feat(native, aspect=w / h), _feat(converted, aspect=w / h)
    for name in FEATURE_NAMES:
        assert a[name] == pytest.approx(b[name], abs=1e-4), name


def test_conversion_rejects_missing_core_joint():
    kp = _coco_from_landmarks(_landmarks(), 640, 480)
    kp[13] = (0, 0, 0.0)  # OpenPose writes (0,0,0) for undetected joints
    assert to_mediapipe_landmarks(kp, "coco17", 640, 480) is None
    with pytest.raises(ValueError):
        to_mediapipe_landmarks(kp, "nope", 640, 480)


def _skeleton_df(w=640, h=480):
    rows = []
    for subject, activity, rot in [("p1", "walk", 0), ("p1", "lay", 90), ("p2", "walk", 0), ("p2", "jump", 0)]:
        for frame in range(6):
            kp = _coco_from_landmarks(_landmarks(rotate_deg=rot, aspect=w / h, offset=(0.3 + 0.02 * frame, 0.4)), w, h)
            r = {"subject": subject, "clip": f"{subject}_{activity}", "frame": frame, "activity": activity}
            for k in range(17):
                r.update({f"kp{k}_x": kp[k, 0], f"kp{k}_y": kp[k, 1], f"kp{k}_c": kp[k, 2]})
            rows.append(r)
    return pd.DataFrame(rows)


def test_ingest_maps_labels_drops_unmapped_and_namespaces_subjects():
    rows, stats = ingest.convert_dataframe(
        _skeleton_df(), "toyset", "coco17", 640, 480, 15.0, {"walk": "walking", "lay": "lying"}
    )
    assert {r["activity_label"] for r in rows} == {"walking", "lying"}
    assert {r["subject_id"] for r in rows} == {"toyset-p1", "toyset-p2"}
    assert stats["dropped_activity_frames"] == {"jump": 6}  # unmapped activity dropped, never guessed
    assert all(r["source_dataset"] == "toyset" and "timestamp_sec" in r for r in rows)
    lying = [r for r in rows if r["activity_label"] == "lying"]
    assert all(r["torso_inclination_deg"] > 80 for r in lying)


def test_merge_replaces_only_own_source(tmp_path):
    csv_path = tmp_path / "t.csv"
    def row(src, subj):
        r = {n: 0.0 for n in FEATURE_NAMES}
        r.update(activity_label="walking", subject_id=subj, source_dataset=src, source_clip="c", frame_index=0, timestamp_sec=0.0)
        return r
    dataset_io.merge_source_into_csv(csv_path, [row("a", "a-1")], "a")
    dataset_io.merge_source_into_csv(csv_path, [row("b", "b-1"), row("b", "b-2")], "b")
    dataset_io.merge_source_into_csv(csv_path, [row("a", "a-9")], "a")  # re-ingest a
    df = pd.read_csv(csv_path)
    assert sorted(df.subject_id) == ["a-9", "b-1", "b-2"]


# ---------------- training / evaluation logic ----------------

def _fake_multi_subject_csv(path, n_subjects):
    """Test fixture ONLY: per-'subject' jittered draws of the synthetic generator, to exercise the
    splitting/reporting code. Not real data; never used outside tests."""
    from app.ml.data.generate_synthetic_data import generate_dataset
    frames = []
    for i in range(n_subjects):
        d = generate_dataset(samples_per_class=60, seed=100 + i)
        d["subject_id"] = f"t{i}"
        d["source_dataset"] = "toy"
        d["source_clip"] = d["activity_label"] + f"_t{i}"
        d["frame_index"] = range(len(d))
        d["timestamp_sec"] = d.groupby("source_clip").cumcount() / 15.0
        frames.append(d)
    pd.concat(frames, ignore_index=True).to_csv(path, index=False)


@pytest.fixture
def isolated_training(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "MODELS_DIR", str(tmp_path / "models"))
    monkeypatch.setattr(train_model, "DATA_PATH", tmp_path / "training_features.csv")
    monkeypatch.setattr(train_model, "DATASET_INFO_PATH", tmp_path / "dataset_info.json")
    return tmp_path


def test_train_refuses_to_silently_use_synthetic_data(isolated_training):
    with pytest.raises(SystemExit):
        train_model.train(synthetic=False)


def test_synthetic_run_is_flagged_as_no_evidence(isolated_training):
    m = train_model.train(synthetic=True)
    assert m["data_source"] == "synthetic" and m["generalization_evidence"] == "none_synthetic"
    assert m["n_subjects"] == 0 and m["limitations"]


def test_subject_wise_holdout_never_leaks_subjects(isolated_training):
    _fake_multi_subject_csv(train_model.DATA_PATH, 10)
    m = train_model.train(synthetic=False)
    assert m["split_method"] == "subject_wise_holdout" and m["generalization_evidence"] == "subject_wise_holdout"
    assert m["test_subjects"] and not set(m["test_subjects"]) & set(m["train_subjects"])
    assert len(m["test_subjects"]) + len(m["train_subjects"]) == 10
    assert m["n_train_samples"] + m["n_test_samples"] == m["n_total_samples"]
    assert m["evaluation"]["validation_loso"]["per_held_out_subject_accuracy"]
    assert m["evaluation"]["smoothing_offline"]["window_sec"] == settings.ACTIVITY_SMOOTHING_WINDOW_SEC
    saved = json.loads((isolated_training / "models" / "metrics.json").read_text())
    assert saved["feature_names"] == FEATURE_NAMES


def test_few_subjects_reported_as_limited_and_single_subject_as_no_evidence(isolated_training):
    _fake_multi_subject_csv(train_model.DATA_PATH, 3)
    m = train_model.train(synthetic=False)
    assert m["generalization_evidence"] == "subject_wise_cv_limited" and m["test_subjects"] == []
    assert any("Only 3 subjects" in l for l in m["limitations"])
    _fake_multi_subject_csv(train_model.DATA_PATH, 1)
    m = train_model.train(synthetic=False)
    assert m["generalization_evidence"] == "none_random_split"
    assert any("Single subject" in l for l in m["limitations"])


def test_classifier_refuses_model_with_wrong_feature_count(tmp_path, monkeypatch):
    import joblib
    from sklearn.ensemble import RandomForestClassifier
    from app.ml.activity_classifier import ActivityClassifier, MODEL_FILENAME

    monkeypatch.setattr(settings, "MODELS_DIR", str(tmp_path))
    rf = RandomForestClassifier(n_estimators=3).fit(np.random.rand(20, 12), ["lying", "sitting"] * 10)
    joblib.dump(rf, tmp_path / MODEL_FILENAME)
    assert not ActivityClassifier().is_ready()
