"""
Low-level security helpers: secure random token generation used for
password-reset flows. Password hashing and JWT logic live in
app/services/auth_service.py, which is the higher-level consumer of
these primitives.
"""

import secrets


def generate_secure_token(length: int = 32) -> str:
    """Generates a cryptographically secure URL-safe token, e.g. for password resets."""
    return secrets.token_urlsafe(length)
