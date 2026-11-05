"""User table: caregivers and administrators who can log into the system."""

import enum
from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, Enum
from sqlalchemy.orm import relationship

from app.database.session import Base


class UserRole(str, enum.Enum):
    admin = "admin"
    caregiver = "caregiver"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), default=UserRole.caregiver, nullable=False)
    reset_token = Column(String(255), nullable=True)
    reset_token_expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    resolved_alerts = relationship("Alert", back_populates="resolver")
