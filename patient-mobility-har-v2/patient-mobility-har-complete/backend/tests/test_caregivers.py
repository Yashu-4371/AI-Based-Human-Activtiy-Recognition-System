from app.models.alert import AlertType, AlertPriority
from app.models.patient import Patient
from app.models.user import UserRole
from app.services import alert_service, auth_service, caregiver_service
from app.schemas.caregiver import CaregiverCreate


def _auth_headers(client, db_session):
    auth_service.register_user(db_session, "Admin", "admin@test.com", "AdminPass123!", UserRole.admin)
    response = client.post("/api/v1/auth/login", data={"username": "admin@test.com", "password": "AdminPass123!"})
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _create_patient(db_session, name="Test Patient") -> Patient:
    patient = Patient(name=name)
    db_session.add(patient)
    db_session.commit()
    db_session.refresh(patient)
    return patient


def test_create_caregiver_service(db_session):
    caregiver = caregiver_service.create_caregiver(
        db_session,
        CaregiverCreate(full_name="Jane Doe", phone="+1234567890", email="jane@example.com", relationship_to_patient="Daughter"),
    )
    assert caregiver.id is not None
    assert caregiver.full_name == "Jane Doe"
    assert caregiver.patients == []


def test_assign_and_unassign_caregiver(db_session):
    patient = _create_patient(db_session)
    caregiver = caregiver_service.create_caregiver(
        db_session, CaregiverCreate(full_name="Jane Doe", phone="+1234567890")
    )

    caregiver_service.assign_to_patient(db_session, caregiver, patient)
    assert patient in caregiver.patients
    assert caregiver in patient.caregivers

    caregiver_service.unassign_from_patient(db_session, caregiver, patient)
    assert patient not in caregiver.patients


def test_multiple_caregivers_per_patient_and_vice_versa(db_session):
    patient_a = _create_patient(db_session, "Patient A")
    patient_b = _create_patient(db_session, "Patient B")
    caregiver_1 = caregiver_service.create_caregiver(db_session, CaregiverCreate(full_name="C1", phone="1"))
    caregiver_2 = caregiver_service.create_caregiver(db_session, CaregiverCreate(full_name="C2", phone="2"))

    caregiver_service.assign_to_patient(db_session, caregiver_1, patient_a)
    caregiver_service.assign_to_patient(db_session, caregiver_2, patient_a)
    caregiver_service.assign_to_patient(db_session, caregiver_1, patient_b)

    assert {c.id for c in patient_a.caregivers} == {caregiver_1.id, caregiver_2.id}
    assert {p.id for p in caregiver_1.patients} == {patient_a.id, patient_b.id}


def test_caregiver_crud_endpoints(client, db_session):
    headers = _auth_headers(client, db_session)
    patient = _create_patient(db_session)

    create_resp = client.post(
        "/api/v1/caregivers",
        json={"full_name": "Jane Doe", "phone": "+1234567890", "email": "jane@example.com",
              "relationship_to_patient": "Daughter", "patient_ids": [patient.id]},
        headers=headers,
    )
    assert create_resp.status_code == 201
    caregiver_id = create_resp.json()["id"]
    assert create_resp.json()["patients"][0]["id"] == patient.id

    list_resp = client.get(f"/api/v1/caregivers?patient_id={patient.id}", headers=headers)
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1

    update_resp = client.put(f"/api/v1/caregivers/{caregiver_id}", json={"phone": "+19999999999"}, headers=headers)
    assert update_resp.status_code == 200
    assert update_resp.json()["phone"] == "+19999999999"

    delete_resp = client.delete(f"/api/v1/caregivers/{caregiver_id}", headers=headers)
    assert delete_resp.status_code == 204


def test_assign_endpoint(client, db_session):
    headers = _auth_headers(client, db_session)
    patient = _create_patient(db_session)
    create_resp = client.post("/api/v1/caregivers", json={"full_name": "Jane", "phone": "1"}, headers=headers)
    caregiver_id = create_resp.json()["id"]

    assign_resp = client.post(f"/api/v1/caregivers/{caregiver_id}/assign/{patient.id}", headers=headers)
    assert assign_resp.status_code == 200
    assert len(assign_resp.json()["patients"]) == 1

    unassign_resp = client.delete(f"/api/v1/caregivers/{caregiver_id}/assign/{patient.id}", headers=headers)
    assert unassign_resp.status_code == 200
    assert len(unassign_resp.json()["patients"]) == 0


def test_alert_creation_notifies_assigned_caregiver_without_crashing(db_session, monkeypatch):
    """
    create_alert must not raise even though SMTP/Twilio aren't configured (handled in
    conftest's autouse fixture) — and it should hand the patient's assigned caregivers
    to the e-mail dispatcher. (Detailed e-mail behaviour is covered in test_email_alerts.py.)
    """
    patient = _create_patient(db_session)
    caregiver = caregiver_service.create_caregiver(
        db_session, CaregiverCreate(full_name="Jane", phone="+1234567890", email="jane@example.com")
    )
    caregiver_service.assign_to_patient(db_session, caregiver, patient)

    dispatched_to = []
    monkeypatch.setattr(
        "app.services.alert_service.alert_email_service.dispatch_alert_emails",
        lambda db, alert, patient, screenshot_path=None: dispatched_to.append([c.email for c in patient.caregivers]),
    )

    alert = alert_service.create_alert(
        db_session, patient=patient, alert_type=AlertType.fall, priority=AlertPriority.critical, message="Test fall"
    )

    assert alert.id is not None
    assert dispatched_to == [["jane@example.com"]]
