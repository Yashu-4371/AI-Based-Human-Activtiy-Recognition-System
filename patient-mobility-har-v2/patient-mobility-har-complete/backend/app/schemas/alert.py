from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict

from app.models.alert import AlertType, AlertPriority, AlertStatus
from app.models.alert_email_delivery import EmailDeliveryStatus


class EmailDeliveryOut(BaseModel):
    """Whether a caregiver notification e-mail went out for an alert. Never includes addresses or credentials."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    caregiver_id: Optional[int] = None
    status: EmailDeliveryStatus
    detail: Optional[str] = None
    created_at: datetime
    sent_at: Optional[datetime] = None


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    type: AlertType
    priority: AlertPriority
    status: AlertStatus
    message: str
    screenshot_path: Optional[str] = None
    created_at: datetime
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[int] = None
    email_deliveries: List[EmailDeliveryOut] = []


class AlertResolve(BaseModel):
    resolution_notes: Optional[str] = None
