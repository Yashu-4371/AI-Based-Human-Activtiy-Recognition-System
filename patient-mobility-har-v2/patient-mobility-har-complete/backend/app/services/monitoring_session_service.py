"""Business logic for MonitoringSession: opened when live monitoring starts, closed when it stops."""

from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.monitoring_session import MonitoringSession


def open_session(db: Session, patient_id: int, camera_id: Optional[int]) -> MonitoringSession:
    session = MonitoringSession(patient_id=patient_id, camera_id=camera_id, started_at=datetime.utcnow())
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def close_session(db: Session, session_id: int) -> Optional[MonitoringSession]:
    session = db.query(MonitoringSession).filter(MonitoringSession.id == session_id).first()
    if session is None or session.ended_at is not None:
        return session
    session.ended_at = datetime.utcnow()
    session.duration_sec = (session.ended_at - session.started_at).total_seconds()
    db.commit()
    db.refresh(session)
    return session


def get_sessions(
    db: Session, patient_id: int, date_from: Optional[datetime] = None, date_to: Optional[datetime] = None
) -> List[MonitoringSession]:
    query = db.query(MonitoringSession).filter(MonitoringSession.patient_id == patient_id)
    if date_from:
        query = query.filter(MonitoringSession.started_at >= date_from)
    if date_to:
        query = query.filter(MonitoringSession.started_at <= date_to)
    return query.order_by(MonitoringSession.started_at.asc()).all()


def total_monitoring_seconds(
    db: Session, patient_id: int, date_from: datetime, date_to: datetime
) -> float:
    total = 0.0
    now = datetime.utcnow()
    for session in get_sessions(db, patient_id, date_from, date_to):
        end = session.ended_at or (now if session.started_at <= now else session.started_at)
        # Clip to the report window in case a session started before it.
        window_start = max(session.started_at, date_from)
        window_end = min(end, date_to)
        if window_end > window_start:
            total += (window_end - window_start).total_seconds()
    return total
