"""
Caregiver e-mail notifications for alerts.

Called from `alert_service.create_alert()` right after an alert has been
saved (so the alert exists in the database no matter what happens here).

How the recipient is found (nothing about recipients lives in `.env`):
    alert -> patient -> patient.caregivers (the patient<->caregiver
    assignments made on the Caregivers page) -> each caregiver's saved
    e-mail address.
Caregivers NOT assigned to the patient are never e-mailed.

Safety properties:
  * `dispatch_alert_emails()` never raises — a mail problem can't crash
    camera monitoring or stop the alert from being saved.
  * Duplicate prevention: UNIQUE(alert_id, recipient_email) in the
    `alert_email_deliveries` table, plus a short per-patient/per-alert-type
    cooldown (ALERT_EMAIL_COOLDOWN_SEC) against a flapping detector.
  * Sending happens on a small background worker (ALERT_EMAIL_ASYNC) so a
    slow SMTP server can't stall the camera loop.
  * Every outcome (sent / failed / skipped) is logged — with masked
    addresses and no credentials — and stored for the Alerts page.
"""

import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.alerts import email_notifier
from app.alerts.email_notifier import AlertEmailContext
from app.config import settings
from app.database.session import SessionLocal
from app.models.activity import Activity
from app.models.alert import Alert
from app.models.alert_email_delivery import AlertEmailDelivery, EmailDeliveryStatus
from app.models.caregiver import Caregiver
from app.models.patient import Patient
from app.utils.email_validation import mask_email, normalize_email
from app.utils.logger import get_logger

logger = get_logger(__name__)

# A tiny pool: alert e-mails are rare, and two workers keep one slow send
# from delaying another caregiver's message.
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="alert-email")
_pending: "set[Future]" = set()
_pending_lock = threading.Lock()


# --------------------------------------------------------------------------
# Recipient selection
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Recipient:
    caregiver_id: int
    name: str
    email: str  # validated + normalized


@dataclass
class RecipientSelection:
    recipients: List[Recipient]
    skipped: List[Tuple[int, str, str]]  # (caregiver_id, caregiver_name, reason)


def select_recipients(patient: Patient) -> RecipientSelection:
    """
    Returns the caregivers who should be e-mailed about `patient`:
    only caregivers ASSIGNED to this patient, with a valid saved e-mail
    address, one entry per distinct address.
    """
    recipients: List[Recipient] = []
    skipped: List[Tuple[int, str, str]] = []
    seen_addresses = set()

    for caregiver in sorted(patient.caregivers, key=lambda c: c.id):
        raw_email = (caregiver.email or "").strip()
        if not raw_email:
            skipped.append((caregiver.id, caregiver.full_name, "no email address saved"))
            continue
        normalized = normalize_email(raw_email)
        if normalized is None:
            skipped.append((caregiver.id, caregiver.full_name, "saved email address is not valid"))
            continue
        if normalized.lower() in seen_addresses:
            skipped.append((caregiver.id, caregiver.full_name, "same address already included for another caregiver"))
            continue
        seen_addresses.add(normalized.lower())
        recipients.append(Recipient(caregiver_id=caregiver.id, name=caregiver.full_name, email=normalized))

    return RecipientSelection(recipients=recipients, skipped=skipped)


# --------------------------------------------------------------------------
# Delivery records (duplicate prevention + visibility)
# --------------------------------------------------------------------------
def _record_skip(db: Session, alert: Alert, caregiver_id: Optional[int], email: Optional[str], reason: str) -> None:
    """Stores a 'skipped' row once per (alert, address); safe to call repeatedly."""
    key = email.lower() if email else None
    existing = (
        db.query(AlertEmailDelivery.id)
        .filter(
            AlertEmailDelivery.alert_id == alert.id,
            AlertEmailDelivery.recipient_email.is_(None) if key is None else AlertEmailDelivery.recipient_email == key,
        )
        .first()
    )
    if existing:
        return
    try:
        with db.begin_nested():
            db.add(
                AlertEmailDelivery(
                    alert_id=alert.id,
                    caregiver_id=caregiver_id,
                    recipient_email=key,
                    status=EmailDeliveryStatus.skipped,
                    detail=reason[:255],
                )
            )
        db.commit()
    except IntegrityError:
        db.rollback()


def _in_cooldown(db: Session, alert: Alert, patient_id: int, email_key: str) -> bool:
    window = settings.ALERT_EMAIL_COOLDOWN_SEC
    if window <= 0:
        return False
    cutoff = datetime.utcnow() - timedelta(seconds=window)
    recent = (
        db.query(AlertEmailDelivery.id)
        .join(Alert, Alert.id == AlertEmailDelivery.alert_id)
        .filter(
            Alert.patient_id == patient_id,
            Alert.type == alert.type,
            AlertEmailDelivery.alert_id != alert.id,
            func.lower(AlertEmailDelivery.recipient_email) == email_key,
            AlertEmailDelivery.status.in_([EmailDeliveryStatus.sent, EmailDeliveryStatus.pending]),
            AlertEmailDelivery.created_at >= cutoff,
        )
        .first()
    )
    return recent is not None


def _claim_delivery(db: Session, alert: Alert, patient_id: int, recipient: Recipient) -> Optional[int]:
    """
    Reserves the right to e-mail `recipient` about `alert`. Returns the new
    delivery row id, or None if this address was already handled for this
    alert (duplicate) or is in its cooldown window.
    """
    key = recipient.email.lower()

    already = (
        db.query(AlertEmailDelivery.id)
        .filter(AlertEmailDelivery.alert_id == alert.id, AlertEmailDelivery.recipient_email == key)
        .first()
    )
    if already:
        logger.info("Alert id=%s: %s was already handled for this alert — not e-mailing twice.", alert.id, mask_email(key))
        return None

    if _in_cooldown(db, alert, patient_id, key):
        reason = (
            f"Skipped: this address was already e-mailed about a {alert.type.value} alert for this patient "
            f"in the last {settings.ALERT_EMAIL_COOLDOWN_SEC:.0f}s"
        )
        logger.warning("Alert id=%s: %s (caregiver id=%s)", alert.id, reason, recipient.caregiver_id)
        _record_skip(db, alert, recipient.caregiver_id, key, reason)
        return None

    delivery = AlertEmailDelivery(
        alert_id=alert.id,
        caregiver_id=recipient.caregiver_id,
        recipient_email=key,
        status=EmailDeliveryStatus.pending,
    )
    try:
        with db.begin_nested():
            db.add(delivery)
        db.commit()
    except IntegrityError:
        # A concurrent dispatch for the same alert got there first.
        db.rollback()
        logger.info("Alert id=%s: duplicate delivery for %s prevented.", alert.id, mask_email(key))
        return None
    return delivery.id


def _finish_delivery(delivery_id: int, status: EmailDeliveryStatus, detail: Optional[str]) -> None:
    """Records the outcome using its own short-lived session (this runs on the background worker)."""
    session = SessionLocal()
    try:
        row = session.query(AlertEmailDelivery).filter(AlertEmailDelivery.id == delivery_id).first()
        if row is None:
            return
        row.status = status
        row.detail = detail[:255] if detail else None
        row.sent_at = datetime.utcnow() if status == EmailDeliveryStatus.sent else None
        session.commit()
    except Exception as exc:
        session.rollback()
        logger.error("Could not record e-mail delivery outcome for delivery id=%s (%s)", delivery_id, type(exc).__name__)
    finally:
        session.close()


# --------------------------------------------------------------------------
# Building + sending
# --------------------------------------------------------------------------
def _build_context(db: Session, alert: Alert, patient: Patient, screenshot_path: Optional[str]) -> AlertEmailContext:
    """Collects ONLY facts the system has recorded; optional fields stay empty if unknown."""
    last_activity = None
    last_activity_at = None
    try:
        activity = (
            db.query(Activity).filter(Activity.patient_id == patient.id).order_by(Activity.started_at.desc()).first()
        )
        if activity is not None:
            last_activity = activity.activity_type.value
            last_activity_at = activity.started_at
    except Exception as exc:
        logger.warning("Could not look up last activity for alert e-mail (%s)", type(exc).__name__)

    return AlertEmailContext(
        patient_name=patient.name,
        patient_id=patient.id,
        patient_room=patient.room_number,
        alert_type=alert.type.value,
        priority=alert.priority.value if alert.priority else None,
        alert_id=alert.id,
        message=alert.message,
        detected_at_utc=alert.created_at,
        last_activity=last_activity,
        last_activity_at_utc=last_activity_at,
        screenshot_path=screenshot_path or alert.screenshot_path,
    )


def _deliver(delivery_id: int, alert_id: int, context: AlertEmailContext, recipient: Recipient) -> None:
    """Builds and sends one e-mail, then records the outcome. Never raises."""
    status = EmailDeliveryStatus.failed
    detail: Optional[str] = "Unexpected error while sending email (see server log)"
    try:
        message = email_notifier.build_alert_email(replace(context, caregiver_name=recipient.name), recipient.email)
        result = email_notifier.send_message(message)
        if result.ok:
            status, detail = EmailDeliveryStatus.sent, None
            logger.info(
                "Alert id=%s: e-mail SENT to caregiver id=%s (%s)", alert_id, recipient.caregiver_id, mask_email(recipient.email)
            )
        else:
            detail = result.detail
            logger.error(
                "Alert id=%s: e-mail FAILED for caregiver id=%s (%s): %s",
                alert_id, recipient.caregiver_id, mask_email(recipient.email), result.category,
            )
    except Exception as exc:
        logger.error(
            "Alert id=%s: e-mail FAILED for caregiver id=%s (%s): %s",
            alert_id, recipient.caregiver_id, mask_email(recipient.email), type(exc).__name__,
        )
    _finish_delivery(delivery_id, status, detail)


def _submit(delivery_id: int, alert_id: int, context: AlertEmailContext, recipient: Recipient) -> None:
    if not settings.ALERT_EMAIL_ASYNC:
        _deliver(delivery_id, alert_id, context, recipient)
        return
    future = _executor.submit(_deliver, delivery_id, alert_id, context, recipient)
    with _pending_lock:
        _pending.add(future)
    future.add_done_callback(_forget)


def _forget(future: Future) -> None:
    with _pending_lock:
        _pending.discard(future)


def flush(timeout: float = 15.0) -> bool:
    """Waits for queued e-mails to finish (used by tests and could be used on shutdown). True if all done."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with _pending_lock:
            if not _pending:
                return True
        time.sleep(0.02)
    return False


# --------------------------------------------------------------------------
# Public entry point
# --------------------------------------------------------------------------
def dispatch_alert_emails(db: Session, alert: Alert, patient: Patient, screenshot_path: Optional[str] = None) -> None:
    """
    E-mails every caregiver assigned to `patient` about `alert`.
    NEVER raises: the alert is already saved before this is called, and
    nothing that goes wrong here may affect monitoring.
    """
    try:
        _dispatch(db, alert, patient, screenshot_path)
    except Exception as exc:
        logger.error(
            "Caregiver e-mail dispatch failed for alert id=%s (%s). The alert itself was saved.",
            getattr(alert, "id", "?"), type(exc).__name__,
        )
        try:
            db.rollback()
        except Exception:
            pass


def _dispatch(db: Session, alert: Alert, patient: Patient, screenshot_path: Optional[str]) -> None:
    if not settings.EMAIL_ALERTS_ENABLED:
        logger.info("Caregiver e-mail alerts are switched off (EMAIL_ALERTS_ENABLED=false); alert id=%s not e-mailed.", alert.id)
        return

    assigned_count = len(patient.caregivers)
    selection = select_recipients(patient)

    for caregiver_id, caregiver_name, reason in selection.skipped:
        logger.warning(
            "Alert id=%s: not e-mailing caregiver id=%s (%s): %s", alert.id, caregiver_id, caregiver_name, reason
        )

    if not selection.recipients:
        if assigned_count == 0:
            reason = "No caregiver is assigned to this patient"
        else:
            reason = "No assigned caregiver has a valid email address"
        logger.warning(
            "Alert id=%s for patient id=%s was saved but no caregiver email could be sent: %s. "
            "Assign a caregiver with an email on the Caregivers page.",
            alert.id, patient.id, reason,
        )
        _record_skip(db, alert, None, None, reason)
        return

    if not email_notifier.is_smtp_configured():
        logger.warning(
            "Alert id=%s was saved, but the sender email account is not configured (SMTP_USERNAME / SMTP_PASSWORD in "
            "backend/.env), so %d caregiver email(s) were not sent.",
            alert.id, len(selection.recipients),
        )
        _record_skip(db, alert, None, None, "Email (SMTP) is not configured on the server")
        return

    context = _build_context(db, alert, patient, screenshot_path)
    patient_id = patient.id
    alert_id = alert.id

    claimed: List[Tuple[int, Recipient]] = []
    for recipient in selection.recipients:
        delivery_id = _claim_delivery(db, alert, patient_id, recipient)
        if delivery_id is not None:
            claimed.append((delivery_id, recipient))

    for delivery_id, recipient in claimed:
        _submit(delivery_id, alert_id, context, recipient)


# --------------------------------------------------------------------------
# "Send test email" support (Caregivers page button)
# --------------------------------------------------------------------------
class TestEmailError(Exception):
    """Raised with a ready-to-show message and a suggested HTTP status code."""

    __test__ = False  # not a pytest test class despite the name

    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


_TEST_EMAIL_MIN_INTERVAL_SEC = 30.0   # after a successful test email
_TEST_EMAIL_RETRY_AFTER_FAILURE_SEC = 5.0  # after a failed one — so fixing a password and retrying isn't a long wait
_test_email_last_sent: Dict[int, float] = {}
_test_email_lock = threading.Lock()


def _now() -> float:
    return time.monotonic()


def send_test_email(caregiver: Caregiver) -> str:
    """
    Sends a clearly-labelled test message to the caregiver's SAVED address
    (never to an arbitrary address supplied by the caller). Returns the
    masked address on success; raises TestEmailError otherwise.
    """
    recipient = normalize_email(caregiver.email)
    if recipient is None:
        raise TestEmailError(400, "This caregiver has no valid email address saved. Edit the caregiver and add one.")
    if not email_notifier.is_smtp_configured():
        raise TestEmailError(
            503,
            "Email sending is not configured on the server. Set SMTP_USERNAME and SMTP_PASSWORD in backend/.env, "
            "then restart the backend.",
        )

    now = _now()
    with _test_email_lock:
        last = _test_email_last_sent.get(caregiver.id)
        if last is not None and now - last < _TEST_EMAIL_MIN_INTERVAL_SEC:
            raise TestEmailError(429, "A test email was just sent. Please wait a few seconds before trying again.")
        _test_email_last_sent[caregiver.id] = now  # also blocks a double-click while this send is in flight

    result = email_notifier.send_message(email_notifier.build_test_email(recipient, caregiver.full_name))
    if not result.ok:
        with _test_email_lock:  # failures only block for a few seconds
            _test_email_last_sent[caregiver.id] = now - (_TEST_EMAIL_MIN_INTERVAL_SEC - _TEST_EMAIL_RETRY_AFTER_FAILURE_SEC)
        logger.error("Test email to caregiver id=%s failed: %s", caregiver.id, result.category)
        raise TestEmailError(502, f"Test email could not be sent: {result.detail}.")
    logger.info("Test email sent to caregiver id=%s (%s)", caregiver.id, mask_email(recipient))
    return mask_email(recipient)
