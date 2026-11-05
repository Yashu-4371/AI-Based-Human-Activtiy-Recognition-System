from typing import Dict, List

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_admin
from app.models.user import User
from app.services import system_settings_service

router = APIRouter(prefix="/api/v1/settings", tags=["Settings"])


class SettingItem(BaseModel):
    key: str
    value: str


class SettingsUpdateRequest(BaseModel):
    settings: List[SettingItem]


@router.get("", response_model=Dict[str, str])
def get_settings(db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    return system_settings_service.get_all(db)


@router.put("", response_model=Dict[str, str])
def update_settings(
    payload: SettingsUpdateRequest, db: Session = Depends(get_db), _admin: User = Depends(require_admin)
):
    items = {item.key: item.value for item in payload.settings}
    return system_settings_service.set_many(db, items)
