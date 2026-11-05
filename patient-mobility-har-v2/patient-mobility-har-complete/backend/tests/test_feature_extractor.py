import math

from app.ml.feature_extractor import FeatureExtractor, FEATURE_NAMES, FEATURE_INDEX, _angle_between, _euclidean
from app.ml.pose_estimator import Landmark, LEFT_SHOULDER, RIGHT_SHOULDER, LEFT_HIP, RIGHT_HIP, \
    LEFT_KNEE, RIGHT_KNEE, LEFT_ANKLE, RIGHT_ANKLE, LEFT_ELBOW, RIGHT_ELBOW, LEFT_WRIST, RIGHT_WRIST, NOSE


def _make_landmark(x: float, y: float) -> Landmark:
    return Landmark(x=x, y=y, z=0.0, visibility=1.0)


def _full_landmark_set() -> list:
    """Builds a 33-point landmark list representing a person standing upright,
    with all indices used by feature_extractor filled with plausible values."""
    landmarks = [_make_landmark(0.5, 0.5) for _ in range(33)]

    landmarks[NOSE] = _make_landmark(0.5, 0.10)
    landmarks[LEFT_SHOULDER] = _make_landmark(0.45, 0.25)
    landmarks[RIGHT_SHOULDER] = _make_landmark(0.55, 0.25)
    landmarks[LEFT_ELBOW] = _make_landmark(0.45, 0.40)
    landmarks[RIGHT_ELBOW] = _make_landmark(0.55, 0.40)
    landmarks[LEFT_WRIST] = _make_landmark(0.45, 0.55)
    landmarks[RIGHT_WRIST] = _make_landmark(0.55, 0.55)
    landmarks[LEFT_HIP] = _make_landmark(0.47, 0.55)
    landmarks[RIGHT_HIP] = _make_landmark(0.53, 0.55)
    landmarks[LEFT_KNEE] = _make_landmark(0.47, 0.75)
    landmarks[RIGHT_KNEE] = _make_landmark(0.53, 0.75)
    landmarks[LEFT_ANKLE] = _make_landmark(0.47, 0.95)
    landmarks[RIGHT_ANKLE] = _make_landmark(0.53, 0.95)

    return landmarks


def test_angle_between_straight_line_is_180_degrees():
    a = _make_landmark(0.0, 0.0)
    b = _make_landmark(0.5, 0.0)
    c = _make_landmark(1.0, 0.0)

    angle = _angle_between(a, b, c)

    assert math.isclose(angle, 180.0, abs_tol=1e-3)


def test_angle_between_right_angle_is_90_degrees():
    a = _make_landmark(0.0, 0.0)
    b = _make_landmark(0.0, 1.0)
    c = _make_landmark(1.0, 1.0)

    angle = _angle_between(a, b, c)

    assert math.isclose(angle, 90.0, abs_tol=1e-3)


def test_euclidean_distance():
    a = _make_landmark(0.0, 0.0)
    b = _make_landmark(3.0, 4.0)

    assert math.isclose(_euclidean(a, b), 5.0, abs_tol=1e-6)


def test_extract_returns_correct_length_feature_vector():
    extractor = FeatureExtractor()
    landmarks = _full_landmark_set()

    feature_vector = extractor.extract(landmarks, timestamp_sec=0.0)

    assert feature_vector is not None
    assert feature_vector.shape[0] == len(FEATURE_NAMES)


def test_standing_pose_has_low_torso_inclination():
    extractor = FeatureExtractor()
    landmarks = _full_landmark_set()  # shoulders directly above hips -> near-vertical torso

    feature_vector = extractor.extract(landmarks, timestamp_sec=0.0)

    torso_inclination_deg = feature_vector[FEATURE_INDEX["torso_inclination_deg"]]
    assert torso_inclination_deg < 15.0  # near-upright


def test_velocity_increases_with_movement_between_frames():
    extractor = FeatureExtractor()
    landmarks_frame_1 = _full_landmark_set()

    extractor.extract(landmarks_frame_1, timestamp_sec=0.0)

    landmarks_frame_2 = _full_landmark_set()
    # Shift hips significantly to simulate movement.
    landmarks_frame_2[LEFT_HIP] = _make_landmark(0.70, 0.55)
    landmarks_frame_2[RIGHT_HIP] = _make_landmark(0.76, 0.55)

    feature_vector = extractor.extract(landmarks_frame_2, timestamp_sec=0.2)

    centroid_velocity = feature_vector[FEATURE_INDEX["centroid_velocity_norm"]]
    assert centroid_velocity > 0.0
