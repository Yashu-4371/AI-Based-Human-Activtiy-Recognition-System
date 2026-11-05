from app.models.activity import ActivityType
from app.models.patient import Patient
from app.models.user import UserRole
from app.services import activity_service, auth_service


def _auth_headers(client, db_session):
    auth_service.register_user(db_session, "Admin", "admin@test.com", "AdminPass123!", UserRole.admin)
    response = client.post("/api/v1/auth/login", data={"username": "admin@test.com", "password": "AdminPass123!"})
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _create_patient(db_session) -> Patient:
    patient = Patient(name="Test Patient")
    db_session.add(patient)
    db_session.commit()
    db_session.refresh(patient)
    return patient


def test_open_and_close_activity_segment(db_session):
    patient = _create_patient(db_session)

    segment = activity_service.open_activity_segment(
        db_session, patient_id=patient.id, camera_id=None, activity_type=ActivityType.walking, confidence=0.9
    )
    assert segment.ended_at is None

    closed = activity_service.close_activity_segment(db_session, segment)
    assert closed.ended_at is not None
    assert closed.duration_sec is not None
    assert closed.duration_sec >= 0


def test_opening_new_segment_closes_previous_one(db_session):
    patient = _create_patient(db_session)

    first_segment = activity_service.open_activity_segment(
        db_session, patient_id=patient.id, camera_id=None, activity_type=ActivityType.sitting, confidence=0.8
    )
    activity_service.open_activity_segment(
        db_session, patient_id=patient.id, camera_id=None, activity_type=ActivityType.standing, confidence=0.85
    )

    db_session.refresh(first_segment)
    assert first_segment.ended_at is not None


def test_activity_history_endpoint(client, db_session):
    headers = _auth_headers(client, db_session)
    patient = _create_patient(db_session)

    activity_service.open_activity_segment(
        db_session, patient_id=patient.id, camera_id=None, activity_type=ActivityType.walking, confidence=0.9
    )

    response = client.get(f"/api/v1/activities/history?patient_id={patient.id}", headers=headers)
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["activity_type"] == "walking"
