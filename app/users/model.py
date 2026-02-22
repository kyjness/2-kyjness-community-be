# app/users/model.py

from datetime import datetime
from typing import Optional, Any

from app.core.database import get_connection


class UsersModel:

    # --- Create ---
    @classmethod
    def create_user(cls, email: str, hashed_password: str, nickname: str, profile_image_url: Optional[str] = None) -> dict:
        profile = profile_image_url if profile_image_url else ""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO users (email, password, nickname, profile_image_url)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (email.lower(), hashed_password, nickname, profile),
                )
                user_id = cur.lastrowid
            conn.commit()
        return {
            "id": user_id,
            "email": email,
            "nickname": nickname,
            "profile_image_url": profile,
            "created_at": datetime.now(),
        }

    # --- Read ---
    @classmethod
    def find_user_by_id(cls, user_id: int) -> Optional[dict]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, email, nickname, profile_image_url, created_at
                    FROM users WHERE id = %s AND deleted_at IS NULL
                    """,
                    (user_id,),
                )
                return cur.fetchone()

    @classmethod
    def find_user_by_email(cls, email: str) -> Optional[dict]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, email, password, nickname, profile_image_url, created_at
                    FROM users WHERE email = %s AND deleted_at IS NULL
                    """,
                    (email.lower(),),
                )
                return cur.fetchone()

    @classmethod
    def get_user_summary(cls, user_id: int) -> Optional[dict]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, email, nickname, profile_image_url
                    FROM users WHERE id = %s AND deleted_at IS NULL
                    """,
                    (user_id,),
                )
                return cur.fetchone()

    @classmethod
    def get_password_hash(cls, user_id: int) -> Optional[str]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT password FROM users WHERE id = %s AND deleted_at IS NULL",
                    (user_id,),
                )
                row = cur.fetchone()
        return row["password"] if row and row.get("password") else None

    @classmethod
    def email_exists(cls, email: str) -> bool:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM users WHERE email = %s AND deleted_at IS NULL LIMIT 1",
                    (email.lower(),),
                )
                return cur.fetchone() is not None

    @classmethod
    def nickname_exists(cls, nickname: str) -> bool:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM users WHERE nickname = %s AND deleted_at IS NULL LIMIT 1",
                    (nickname,),
                )
                return cur.fetchone() is not None

    # --- Update ---
    @classmethod
    def update_nickname(cls, user_id: int, new_nickname: str, conn: Optional[Any] = None) -> bool:
        user = cls.find_user_by_id(user_id)
        if not user:
            return False
        if conn is not None:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE users SET nickname = %s WHERE id = %s AND deleted_at IS NULL",
                    (new_nickname, user_id),
                )
                return cur.rowcount > 0
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE users SET nickname = %s WHERE id = %s AND deleted_at IS NULL",
                    (new_nickname, user_id),
                )
                affected = cur.rowcount
            conn.commit()
        return affected > 0

    @classmethod
    def update_password(cls, user_id: int, hashed_password: str, conn: Optional[Any] = None) -> bool:
        if conn is not None:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE users SET password = %s WHERE id = %s AND deleted_at IS NULL",
                    (hashed_password, user_id),
                )
                return cur.rowcount > 0
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE users SET password = %s WHERE id = %s AND deleted_at IS NULL",
                    (hashed_password, user_id),
                )
                affected = cur.rowcount
            conn.commit()
        return affected > 0

    @classmethod
    def update_profile_image_url(cls, user_id: int, profile_image_url: str, conn: Optional[Any] = None) -> bool:
        if conn is not None:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE users SET profile_image_url = %s WHERE id = %s AND deleted_at IS NULL",
                    (profile_image_url, user_id),
                )
                return cur.rowcount > 0
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE users SET profile_image_url = %s WHERE id = %s AND deleted_at IS NULL",
                    (profile_image_url, user_id),
                )
                affected = cur.rowcount
            conn.commit()
        return affected > 0

    # --- Delete ---
    @classmethod
    def withdraw_user(cls, user_id: int, conn: Optional[Any] = None) -> bool:
        if conn is not None:
            with conn.cursor() as cur:
                cur.execute("UPDATE users SET deleted_at = NOW() WHERE id = %s", (user_id,))
                return cur.rowcount > 0
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE users SET deleted_at = NOW() WHERE id = %s", (user_id,))
                affected = cur.rowcount
            conn.commit()
        return affected > 0
