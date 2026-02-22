# app/auth/model.py

from datetime import datetime, timedelta
from typing import Optional, Any

import secrets

from app.core.config import settings
from app.core.database import get_connection


class AuthModel:
    SESSION_EXPIRY_TIME = settings.SESSION_EXPIRY_TIME
    @classmethod
    def create_session(cls, user_id: int) -> str:
        session_id = secrets.token_urlsafe(32)
        expires_at = datetime.now() + timedelta(seconds=cls.SESSION_EXPIRY_TIME)
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO sessions (session_id, user_id, expires_at) VALUES (%s, %s, %s)",
                    (session_id, user_id, expires_at),
                )
            conn.commit()
        return session_id

    @classmethod
    def get_user_id_by_session(cls, session_id: Optional[str]) -> Optional[int]:
        if not session_id:
            return None
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT user_id FROM sessions WHERE session_id = %s AND expires_at > NOW()",
                    (session_id,),
                )
                row = cur.fetchone()
        return row["user_id"] if row else None

    @classmethod
    def revoke_session(cls, session_id: Optional[str]) -> bool:
        if not session_id:
            return False
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM sessions WHERE session_id = %s", (session_id,))
                affected = cur.rowcount
            conn.commit()
        return affected > 0

    @classmethod
    def revoke_sessions_for_user(cls, user_id: int, conn: Optional[Any] = None) -> None:
        if conn is not None:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM sessions WHERE user_id = %s", (user_id,))
            return
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM sessions WHERE user_id = %s", (user_id,))
            conn.commit()

    @classmethod
    def cleanup_expired_sessions(cls) -> int:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM sessions WHERE expires_at <= NOW()")
                count = cur.rowcount
            conn.commit()
        return count
