from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.models.activity import ActivityType


class ActivityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    camera_id: Optional[int] = None
    activity_type: ActivityType
    confidence: float
    started_at: datetime
    ended_at: Optional[datetime] = None
    duration_sec: Optional[float] = None


class CurrentActivityOut(BaseModel):
    patient_id: int
    activity_type: ActivityType
    confidence: float
    updated_at: datetime
    fall_detected: bool = False
    inactivity_warning: bool = False
