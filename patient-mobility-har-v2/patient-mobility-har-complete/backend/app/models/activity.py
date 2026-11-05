"""
Activity table: one row per continuous activity segment (not per frame).
A new row is opened when the classified activity changes, and the
previous row's ended_at/duration_sec is closed off at that point.
"""

import enum
from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey, Enum
from sqlalchemy.orm import relationship

from app.database.session import Base


class ActivityType(str, enum.Enum):
    walking = "walking"
    standing = "standing"
    sitting = "sitting"
    lying = "lying"


class Activity(Base):
    __tablename__ = "activities"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False, index=True)
    camera_id = Column(Integer, ForeignKey("camera_settings.id"), nullable=True)
    activity_type = Column(Enum(ActivityType), nullable=False)
    confidence = Column(Float, nullable=False)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    ended_at = Column(DateTime, nullable=True)
    duration_sec = Column(Float, nullable=True)

    patient = relationship("Patient", back_populates="activities")
    camera = relationship("CameraSetting")
