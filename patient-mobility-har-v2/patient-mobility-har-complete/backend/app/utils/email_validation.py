"""
Small helpers for validating and normalizing e-mail addresses.

Used in two places so the rules are identical everywhere:
  * when a caregiver is created/updated (reject obviously bad input early), and
  * at alert time (older records saved before validation existed may still
    contain bad values, so every address is re-checked before sending).

Addresses containing line breaks, display names ("Name <a@b.com>") or
multiple recipients are rejected, which also prevents e-mail header injection.
"""

from typing import Optional

from email_validator import EmailNotValidError, validate_email


def normalize_email(value: Optional[str]) -> Optional[str]:
    """Returns the cleaned address, or None if `value` is empty or not a valid address."""
    if value is None:
        return None
    candidate = str(value).strip()
    if not candidate:
        return None
    try:
        # check_deliverability=False: never do DNS lookups (keeps this fast and offline-safe).
        result = validate_email(candidate, check_deliverability=False)
    except EmailNotValidError:
        return None
    return result.normalized


def clean_optional_email(value: Optional[str]) -> Optional[str]:
    """
    For API input: blank -> None, valid -> normalized address,
    anything else -> ValueError (surfaces as a 422 validation error).
    """
    if value is None or not str(value).strip():
        return None
    normalized = normalize_email(value)
    if normalized is None:
        raise ValueError("Enter a valid email address, e.g. name@gmail.com")
    return normalized


def mask_email(value: Optional[str]) -> str:
    """'jane.doe@gmail.com' -> 'j***@gmail.com' for logs and API responses."""
    if not value or "@" not in value:
        return "<no email>"
    local, _, domain = value.partition("@")
    return f"{local[:1]}***@{domain}"
