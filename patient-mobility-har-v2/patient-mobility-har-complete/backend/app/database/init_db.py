"""
Called once at application startup:
  1. Creates all tables if they don't already exist.
  2. Seeds a default admin user if the users table is empty, so the
     system is usable immediately after first install without a
     separate manual setup step.
  3. Seeds a default camera setting if none exists.
"""

from sqlalchemy.orm import Session

from app.database.session import Base, engine, SessionLocal
from app.config import settings
from app.utils.logger import get_logger

# Import every model so Base.metadata is aware of all tables before create_all().
from app.models.user import User, UserRole
from app.models.patient import Patient
from app.models.activity import Activity
from app.models.alert import Alert
from app.models.alert_email_delivery import AlertEmailDelivery  # noqa: F401  (new table; created by create_all)
from app.models.report import Report
from app.models.camera_setting import CameraSetting, CameraSourceType
from app.models.system_setting import SystemSetting
from app.models.log import Log
from app.models.caregiver import Caregiver
from app.models.monitoring_session import MonitoringSession

from app.services.auth_service import hash_password

logger = get_logger(__name__)


def _seed_default_admin(db: Session) -> None:
    existing_user = db.query(User).first()
    if existing_user:
        return

    admin = User(
        name=settings.DEFAULT_ADMIN_NAME,
        email=settings.DEFAULT_ADMIN_EMAIL,
        password_hash=hash_password(settings.DEFAULT_ADMIN_PASSWORD),
        role=UserRole.admin,
    )
    db.add(admin)
    db.commit()
    logger.info("Seeded default admin user: %s", settings.DEFAULT_ADMIN_EMAIL)


def _seed_default_camera(db: Session) -> None:
    existing_camera = db.query(CameraSetting).first()
    if existing_camera:
        return

    camera = CameraSetting(
        name="Default Camera",
        source_type=CameraSourceType.webcam,
        source_uri=settings.DEFAULT_CAMERA_SOURCE,
        resolution_width=640,
        resolution_height=480,
        is_active=True,
    )
    db.add(camera)
    db.commit()
    logger.info("Seeded default camera setting (source=%s)", settings.DEFAULT_CAMERA_SOURCE)


def _seed_default_system_settings(db: Session) -> None:
    defaults = {
        "fall_torso_angle_threshold_deg": str(settings.FALL_TORSO_ANGLE_THRESHOLD_DEG),
        "fall_vertical_velocity_threshold": str(settings.FALL_VERTICAL_VELOCITY_THRESHOLD),
        "fall_confirmation_window_sec": str(settings.FALL_CONFIRMATION_WINDOW_SEC),
        "inactivity_threshold_sec": str(settings.INACTIVITY_THRESHOLD_SEC),
        "alarm_sound_enabled": "true",
        "theme_default": "light",
    }
    for key, value in defaults.items():
        if not db.query(SystemSetting).filter(SystemSetting.key == key).first():
            db.add(SystemSetting(key=key, value=value))
    db.commit()


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables ensured (create_all complete).")

    db = SessionLocal()
    try:
        _seed_default_admin(db)
        _seed_default_camera(db)
        _seed_default_system_settings(db)
    finally:
        db.close()
