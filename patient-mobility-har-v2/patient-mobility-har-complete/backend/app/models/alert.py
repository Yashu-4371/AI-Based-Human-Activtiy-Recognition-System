"""Alert table: emergency and warning events raised by the monitoring pipeline."""

import enum
from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Enum
from sqlalchemy.orm import relationship

from app.database.session import Base
from app.models.alert_email_delivery import AlertEmailDelivery  # noqa: F401  (registers the table / relationship)


class AlertType(str, enum.Enum):
    fall = "fall"
    inactivity = "inactivity"
    abnormal = "abnormal"


class AlertPriority(str, enum.Enum):
    critical = "critical"
    warning = "warning"
    normal = "normal"


class AlertStatus(str, enum.Enum):
    open = "open"
    resolved = "resolved"


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False, index=True)
    type = Column(Enum(AlertType), nullable=False)
    priority = Column(Enum(AlertPriority), nullable=False)
    status = Column(Enum(AlertStatus), default=AlertStatus.open, nullable=False)
    message = Column(Text, nullable=False)
    screenshot_path = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    resolved_at = Column(DateTime, nullable=True)
    resolved_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    patient = relationship("Patient", back_populates="alerts")
    resolver = relationship("User", back_populates="resolved_alerts")
    email_deliveries = relationship(
        "AlertEmailDelivery", back_populates="alert", cascade="all, delete-orphan", order_by="AlertEmailDelivery.id"
    )
