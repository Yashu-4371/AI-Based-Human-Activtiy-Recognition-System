from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.config import settings
from app.models.user import User
from app.schemas.report import ReportOut, ReportRequest
from app.services import patient_service, report_service

router = APIRouter(prefix="/api/v1/reports", tags=["Reports"])


@router.post("/generate", response_model=ReportOut, status_code=status.HTTP_201_CREATED)
def generate_report(payload: ReportRequest, db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    patient = patient_service.get_patient(db, payload.patient_id)
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")

    report = report_service.generate_report(db, patient, payload.report_type, payload.report_format)
    return report


@router.get("", response_model=List[ReportOut])
def list_reports(
    patient_id: Optional[int] = Query(default=None),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    return report_service.list_reports(db, patient_id)


_MEDIA_TYPES = {"pdf": "application/pdf", "csv": "text/csv", "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}


@router.get("/{report_id}/download")
def download_report(report_id: int, db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    report = report_service.get_report(db, report_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    relative_path = report.file_path.replace("/uploads/", "", 1)
    absolute_path = settings.upload_path / relative_path
    if not absolute_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report file missing on disk")

    patient = patient_service.get_patient(db, report.patient_id)
    download_filename = report_service.build_download_filename(report, patient.name if patient else "patient")
    extension = absolute_path.suffix.lstrip(".")

    return FileResponse(
        path=str(absolute_path),
        filename=download_filename,
        media_type=_MEDIA_TYPES.get(extension, "application/octet-stream"),
    )
