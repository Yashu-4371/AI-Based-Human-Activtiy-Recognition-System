from app.models.alert import AlertType, AlertPriority, AlertStatus
from app.models.patient import Patient
from app.models.user import UserRole
from app.services import alert_service, auth_service


def _auth_headers_and_user(client, db_session):
    user = auth_service.register_user(db_session, "Admin", "admin@test.com", "AdminPass123!", UserRole.admin)
    response = client.post("/api/v1/auth/login", data={"username": "admin@test.com", "password": "AdminPass123!"})
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}, user


def _create_patient(db_session) -> Patient:
    patient = Patient(name="Test Patient")
    db_session.add(patient)
    db_session.commit()
    db_session.refresh(patient)
    return patient


def test_create_alert_defaults_to_open_status(db_session):
    patient = _create_patient(db_session)

    alert = alert_service.create_alert(
        db_session,
        patient=patient,
        alert_type=AlertType.fall,
        priority=AlertPriority.critical,
        message="Fall detected in test",
    )

    assert alert.status == AlertStatus.open
    assert alert.type == AlertType.fall
    assert alert.priority == AlertPriority.critical


def test_resolve_alert(db_session):
    patient = _create_patient(db_session)
    alert = alert_service.create_alert(
        db_session, patient=patient, alert_type=AlertType.inactivity, priority=AlertPriority.warning, message="Test"
    )

    resolved = alert_service.resolve_alert(db_session, alert, resolved_by_user_id=1)

    assert resolved.status == AlertStatus.resolved
    assert resolved.resolved_at is not None
    assert resolved.resolved_by == 1


def test_alert_list_endpoint_filters_by_patient(client, db_session):
    headers, _user = _auth_headers_and_user(client, db_session)
    patient = _create_patient(db_session)

    alert_service.create_alert(
        db_session, patient=patient, alert_type=AlertType.fall, priority=AlertPriority.critical, message="Test fall"
    )

    response = client.get(f"/api/v1/alerts?patient_id={patient.id}", headers=headers)
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_resolve_alert_endpoint(client, db_session):
    headers, _user = _auth_headers_and_user(client, db_session)
    patient = _create_patient(db_session)

    alert = alert_service.create_alert(
        db_session, patient=patient, alert_type=AlertType.fall, priority=AlertPriority.critical, message="Test fall"
    )

    response = client.patch(f"/api/v1/alerts/{alert.id}/resolve", json={}, headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "resolved"
