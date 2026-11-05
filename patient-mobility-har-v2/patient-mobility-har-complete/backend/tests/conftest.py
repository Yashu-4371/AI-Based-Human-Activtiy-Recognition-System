"""Shared pytest fixtures: an isolated in-memory SQLite DB per test session and a FastAPI TestClient."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.session import Base
from app.api.deps import get_db
from app.main import app
from app.config import settings

TEST_DATABASE_URL = "sqlite:///:memory:"

# StaticPool: a plain in-memory sqlite engine opens a NEW empty database on
# every connection, so the TestClient's request-scoped session and the
# db_session fixture's session would otherwise see two different empty
# databases ("no such table" errors). StaticPool keeps them on one shared
# connection for the lifetime of the engine.
engine = create_engine(
    TEST_DATABASE_URL, connect_args={"check_same_thread": False}, poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = _override_get_db


@pytest.fixture(autouse=True)
def _disable_external_notifications(monkeypatch):
    """
    Tests must never depend on real network access or message real people.
    Whatever the developer's local/CI .env happens to contain (real or
    placeholder-but-truthy SMTP/Twilio/Telegram values), force every
    external-notification channel to its "unconfigured" state so
    create_alert()'s notification dispatch no-ops instantly instead of
    attempting (and timing out on) a real SMTP/Telegram/Twilio call.

    As a second line of defence, smtplib.SMTP inside the e-mail module is
    replaced by a guard that records any attempted real connection; the
    fixture below fails the test if one ever happens. Tests that exercise
    e-mail sending install their own mock (see tests/test_email_alerts.py).
    """
    from app.alerts import email_notifier
    from app.services import alert_email_service

    monkeypatch.setattr(settings, "SMTP_USERNAME", "")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "")
    monkeypatch.setattr(settings, "SMTP_FROM_EMAIL", "")
    monkeypatch.setattr(settings, "TELEGRAM_ENABLED", False)
    monkeypatch.setattr(settings, "SMS_ENABLED", False)
    # The WhatsApp notifier only checks these three values, so blank them too.
    monkeypatch.setattr(settings, "TWILIO_ACCOUNT_SID", "")
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", "")
    monkeypatch.setattr(settings, "TWILIO_WHATSAPP_FROM", "")
    # Deterministic: send inline instead of on the background worker, no cooldown surprises.
    monkeypatch.setattr(settings, "ALERT_EMAIL_ASYNC", False)
    monkeypatch.setattr(settings, "ALERT_EMAIL_COOLDOWN_SEC", 0.0)
    # The e-mail service records outcomes through its own session; point it at the test database.
    monkeypatch.setattr(alert_email_service, "SessionLocal", TestingSessionLocal)
    alert_email_service._test_email_last_sent.clear()

    real_smtp_attempts = []

    def _smtp_guard(*args, **kwargs):
        real_smtp_attempts.append((args, kwargs))
        raise ConnectionError("Real SMTP connections are blocked during tests")

    monkeypatch.setattr(email_notifier.smtplib, "SMTP", _smtp_guard)
    yield
    assert not real_smtp_attempts, "A test attempted a real SMTP connection"


@pytest.fixture(scope="function", autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db_session():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
