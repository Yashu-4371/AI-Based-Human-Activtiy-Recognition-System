from app.ml.fall_detector import FallDetector


def test_no_fall_when_standing_still():
    detector = FallDetector(torso_angle_threshold_deg=55, vertical_velocity_threshold=0.35, confirmation_window_sec=5)

    result = detector.update(
        torso_inclination_deg=3.0,
        vertical_velocity=0.01,
        bbox_aspect_ratio=3.0,  # tall/thin, standing
        centroid_velocity=0.01,
        timestamp_sec=0.0,
    )

    assert result is False
    assert detector.is_in_confirmed_fall_state() is False


def test_fall_confirmed_after_sudden_drop_and_stillness():
    detector = FallDetector(torso_angle_threshold_deg=55, vertical_velocity_threshold=0.35, confirmation_window_sec=2)

    # Frame 1: sudden drop meets the fall signature.
    result_frame_1 = detector.update(
        torso_inclination_deg=70.0,
        vertical_velocity=0.6,
        bbox_aspect_ratio=0.5,  # wide/short, lying
        centroid_velocity=0.5,
        timestamp_sec=0.0,
    )
    assert result_frame_1 is False  # not confirmed yet — confirmation window not elapsed

    # Frame 2: patient remains still for the confirmation window.
    result_frame_2 = detector.update(
        torso_inclination_deg=75.0,
        vertical_velocity=0.0,
        bbox_aspect_ratio=0.45,
        centroid_velocity=0.01,  # below stillness threshold
        timestamp_sec=2.5,  # elapsed = 2.5s >= confirmation_window_sec (2s)
    )

    assert result_frame_2 is True
    assert detector.is_in_confirmed_fall_state() is True


def test_no_false_positive_when_patient_gets_up_quickly():
    detector = FallDetector(torso_angle_threshold_deg=55, vertical_velocity_threshold=0.35, confirmation_window_sec=5)

    # Momentary bend/crouch that meets the raw signature briefly.
    detector.update(
        torso_inclination_deg=60.0,
        vertical_velocity=0.4,
        bbox_aspect_ratio=0.8,
        centroid_velocity=0.4,
        timestamp_sec=0.0,
    )

    # Patient immediately moves significantly again before the confirmation
    # window elapses (e.g., stood back up) — should reset, not confirm.
    result = detector.update(
        torso_inclination_deg=10.0,
        vertical_velocity=0.05,
        bbox_aspect_ratio=2.8,
        centroid_velocity=0.5,  # significant movement, not "still"
        timestamp_sec=1.0,
    )

    assert result is False
    assert detector.is_in_confirmed_fall_state() is False


def test_reset_clears_state():
    detector = FallDetector(torso_angle_threshold_deg=55, vertical_velocity_threshold=0.35, confirmation_window_sec=2)

    detector.update(
        torso_inclination_deg=70.0, vertical_velocity=0.6, bbox_aspect_ratio=0.5, centroid_velocity=0.5, timestamp_sec=0.0
    )
    detector.reset()

    assert detector.is_in_confirmed_fall_state() is False
