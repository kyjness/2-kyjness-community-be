# 인증 의존성. Authorization Bearer 검증 → CurrentUser. 만료 시 TOKEN_EXPIRED, 무효 시 UNAUTHORIZED.
from typing import Optional

import jwt
from fastapi import Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.common import ApiCode, UserStatus, UtcDatetime, raise_http_error
from app.core.security import verify_access_token
from app.db import utc_now
from app.users.model import UsersModel

from .db import get_slave_db


class CurrentUser(BaseModel):
    id: int = Field(..., description="사용자 ID")
    email: str = ""
    nickname: str = ""
    profile_image_id: Optional[int] = None
    profile_image_url: Optional[str] = None
    created_at: UtcDatetime = Field(default_factory=utc_now)

    model_config = {"from_attributes": True}


def _bearer_token(request: Request) -> Optional[str]:
    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        return None
    return auth[7:].strip() or None


def get_current_user(
    request: Request,
    db: Session = Depends(get_slave_db),
) -> CurrentUser:
    """Bearer 파싱 → verify_access_token → DB 조회. 만료 시 TOKEN_EXPIRED, 무효 시 UNAUTHORIZED."""
    token = _bearer_token(request)
    if not token:
        raise_http_error(401, ApiCode.UNAUTHORIZED, "Authorization Bearer required")
    try:
        payload = verify_access_token(token)
    except jwt.ExpiredSignatureError:
        raise_http_error(401, ApiCode.TOKEN_EXPIRED, "Access token expired")
    except jwt.InvalidTokenError:
        raise_http_error(401, ApiCode.UNAUTHORIZED, "Invalid token")
    sub = payload.get("sub")
    if sub is None:
        raise_http_error(401, ApiCode.UNAUTHORIZED)
    try:
        user_id = int(sub)
    except (TypeError, ValueError):
        raise_http_error(401, ApiCode.UNAUTHORIZED)
    user = UsersModel.get_user_by_id(user_id, db=db)
    if not user:
        raise_http_error(401, ApiCode.UNAUTHORIZED)
    if not UserStatus.is_active_value(user.status):
        raise_http_error(403, ApiCode.FORBIDDEN, UserStatus.inactive_message_ko(user.status))
    return CurrentUser.model_validate(user)
