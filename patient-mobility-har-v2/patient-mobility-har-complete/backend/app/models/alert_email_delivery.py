"""
AlertEmailDelivery table: one row per (alert, recipient address) recording
whether the caregiver notification e-mail was sent, failed, or skipped.

This is a NEW table. It is created automatically at startup
(Base.metadata.create_all) and does not alter any existing table, so
existing data is untouched.

Purposes:
  * Duplicate prevention — UNIQUE(alert_id, recipient_email) means the same
    alert can never e-mail the same address twice, even across restarts.
  * Visibility — the Alerts page can show whether caregivers were e-mailed.
  * Cooldown — recent rows tell us whether this caregiver was just e-mailed
    about the same kind of alert for the same patient.

Only a short, sanitized `detail` is stored — never credentials or raw
exception text.
"""

import enum
from datetime import datetime

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database.session import Base


class EmailDeliveryStatus(str, enum.Enum):
    pending = "pending"  # claimed, waiting to be sent
    sent = "sent"        # accepted by the SMTP server
    failed = "failed"    # SMTP error (see `detail`)
    skipped = "skipped"  # intentionally not sent (see `detail`)


class AlertEmailDelivery(Base):
    __tablename__ = "alert_email_deliveries"
    __table_args__ = (UniqueConstraint("alert_id", "recipient_email", name="uq_alert_email_recipient"),)

    id = Column(Integer, primary_key=True, index=True)
    alert_id = Column(Integer, ForeignKey("alerts.id"), nullable=False, index=True)
    # Plain integer (no FK): this is a historical record that should survive caregiver deletion.
    caregiver_id = Column(Integer, nullable=True)
    # NULL for "nothing to send" rows (e.g. no caregiver has an email).
    recipient_email = Column(String(255), nullable=True)
    status = Column(Enum(EmailDeliveryStatus), nullable=False, default=EmailDeliveryStatus.pending)
    detail = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    sent_at = Column(DateTime, nullable=True)

    alert = relationship("Alert", back_populates="email_deliveries")
