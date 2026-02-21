# app/users/model.py
"""사용자 데이터 모델. users 테이블 전담."""

from datetime import datetime
from typing import Optional

from app.core.database import get_connection
from app.core.security import hash_password, verify_password as security_verify_password


class UsersModel:
    """users 테이블 CRUD 전담."""

    @classmethod
    def _row_to_user(cls, row: dict, include_password: bool = False) -> Optional[dict]:
        if not row:
            return None
        user = {
            "userId": row["id"],
            "email": row["email"],
            "nickname": row["nickname"],
            "profileImageUrl": row["profile_image_url"] or "",
            "createdAt": row["created_at"].isoformat() if row.get("created_at") else "",
        }
        if include_password:
            user["password"] = row["password"]
        return user

    @classmethod
    def create_user(
        cls,
        email: str,
        password: str,
        nickname: str,
        profile_image_url: Optional[str] = None,
    ) -> dict:
        hashed = hash_password(password)
        profile = profile_image_url if profile_image_url else ""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO users (email, password, nickname, profile_image_url)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (email.lower(), hashed, nickname, profile),
                )
                user_id = cur.lastrowid
            conn.commit()
        return cls._row_to_user(
            {
                "id": user_id,
                "email": email,
                "nickname": nickname,
                "profile_image_url": profile,
                "created_at": datetime.now(),
            }
        )

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
                row = cur.fetchone()
        return cls._row_to_user(row, include_password=True) if row else None

    @classmethod
    def get_user_by_id(cls, user_id: int) -> Optional[dict]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, email, nickname, profile_image_url, created_at
                    FROM users WHERE id = %s AND deleted_at IS NULL
                    """,
                    (user_id,),
                )
                row = cur.fetchone()
        return cls._row_to_user(row) if row else None

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
                row = cur.fetchone()
        if not row:
            return None
        return {
            "userId": row["id"],
            "email": row["email"],
            "nickname": row["nickname"],
            "profileImageUrl": row["profile_image_url"] or "",
        }

    @classmethod
    def find_user_by_id(cls, user_id: int) -> Optional[dict]:
        return cls.get_user_by_id(user_id)

    @classmethod
    def update_nickname(cls, user_id: int, new_nickname: str) -> bool:
        user = cls.get_user_by_id(user_id)
        if not user:
            return False
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
    def update_password(cls, user_id: int, new_password: str) -> bool:
        hashed = hash_password(new_password)
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE users SET password = %s WHERE id = %s AND deleted_at IS NULL",
                    (hashed, user_id),
                )
                affected = cur.rowcount
            conn.commit()
        return affected > 0

    @classmethod
    def update_profile_image_url(cls, user_id: int, profile_image_url: str) -> bool:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE users SET profile_image_url = %s WHERE id = %s AND deleted_at IS NULL",
                    (profile_image_url, user_id),
                )
                affected = cur.rowcount
            conn.commit()
        return affected > 0

    @classmethod
    def withdraw_user(cls, user_id: int) -> bool:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE users SET deleted_at = NOW() WHERE id = %s", (user_id,))
                affected = cur.rowcount
            conn.commit()
        return affected > 0

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

    @classmethod
    def verify_password(cls, user_id: int, password: str) -> bool:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT password FROM users WHERE id = %s AND deleted_at IS NULL",
                    (user_id,),
                )
                row = cur.fetchone()
        return (
            security_verify_password(password, row["password"])
            if row and row.get("password")
            else False
        )

    @classmethod
    def withdraw_old_profile_image(cls, user_id: int) -> None:
        user = cls.get_user_by_id(user_id)
        if not user or not user.get("profileImageUrl"):
            return
        from app.media.model import MediaModel
        MediaModel.withdraw_by_url(user["profileImageUrl"])

    @classmethod
    def resolve_image_url(cls, image_id: int) -> Optional[str]:
        from app.media.model import MediaModel
        return MediaModel.get_url_by_id(image_id)
