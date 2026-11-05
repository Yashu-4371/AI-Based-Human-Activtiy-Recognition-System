"""
The continuous monitoring loop: pulls a frame, runs pose estimation,
feature extraction, activity classification, fall/inactivity detection,
persists activity-segment/alert changes, and updates the shared
FrameBuffer that the WebSocket route streams to the frontend.

Runs in a background thread (OpenCV/MediaPipe calls are blocking, so a
thread — not an asyncio coroutine — is the correct concurrency primitive
here) started/stopped via the /camera API.
"""

import threading
import time
from typing import Optional

import cv2

from app.camera.camera_manager import CameraManager
from app.camera.frame_buffer import live_frame_buffer
from app.database.session import SessionLocal
from app.ml.pose_estimator import PoseEstimator
from app.ml.feature_extractor import FeatureExtractor
from app.ml.activity_classifier import activity_classifier
from app.ml.fall_detector import FallDetector
from app.ml.activity_smoother import ActivitySmoother
from app.ml.inactivity_detector import InactivityDetector
from app.models.camera_setting import CameraSetting
from app.models.patient import Patient
from app.models.alert import AlertType, AlertPriority
from app.models.activity import ActivityType
from app.services.activity_service import open_activity_segment, get_open_segment, close_activity_segment
from app.services.alert_service import create_alert
from app.services import system_settings_service
from app.services import monitoring_session_service
from app.utils.file_storage import new_alert_screenshot_path, to_relative_url
from app.utils.logger import get_logger
from app.config import settings

logger = get_logger(__name__)


class MonitoringWorker:
    def __init__(self):
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._active_patient_id: Optional[int] = None
        self._active_camera_setting: Optional[CameraSetting] = None
        self._active_session_id: Optional[int] = None
        self._activity_smoother = self._new_activity_smoother()

    @staticmethod
    def _new_activity_smoother() -> ActivitySmoother:
        return ActivitySmoother(
            window_sec=settings.ACTIVITY_SMOOTHING_WINDOW_SEC,
            min_confidence=settings.ACTIVITY_CONFIDENCE_MIN,
            switch_margin=settings.ACTIVITY_SWITCH_MARGIN,
        )

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self, patient_id: int, camera_setting: CameraSetting) -> bool:
        if self.is_running():
            logger.warning("Monitoring worker already running — ignoring start request.")
            return False

        self._active_patient_id = patient_id
        self._active_camera_setting = camera_setting
        self._stop_event.clear()

        db = SessionLocal()
        try:
            session = monitoring_session_service.open_session(db, patient_id, camera_setting.id)
            self._active_session_id = session.id
        finally:
            db.close()

        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("Monitoring worker started for patient_id=%s (session_id=%s)", patient_id, self._active_session_id)
        return True

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
        self._thread = None
        live_frame_buffer.update(camera_connected=False)

        if self._active_session_id is not None:
            db = SessionLocal()
            try:
                monitoring_session_service.close_session(db, self._active_session_id)
                if self._active_patient_id is not None:
                    open_segment = get_open_segment(db, self._active_patient_id)
                    if open_segment is not None:
                        close_activity_segment(db, open_segment)
            finally:
                db.close()
            self._active_session_id = None

        logger.info("Monitoring worker stopped.")

    def _build_detectors(self):
        """
        Reads the current fall/inactivity thresholds from the SystemSetting
        table (stored via the /settings API; the Settings page was removed from the UI, so the seeded values apply) rather than only
        the static .env defaults, so a threshold change actually takes
        effect the next time monitoring is started — not just in the UI.
        Falls back to app/config.py defaults if a DB row is missing.
        """
        db = SessionLocal()
        try:
            fall_detector = FallDetector(
                torso_angle_threshold_deg=system_settings_service.get_float(
                    db, "fall_torso_angle_threshold_deg", settings.FALL_TORSO_ANGLE_THRESHOLD_DEG
                ),
                vertical_velocity_threshold=system_settings_service.get_float(
                    db, "fall_vertical_velocity_threshold", settings.FALL_VERTICAL_VELOCITY_THRESHOLD
                ),
                confirmation_window_sec=system_settings_service.get_float(
                    db, "fall_confirmation_window_sec", settings.FALL_CONFIRMATION_WINDOW_SEC
                ),
            )
            inactivity_detector = InactivityDetector(
                threshold_sec=system_settings_service.get_float(
                    db, "inactivity_threshold_sec", settings.INACTIVITY_THRESHOLD_SEC
                ),
            )
            logger.info(
                "Detectors configured from system settings: fall_angle=%.1f fall_velocity=%.2f "
                "fall_window=%.1fs inactivity=%.0fs",
                fall_detector.torso_angle_threshold_deg,
                fall_detector.vertical_velocity_threshold,
                fall_detector.confirmation_window_sec,
                inactivity_detector.threshold_sec,
            )
            return fall_detector, inactivity_detector
        finally:
            db.close()

    def _run_loop(self) -> None:
        camera = CameraManager(
            source_type=self._active_camera_setting.source_type,
            source_uri=self._active_camera_setting.source_uri,
            width=self._active_camera_setting.resolution_width,
            height=self._active_camera_setting.resolution_height,
        )

        if not camera.open():
            live_frame_buffer.update(camera_connected=False)
            return

        pose_estimator = PoseEstimator()
        feature_extractor = FeatureExtractor()
        self._activity_smoother = self._new_activity_smoother()
        fall_detector, inactivity_detector = self._build_detectors()

        target_frame_interval = 1.0 / max(settings.CAMERA_TARGET_FPS, 1)
        frame_count = 0
        fps_window_start = time.time()

        try:
            while not self._stop_event.is_set():
                loop_start = time.time()
                frame = camera.read_frame()

                if frame is None:
                    live_frame_buffer.update(camera_connected=False)
                    time.sleep(0.5)
                    continue

                live_frame_buffer.update(camera_connected=True)
                self._process_frame(frame, pose_estimator, feature_extractor, fall_detector, inactivity_detector)

                frame_count += 1
                elapsed_window = time.time() - fps_window_start
                if elapsed_window >= 1.0:
                    live_frame_buffer.update(fps=frame_count / elapsed_window)
                    frame_count = 0
                    fps_window_start = time.time()

                sleep_time = target_frame_interval - (time.time() - loop_start)
                if sleep_time > 0:
                    time.sleep(sleep_time)
        finally:
            pose_estimator.close()
            camera.release()

    def _process_frame(self, frame, pose_estimator, feature_extractor, fall_detector, inactivity_detector) -> None:
        timestamp_sec = time.time()
        landmarks = pose_estimator.process(frame)

        skeleton_points = []
        activity_label = None
        confidence = 0.0
        fall_confirmed = False
        inactivity_warning = False

        if landmarks is not None:
            skeleton_points = [(lm.x, lm.y) for lm in landmarks]
            frame_h, frame_w = frame.shape[:2]
            feature_vector = feature_extractor.extract(landmarks, timestamp_sec, frame_w / max(frame_h, 1))

            if feature_vector is not None:
                probabilities = activity_classifier.predict_proba(feature_vector)
                if probabilities is not None:
                    prediction = self._activity_smoother.update(probabilities, timestamp_sec)
                    if prediction is not None:
                        activity_label, confidence = prediction

                # Fall/inactivity detection keeps its original signal definitions.
                torso_inclination_deg = feature_extractor.torso_inclination_for_fall_detector
                bbox_aspect_ratio = feature_extractor.bbox_aspect_ratio_for_fall_detector
                vertical_velocity = feature_extractor.vertical_velocity()
                instantaneous_speed = feature_extractor.instantaneous_speed()

                fall_confirmed = fall_detector.update(
                    torso_inclination_deg=torso_inclination_deg,
                    vertical_velocity=vertical_velocity,
                    bbox_aspect_ratio=bbox_aspect_ratio,
                    centroid_velocity=instantaneous_speed,
                    timestamp_sec=timestamp_sec,
                )

                if activity_label is not None:
                    inactivity_warning = inactivity_detector.update(
                        centroid_velocity=instantaneous_speed,
                        activity_label=activity_label,
                        timestamp_sec=timestamp_sec,
                    )
        else:
            feature_extractor.reset()
            self._activity_smoother.reset()

        _, jpeg_buffer = cv2.imencode(".jpg", frame)

        live_frame_buffer.update(
            jpeg_bytes=jpeg_buffer.tobytes(),
            skeleton_points=skeleton_points,
            activity_label=activity_label,
            confidence=confidence,
            fall_detected=fall_detector.is_in_confirmed_fall_state(),
            inactivity_warning=inactivity_detector.is_warning_active(),
        )

        if activity_label is not None and confidence >= settings.ACTIVITY_CONFIDENCE_MIN:
            self._sync_activity_segment(activity_label, confidence)

        if fall_confirmed:
            self._raise_alert(AlertType.fall, AlertPriority.critical, "Fall detected and confirmed.", frame)

        if inactivity_warning:
            self._raise_alert(
                AlertType.inactivity,
                AlertPriority.warning,
                f"No significant movement for over {settings.INACTIVITY_THRESHOLD_SEC:.0f} seconds.",
                frame,
            )

    def _sync_activity_segment(self, activity_label: str, confidence: float) -> None:
        db = SessionLocal()
        try:
            open_segment = get_open_segment(db, self._active_patient_id)
            if open_segment is None or open_segment.activity_type.value != activity_label:
                open_activity_segment(
                    db,
                    patient_id=self._active_patient_id,
                    camera_id=self._active_camera_setting.id,
                    activity_type=ActivityType(activity_label),
                    confidence=confidence,
                )
        finally:
            db.close()

    def _raise_alert(self, alert_type: AlertType, priority: AlertPriority, message: str, frame) -> None:
        db = SessionLocal()
        try:
            patient = db.query(Patient).filter(Patient.id == self._active_patient_id).first()
            if patient is None:
                return

            screenshot_path = new_alert_screenshot_path()
            cv2.imwrite(str(screenshot_path), frame)

            create_alert(
                db,
                patient=patient,
                alert_type=alert_type,
                priority=priority,
                message=message,
                screenshot_path=to_relative_url(screenshot_path),
            )
        finally:
            db.close()


# Module-level singleton — one active monitoring session per backend process.
monitoring_worker = MonitoringWorker()
