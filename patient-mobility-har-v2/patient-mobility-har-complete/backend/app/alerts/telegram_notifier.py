"""
Optional Telegram Bot API notifier. Cleanly no-ops if TELEGRAM_ENABLED
is false or credentials are missing, so it never blocks or breaks the
core alert flow — this is a bonus channel, not a required one.
"""

import requests

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

_TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"


def send_alert_telegram(patient_name: str, alert_type: str, message: str) -> bool:
    if not settings.TELEGRAM_ENABLED or not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_CHAT_ID:
        return False

    url = _TELEGRAM_API_URL.format(token=settings.TELEGRAM_BOT_TOKEN)
    text = f"🚨 ALERT: {alert_type.upper()}\nPatient: {patient_name}\n{message}"

    try:
        response = requests.post(url, data={"chat_id": settings.TELEGRAM_CHAT_ID, "text": text}, timeout=5)
        response.raise_for_status()
        logger.info("Telegram alert sent for patient=%s type=%s", patient_name, alert_type)
        return True
    except Exception as exc:
        logger.error("Failed to send Telegram alert: %s", exc)
        return False
