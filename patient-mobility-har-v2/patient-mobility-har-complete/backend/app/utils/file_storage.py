"""
Resolves and creates file paths under the uploads directory.
Keeps all "where does this kind of file live on disk" logic in one place
so no other module hardcodes a path.
"""

import uuid
from pathlib import Path

from app.config import settings

PATIENT_PHOTOS_SUBDIR = "patient_photos"
ALERT_SCREENSHOTS_SUBDIR = "alert_screenshots"
REPORTS_SUBDIR = "reports"


def _ensure_subdir(subdir: str) -> Path:
    path = settings.upload_path / subdir
    path.mkdir(parents=True, exist_ok=True)
    return path


def new_patient_photo_path(original_filename: str) -> Path:
    ext = Path(original_filename).suffix or ".jpg"
    filename = f"{uuid.uuid4().hex}{ext}"
    return _ensure_subdir(PATIENT_PHOTOS_SUBDIR) / filename


def new_alert_screenshot_path() -> Path:
    filename = f"{uuid.uuid4().hex}.jpg"
    return _ensure_subdir(ALERT_SCREENSHOTS_SUBDIR) / filename


def new_report_path(patient_id: int, report_type: str, extension: str) -> Path:
    filename = f"patient_{patient_id}_{report_type}_{uuid.uuid4().hex[:8]}.{extension}"
    return _ensure_subdir(REPORTS_SUBDIR) / filename


def to_relative_url(absolute_path: Path) -> str:
    """Converts an absolute uploads path into a URL path served by the static mount."""
    relative = absolute_path.relative_to(settings.upload_path)
    return f"/uploads/{relative.as_posix()}"
