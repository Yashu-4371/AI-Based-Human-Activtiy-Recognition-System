from app.pipeline.monitoring_worker import MonitoringWorker
from app.services import system_settings_service


def test_settings_endpoint_roundtrip(client, db_session):
    from app.services import auth_service
    from app.models.user import UserRole

    auth_service.register_user(db_session, "Admin", "admin@test.com", "AdminPass123!", UserRole.admin)
    login = client.post("/api/v1/auth/login", data={"username": "admin@test.com", "password": "AdminPass123!"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    resp = client.put(
        "/api/v1/settings",
        json={"settings": [{"key": "inactivity_threshold_sec", "value": "120"}]},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["inactivity_threshold_sec"] == "120"

    get_resp = client.get("/api/v1/settings", headers=headers)
    assert get_resp.json()["inactivity_threshold_sec"] == "120"


def test_monitoring_worker_uses_db_configured_thresholds(db_session, monkeypatch):
    import app.pipeline.monitoring_worker as mw

    monkeypatch.setattr(mw, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(db_session, "close", lambda: None)  # keep the shared test session open

    system_settings_service.set_many(
        db_session,
        {
            "inactivity_threshold_sec": "45",
            "fall_torso_angle_threshold_deg": "40",
        },
    )

    worker = MonitoringWorker()
    fall_detector, inactivity_detector = worker._build_detectors()

    assert inactivity_detector.threshold_sec == 45.0
    assert fall_detector.torso_angle_threshold_deg == 40.0
