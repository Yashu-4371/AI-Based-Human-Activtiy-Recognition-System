from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.camera.frame_buffer import live_frame_buffer
from app.models.user import User
from app.schemas.activity import ActivityOut, CurrentActivityOut
from app.services import activity_service

router = APIRouter(prefix="/api/v1/activities", tags=["Activities"])


@router.get("/current", response_model=Optional[CurrentActivityOut])
def get_current_activity(patient_id: int, _user: User = Depends(get_current_user)):
    state = live_frame_buffer.get_state()
    if state.activity_label is None or state.updated_at is None:
        return None

    return CurrentActivityOut(
        patient_id=patient_id,
        activity_type=state.activity_label,
        confidence=state.confidence,
        updated_at=state.updated_at,
        fall_detected=state.fall_detected,
        inactivity_warning=state.inactivity_warning,
    )


@router.get("/history", response_model=List[ActivityOut])
def get_activity_history(
    patient_id: int,
    date_from: Optional[datetime] = Query(default=None),
    date_to: Optional[datetime] = Query(default=None),
    limit: int = Query(default=200, le=1000),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    return activity_service.get_history(db, patient_id, date_from, date_to, limit)
