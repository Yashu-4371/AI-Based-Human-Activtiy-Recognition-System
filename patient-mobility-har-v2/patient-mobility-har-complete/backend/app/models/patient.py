"""Patient table: the individuals being monitored."""

from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.orm import relationship

from app.database.session import Base


class Patient(Base):
    __tablename__ = "patients"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=False)
    photo_path = Column(String(500), nullable=True)
    age = Column(Integer, nullable=True)
    gender = Column(String(20), nullable=True)
    blood_group = Column(String(10), nullable=True)
    disease = Column(String(255), nullable=True)
    doctor = Column(String(120), nullable=True)
    room_number = Column(String(20), nullable=True)
    emergency_contact = Column(String(50), nullable=True)
    medical_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    activities = relationship("Activity", back_populates="patient", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="patient", cascade="all, delete-orphan")
    reports = relationship("Report", back_populates="patient", cascade="all, delete-orphan")
    caregivers = relationship("Caregiver", secondary="patient_caregivers", back_populates="patients")
    monitoring_sessions = relationship("MonitoringSession", back_populates="patient", cascade="all, delete-orphan")
