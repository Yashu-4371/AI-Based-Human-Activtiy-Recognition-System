from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class PatientBase(BaseModel):
    name: str
    age: Optional[int] = None
    gender: Optional[str] = None
    blood_group: Optional[str] = None
    disease: Optional[str] = None
    doctor: Optional[str] = None
    room_number: Optional[str] = None
    emergency_contact: Optional[str] = None
    medical_notes: Optional[str] = None


class PatientCreate(PatientBase):
    pass


class PatientUpdate(BaseModel):
    name: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    blood_group: Optional[str] = None
    disease: Optional[str] = None
    doctor: Optional[str] = None
    room_number: Optional[str] = None
    emergency_contact: Optional[str] = None
    medical_notes: Optional[str] = None


class PatientOut(PatientBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    photo_path: Optional[str] = None
    created_at: datetime
