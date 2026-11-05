from datetime import datetime, timedelta

from app.models.activity import Activity, ActivityType
from app.models.alert import AlertType, AlertPriority
from app.models.patient import Patient
from app.models.report import ReportFormat, ReportType
from app.models.user import UserRole
from app.services import alert_service, auth_service, monitoring_session_service, report_service


def _auth_headers(client, db_session):
    auth_service.register_user(db_session, "Admin", "admin@test.com", "AdminPass123!", UserRole.admin)
    response = client.post("/api/v1/auth/login", data={"username": "admin@test.com", "password": "AdminPass123!"})
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _seed_patient_with_real_data(db_session) -> Patient:
    patient = Patient(name="Report Test Patient", room_number="12B", age=78, disease="Parkinson's")
    db_session.add(patient)
    db_session.commit()
    db_session.refresh(patient)

    now = datetime.utcnow()
    # Two closed activity segments (walking, then sitting), each with a real duration.
    walking = Activity(
        patient_id=patient.id, activity_type=ActivityType.walking, confidence=0.9,
        started_at=now - timedelta(minutes=30), ended_at=now - timedelta(minutes=20), duration_sec=600,
    )
    sitting = Activity(
        patient_id=patient.id, activity_type=ActivityType.sitting, confidence=0.85,
        started_at=now - timedelta(minutes=20), ended_at=now - timedelta(minutes=5), duration_sec=900,
    )
    db_session.add_all([walking, sitting])
    db_session.commit()

    # A fall alert and an inactivity alert, both real DB rows via the real service.
    alert_service.create_alert(
        db_session, patient=patient, alert_type=AlertType.fall, priority=AlertPriority.critical, message="Fall detected in test"
    )
    alert_service.create_alert(
        db_session, patient=patient, alert_type=AlertType.inactivity, priority=AlertPriority.warning, message="Prolonged inactivity in test"
    )

    # A monitoring session so "total monitoring time" isn't zero.
    session = monitoring_session_service.open_session(db_session, patient.id, camera_id=None)
    monitoring_session_service.close_session(db_session, session.id)

    return patient


def test_generate_pdf_report_uses_real_data(db_session):
    patient = _seed_patient_with_real_data(db_session)

    report = report_service.generate_report(db_session, patient, ReportType.weekly, ReportFormat.pdf)

    assert report.id is not None
    assert report.file_path.endswith(".pdf")

    from app.utils.file_storage import to_relative_url
    from app.config import settings
    from pathlib import Path

    # Resolve the actual file on disk from the stored relative URL.
    local_path = Path(settings.UPLOAD_DIR) / Path(report.file_path).relative_to("/uploads")
    assert local_path.exists()
    assert local_path.stat().st_size > 500  # a real rendered PDF, not an empty stub
    with open(local_path, "rb") as f:
        assert f.read(5) == b"%PDF-"  # a genuinely valid PDF file


def test_generate_csv_and_xlsx_reports(db_session):
    patient = _seed_patient_with_real_data(db_session)

    csv_report = report_service.generate_report(db_session, patient, ReportType.weekly, ReportFormat.csv)
    xlsx_report = report_service.generate_report(db_session, patient, ReportType.weekly, ReportFormat.xlsx)

    assert csv_report.file_path.endswith(".csv")
    assert xlsx_report.file_path.endswith(".xlsx")


def test_report_context_includes_real_falls_and_inactivity(db_session):
    patient = _seed_patient_with_real_data(db_session)
    now = datetime.utcnow()
    ctx = report_service._report_context(patient, ReportType.weekly, now - timedelta(days=7), now, db_session)

    assert ctx["falls"] == 1
    assert ctx["inactivity_events"] == 1
    assert len(ctx["alerts"]) == 2
    assert ctx["monitoring_seconds"] >= 0
    assert ctx["distribution"].get("walking", 0) > 0
    assert ctx["distribution"].get("sitting", 0) > 0


def test_report_generate_and_download_endpoints_roundtrip(client, db_session):
    headers = _auth_headers(client, db_session)
    patient = _seed_patient_with_real_data(db_session)

    gen_resp = client.post(
        "/api/v1/reports/generate",
        json={"patient_id": patient.id, "report_type": "weekly", "report_format": "pdf"},
        headers=headers,
    )
    assert gen_resp.status_code in (200, 201)
    report_id = gen_resp.json()["id"]

    download_resp = client.get(f"/api/v1/reports/{report_id}/download", headers=headers)
    assert download_resp.status_code == 200
    assert download_resp.headers["content-type"] == "application/pdf"
    assert download_resp.content[:5] == b"%PDF-"

    # No auth header -> must be rejected (this is exactly the bug being fixed on the frontend).
    unauth_resp = client.get(f"/api/v1/reports/{report_id}/download")
    assert unauth_resp.status_code in (401, 403)
