
from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


def send_alert_whatsapp(
    patient_name: str,
    alert_type: str,
    message: str,
    to_whatsapp: str,
) -> bool:
    if not (
        settings.TWILIO_ACCOUNT_SID
        and settings.TWILIO_AUTH_TOKEN
        and settings.TWILIO_WHATSAPP_FROM
    ):
        logger.warning("WhatsApp not configured; skipping dispatch.")
        return False

    if not to_whatsapp:
        logger.warning("No caregiver WhatsApp number provided.")
        return False

    try:
        from twilio.rest import Client

        client = Client(
            settings.TWILIO_ACCOUNT_SID,
            settings.TWILIO_AUTH_TOKEN,
        )

        body = (
            f"PATIENT FALL ALERT\n"
            f"Patient: {patient_name}\n"
            f"Alert: {alert_type.upper()}\n"
            f"Details: {message}\n"
            f"Please check the patient immediately."
        )

        client.messages.create(
            body=body,
            from_=f"whatsapp:{settings.TWILIO_WHATSAPP_FROM.removeprefix('whatsapp:')}",
            to=f"whatsapp:{to_whatsapp.removeprefix('whatsapp:')}",
        )

        logger.info("WhatsApp alert accepted by Twilio for patient=%s", patient_name)
        return True

    except Exception as exc:
        logger.error("Failed to send WhatsApp alert: %s", exc)
        return False
