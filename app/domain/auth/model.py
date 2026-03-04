# 레거시 세션 테이블. 대규모 무효화(탈퇴)·만료 정리용. revoke_sessions_for_user, cleanup_expired_sessions 만 사용.
from sqlalchemy import delete
from sqlalchemy.orm import Session, mapped_column
from sqlalchemy import String, Integer, DateTime, ForeignKey

from app.db import Base, get_connection, utc_now


class AuthSession(Base):
    __tablename__ = "sessions"

    session_id = mapped_column(String(255), primary_key=True)
    user_id = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = mapped_column(DateTime, nullable=False)
    expires_at = mapped_column(DateTime, nullable=False)


class AuthModel:
    @classmethod
    def revoke_sessions_for_user(cls, user_id: int, db: Session) -> None:
        db.execute(delete(AuthSession).where(AuthSession.user_id == user_id))

    @classmethod
    def cleanup_expired_sessions(cls) -> int:
        with get_connection() as db:
            r = db.execute(delete(AuthSession).where(AuthSession.expires_at <= utc_now()))
            return r.rowcount
