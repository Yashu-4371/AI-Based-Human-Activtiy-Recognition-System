from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.models.alert import AlertPriority, AlertStatus
from app.models.user import User
from app.schemas.alert import AlertOut, AlertResolve
from app.services import alert_service

router = APIRouter(prefix="/api/v1/alerts", tags=["Alerts"])


def _get_or_404(db: Session, alert_id: int):
    alert = alert_service.get_alert(db, alert_id)
    if not alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    return alert


@router.get("", response_model=List[AlertOut])
def list_alerts(
    patient_id: Optional[int] = Query(default=None),
    status_filter: Optional[AlertStatus] = Query(default=None, alias="status"),
    priority: Optional[AlertPriority] = Query(default=None),
    limit: int = Query(default=200, le=1000),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    return alert_service.list_alerts(db, patient_id, status_filter, priority, limit)


@router.get("/{alert_id}", response_model=AlertOut)
def get_alert(alert_id: int, db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    return _get_or_404(db, alert_id)


@router.patch("/{alert_id}/resolve", response_model=AlertOut)
def resolve_alert(
    alert_id: int,
    _payload: AlertResolve,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    alert = _get_or_404(db, alert_id)
    return alert_service.resolve_alert(db, alert, current_user.id)
