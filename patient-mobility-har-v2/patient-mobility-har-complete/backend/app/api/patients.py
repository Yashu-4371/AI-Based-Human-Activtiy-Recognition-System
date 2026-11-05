from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.schemas.patient import PatientCreate, PatientOut, PatientUpdate
from app.services import patient_service

router = APIRouter(prefix="/api/v1/patients", tags=["Patients"])


def _get_or_404(db: Session, patient_id: int):
    patient = patient_service.get_patient(db, patient_id)
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    return patient


@router.get("", response_model=List[PatientOut])
def list_patients(db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    return patient_service.list_patients(db)


@router.post("", response_model=PatientOut, status_code=status.HTTP_201_CREATED)
def create_patient(payload: PatientCreate, db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    return patient_service.create_patient(db, payload)


@router.get("/{patient_id}", response_model=PatientOut)
def get_patient(patient_id: int, db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    return _get_or_404(db, patient_id)


@router.put("/{patient_id}", response_model=PatientOut)
def update_patient(
    patient_id: int, payload: PatientUpdate, db: Session = Depends(get_db), _user: User = Depends(get_current_user)
):
    patient = _get_or_404(db, patient_id)
    return patient_service.update_patient(db, patient, payload)


@router.delete("/{patient_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_patient(patient_id: int, db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    patient = _get_or_404(db, patient_id)
    patient_service.delete_patient(db, patient)


@router.post("/{patient_id}/photo", response_model=PatientOut)
def upload_patient_photo(
    patient_id: int,
    photo: UploadFile = File(...),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    patient = _get_or_404(db, patient_id)
    return patient_service.save_patient_photo(db, patient, photo)
