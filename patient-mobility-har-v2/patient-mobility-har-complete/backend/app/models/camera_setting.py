"""Camera settings table: configured video sources."""

import enum
from datetime import datetime

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum

from app.database.session import Base


class CameraSourceType(str, enum.Enum):
    webcam = "webcam"
    usb = "usb"
    ip = "ip"
    rtsp = "rtsp"


class CameraSetting(Base):
    __tablename__ = "camera_settings"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=False)
    source_type = Column(Enum(CameraSourceType), default=CameraSourceType.webcam, nullable=False)
    source_uri = Column(String(500), nullable=False, default="0")
    resolution_width = Column(Integer, default=640)
    resolution_height = Column(Integer, default=480)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
