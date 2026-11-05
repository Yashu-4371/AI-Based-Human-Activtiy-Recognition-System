"""Report table: metadata for generated activity/mobility reports."""

import enum
from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship

from app.database.session import Base


class ReportType(str, enum.Enum):
    daily = "daily"
    weekly = "weekly"
    monthly = "monthly"


class ReportFormat(str, enum.Enum):
    pdf = "pdf"
    csv = "csv"
    xlsx = "xlsx"


class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False, index=True)
    report_type = Column(Enum(ReportType), nullable=False)
    report_format = Column(Enum(ReportFormat), nullable=False)
    file_path = Column(String(500), nullable=False)
    generated_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    patient = relationship("Patient", back_populates="reports")
