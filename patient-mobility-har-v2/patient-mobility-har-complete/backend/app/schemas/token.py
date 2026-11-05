from typing import Optional

from pydantic import BaseModel

from app.schemas.user import UserOut


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class TokenPayload(BaseModel):
    sub: Optional[str] = None   # user id, stored as string in the JWT "sub" claim
    role: Optional[str] = None
    exp: Optional[int] = None
