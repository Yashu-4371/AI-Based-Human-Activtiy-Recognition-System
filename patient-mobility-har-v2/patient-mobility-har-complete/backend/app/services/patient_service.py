"""Patient business logic: create/read/update/delete and photo handling."""

from typing import List, Optional

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.models.patient import Patient
from app.schemas.patient import PatientCreate, PatientUpdate
from app.utils.file_storage import new_patient_photo_path, to_relative_url
from app.utils.logger import get_logger

logger = get_logger(__name__)


def list_patients(db: Session) -> List[Patient]:
    return db.query(Patient).order_by(Patient.name.asc()).all()


def get_patient(db: Session, patient_id: int) -> Optional[Patient]:
    return db.query(Patient).filter(Patient.id == patient_id).first()


def create_patient(db: Session, data: PatientCreate) -> Patient:
    patient = Patient(**data.model_dump())
    db.add(patient)
    db.commit()
    db.refresh(patient)
    logger.info("Created patient id=%s name=%s", patient.id, patient.name)
    return patient


def update_patient(db: Session, patient: Patient, data: PatientUpdate) -> Patient:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(patient, field, value)
    db.commit()
    db.refresh(patient)
    return patient


def delete_patient(db: Session, patient: Patient) -> None:
    db.delete(patient)
    db.commit()
    logger.info("Deleted patient id=%s", patient.id)


def save_patient_photo(db: Session, patient: Patient, photo: UploadFile) -> Patient:
    destination = new_patient_photo_path(photo.filename or "photo.jpg")
    with open(destination, "wb") as f:
        f.write(photo.file.read())
    patient.photo_path = to_relative_url(destination)
    db.commit()
    db.refresh(patient)
    return patient
