from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.report import ReportType, ReportFormat


class ReportRequest(BaseModel):
    patient_id: int
    report_type: ReportType
    report_format: ReportFormat = ReportFormat.pdf


class ReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    report_type: ReportType
    report_format: ReportFormat
    file_path: str
    generated_at: datetime
