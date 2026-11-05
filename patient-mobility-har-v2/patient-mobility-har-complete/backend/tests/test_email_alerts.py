"""
Caregiver e-mail alerts.

Nothing here talks to a real mail server: smtplib.SMTP is replaced by an
in-memory fake (see `fake_smtp`), and the autouse fixture in conftest.py
fails any test that attempts a real SMTP connection. The "sender account"
used below is a made-up address with a made-up password.
"""

import logging
import threading
import time
import smtplib
from datetime import datetime, timedelta

import numpy as np
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.alerts import email_notifier
from app.config import settings
from app.database.session import Base
from app.models.activity import Activity, ActivityType
from app.models.alert import Alert, AlertPriority, AlertType
from app.models.alert_email_delivery import AlertEmailDelivery, EmailDeliveryStatus
from app.models.caregiver import Caregiver
from app.models.patient import Patient
from app.models.user import UserRole
from app.schemas.caregiver import CaregiverCreate
from app.services import alert_email_service, alert_service, auth_service, caregiver_service

FAKE_PASSWORD_AS_PASTED = "abcd efgh ijkl mnop"  # how Google displays an App Password (fake value)
FAKE_PASSWORD = "abcdefghijklmnop"


# --------------------------------------------------------------------------
# Fixtures / helpers
# --------------------------------------------------------------------------
@pytest.fixture
def fake_smtp(monkeypatch):
    """Installs an in-memory SMTP server. Returns the class so tests can inspect/steer it."""

    class FakeSMTP:
        instances: list = []
        fail_connect = None   # exception to raise when connecting
        fail_login = None     # exception to raise on login
        fail_send = None      # exception, or callable(msg) -> exception | None
        gate = None           # threading.Event the send waits on (to prove sending is non-blocking)

        def __init__(self, host, port, timeout=None):
            if FakeSMTP.fail_connect is not None:
                raise FakeSMTP.fail_connect
            self.host, self.port, self.timeout = host, port, timeout
            self.calls, self.sent, self.login_args = [], [], None
            FakeSMTP.instances.append(self)

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def ehlo(self):
            self.calls.append("ehlo")

        def starttls(self, context=None):
            self.calls.append("starttls")

        def login(self, user, password):
            self.calls.append("login")
            self.login_args = (user, password)
            if FakeSMTP.fail_login is not None:
                raise FakeSMTP.fail_login

        def send_message(self, msg):
            if FakeSMTP.gate is not None:
                assert FakeSMTP.gate.wait(timeout=10), "test gate was never released"
            failure = FakeSMTP.fail_send(msg) if callable(FakeSMTP.fail_send) else FakeSMTP.fail_send
            if failure is not None:
                raise failure
            self.calls.append("send_message")
            self.sent.append(msg)

    monkeypatch.setattr(email_notifier.smtplib, "SMTP", FakeSMTP)
    return FakeSMTP


def all_sent(fake_smtp):
    return [m for inst in fake_smtp.instances for m in inst.sent]


@pytest.fixture
def smtp_configured(monkeypatch):
    """A made-up sender account — enough for is_smtp_configured() to be True."""
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.gmail.com")
    monkeypatch.setattr(settings, "SMTP_PORT", 587)
    monkeypatch.setattr(settings, "SMTP_USERNAME", "sender.account@gmail.com")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", FAKE_PASSWORD_AS_PASTED)
    monkeypatch.setattr(settings, "SMTP_FROM_EMAIL", "sender.account@gmail.com")
    monkeypatch.setattr(settings, "SMTP_FROM_NAME", "MobilityWatch Alerts")


def make_patient(db, name="Asha Rao", room=None) -> Patient:
    patient = Patient(name=name, room_number=room)
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return patient


def make_caregiver(db, name, email, patients=()) -> Caregiver:
    caregiver = caregiver_service.create_caregiver(db, CaregiverCreate(full_name=name, phone="+911234567890"))
    # Write the e-mail straight to the row so tests can also store values the API would reject.
    caregiver.email = email
    db.commit()
    for patient in patients:
        caregiver_service.assign_to_patient(db, caregiver, patient)
    db.refresh(caregiver)
    return caregiver


def fire_alert(db, patient, alert_type=AlertType.fall, priority=AlertPriority.critical, message="Fall detected and confirmed.", screenshot_path=None):
    return alert_service.create_alert(
        db, patient=patient, alert_type=alert_type, priority=priority, message=message, screenshot_path=screenshot_path
    )


def deliveries(db, alert):
    db.expire_all()
    return db.query(AlertEmailDelivery).filter(AlertEmailDelivery.alert_id == alert.id).order_by(AlertEmailDelivery.id).all()


def plain_body(msg) -> str:
    return msg.get_body(preferencelist=("plain",)).get_content()


def html_body(msg) -> str:
    return msg.get_body(preferencelist=("html",)).get_content()


def admin_headers(client, db_session):
    auth_service.register_user(db_session, "Admin", "admin@test.com", "AdminPass123!", UserRole.admin)
    token = client.post("/api/v1/auth/login", data={"username": "admin@test.com", "password": "AdminPass123!"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# --------------------------------------------------------------------------
# Recipient selection
# --------------------------------------------------------------------------
def test_only_caregivers_assigned_to_the_patient_are_selected(db_session):
    patient = make_patient(db_session)
    other_patient = make_patient(db_session, "Someone Else")
    assigned = make_caregiver(db_session, "Assigned", "assigned@example.com", [patient])
    make_caregiver(db_session, "Unrelated", "unrelated@example.com", [other_patient])
    make_caregiver(db_session, "Unassigned", "nobody@example.com")

    selection = alert_email_service.select_recipients(patient)

    assert [r.email for r in selection.recipients] == ["assigned@example.com"]
    assert selection.recipients[0].caregiver_id == assigned.id


def test_all_assigned_caregivers_with_valid_emails_are_selected(db_session):
    patient = make_patient(db_session)
    make_caregiver(db_session, "One", "one@example.com", [patient])
    make_caregiver(db_session, "Two", "two@example.org", [patient])
    make_caregiver(db_session, "Three", "three@example.net", [patient])

    selection = alert_email_service.select_recipients(patient)

    assert [r.email for r in selection.recipients] == ["one@example.com", "two@example.org", "three@example.net"]
    assert selection.skipped == []


def test_missing_and_invalid_addresses_are_skipped_with_a_reason(db_session):
    patient = make_patient(db_session)
    make_caregiver(db_session, "Good", "good@example.com", [patient])
    make_caregiver(db_session, "NoEmail", None, [patient])
    make_caregiver(db_session, "Blank", "   ", [patient])
    make_caregiver(db_session, "Garbage", "not-an-email", [patient])
    make_caregiver(db_session, "Injection", "a@example.com\nBcc: evil@example.com", [patient])
    make_caregiver(db_session, "DisplayName", "Raj <raj@example.com>", [patient])

    selection = alert_email_service.select_recipients(patient)

    assert [r.email for r in selection.recipients] == ["good@example.com"]
    assert {name for _, name, _ in selection.skipped} == {"NoEmail", "Blank", "Garbage", "Injection", "DisplayName"}


def test_duplicate_addresses_are_only_used_once_and_whitespace_is_trimmed(db_session):
    patient = make_patient(db_session)
    make_caregiver(db_session, "A", "  Family@Example.com ", [patient])
    make_caregiver(db_session, "B", "family@example.com", [patient])

    selection = alert_email_service.select_recipients(patient)

    assert len(selection.recipients) == 1
    assert selection.recipients[0].email.lower() == "family@example.com"
    assert len(selection.skipped) == 1


def test_there_is_no_global_recipient_setting():
    """The recipient must come from the caregivers saved in the database, never from .env."""
    assert not hasattr(settings, "ALERT_RECIPIENT_EMAIL")


# --------------------------------------------------------------------------
# Sending through the alert pipeline
# --------------------------------------------------------------------------
def test_alert_emails_the_assigned_caregivers_saved_address(db_session, fake_smtp, smtp_configured):
    patient = make_patient(db_session, "Asha Rao", room="204")
    make_caregiver(db_session, "Priya", "priya.caregiver@gmail.com", [patient])

    alert = fire_alert(db_session, patient)

    sent = all_sent(fake_smtp)
    assert len(sent) == 1
    msg = sent[0]
    assert msg["To"] == "priya.caregiver@gmail.com"
    assert "sender.account@gmail.com" in msg["From"] and "MobilityWatch" in msg["From"]
    assert msg["Subject"] == "[MobilityWatch] Fall detected — Asha Rao"

    # Gmail settings: 587 + STARTTLS + login with the sender account (spaces in the pasted App Password removed)
    smtp = fake_smtp.instances[0]
    assert (smtp.host, smtp.port) == ("smtp.gmail.com", 587)
    assert smtp.calls.index("starttls") < smtp.calls.index("login") < smtp.calls.index("send_message")
    assert smtp.login_args == ("sender.account@gmail.com", FAKE_PASSWORD)
    assert smtp.timeout and smtp.timeout > 0

    body = plain_body(msg)
    for expected in [
        "MobilityWatch", "Hello Priya", "Asha Rao", "Patient ID:", f"#{patient.id}", "Room:", "204",
        "Fall detected", "Critical", "Fall detected and confirmed.", "Detected at:",
        email_notifier.format_local_time(alert.created_at), "RECOMMENDED ACTION", "check on the patient",
    ]:
        assert expected in body, f"{expected!r} missing from plain-text body"
    assert "Asha Rao" in html_body(msg) and "Recommended action" in html_body(msg)

    rows = deliveries(db_session, alert)
    assert len(rows) == 1 and rows[0].status == EmailDeliveryStatus.sent and rows[0].sent_at is not None


def test_recipient_comes_from_the_database_and_follows_edits(db_session, fake_smtp, smtp_configured):
    patient = make_patient(db_session)
    caregiver = make_caregiver(db_session, "Priya", "old.address@gmail.com", [patient])
    caregiver.email = "new.address@gmail.com"
    db_session.commit()

    fire_alert(db_session, patient)

    assert [m["To"] for m in all_sent(fake_smtp)] == ["new.address@gmail.com"]


def test_multiple_assigned_caregivers_all_get_the_alert_and_unrelated_ones_do_not(db_session, fake_smtp, smtp_configured):
    patient = make_patient(db_session)
    other_patient = make_patient(db_session, "Other Patient")
    make_caregiver(db_session, "One", "one@gmail.com", [patient])
    make_caregiver(db_session, "Two", "two@gmail.com", [patient, other_patient])
    make_caregiver(db_session, "Unrelated", "unrelated@gmail.com", [other_patient])
    make_caregiver(db_session, "Nobody", "nobody@gmail.com")

    alert = fire_alert(db_session, patient)

    assert sorted(m["To"] for m in all_sent(fake_smtp)) == ["one@gmail.com", "two@gmail.com"]
    assert {r.status for r in deliveries(db_session, alert)} == {EmailDeliveryStatus.sent}
    # each person is addressed individually (no caregiver can see another's address)
    assert all("," not in m["To"] and m["Cc"] is None for m in all_sent(fake_smtp))


def test_inactivity_alert_uses_its_own_label_and_advice(db_session, fake_smtp, smtp_configured):
    patient = make_patient(db_session)
    make_caregiver(db_session, "Priya", "priya@gmail.com", [patient])

    fire_alert(
        db_session, patient, AlertType.inactivity, AlertPriority.warning,
        "No significant movement for over 60 seconds.",
    )

    msg = all_sent(fake_smtp)[0]
    assert msg["Subject"] == "[MobilityWatch] Inactivity warning — Asha Rao"
    body = plain_body(msg)
    assert "Inactivity warning" in body and "Warning" in body
    assert "No significant movement for over 60 seconds." in body
    assert "emergency services" not in body  # that advice is only for falls


def test_last_recorded_activity_is_included_only_when_it_exists(db_session, fake_smtp, smtp_configured):
    with_activity = make_patient(db_session, "Has Activity")
    without_activity = make_patient(db_session, "No Activity")
    make_caregiver(db_session, "C1", "c1@gmail.com", [with_activity])
    make_caregiver(db_session, "C2", "c2@gmail.com", [without_activity])
    db_session.add(Activity(patient_id=with_activity.id, activity_type=ActivityType.sitting, confidence=0.9))
    db_session.commit()

    fire_alert(db_session, with_activity)
    fire_alert(db_session, without_activity)

    bodies = {m["To"]: plain_body(m) for m in all_sent(fake_smtp)}
    assert "Last recorded activity:" in bodies["c1@gmail.com"] and "Sitting" in bodies["c1@gmail.com"]
    assert "Last recorded activity" not in bodies["c2@gmail.com"]  # nothing is invented
    assert "Room:" not in bodies["c2@gmail.com"]  # no room saved -> no room line


def test_patient_names_cannot_inject_headers_or_html(db_session, fake_smtp, smtp_configured):
    patient = make_patient(db_session, 'Evil\r\nBcc: attacker@example.com <script>alert(1)</script>')
    make_caregiver(db_session, "Priya", "priya@gmail.com", [patient])

    fire_alert(db_session, patient)

    msg = all_sent(fake_smtp)[0]
    assert "\n" not in msg["Subject"] and "\r" not in msg["Subject"]
    assert msg["Bcc"] is None
    assert "<script>" not in html_body(msg) and "&lt;script&gt;" in html_body(msg)


@pytest.mark.skipif(not hasattr(time, "tzset"), reason="time.tzset is not available on Windows")
def test_detection_time_is_shown_in_local_time_with_offset(monkeypatch):
    monkeypatch.setenv("TZ", "Asia/Kolkata")
    time.tzset()
    try:
        # The real fall in the project's own log: stored as 11:55:33 UTC, i.e. 17:25:33 in India.
        text_ = email_notifier.format_local_time(datetime(2026, 10, 12, 11, 55, 33))
        assert text_ == "12 Oct 2026, 05:25:33 PM IST (UTC+05:30)"
    finally:
        monkeypatch.undo()
        time.tzset()
    assert email_notifier.format_local_time(None) == "Not recorded"


# --------------------------------------------------------------------------
# Screenshot attachment
# --------------------------------------------------------------------------
def test_screenshot_is_attached_only_when_it_lives_inside_the_uploads_folder(db_session, fake_smtp, smtp_configured, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path / "uploads"))
    shots = settings.upload_path / "alert_screenshots"
    shots.mkdir(parents=True)
    (shots / "ok.jpg").write_bytes(b"\xff\xd8\xff fake jpeg bytes")
    (tmp_path / "secret.txt").write_text("do not attach me")

    patient = make_patient(db_session)
    make_caregiver(db_session, "Priya", "priya@gmail.com", [patient])

    fire_alert(db_session, patient, screenshot_path="/uploads/alert_screenshots/ok.jpg")
    fire_alert(db_session, patient, screenshot_path="/uploads/../secret.txt")      # path traversal attempt
    fire_alert(db_session, patient, screenshot_path="/uploads/alert_screenshots/missing.jpg")  # file gone

    first, traversal, missing = all_sent(fake_smtp)
    assert [a.get_filename() for a in first.iter_attachments()] == ["ok.jpg"]
    assert list(traversal.iter_attachments()) == []
    assert list(missing.iter_attachments()) == []  # still delivered, just without a picture

    monkeypatch.setattr(settings, "ALERT_EMAIL_ATTACH_SCREENSHOT", False)
    fire_alert(db_session, patient, screenshot_path="/uploads/alert_screenshots/ok.jpg")
    assert list(all_sent(fake_smtp)[-1].iter_attachments()) == []


# --------------------------------------------------------------------------
# Nothing to send / not configured
# --------------------------------------------------------------------------
def test_alert_is_saved_and_nothing_is_sent_when_no_caregiver_is_assigned(db_session, fake_smtp, smtp_configured):
    patient = make_patient(db_session)
    make_caregiver(db_session, "Unassigned", "unassigned@gmail.com")

    alert = fire_alert(db_session, patient)

    assert db_session.query(Alert).count() == 1
    assert all_sent(fake_smtp) == []
    rows = deliveries(db_session, alert)
    assert len(rows) == 1 and rows[0].status == EmailDeliveryStatus.skipped
    assert "No caregiver is assigned" in rows[0].detail


def test_alert_is_saved_when_assigned_caregivers_have_no_usable_email(db_session, fake_smtp, smtp_configured, caplog):
    patient = make_patient(db_session)
    make_caregiver(db_session, "NoEmail", None, [patient])
    make_caregiver(db_session, "BadEmail", "oops", [patient])

    with caplog.at_level(logging.WARNING):
        alert = fire_alert(db_session, patient)

    assert db_session.query(Alert).count() == 1 and all_sent(fake_smtp) == []
    assert "no email address saved" in caplog.text and "not valid" in caplog.text  # the problem is logged
    assert "No assigned caregiver has a valid email address" in deliveries(db_session, alert)[0].detail


def test_alert_is_saved_and_app_keeps_running_when_smtp_is_not_configured(db_session, fake_smtp):
    patient = make_patient(db_session)
    make_caregiver(db_session, "Priya", "priya@gmail.com", [patient])  # smtp_configured fixture NOT used

    alert = fire_alert(db_session, patient)

    assert alert.id is not None and db_session.query(Alert).count() == 1
    assert fake_smtp.instances == []  # not even a connection attempt
    rows = deliveries(db_session, alert)
    assert rows[0].status == EmailDeliveryStatus.skipped and "not configured" in rows[0].detail


@pytest.mark.parametrize(
    "username,password",
    [
        ("your_sender_gmail@gmail.com", "your_gmail_app_password"),  # untouched .env.example placeholders
        ("sender.account@gmail.com", "your_app_password"),
        ("sender.account@gmail.com", ""),
        ("", FAKE_PASSWORD),
        ("sender.account@gmail.com", "   "),
    ],
)
def test_placeholder_or_partial_credentials_count_as_not_configured(monkeypatch, username, password):
    monkeypatch.setattr(settings, "SMTP_USERNAME", username)
    monkeypatch.setattr(settings, "SMTP_PASSWORD", password)
    assert email_notifier.is_smtp_configured() is False


def test_from_address_falls_back_to_the_login_when_not_set(monkeypatch, smtp_configured):
    monkeypatch.setattr(settings, "SMTP_FROM_EMAIL", "")
    assert email_notifier.from_address() == "sender.account@gmail.com"


def test_master_switch_turns_caregiver_emails_off_but_still_saves_alerts(db_session, fake_smtp, smtp_configured, monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_ALERTS_ENABLED", False)
    patient = make_patient(db_session)
    make_caregiver(db_session, "Priya", "priya@gmail.com", [patient])

    fire_alert(db_session, patient)

    assert db_session.query(Alert).count() == 1 and fake_smtp.instances == []


# --------------------------------------------------------------------------
# SMTP failures
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "failure_attr,exception,expected_text",
    [
        ("fail_login", smtplib.SMTPAuthenticationError(535, b"5.7.8 Username and Password not accepted"), "rejected the sender login"),
        ("fail_connect", smtplib.SMTPConnectError(421, "Service not available"), "Could not connect"),
        ("fail_connect", TimeoutError("timed out"), "Could not connect"),
        ("fail_connect", OSError("Network is unreachable"), "Could not connect"),
        ("fail_send", smtplib.SMTPRecipientsRefused({"x@y.com": (550, b"no such user")}), "refused the recipient"),
        ("fail_send", smtplib.SMTPDataError(554, b"rejected as spam"), "reported an error"),
        ("fail_send", RuntimeError("boom"), "Unexpected error"),
    ],
)
def test_smtp_failure_never_breaks_alert_saving_and_never_leaks_the_password(
    db_session, fake_smtp, smtp_configured, caplog, failure_attr, exception, expected_text
):
    setattr(fake_smtp, failure_attr, exception)
    patient = make_patient(db_session)
    make_caregiver(db_session, "Priya", "priya@gmail.com", [patient])

    with caplog.at_level(logging.DEBUG):
        alert = fire_alert(db_session, patient)  # must not raise

    assert db_session.query(Alert).count() == 1
    rows = deliveries(db_session, alert)
    assert len(rows) == 1 and rows[0].status == EmailDeliveryStatus.failed
    assert expected_text in rows[0].detail
    assert rows[0].sent_at is None
    assert "FAILED" in caplog.text  # failure is recorded in the logs
    for secret in (FAKE_PASSWORD, FAKE_PASSWORD_AS_PASTED):
        assert secret not in caplog.text and secret not in (rows[0].detail or "")


def test_one_failing_recipient_does_not_stop_the_others(db_session, fake_smtp, smtp_configured):
    patient = make_patient(db_session)
    make_caregiver(db_session, "Bad", "bad@gmail.com", [patient])
    make_caregiver(db_session, "Good", "good@gmail.com", [patient])
    fake_smtp.fail_send = lambda msg: smtplib.SMTPRecipientsRefused({}) if msg["To"] == "bad@gmail.com" else None

    alert = fire_alert(db_session, patient)

    assert [m["To"] for m in all_sent(fake_smtp)] == ["good@gmail.com"]
    statuses = {r.recipient_email: r.status for r in deliveries(db_session, alert)}
    assert statuses == {"bad@gmail.com": EmailDeliveryStatus.failed, "good@gmail.com": EmailDeliveryStatus.sent}


def test_failures_while_building_the_message_are_contained(db_session, fake_smtp, smtp_configured, monkeypatch):
    monkeypatch.setattr(email_notifier, "build_alert_email", lambda *a, **k: (_ for _ in ()).throw(ValueError("template bug")))
    patient = make_patient(db_session)
    make_caregiver(db_session, "Priya", "priya@gmail.com", [patient])

    alert = fire_alert(db_session, patient)

    assert db_session.query(Alert).count() == 1
    assert deliveries(db_session, alert)[0].status == EmailDeliveryStatus.failed


def test_unexpected_error_inside_dispatch_is_swallowed(db_session, smtp_configured, monkeypatch):
    patient = make_patient(db_session)
    make_caregiver(db_session, "Priya", "priya@gmail.com", [patient])
    monkeypatch.setattr(alert_email_service, "select_recipients", lambda p: (_ for _ in ()).throw(RuntimeError("db hiccup")))

    alert = fire_alert(db_session, patient)  # must not raise

    assert alert.id is not None and db_session.query(Alert).count() == 1


# --------------------------------------------------------------------------
# Duplicate prevention
# --------------------------------------------------------------------------
def test_dispatching_the_same_alert_twice_sends_only_one_email(db_session, fake_smtp, smtp_configured):
    patient = make_patient(db_session)
    make_caregiver(db_session, "Priya", "priya@gmail.com", [patient])
    alert = fire_alert(db_session, patient)
    assert len(all_sent(fake_smtp)) == 1

    alert_email_service.dispatch_alert_emails(db_session, alert, patient)
    alert_email_service.dispatch_alert_emails(db_session, alert, patient)

    assert len(all_sent(fake_smtp)) == 1
    assert len(deliveries(db_session, alert)) == 1


def test_database_itself_refuses_a_second_delivery_row_for_the_same_alert_and_address(db_session):
    patient = make_patient(db_session)
    alert = Alert(patient_id=patient.id, type=AlertType.fall, priority=AlertPriority.critical, message="x")
    db_session.add(alert)
    db_session.commit()
    db_session.add(AlertEmailDelivery(alert_id=alert.id, recipient_email="a@example.com", status=EmailDeliveryStatus.sent))
    db_session.commit()

    db_session.add(AlertEmailDelivery(alert_id=alert.id, recipient_email="a@example.com", status=EmailDeliveryStatus.pending))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_a_concurrent_claim_for_the_same_alert_is_detected_and_skipped(db_session, fake_smtp, smtp_configured, monkeypatch):
    """Simulates another thread claiming the same (alert, address) between our check and our insert."""
    patient = make_patient(db_session)
    make_caregiver(db_session, "Priya", "priya@gmail.com", [patient])
    alert = alert_service.Alert(patient_id=patient.id, type=AlertType.fall, priority=AlertPriority.critical, message="x")
    db_session.add(alert)
    db_session.commit()

    real_cooldown = alert_email_service._in_cooldown

    def racing_cooldown(db, a, pid, key):
        other = sessionmaker(bind=db.get_bind())()
        other.add(AlertEmailDelivery(alert_id=a.id, recipient_email=key, status=EmailDeliveryStatus.pending))
        other.commit()
        other.close()
        return real_cooldown(db, a, pid, key)

    monkeypatch.setattr(alert_email_service, "_in_cooldown", racing_cooldown)

    alert_email_service.dispatch_alert_emails(db_session, alert, patient)

    assert fake_smtp.instances == []  # we lost the race, so we do not send a second copy
    assert len(deliveries(db_session, alert)) == 1


def test_cooldown_suppresses_a_repeat_email_for_the_same_patient_and_alert_type(db_session, fake_smtp, smtp_configured, monkeypatch, caplog):
    monkeypatch.setattr(settings, "ALERT_EMAIL_COOLDOWN_SEC", 60.0)
    patient = make_patient(db_session)
    make_caregiver(db_session, "Priya", "priya@gmail.com", [patient])

    first = fire_alert(db_session, patient)
    with caplog.at_level(logging.WARNING):
        second = fire_alert(db_session, patient)                                            # same patient + type, right away
    third = fire_alert(db_session, patient, AlertType.inactivity, AlertPriority.warning, "idle")  # different type

    assert len(all_sent(fake_smtp)) == 2  # first fall + the inactivity alert
    assert deliveries(db_session, first)[0].status == EmailDeliveryStatus.sent
    assert deliveries(db_session, second)[0].status == EmailDeliveryStatus.skipped
    assert "already e-mailed" in deliveries(db_session, second)[0].detail
    assert "already e-mailed" in caplog.text
    assert deliveries(db_session, third)[0].status == EmailDeliveryStatus.sent
    assert db_session.query(Alert).count() == 3  # every alert is still saved


def test_cooldown_does_not_apply_to_other_patients_or_after_it_expires_or_when_disabled(db_session, fake_smtp, smtp_configured, monkeypatch):
    monkeypatch.setattr(settings, "ALERT_EMAIL_COOLDOWN_SEC", 60.0)
    p1, p2 = make_patient(db_session, "P1"), make_patient(db_session, "P2")
    make_caregiver(db_session, "Shared", "shared@gmail.com", [p1, p2])

    first = fire_alert(db_session, p1)
    fire_alert(db_session, p2)                           # different patient -> sends
    assert len(all_sent(fake_smtp)) == 2

    row = deliveries(db_session, first)[0]
    row.created_at = datetime.utcnow() - timedelta(seconds=120)  # cooldown window has passed
    db_session.commit()
    fire_alert(db_session, p1)
    assert len(all_sent(fake_smtp)) == 3

    monkeypatch.setattr(settings, "ALERT_EMAIL_COOLDOWN_SEC", 0.0)
    fire_alert(db_session, p1)                           # guard disabled -> sends again
    assert len(all_sent(fake_smtp)) == 4


# --------------------------------------------------------------------------
# Never blocks monitoring
# --------------------------------------------------------------------------
def test_slow_smtp_does_not_block_alert_creation_when_async(db_session, fake_smtp, smtp_configured, monkeypatch):
    monkeypatch.setattr(settings, "ALERT_EMAIL_ASYNC", True)
    fake_smtp.gate = threading.Event()  # the "mail server" stalls until we release it
    patient = make_patient(db_session)
    make_caregiver(db_session, "Priya", "priya@gmail.com", [patient])

    started = time.monotonic()
    alert = fire_alert(db_session, patient)   # returns while the send is still stuck
    elapsed = time.monotonic() - started

    assert elapsed < 3, "alert creation waited for the mail server"
    assert db_session.query(Alert).count() == 1
    assert all_sent(fake_smtp) == []
    assert deliveries(db_session, alert)[0].status == EmailDeliveryStatus.pending

    fake_smtp.gate.set()
    assert alert_email_service.flush(timeout=10)
    assert len(all_sent(fake_smtp)) == 1
    assert deliveries(db_session, alert)[0].status == EmailDeliveryStatus.sent


# --------------------------------------------------------------------------
# Camera pipeline -> alert -> e-mail
# --------------------------------------------------------------------------
def test_pipeline_alert_path_emails_the_patients_assigned_caregiver(db_session, fake_smtp, smtp_configured, tmp_path, monkeypatch):
    """
    Drives the real MonitoringWorker alert path (screenshot capture -> create_alert -> caregiver e-mail).
    Pose and classifier are stubbed exactly as in test_worker_activity_pipeline.py; the detector
    outcome is the thing under test here, so a confirmed fall is injected at that point.
    """
    from app.pipeline import monitoring_worker as mw

    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setattr(mw, "SessionLocal", sessionmaker(bind=db_session.get_bind()))
    monkeypatch.setattr(mw.live_frame_buffer, "update", lambda **kw: None)

    patient = make_patient(db_session, "Pipeline Patient")
    make_caregiver(db_session, "Priya", "priya@gmail.com", [patient])
    make_caregiver(db_session, "Not Assigned", "stranger@gmail.com")

    worker = mw.MonitoringWorker()
    worker._active_patient_id = patient.id
    frame = np.zeros((48, 64, 3), dtype=np.uint8)

    worker._raise_alert(AlertType.fall, AlertPriority.critical, "Fall detected and confirmed.", frame)

    assert db_session.query(Alert).count() == 1
    msgs = all_sent(fake_smtp)
    assert [m["To"] for m in msgs] == ["priya@gmail.com"]
    assert "Pipeline Patient" in msgs[0]["Subject"]
    attachments = list(msgs[0].iter_attachments())
    assert len(attachments) == 1 and attachments[0].get_filename().endswith(".jpg")  # the real captured frame


def test_pipeline_survives_email_failure(db_session, fake_smtp, smtp_configured, tmp_path, monkeypatch):
    from app.pipeline import monitoring_worker as mw

    fake_smtp.fail_connect = ConnectionRefusedError("down")
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setattr(mw, "SessionLocal", sessionmaker(bind=db_session.get_bind()))
    patient = make_patient(db_session)
    make_caregiver(db_session, "Priya", "priya@gmail.com", [patient])
    worker = mw.MonitoringWorker()
    worker._active_patient_id = patient.id

    worker._raise_alert(AlertType.inactivity, AlertPriority.warning, "idle", np.zeros((48, 64, 3), dtype=np.uint8))

    assert db_session.query(Alert).count() == 1


# --------------------------------------------------------------------------
# Test-email endpoint (admin only)
# --------------------------------------------------------------------------
def test_test_email_endpoint_requires_login(client, db_session):
    caregiver = make_caregiver(db_session, "Priya", "priya@gmail.com")
    assert client.post(f"/api/v1/caregivers/{caregiver.id}/test-email").status_code == 401


def test_test_email_endpoint_is_admin_only(client, db_session, fake_smtp, smtp_configured):
    caregiver = make_caregiver(db_session, "Priya", "priya@gmail.com")
    auth_service.register_user(db_session, "Care", "care@test.com", "CarePass123!", UserRole.caregiver)
    token = client.post("/api/v1/auth/login", data={"username": "care@test.com", "password": "CarePass123!"}).json()["access_token"]

    response = client.post(f"/api/v1/caregivers/{caregiver.id}/test-email", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 403
    assert fake_smtp.instances == []


def test_test_email_goes_to_the_saved_address_and_response_hides_secrets(client, db_session, fake_smtp, smtp_configured):
    headers = admin_headers(client, db_session)
    caregiver = make_caregiver(db_session, "Priya", "priya.caregiver@gmail.com")

    response = client.post(f"/api/v1/caregivers/{caregiver.id}/test-email", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["sent"] is True and body["recipient"] == "p***@gmail.com"
    for secret in (FAKE_PASSWORD, FAKE_PASSWORD_AS_PASTED, "priya.caregiver"):
        assert secret not in response.text
    msg = all_sent(fake_smtp)[0]
    assert msg["To"] == "priya.caregiver@gmail.com" and "Test email" in msg["Subject"]
    assert "TEST" in plain_body(msg) and "nothing needs your attention" in plain_body(msg)


def test_test_email_cannot_be_aimed_at_an_arbitrary_address(client, db_session, fake_smtp, smtp_configured):
    headers = admin_headers(client, db_session)
    caregiver = make_caregiver(db_session, "Priya", "priya@gmail.com")

    client.post(f"/api/v1/caregivers/{caregiver.id}/test-email", params={"to": "attacker@example.com"},
                json={"to": "attacker@example.com", "email": "attacker@example.com"}, headers=headers)

    assert [m["To"] for m in all_sent(fake_smtp)] == ["priya@gmail.com"]


def test_test_email_error_cases(client, db_session, fake_smtp, smtp_configured, monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(alert_email_service, "_now", lambda: clock[0])
    headers = admin_headers(client, db_session)
    no_email = make_caregiver(db_session, "NoEmail", None)
    good = make_caregiver(db_session, "Priya", "priya@gmail.com")
    url = f"/api/v1/caregivers/{good.id}/test-email"

    assert client.post("/api/v1/caregivers/9999/test-email", headers=headers).status_code == 404
    assert client.post(f"/api/v1/caregivers/{no_email.id}/test-email", headers=headers).status_code == 400

    fake_smtp.fail_login = smtplib.SMTPAuthenticationError(535, b"bad credentials")
    failed = client.post(url, headers=headers)
    assert failed.status_code == 502 and "rejected the sender login" in failed.json()["detail"]
    assert FAKE_PASSWORD not in failed.text

    # After a FAILURE only a short wait applies, so fixing the password and retrying is quick...
    fake_smtp.fail_login = None
    assert client.post(url, headers=headers).status_code == 429
    clock[0] += 6
    assert client.post(url, headers=headers).status_code == 200
    # ...but after a SUCCESS the longer limit protects the caregiver's inbox.
    clock[0] += 6
    assert client.post(url, headers=headers).status_code == 429
    clock[0] += 31
    assert client.post(url, headers=headers).status_code == 200

    monkeypatch.setattr(settings, "SMTP_PASSWORD", "")
    other = make_caregiver(db_session, "Other", "other@gmail.com")
    unconfigured = client.post(f"/api/v1/caregivers/{other.id}/test-email", headers=headers)
    assert unconfigured.status_code == 503 and "not configured" in unconfigured.json()["detail"]


# --------------------------------------------------------------------------
# Caregiver e-mail validation + Alerts API
# --------------------------------------------------------------------------
def test_caregiver_email_is_validated_normalized_and_optional(client, db_session):
    headers = admin_headers(client, db_session)

    bad = client.post("/api/v1/caregivers", json={"full_name": "X", "phone": "1", "email": "not-an-email"}, headers=headers)
    assert bad.status_code == 422

    blank = client.post("/api/v1/caregivers", json={"full_name": "X", "phone": "1", "email": "   "}, headers=headers)
    assert blank.status_code == 201 and blank.json()["email"] is None

    padded = client.post("/api/v1/caregivers", json={"full_name": "Y", "phone": "1", "email": "  Raj@Gmail.com "}, headers=headers)
    assert padded.status_code == 201 and padded.json()["email"] == "Raj@gmail.com"

    cid = padded.json()["id"]
    assert client.put(f"/api/v1/caregivers/{cid}", json={"email": "bad@@x"}, headers=headers).status_code == 422
    assert client.put(f"/api/v1/caregivers/{cid}", json={"email": "ok@example.com"}, headers=headers).json()["email"] == "ok@example.com"


def test_legacy_caregiver_with_a_bad_saved_email_can_still_be_listed(client, db_session):
    headers = admin_headers(client, db_session)
    make_caregiver(db_session, "Legacy", "typo-without-at-sign")
    response = client.get("/api/v1/caregivers", headers=headers)
    assert response.status_code == 200 and response.json()[0]["email"] == "typo-without-at-sign"


def test_alerts_api_reports_email_delivery_without_leaking_addresses_or_secrets(client, db_session, fake_smtp, smtp_configured):
    headers = admin_headers(client, db_session)
    patient = make_patient(db_session)
    make_caregiver(db_session, "Priya", "priya@gmail.com", [patient])
    alert = fire_alert(db_session, patient)

    response = client.get("/api/v1/alerts", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1 and data[0]["id"] == alert.id
    assert [d["status"] for d in data[0]["email_deliveries"]] == ["sent"]
    for forbidden in ("priya@gmail.com", FAKE_PASSWORD, "sender.account"):
        assert forbidden not in response.text
    # existing behaviour is unchanged
    assert client.patch(f"/api/v1/alerts/{alert.id}/resolve", json={}, headers=headers).json()["status"] == "resolved"


def test_deleting_a_patient_also_removes_its_alerts_and_delivery_records(client, db_session, fake_smtp, smtp_configured):
    headers = admin_headers(client, db_session)
    patient = make_patient(db_session)
    make_caregiver(db_session, "Priya", "priya@gmail.com", [patient])
    fire_alert(db_session, patient)
    assert db_session.query(AlertEmailDelivery).count() == 1

    assert client.delete(f"/api/v1/patients/{patient.id}", headers=headers).status_code == 204

    db_session.expire_all()
    assert db_session.query(Alert).count() == 0 and db_session.query(AlertEmailDelivery).count() == 0


# --------------------------------------------------------------------------
# Upgrading an existing database
# --------------------------------------------------------------------------
def test_new_table_is_added_to_an_existing_database_without_touching_existing_data(tmp_path):
    """Mimics a user's old patient_mobility.db that predates the delivery table."""
    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    old_tables = [t for name, t in Base.metadata.tables.items() if name != "alert_email_deliveries"]
    Base.metadata.create_all(engine, tables=old_tables)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO patients (id, name, created_at) VALUES (1, 'Existing Patient', '2026-10-01 10:00:00')"))
        conn.execute(text(
            "INSERT INTO alerts (id, patient_id, type, priority, status, message, created_at) "
            "VALUES (1, 1, 'fall', 'critical', 'resolved', 'old alert', '2026-10-01 10:05:00')"
        ))
        assert "alert_email_deliveries" not in {r[0] for r in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))}

    Base.metadata.create_all(engine)  # this is exactly what init_db() does at every startup

    with engine.connect() as conn:
        tables = {r[0] for r in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))}
        assert "alert_email_deliveries" in tables
        assert conn.execute(text("SELECT name FROM patients")).scalar() == "Existing Patient"
        assert conn.execute(text("SELECT message FROM alerts")).scalar() == "old alert"
    engine.dispose()


def test_full_chain_landmarks_to_fall_detector_to_alert_to_caregiver_email(db_session, fake_smtp, smtp_configured, tmp_path, monkeypatch):
    """
    landmarks -> real FeatureExtractor -> real FallDetector -> real worker alert path ->
    create_alert -> caregiver e-mail. Only the camera/MediaPipe landmarks and the activity
    classifier are stubbed (same technique as test_worker_activity_pipeline.py). This does NOT
    prove MediaPipe or the trained classifier work on a live camera.
    """
    from app.ml.fall_detector import FallDetector
    from app.ml.feature_extractor import FeatureExtractor
    from app.ml.inactivity_detector import InactivityDetector
    from app.pipeline import monitoring_worker as mw
    from tests.test_activity_recognition import _landmarks, _p

    class StubClassifier:
        label = "standing"

        def predict_proba(self, _v):
            return _p(self.label, 0.9)

    class Pose:
        landmarks = None

        def process(self, _frame):
            return self.landmarks

    clock = {"t": 1000.0}
    classifier = StubClassifier()
    monkeypatch.setattr(mw, "activity_classifier", classifier)
    monkeypatch.setattr(mw.live_frame_buffer, "update", lambda **kw: None)
    monkeypatch.setattr(mw.time, "time", lambda: clock["t"])
    monkeypatch.setattr(mw, "SessionLocal", sessionmaker(bind=db_session.get_bind()))
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path / "uploads"))

    patient = make_patient(db_session, "Chain Patient")
    make_caregiver(db_session, "Priya", "priya@gmail.com", [patient])
    worker = mw.MonitoringWorker()
    worker._active_patient_id = patient.id
    worker._active_camera_setting = type("Cam", (), {"id": None})()
    monkeypatch.setattr(worker, "_sync_activity_segment", lambda *a, **k: None)

    pose, extractor = Pose(), FeatureExtractor()
    fall, idle = FallDetector(confirmation_window_sec=1.0), InactivityDetector(threshold_sec=999)
    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    def run(frames, **pose_kwargs):
        for _ in range(frames):
            pose.landmarks = _landmarks(aspect=640 / 480, **pose_kwargs)
            worker._process_frame(frame, pose, extractor, fall, idle)
            clock["t"] += 0.1

    run(15, offset=(0.5, 0.35))                                  # standing
    assert db_session.query(Alert).count() == 0 and fake_smtp.instances == []
    classifier.label = "lying"
    run(1, rotate_deg=90, offset=(0.5, 0.80))                    # sudden drop
    run(15, rotate_deg=90, offset=(0.5, 0.80))                   # motionless afterwards

    assert db_session.query(Alert).count() == 1
    assert [m["To"] for m in all_sent(fake_smtp)] == ["priya@gmail.com"]
    assert "Fall detected — Chain Patient" in all_sent(fake_smtp)[0]["Subject"]
