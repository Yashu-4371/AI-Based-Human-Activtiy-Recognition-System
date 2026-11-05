"""
Caregiver table: contact records (family member, professional
caregiver, etc.) who should be notified about a patient's alerts.

Distinct from `User` (app/models/user.py), which is a login account —
a caregiver here is a contact, not necessarily someone who logs into
the system. A caregiver can be assigned to more than one patient, and
a patient can have more than one caregiver, so the relationship is
many-to-many via `patient_caregivers`.
"""

from datetime import datetime

from sqlalchemy import Column, Integer, String, Text, DateTime, Table, ForeignKey
from sqlalchemy.orm import relationship

from app.database.session import Base

patient_caregivers = Table(
    "patient_caregivers",
    Base.metadata,
    Column("patient_id", Integer, ForeignKey("patients.id", ondelete="CASCADE"), primary_key=True),
    Column("caregiver_id", Integer, ForeignKey("caregivers.id", ondelete="CASCADE"), primary_key=True),
)


class Caregiver(Base):
    __tablename__ = "caregivers"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(120), nullable=False)
    phone = Column(String(30), nullable=False)
    email = Column(String(255), nullable=True, index=True)
    relationship_to_patient = Column(String(50), nullable=True)
    additional_contact_info = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    patients = relationship("Patient", secondary=patient_caregivers, back_populates="caregivers")
