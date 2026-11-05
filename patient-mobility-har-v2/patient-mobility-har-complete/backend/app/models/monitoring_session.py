"""
MonitoringSession table: one row per start->stop monitoring run for a
patient/camera. This is what reports use for "total monitoring time"
and "monitoring period" — summing Activity segment durations alone
would undercount any time where no person was detected in frame
(no activity segment is opened when pose estimation finds nobody).
"""

from datetime import datetime

from sqlalchemy import Column, Integer, DateTime, Float, ForeignKey
from sqlalchemy.orm import relationship

from app.database.session import Base


class MonitoringSession(Base):
    __tablename__ = "monitoring_sessions"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False, index=True)
    camera_id = Column(Integer, ForeignKey("camera_settings.id"), nullable=True)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    ended_at = Column(DateTime, nullable=True)
    duration_sec = Column(Float, nullable=True)

    patient = relationship("Patient", back_populates="monitoring_sessions")
    camera = relationship("CameraSetting")
