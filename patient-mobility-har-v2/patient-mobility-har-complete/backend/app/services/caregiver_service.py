"""Caregiver business logic: create/read/update/delete plus patient assignment."""

from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.caregiver import Caregiver
from app.models.patient import Patient
from app.schemas.caregiver import CaregiverCreate, CaregiverUpdate
from app.utils.logger import get_logger

logger = get_logger(__name__)


def list_caregivers(db: Session, patient_id: Optional[int] = None) -> List[Caregiver]:
    query = db.query(Caregiver)
    if patient_id is not None:
        query = query.join(Caregiver.patients).filter(Patient.id == patient_id)
    return query.order_by(Caregiver.full_name.asc()).all()


def get_caregiver(db: Session, caregiver_id: int) -> Optional[Caregiver]:
    return db.query(Caregiver).filter(Caregiver.id == caregiver_id).first()


def create_caregiver(db: Session, data: CaregiverCreate) -> Caregiver:
    payload = data.model_dump(exclude={"patient_ids"})
    caregiver = Caregiver(**payload)

    if data.patient_ids:
        patients = db.query(Patient).filter(Patient.id.in_(data.patient_ids)).all()
        caregiver.patients = patients

    db.add(caregiver)
    db.commit()
    db.refresh(caregiver)
    logger.info("Created caregiver id=%s name=%s", caregiver.id, caregiver.full_name)
    return caregiver


def update_caregiver(db: Session, caregiver: Caregiver, data: CaregiverUpdate) -> Caregiver:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(caregiver, field, value)
    db.commit()
    db.refresh(caregiver)
    return caregiver


def delete_caregiver(db: Session, caregiver: Caregiver) -> None:
    db.delete(caregiver)
    db.commit()
    logger.info("Deleted caregiver id=%s", caregiver.id)


def assign_to_patient(db: Session, caregiver: Caregiver, patient: Patient) -> Caregiver:
    if patient not in caregiver.patients:
        caregiver.patients.append(patient)
        db.commit()
        db.refresh(caregiver)
        logger.info("Assigned caregiver id=%s to patient id=%s", caregiver.id, patient.id)
    return caregiver


def unassign_from_patient(db: Session, caregiver: Caregiver, patient: Patient) -> Caregiver:
    if patient in caregiver.patients:
        caregiver.patients.remove(patient)
        db.commit()
        db.refresh(caregiver)
        logger.info("Unassigned caregiver id=%s from patient id=%s", caregiver.id, patient.id)
    return caregiver
