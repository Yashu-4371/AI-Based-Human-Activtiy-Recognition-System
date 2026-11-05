"""
SMTP e-mail sending for MobilityWatch.

This module only knows HOW to build and send an e-mail through the
configured *sender* account (e.g. a Gmail address + App Password from the
backend `.env`). It does not decide WHO receives an alert — recipients are
looked up from the database (the caregivers assigned to the patient) by
`app/services/alert_email_service.py`.

Design rules:
  * Never raises into the caller from the high-level helpers — a mail
    problem must not break camera monitoring or alert saving.
  * Never logs or returns the SMTP password. Failures are reduced to a
    short category + a human-friendly hint.
  * Never reports success unless the SMTP server accepted the message.
  * Nothing is invented: the e-mail only contains values the system
    actually recorded (alert fields, patient fields, last saved activity).
"""

import html
import smtplib
import ssl
from dataclasses import dataclass
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import formataddr
from pathlib import Path
from typing import Optional

from app.config import settings
from app.utils.email_validation import mask_email, normalize_email
from app.utils.logger import get_logger

logger = get_logger(__name__)

APP_NAME = "MobilityWatch"

# Values copied straight from .env.example. If someone copies the template
# without editing it, treat the mail setup as "not configured" instead of
# attempting (and failing) a real login with the placeholder text.
_PLACEHOLDER_USERNAMES = {
    "your_email@gmail.com",
    "your_sender_gmail@gmail.com",
    "your_gmail_address@gmail.com",
}
_PLACEHOLDER_PASSWORDS = {
    "your_app_password",
    "your_gmail_app_password",
    "your_16_character_app_password",
}

_MAX_ATTACHMENT_BYTES = 5 * 1024 * 1024

_ALERT_LABELS = {
    "fall": "Fall detected",
    "inactivity": "Inactivity warning",
    "abnormal": "Abnormal activity alert",
}

_RECOMMENDATIONS = {
    "fall": (
        "Please check on the patient right away. If they are hurt, unresponsive, or you cannot "
        "reach them, contact emergency services."
    ),
    "inactivity": (
        "Please check on the patient soon to make sure they are comfortable and safe. "
        "Long periods without movement can be normal (for example, resting), but are worth a quick check."
    ),
}
_DEFAULT_RECOMMENDATION = "Please check on the patient and review the alert details in MobilityWatch."


# --------------------------------------------------------------------------
# Configuration helpers
# --------------------------------------------------------------------------
def _smtp_username() -> str:
    return (settings.SMTP_USERNAME or "").strip()


def _smtp_password() -> str:
    # Google displays App Passwords in four groups separated by spaces
    # ("abcd efgh ijkl mnop"). Spaces aren't part of the password, so remove
    # them in case the value was pasted exactly as shown.
    return "".join((settings.SMTP_PASSWORD or "").split())


def is_smtp_configured() -> bool:
    """True only when a real-looking sender account has been set in the backend .env."""
    username = _smtp_username()
    password = _smtp_password()
    if not username or not password or not (settings.SMTP_HOST or "").strip():
        return False
    if username.lower() in _PLACEHOLDER_USERNAMES or password.lower() in _PLACEHOLDER_PASSWORDS:
        return False
    return from_address() is not None


def from_address() -> Optional[str]:
    """The sender address: SMTP_FROM_EMAIL if set, otherwise the SMTP login (SMTP_USERNAME)."""
    return normalize_email(settings.SMTP_FROM_EMAIL) or normalize_email(settings.SMTP_USERNAME)


# --------------------------------------------------------------------------
# Message content
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class AlertEmailContext:
    """Plain data (no DB objects) so a message can be built from a background thread."""

    patient_name: str
    alert_type: str  # "fall" | "inactivity" | "abnormal"
    message: str
    patient_id: Optional[int] = None
    patient_room: Optional[str] = None
    priority: Optional[str] = None
    alert_id: Optional[int] = None
    detected_at_utc: Optional[datetime] = None  # naive UTC, exactly as stored in the database
    last_activity: Optional[str] = None
    last_activity_at_utc: Optional[datetime] = None
    caregiver_name: Optional[str] = None
    screenshot_path: Optional[str] = None


def alert_label(alert_type: str) -> str:
    return _ALERT_LABELS.get(alert_type, alert_type.replace("_", " ").title())


def _clean_header_text(value: str) -> str:
    """Collapse whitespace/newlines so user-entered names can never inject extra mail headers."""
    return " ".join(str(value).split())


def format_local_time(value_utc: Optional[datetime]) -> str:
    """
    Alert times are stored as naive UTC. Show them in the server computer's
    local timezone with an explicit offset so there is no ambiguity.
    """
    if value_utc is None:
        return "Not recorded"
    aware = value_utc.replace(tzinfo=timezone.utc) if value_utc.tzinfo is None else value_utc
    local = aware.astimezone()
    offset = local.strftime("%z")  # e.g. +0530
    offset_text = f"UTC{offset[:3]}:{offset[3:]}" if offset else "UTC"
    zone = local.tzname() or ""
    zone_text = f"{zone} " if zone and zone != offset_text else ""
    return f"{local.strftime('%d %b %Y, %I:%M:%S %p')} {zone_text}({offset_text})".replace("  ", " ")


def _detail_rows(ctx: AlertEmailContext) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = [("Patient", _clean_header_text(ctx.patient_name))]
    if ctx.patient_id is not None:
        rows.append(("Patient ID", f"#{ctx.patient_id}"))
    if ctx.patient_room:
        rows.append(("Room", _clean_header_text(ctx.patient_room)))
    rows.append(("Alert type", alert_label(ctx.alert_type)))
    if ctx.priority:
        rows.append(("Priority", ctx.priority.capitalize()))
    rows.append(("Detected at", format_local_time(ctx.detected_at_utc)))
    rows.append(("Alert details", ctx.message))
    if ctx.last_activity:
        when = f" (recorded {format_local_time(ctx.last_activity_at_utc)})" if ctx.last_activity_at_utc else ""
        rows.append(("Last recorded activity", f"{ctx.last_activity.capitalize()}{when}"))
    if ctx.alert_id is not None:
        rows.append(("Alert reference", f"#{ctx.alert_id}"))
    return rows


def _render_plain(ctx: AlertEmailContext, recommendation: str) -> str:
    label = alert_label(ctx.alert_type)
    greeting = f"Hello {_clean_header_text(ctx.caregiver_name)}," if ctx.caregiver_name else "Hello,"
    width = max(len(k) for k, _ in _detail_rows(ctx)) + 2
    lines = [
        f"{APP_NAME} — Patient Alert",
        "=" * 40,
        "",
        greeting,
        "",
        f"{APP_NAME} has raised an alert for a patient you are listed as a caregiver for: {label.upper()}.",
        "",
    ]
    lines += [f"{key + ':':<{width}}{value}" for key, value in _detail_rows(ctx)]
    lines += [
        "",
        "RECOMMENDED ACTION",
        recommendation,
        "",
        "Please note: this alert was generated automatically by a camera-based monitoring system. "
        "Automatic detection can be wrong (false alarms and missed events both happen), so please "
        "use your own judgement and check on the patient.",
        "",
        "—",
        f"{APP_NAME} · Patient Monitoring",
        "You are receiving this because your email address is saved as a caregiver for this patient.",
    ]
    return "\n".join(lines)


def _render_html(ctx: AlertEmailContext, recommendation: str) -> str:
    esc = html.escape
    label = alert_label(ctx.alert_type)
    accent = "#b91c1c" if ctx.alert_type == "fall" or (ctx.priority or "") == "critical" else "#b45309"
    greeting = f"Hello {esc(_clean_header_text(ctx.caregiver_name))}," if ctx.caregiver_name else "Hello,"
    rows_html = "".join(
        f'<tr><td style="padding:8px 12px;color:#475569;font-size:13px;white-space:nowrap;vertical-align:top;'
        f'border-bottom:1px solid #e2e8f0;">{esc(key)}</td>'
        f'<td style="padding:8px 12px;color:#0f172a;font-size:14px;border-bottom:1px solid #e2e8f0;">{esc(value)}</td></tr>'
        for key, value in _detail_rows(ctx)
    )
    return f"""<!doctype html>
<html>
<body style="margin:0;padding:0;background:#f1f5f9;font-family:Segoe UI,Helvetica,Arial,sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f1f5f9;padding:24px 0;">
    <tr><td align="center">
      <table role="presentation" width="600" cellpadding="0" cellspacing="0"
             style="max-width:600px;width:100%;background:#ffffff;border-radius:10px;overflow:hidden;border:1px solid #e2e8f0;">
        <tr><td style="background:{accent};padding:18px 24px;color:#ffffff;">
          <div style="font-size:12px;letter-spacing:1px;text-transform:uppercase;opacity:.85;">{esc(APP_NAME)} · Patient Alert</div>
          <div style="font-size:22px;font-weight:700;margin-top:4px;">{esc(label)}</div>
        </td></tr>
        <tr><td style="padding:22px 24px 8px 24px;color:#0f172a;font-size:14px;line-height:1.5;">
          <p style="margin:0 0 12px 0;">{greeting}</p>
          <p style="margin:0 0 16px 0;">{esc(APP_NAME)} has raised an alert for a patient you are listed as a caregiver for.</p>
        </td></tr>
        <tr><td style="padding:0 24px;">
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
                 style="border:1px solid #e2e8f0;border-bottom:none;border-radius:6px;">{rows_html}</table>
        </td></tr>
        <tr><td style="padding:18px 24px 6px 24px;">
          <div style="background:#fef3c7;border-left:4px solid {accent};padding:12px 14px;color:#0f172a;font-size:14px;line-height:1.5;">
            <strong>Recommended action</strong><br>{esc(recommendation)}
          </div>
        </td></tr>
        <tr><td style="padding:14px 24px 22px 24px;color:#64748b;font-size:12px;line-height:1.5;">
          This alert was generated automatically by a camera-based monitoring system. Automatic detection can be
          wrong (false alarms and missed events both happen), so please use your own judgement and check on the patient.
        </td></tr>
        <tr><td style="background:#f8fafc;padding:12px 24px;color:#94a3b8;font-size:11px;">
          {esc(APP_NAME)} · Patient Monitoring — you are receiving this because your email address is saved as a caregiver for this patient.
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


def _resolve_screenshot(screenshot_path: Optional[str]) -> Optional[Path]:
    """
    Maps a stored '/uploads/alert_screenshots/x.jpg' URL path to a file on disk,
    only if it really lives inside the uploads directory (no path traversal).
    """
    if not screenshot_path:
        return None
    try:
        upload_root = settings.upload_path.resolve()
        relative = screenshot_path[len("/uploads/"):] if screenshot_path.startswith("/uploads/") else screenshot_path
        candidate = (upload_root / relative).resolve() if not Path(relative).is_absolute() else Path(relative).resolve()
        candidate.relative_to(upload_root)
        if candidate.is_file() and candidate.stat().st_size <= _MAX_ATTACHMENT_BYTES:
            return candidate
    except (ValueError, OSError):
        pass
    return None


def build_alert_email(ctx: AlertEmailContext, to_email: str) -> EmailMessage:
    """Builds the caregiver alert e-mail (plain-text + HTML, optional screenshot attachment)."""
    sender = from_address()
    if sender is None:
        raise ValueError("No valid sender address is configured")

    recommendation = _RECOMMENDATIONS.get(ctx.alert_type, _DEFAULT_RECOMMENDATION)

    msg = EmailMessage()
    msg["Subject"] = f"[{APP_NAME}] {alert_label(ctx.alert_type)} — {_clean_header_text(ctx.patient_name)}"
    msg["From"] = formataddr((_clean_header_text(settings.SMTP_FROM_NAME or APP_NAME), sender))
    msg["To"] = to_email
    msg.set_content(_render_plain(ctx, recommendation))
    msg.add_alternative(_render_html(ctx, recommendation), subtype="html")

    if settings.ALERT_EMAIL_ATTACH_SCREENSHOT:
        screenshot = _resolve_screenshot(ctx.screenshot_path)
        if screenshot is not None:
            try:
                msg.add_attachment(screenshot.read_bytes(), maintype="image", subtype="jpeg", filename=screenshot.name)
            except OSError:
                logger.warning("Could not attach alert screenshot; sending the e-mail without it.")
    return msg


def build_test_email(to_email: str, caregiver_name: Optional[str]) -> EmailMessage:
    sender = from_address()
    if sender is None:
        raise ValueError("No valid sender address is configured")
    name = _clean_header_text(caregiver_name) if caregiver_name else ""
    msg = EmailMessage()
    msg["Subject"] = f"[{APP_NAME}] Test email — alert notifications are working"
    msg["From"] = formataddr((_clean_header_text(settings.SMTP_FROM_NAME or APP_NAME), sender))
    msg["To"] = to_email
    msg.set_content(
        f"Hello{' ' + name if name else ''},\n\n"
        f"This is a TEST email from {APP_NAME}. If you can read it, the system can send alert emails to this address.\n\n"
        "No patient event has been detected — nothing needs your attention.\n\n"
        f"— {APP_NAME} · Patient Monitoring"
    )
    return msg


# --------------------------------------------------------------------------
# Sending
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class SendResult:
    ok: bool
    category: str  # sent | not_configured | auth_failed | recipient_refused | connection_failed | smtp_error | unexpected_error
    detail: str  # short, human-friendly, safe to store/show (never contains credentials)


_HINTS = {
    "sent": "Sent",
    "not_configured": "Email (SMTP) is not configured on the server",
    "auth_failed": "The email server rejected the sender login — check SMTP_USERNAME and use a Google App Password",
    "recipient_refused": "The email server refused the recipient address",
    "connection_failed": "Could not connect to the email server (check internet connection, SMTP_HOST and SMTP_PORT)",
    "smtp_error": "The email server reported an error",
    "unexpected_error": "Unexpected error while sending email (see server log)",
}


def _result(ok: bool, category: str) -> SendResult:
    return SendResult(ok=ok, category=category, detail=_HINTS[category])


def send_message(msg: EmailMessage) -> SendResult:
    """
    Sends one prepared message through the configured SMTP account
    (STARTTLS by default). Never raises; returns a SendResult.
    """
    if not is_smtp_configured():
        return _result(False, "not_configured")

    to_masked = mask_email(str(msg["To"]))
    try:
        # Explicit timeout: without one, an unreachable SMTP host could block for a minute or more.
        with smtplib.SMTP(settings.SMTP_HOST.strip(), settings.SMTP_PORT, timeout=settings.SMTP_TIMEOUT_SEC) as server:
            server.ehlo()
            if settings.SMTP_USE_STARTTLS:
                server.starttls(context=ssl.create_default_context())
                server.ehlo()
            server.login(_smtp_username(), _smtp_password())
            server.send_message(msg)
        return _result(True, "sent")
    # NOTE: smtplib.SMTPException is itself a subclass of OSError, so the specific SMTP errors
    # must be handled BEFORE the generic OSError/TimeoutError (network) branch below.
    except smtplib.SMTPAuthenticationError as exc:
        logger.error("SMTP login rejected while e-mailing %s (smtp_code=%s)", to_masked, getattr(exc, "smtp_code", "?"))
        return _result(False, "auth_failed")
    except smtplib.SMTPRecipientsRefused:
        logger.error("SMTP server refused recipient %s", to_masked)
        return _result(False, "recipient_refused")
    except (smtplib.SMTPConnectError, smtplib.SMTPServerDisconnected) as exc:
        logger.error("Could not reach SMTP server while e-mailing %s (%s)", to_masked, type(exc).__name__)
        return _result(False, "connection_failed")
    except smtplib.SMTPException as exc:
        logger.error(
            "SMTP error while e-mailing %s (%s, smtp_code=%s)", to_masked, type(exc).__name__, getattr(exc, "smtp_code", "?")
        )
        return _result(False, "smtp_error")
    except (TimeoutError, OSError) as exc:  # DNS failure, refused/unreachable network, timeout
        logger.error("Could not reach SMTP server while e-mailing %s (%s)", to_masked, type(exc).__name__)
        return _result(False, "connection_failed")
    except Exception as exc:  # last-resort guard: never let mail break monitoring
        logger.error("Unexpected error while e-mailing %s (%s)", to_masked, type(exc).__name__)
        return _result(False, "unexpected_error")


def send_alert_email(
    patient_name: str,
    alert_type: str,
    message: str,
    screenshot_path: Optional[str] = None,
    to_email: Optional[str] = None,
    *,
    patient_id: Optional[int] = None,
    detected_at_utc: Optional[datetime] = None,
    priority: Optional[str] = None,
    caregiver_name: Optional[str] = None,
) -> bool:
    """
    Convenience wrapper: builds and sends one alert e-mail to `to_email`.
    Returns True only if the SMTP server accepted it. There is deliberately
    NO fallback recipient — an alert is only ever e-mailed to an explicit
    address (a caregiver assigned to the patient).
    """
    recipient = normalize_email(to_email)
    if recipient is None:
        logger.warning("No valid recipient address — alert email not sent.")
        return False
    if not is_smtp_configured():
        logger.warning("SMTP not configured — alert email not sent.")
        return False
    try:
        ctx = AlertEmailContext(
            patient_name=patient_name,
            alert_type=alert_type,
            message=message,
            patient_id=patient_id,
            priority=priority,
            detected_at_utc=detected_at_utc or datetime.utcnow(),
            caregiver_name=caregiver_name,
            screenshot_path=screenshot_path,
        )
        result = send_message(build_alert_email(ctx, recipient))
    except Exception as exc:
        logger.error("Could not build alert email (%s)", type(exc).__name__)
        return False
    if result.ok:
        logger.info("Alert email sent to %s for patient=%s type=%s", mask_email(recipient), patient_name, alert_type)
    return result.ok
