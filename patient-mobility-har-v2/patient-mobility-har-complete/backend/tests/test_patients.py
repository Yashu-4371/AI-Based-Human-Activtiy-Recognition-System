from app.models.user import UserRole
from app.services import auth_service


def _auth_headers(client, db_session):
    auth_service.register_user(db_session, "Admin", "admin@test.com", "AdminPass123!", UserRole.admin)
    response = client.post("/api/v1/auth/login", data={"username": "admin@test.com", "password": "AdminPass123!"})
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_create_and_get_patient(client, db_session):
    headers = _auth_headers(client, db_session)

    create_response = client.post(
        "/api/v1/patients",
        json={"name": "John Doe", "age": 72, "gender": "male", "room_number": "204"},
        headers=headers,
    )
    assert create_response.status_code == 201
    patient_id = create_response.json()["id"]

    get_response = client.get(f"/api/v1/patients/{patient_id}", headers=headers)
    assert get_response.status_code == 200
    assert get_response.json()["name"] == "John Doe"


def test_list_patients(client, db_session):
    headers = _auth_headers(client, db_session)
    client.post("/api/v1/patients", json={"name": "Patient A"}, headers=headers)
    client.post("/api/v1/patients", json={"name": "Patient B"}, headers=headers)

    response = client.get("/api/v1/patients", headers=headers)
    assert response.status_code == 200
    assert len(response.json()) == 2


def test_update_patient(client, db_session):
    headers = _auth_headers(client, db_session)
    create_response = client.post("/api/v1/patients", json={"name": "Original Name"}, headers=headers)
    patient_id = create_response.json()["id"]

    update_response = client.put(
        f"/api/v1/patients/{patient_id}", json={"name": "Updated Name"}, headers=headers
    )
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "Updated Name"


def test_delete_patient(client, db_session):
    headers = _auth_headers(client, db_session)
    create_response = client.post("/api/v1/patients", json={"name": "To Delete"}, headers=headers)
    patient_id = create_response.json()["id"]

    delete_response = client.delete(f"/api/v1/patients/{patient_id}", headers=headers)
    assert delete_response.status_code == 204

    get_response = client.get(f"/api/v1/patients/{patient_id}", headers=headers)
    assert get_response.status_code == 404


def test_get_nonexistent_patient_returns_404(client, db_session):
    headers = _auth_headers(client, db_session)
    response = client.get("/api/v1/patients/9999", headers=headers)
    assert response.status_code == 404
