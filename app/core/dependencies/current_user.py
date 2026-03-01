# 쿠키 session_id → 세션 조회 → CurrentUser 반환. get_current_user 의존성.
from datetime import datetime, timezone
from typing import Optional

from fastapi import Cookie, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.model import AuthModel
from app.common import ApiCode, raise_http_error
from app.db import get_db
from app.users.model import UsersModel


class CurrentUser(BaseModel):
    id: int = Field(..., description="사용자 ID")
    email: str = ""
    nickname: str = ""
    profile_image_id: Optional[int] = None
    profile_image_url: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"from_attributes": True}


def get_current_user(
    session_id: Optional[str] = Cookie(None),
    db: Session = Depends(get_db),
) -> CurrentUser:
    if not session_id:
        raise_http_error(401, ApiCode.UNAUTHORIZED)
    user_id = AuthModel.get_user_id_by_session(session_id, db=db)
    if not user_id:
        raise_http_error(401, ApiCode.UNAUTHORIZED)
    user = UsersModel.find_user_by_id(user_id, db=db)
    if not user:
        raise_http_error(401, ApiCode.UNAUTHORIZED)
    return CurrentUser.model_validate(user)
