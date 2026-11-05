from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user, require_admin
from app.camera.frame_buffer import live_frame_buffer
from app.models.camera_setting import CameraSetting
from app.models.user import User
from app.pipeline.monitoring_worker import monitoring_worker

router = APIRouter(prefix="/api/v1/camera", tags=["Camera"])


class CameraStartRequest(BaseModel):
    patient_id: int
    camera_id: int


class CameraSettingUpdate(BaseModel):
    name: str | None = None
    source_type: str | None = None
    source_uri: str | None = None
    resolution_width: int | None = None
    resolution_height: int | None = None
    is_active: bool | None = None


class CameraSettingOut(BaseModel):
    id: int
    name: str
    source_type: str
    source_uri: str
    resolution_width: int
    resolution_height: int
    is_active: bool

    class Config:
        from_attributes = True


@router.get("/status")
def get_camera_status(_user: User = Depends(get_current_user)):
    state = live_frame_buffer.get_state()
    return {
        "is_running": monitoring_worker.is_running(),
        "camera_connected": state.camera_connected,
        "fps": state.fps,
        "activity_label": state.activity_label,
        "confidence": state.confidence,
        "fall_detected": state.fall_detected,
        "inactivity_warning": state.inactivity_warning,
        "updated_at": state.updated_at,
    }


@router.post("/start")
def start_camera(payload: CameraStartRequest, db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    camera_setting = db.query(CameraSetting).filter(CameraSetting.id == payload.camera_id).first()
    if not camera_setting:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Camera setting not found")

    started = monitoring_worker.start(payload.patient_id, camera_setting)
    if not started:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Monitoring is already running")

    return {"message": "Monitoring started"}


@router.post("/stop")
def stop_camera(_user: User = Depends(get_current_user)):
    monitoring_worker.stop()
    return {"message": "Monitoring stopped"}


@router.get("/settings", response_model=List[CameraSettingOut])
def list_camera_settings(db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    return db.query(CameraSetting).all()


@router.put("/settings/{camera_id}", response_model=CameraSettingOut)
def update_camera_setting(
    camera_id: int,
    payload: CameraSettingUpdate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    camera_setting = db.query(CameraSetting).filter(CameraSetting.id == camera_id).first()
    if not camera_setting:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Camera setting not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(camera_setting, field, value)
    db.commit()
    db.refresh(camera_setting)
    return camera_setting
