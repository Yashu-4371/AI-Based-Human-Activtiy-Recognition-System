"""
Aggregation queries used by both the /analytics API endpoints and the
report generator. Kept separate from activity_service since these are
read-only rollups, not core activity CRUD.
"""

from datetime import datetime, timedelta
from typing import Dict, List

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.activity import Activity, ActivityType
from app.models.alert import Alert, AlertType


def activity_distribution(db: Session, patient_id: int, date_from: datetime, date_to: datetime) -> Dict[str, float]:
    """Total seconds spent in each activity type within the window (for a pie chart)."""
    rows = (
        db.query(Activity.activity_type, func.sum(Activity.duration_sec))
        .filter(
            Activity.patient_id == patient_id,
            Activity.started_at >= date_from,
            Activity.started_at <= date_to,
            Activity.duration_sec.isnot(None),
        )
        .group_by(Activity.activity_type)
        .all()
    )
    result = {activity_type.value: 0.0 for activity_type in ActivityType}
    for activity_type, total_seconds in rows:
        result[activity_type.value] = float(total_seconds or 0.0)
    return result


def daily_activity_duration(db: Session, patient_id: int, days: int = 7) -> List[Dict]:
    """Per-day total active duration for the last N days (for a bar/line chart)."""
    start_date = datetime.utcnow() - timedelta(days=days)
    rows = (
        db.query(func.date(Activity.started_at), func.sum(Activity.duration_sec))
        .filter(
            Activity.patient_id == patient_id,
            Activity.started_at >= start_date,
            Activity.duration_sec.isnot(None),
        )
        .group_by(func.date(Activity.started_at))
        .order_by(func.date(Activity.started_at))
        .all()
    )
    return [{"date": str(day), "total_duration_sec": float(total or 0.0)} for day, total in rows]


def fall_frequency(db: Session, patient_id: int, days: int = 30) -> int:
    start_date = datetime.utcnow() - timedelta(days=days)
    return (
        db.query(func.count(Alert.id))
        .filter(Alert.patient_id == patient_id, Alert.type == AlertType.fall, Alert.created_at >= start_date)
        .scalar()
        or 0
    )


def average_walking_time_sec(db: Session, patient_id: int, days: int = 7) -> float:
    start_date = datetime.utcnow() - timedelta(days=days)
    total = (
        db.query(func.sum(Activity.duration_sec))
        .filter(
            Activity.patient_id == patient_id,
            Activity.activity_type == ActivityType.walking,
            Activity.started_at >= start_date,
            Activity.duration_sec.isnot(None),
        )
        .scalar()
        or 0.0
    )
    return float(total) / max(days, 1)
