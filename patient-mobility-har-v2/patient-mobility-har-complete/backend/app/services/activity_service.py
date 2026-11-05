"""
Activity business logic. Handles both:
  1. Read queries used by the API (current activity, history).
  2. Segment open/close logic invoked internally by the monitoring
     pipeline whenever the classified activity changes.
"""

from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.activity import Activity, ActivityType
from app.utils.logger import get_logger

logger = get_logger(__name__)


def get_history(
    db: Session,
    patient_id: int,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    limit: int = 200,
) -> List[Activity]:
    query = db.query(Activity).filter(Activity.patient_id == patient_id)
    if date_from:
        query = query.filter(Activity.started_at >= date_from)
    if date_to:
        query = query.filter(Activity.started_at <= date_to)
    return query.order_by(Activity.started_at.desc()).limit(limit).all()


def get_open_segment(db: Session, patient_id: int) -> Optional[Activity]:
    return (
        db.query(Activity)
        .filter(Activity.patient_id == patient_id, Activity.ended_at.is_(None))
        .order_by(Activity.started_at.desc())
        .first()
    )


def open_activity_segment(
    db: Session, patient_id: int, camera_id: Optional[int], activity_type: ActivityType, confidence: float
) -> Activity:
    """Closes any existing open segment for this patient, then opens a new one."""
    open_segment = get_open_segment(db, patient_id)
    if open_segment:
        close_activity_segment(db, open_segment)

    segment = Activity(
        patient_id=patient_id,
        camera_id=camera_id,
        activity_type=activity_type,
        confidence=confidence,
        started_at=datetime.utcnow(),
    )
    db.add(segment)
    db.commit()
    db.refresh(segment)
    return segment


def close_activity_segment(db: Session, segment: Activity) -> Activity:
    segment.ended_at = datetime.utcnow()
    segment.duration_sec = (segment.ended_at - segment.started_at).total_seconds()
    db.commit()
    db.refresh(segment)
    return segment
