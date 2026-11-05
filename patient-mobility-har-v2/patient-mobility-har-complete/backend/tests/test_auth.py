from app.models.user import UserRole
from app.services import auth_service


def _create_admin(db_session):
    return auth_service.register_user(
        db_session, name="Admin", email="admin@test.com", password="AdminPass123!", role=UserRole.admin
    )


def test_login_success(client, db_session):
    _create_admin(db_session)

    response = client.post(
        "/api/v1/auth/login", data={"username": "admin@test.com", "password": "AdminPass123!"}
    )

    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert body["user"]["email"] == "admin@test.com"


def test_login_wrong_password(client, db_session):
    _create_admin(db_session)

    response = client.post(
        "/api/v1/auth/login", data={"username": "admin@test.com", "password": "WrongPassword"}
    )

    assert response.status_code == 401


def test_login_unknown_user(client):
    response = client.post(
        "/api/v1/auth/login", data={"username": "nobody@test.com", "password": "whatever"}
    )
    assert response.status_code == 401


def test_register_requires_admin(client, db_session):
    _create_admin(db_session)
    login_response = client.post(
        "/api/v1/auth/login", data={"username": "admin@test.com", "password": "AdminPass123!"}
    )
    token = login_response.json()["access_token"]

    response = client.post(
        "/api/v1/auth/register",
        json={"name": "Caregiver One", "email": "caregiver@test.com", "password": "CarePass123!", "role": "caregiver"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    assert response.json()["email"] == "caregiver@test.com"


def test_register_without_token_rejected(client):
    response = client.post(
        "/api/v1/auth/register",
        json={"name": "Someone", "email": "someone@test.com", "password": "Pass123!", "role": "caregiver"},
    )
    assert response.status_code == 401
