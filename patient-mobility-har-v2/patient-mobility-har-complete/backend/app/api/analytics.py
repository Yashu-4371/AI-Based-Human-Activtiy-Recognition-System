from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.services import analytics_service

router = APIRouter(prefix="/api/v1/analytics", tags=["Analytics"])


@router.get("/activity-distribution")
def activity_distribution(
    patient_id: int,
    days: int = Query(default=7, le=90),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    date_to = datetime.utcnow()
    date_from = date_to - timedelta(days=days)
    return analytics_service.activity_distribution(db, patient_id, date_from, date_to)


@router.get("/weekly-trend")
def weekly_trend(
    patient_id: int,
    days: int = Query(default=7, le=90),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    return analytics_service.daily_activity_duration(db, patient_id, days)


@router.get("/fall-frequency")
def fall_frequency(
    patient_id: int,
    days: int = Query(default=30, le=365),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    return {"patient_id": patient_id, "days": days, "fall_count": analytics_service.fall_frequency(db, patient_id, days)}


@router.get("/average-walking-time")
def average_walking_time(
    patient_id: int,
    days: int = Query(default=7, le=90),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    return {
        "patient_id": patient_id,
        "days": days,
        "average_walking_seconds_per_day": analytics_service.average_walking_time_sec(db, patient_id, days),
    }
