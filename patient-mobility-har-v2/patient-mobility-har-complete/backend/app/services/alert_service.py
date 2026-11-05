"""
Alert business logic: creating alerts (with screenshot capture and
notification dispatch), listing, and resolving them.
"""

from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session, selectinload

from app.models.alert import Alert, AlertType, AlertPriority, AlertStatus
from app.models.patient import Patient
from app.services import alert_email_service
from app.alerts.telegram_notifier import send_alert_telegram
from app.alerts.sms_notifier import send_alert_sms, place_alert_call
from app.alerts.whatsapp_notifier import send_alert_whatsapp
from app.utils.logger import get_logger

logger = get_logger(__name__)


def list_alerts(
    db: Session,
    patient_id: Optional[int] = None,
    status: Optional[AlertStatus] = None,
    priority: Optional[AlertPriority] = None,
    limit: int = 200,
    alert_type: Optional[AlertType] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
) -> List[Alert]:
    query = db.query(Alert).options(selectinload(Alert.email_deliveries))
    if patient_id:
        query = query.filter(Alert.patient_id == patient_id)
    if status:
        query = query.filter(Alert.status == status)
    if priority:
        query = query.filter(Alert.priority == priority)
    if alert_type:
        query = query.filter(Alert.type == alert_type)
    if date_from:
        query = query.filter(Alert.created_at >= date_from)
    if date_to:
        query = query.filter(Alert.created_at <= date_to)
    return query.order_by(Alert.created_at.desc()).limit(limit).all()


def get_alert(db: Session, alert_id: int) -> Optional[Alert]:
    return db.query(Alert).filter(Alert.id == alert_id).first()


def create_alert(
    db: Session,
    patient: Patient,
    alert_type: AlertType,
    priority: AlertPriority,
    message: str,
    screenshot_path: Optional[str] = None,
) -> Alert:
    alert = Alert(
        patient_id=patient.id,
        type=alert_type,
        priority=priority,
        status=AlertStatus.open,
        message=message,
        screenshot_path=screenshot_path,
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)

    logger.warning("ALERT created: patient=%s type=%s priority=%s", patient.name, alert_type, priority)
    # The alert is already saved above. Everything below is best-effort
    # notification and must never undo or block it.
    _dispatch_notifications(db, patient, alert, alert_type, priority, message, screenshot_path)
    return alert


def _dispatch_notifications(
    db: Session,
    patient: Patient,
    alert: Alert,
    alert_type: AlertType,
    priority: AlertPriority,
    message: str,
    screenshot_path: Optional[str],
) -> None:
    """
    Notifies the patient's assigned caregiver(s):
      * e-mail  -> addresses saved on the Caregivers page (looked up from the
                   database; see app/services/alert_email_service.py)
      * SMS / WhatsApp / voice call -> only if Twilio is actually configured
    plus the optional global Telegram channel. Every channel is wrapped so a
    notification failure never crashes the monitoring pipeline, and every
    channel logs/returns whether it ACTUALLY sent — nothing reports fake success.
    """
    # Caregiver e-mail first (it runs on a background worker, so it does not delay the other channels).
    # Never raises; see alert_email_service.dispatch_alert_emails.
    alert_email_service.dispatch_alert_emails(db, alert, patient, screenshot_path)

    caregivers = list(patient.caregivers)

    if not caregivers:
        logger.info("No caregiver assigned to patient=%s — caregiver channels skipped (Telegram only, if configured).", patient.name)

    for caregiver in caregivers:
        try:
            send_alert_sms(patient_name=patient.name, alert_type=alert_type.value, message=message, to_phone=caregiver.phone)
        except Exception as exc:
            logger.error("Failed to SMS caregiver id=%s: %s", caregiver.id, exc)

        try:
            send_alert_whatsapp(
                patient_name=patient.name,
                alert_type=alert_type.value,
                message=message,
                to_whatsapp=caregiver.phone,
            )
        except Exception as exc:
            logger.error("Failed to WhatsApp caregiver id=%s: %s", caregiver.id, exc)

        if priority == AlertPriority.critical:
            try:
                place_alert_call(patient_name=patient.name, alert_type=alert_type.value, to_phone=caregiver.phone)
            except Exception as exc:
                logger.error("Failed to call caregiver id=%s: %s", caregiver.id, exc)

    # Optional global admin channel — unchanged behavior, still no-ops cleanly if unconfigured.
    try:
        send_alert_telegram(patient_name=patient.name, alert_type=alert_type.value, message=message)
    except Exception as exc:
        logger.error("Failed to send Telegram alert: %s", exc)


def resolve_alert(db: Session, alert: Alert, resolved_by_user_id: int) -> Alert:
    alert.status = AlertStatus.resolved
    alert.resolved_at = datetime.utcnow()
    alert.resolved_by = resolved_by_user_id
    db.commit()
    db.refresh(alert)
    logger.info("Alert id=%s resolved by user_id=%s", alert.id, resolved_by_user_id)
    return alert
