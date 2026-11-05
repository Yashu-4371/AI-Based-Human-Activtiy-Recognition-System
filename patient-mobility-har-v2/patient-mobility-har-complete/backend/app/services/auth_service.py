"""
Authentication business logic: password hashing/verification, JWT
creation/decoding, login, and password-reset token handling.
Framework-agnostic — no FastAPI imports here.
"""

from datetime import datetime, timedelta
from typing import Optional

from jose import jwt, JWTError
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import settings
from app.models.user import User
from app.utils.security import generate_secure_token
from app.utils.logger import get_logger

logger = get_logger(__name__)

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    return _pwd_context.hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    return _pwd_context.verify(plain_password, password_hash)


def create_access_token(user: User) -> str:
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": str(user.id), "role": user.role.value, "exp": expire}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None


def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.password_hash):
        return None
    return user


def register_user(db: Session, name: str, email: str, password: str, role) -> User:
    user = User(name=name, email=email, password_hash=hash_password(password), role=role)
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info("Registered new user: %s (%s)", email, role)
    return user


def create_password_reset_token(db: Session, email: str) -> Optional[str]:
    user = db.query(User).filter(User.email == email).first()
    if not user:
        return None
    token = generate_secure_token()
    user.reset_token = token
    user.reset_token_expires_at = datetime.utcnow() + timedelta(hours=1)
    db.commit()
    return token


def reset_password(db: Session, token: str, new_password: str) -> bool:
    user = db.query(User).filter(User.reset_token == token).first()
    if not user or not user.reset_token_expires_at or user.reset_token_expires_at < datetime.utcnow():
        return False
    user.password_hash = hash_password(new_password)
    user.reset_token = None
    user.reset_token_expires_at = None
    db.commit()
    return True
