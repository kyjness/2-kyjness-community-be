# 세션 CRUD. AuthSession 모델, 세션 생성·조회·삭제.
from datetime import datetime, timedelta, timezone
from typing import Optional

import secrets
from sqlalchemy import select, delete
from sqlalchemy.orm import Session, mapped_column
from sqlalchemy import String, Integer, DateTime, ForeignKey

from app.core.config import settings
from app.db import Base, get_connection


class AuthSession(Base):
    __tablename__ = "sessions"

    session_id = mapped_column(String(255), primary_key=True)
    user_id = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = mapped_column(DateTime, nullable=False)
    expires_at = mapped_column(DateTime, nullable=False)


class AuthModel:
    SESSION_EXPIRY_TIME = settings.SESSION_EXPIRY_TIME

    @classmethod
    def create_session(cls, user_id: int, db: Session) -> str:
        session_id = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=cls.SESSION_EXPIRY_TIME)
        now = datetime.now(timezone.utc)
        s = AuthSession(session_id=session_id, user_id=user_id, created_at=now, expires_at=expires_at)
        db.add(s)
        return session_id

    @classmethod
    def get_user_id_by_session(cls, session_id: Optional[str], db: Session) -> Optional[int]:
        if not session_id:
            return None
        row = db.execute(
            select(AuthSession.user_id).where(
                AuthSession.session_id == session_id,
                AuthSession.expires_at > datetime.now(timezone.utc),
            )
        ).scalar_one_or_none()
        return row

    @classmethod
    def revoke_session(cls, session_id: Optional[str], db: Session) -> bool:
        if not session_id:
            return False
        r = db.execute(delete(AuthSession).where(AuthSession.session_id == session_id))
        return r.rowcount > 0

    @classmethod
    def revoke_sessions_for_user(cls, user_id: int, db: Session) -> None:
        db.execute(delete(AuthSession).where(AuthSession.user_id == user_id))

    @classmethod
    def cleanup_expired_sessions(cls) -> int:
        with get_connection() as db:
            r = db.execute(delete(AuthSession).where(AuthSession.expires_at <= datetime.now(timezone.utc)))
            return r.rowcount
