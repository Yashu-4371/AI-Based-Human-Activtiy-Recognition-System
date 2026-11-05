from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_admin
from app.models.user import User
from app.schemas.token import Token
from app.schemas.user import UserCreate, UserOut, ForgotPasswordRequest, ResetPasswordRequest
from app.services import auth_service
from app.alerts.email_notifier import send_alert_email
from app.utils.logger import get_logger

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])
logger = get_logger(__name__)


@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = auth_service.authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")

    access_token = auth_service.create_access_token(user)
    return Token(access_token=access_token, user=UserOut.model_validate(user))


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: Session = Depends(get_db), _admin=Depends(require_admin)):
    existing_user = db.query(User).filter(User.email == payload.email).first()
    if existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    user = auth_service.register_user(db, payload.name, payload.email, payload.password, payload.role)
    return UserOut.model_validate(user)


@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    token = auth_service.create_password_reset_token(db, payload.email)
    if token:
        send_alert_email(
            patient_name="N/A",
            alert_type="password_reset",
            message=f"Password reset requested. Reset token: {token} (valid for 1 hour).",
        )
    # Always return a generic success message, regardless of whether the email
    # exists, so this endpoint can't be used to enumerate registered accounts.
    return {"message": "If that email is registered, a reset link has been sent."}


@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    success = auth_service.reset_password(db, payload.token, payload.new_password)
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token")
    return {"message": "Password reset successfully"}
