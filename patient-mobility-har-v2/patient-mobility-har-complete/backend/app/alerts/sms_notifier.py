"""
Optional SMS/voice-call alert notifier via Twilio — the one real,
credentialed external provider this project wires in for SMS/calls.

Cleanly no-ops (returns False, logs a warning) whenever:
  - SMS_ENABLED is false, or
  - any of TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN / TWILIO_FROM_NUMBER
    is missing, or
  - the `twilio` package isn't installed, or
  - the caregiver has no phone number, or
  - the Twilio API call itself fails.

It NEVER reports a successful send unless Twilio's API actually
accepted the request — there is no placeholder/fake success path here.
To enable, set real credentials in .env (see .env.example) and
`pip install twilio`.
"""

from typing import Optional

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


def _is_configured() -> bool:
    return bool(
        settings.SMS_ENABLED
        and settings.TWILIO_ACCOUNT_SID
        and settings.TWILIO_AUTH_TOKEN
        and settings.TWILIO_FROM_NUMBER
    )


def _get_twilio_client():
    try:
        from twilio.rest import Client
    except ImportError:
        logger.warning(
            "SMS_ENABLED is true but the `twilio` package isn't installed — "
            "run `pip install twilio`. Skipping SMS/call dispatch."
        )
        return None
    return Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)


def send_alert_sms(patient_name: str, alert_type: str, message: str, to_phone: Optional[str]) -> bool:
    if not _is_configured():
        logger.warning("SMS not configured (SMS_ENABLED/Twilio credentials missing) — skipping SMS dispatch.")
        return False
    if not to_phone:
        logger.warning("No caregiver phone number on file — skipping SMS dispatch.")
        return False

    client = _get_twilio_client()
    if client is None:
        return False

    body = f"[ALERT] {alert_type.upper()} — {patient_name}: {message}"
    try:
        client.messages.create(body=body, from_=settings.TWILIO_FROM_NUMBER, to=to_phone)
        logger.info("Alert SMS sent to %s for patient=%s type=%s", to_phone, patient_name, alert_type)
        return True
    except Exception as exc:
        logger.error("Failed to send alert SMS: %s", exc)
        return False


def place_alert_call(patient_name: str, alert_type: str, to_phone: Optional[str]) -> bool:
    """Places a short automated voice call for critical alerts (e.g. falls), if enabled."""
    if not _is_configured() or not settings.SMS_CALL_ON_CRITICAL_ALERT:
        return False
    if not to_phone:
        logger.warning("No caregiver phone number on file — skipping alert call.")
        return False

    client = _get_twilio_client()
    if client is None:
        return False

    twiml = (
        f"<Response><Say>Alert. {alert_type} detected for patient {patient_name}. "
        f"Please check the monitoring dashboard immediately.</Say></Response>"
    )
    try:
        client.calls.create(twiml=twiml, from_=settings.TWILIO_FROM_NUMBER, to=to_phone)
        logger.info("Alert call placed to %s for patient=%s type=%s", to_phone, patient_name, alert_type)
        return True
    except Exception as exc:
        logger.error("Failed to place alert call: %s", exc)
        return False
