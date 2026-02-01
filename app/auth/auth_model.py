# app/auth/auth_model.py
"""인증 관련 데이터 모델 (MySQL users, sessions 테이블)"""

from datetime import datetime, timedelta
from typing import Optional

import bcrypt
import secrets

from app.core.config import settings
from app.core.database import get_connection


class AuthModel:
    """인증 관련 데이터 모델 (MySQL)"""

    SESSION_EXPIRY_TIME = settings.SESSION_EXPIRY_TIME  # 초 단위

    @classmethod
    def _hash_password(cls, password: str) -> str:
        """비밀번호 해시화 (bcrypt)"""
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
        return hashed.decode("utf-8")

    @staticmethod
    def _verify_password(password: str, hashed_password: str) -> bool:
        """비밀번호 검증 (bcrypt)"""
        try:
            return bcrypt.checkpw(
                password.encode("utf-8"),
                hashed_password.encode("utf-8"),
            )
        except (ValueError, TypeError):
            return False

    @classmethod
    def _row_to_user(cls, row: dict, include_password: bool = False) -> dict:
        """DB 행을 API 형식 user dict로 변환"""
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
        """새 사용자 생성"""
        conn = get_connection()
        hashed = cls._hash_password(password)
        profile = profile_image_url if profile_image_url else ""

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
        """이메일로 사용자 찾기 (비밀번호 검증용 전체 반환)"""
        conn = get_connection()
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
    def find_user_by_nickname(cls, nickname: str) -> Optional[dict]:
        """닉네임으로 사용자 찾기"""
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, email, nickname, profile_image_url, created_at
                FROM users WHERE nickname = %s AND deleted_at IS NULL
                """,
                (nickname,),
            )
            row = cur.fetchone()
        return cls._row_to_user(row) if row else None

    @classmethod
    def find_user_by_id(cls, user_id: int) -> Optional[dict]:
        """ID로 사용자 찾기 (비밀번호 제외)"""
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, email, nickname, profile_image_url
                FROM users WHERE id = %s AND deleted_at IS NULL
                """,
                (user_id,),
            )
            row = cur.fetchone()
        return cls._row_to_user(row) if row else None

    @classmethod
    def get_user_by_id(cls, user_id: int) -> Optional[dict]:
        """사용자 정보 조회 (비밀번호 제외, createdAt 포함)"""
        conn = get_connection()
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
    def update_user_nickname(
        cls, user_id: int, old_nickname: str, new_nickname: str
    ) -> bool:
        """닉네임 수정"""
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET nickname = %s WHERE id = %s AND deleted_at IS NULL",
                (new_nickname, user_id),
            )
            affected = cur.rowcount
        conn.commit()
        return affected > 0

    @classmethod
    def update_user_password(cls, user_id: int, new_password: str) -> bool:
        """비밀번호 수정"""
        conn = get_connection()
        hashed = cls._hash_password(new_password)
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET password = %s WHERE id = %s AND deleted_at IS NULL",
                (hashed, user_id),
            )
            affected = cur.rowcount
        conn.commit()
        return affected > 0

    @classmethod
    def update_user_profile_image_url(
        cls, user_id: int, profile_image_url: str
    ) -> bool:
        """프로필 이미지 URL 수정"""
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE users SET profile_image_url = %s
                WHERE id = %s AND deleted_at IS NULL
                """,
                (profile_image_url, user_id),
            )
            affected = cur.rowcount
        conn.commit()
        return affected > 0

    @classmethod
    def delete_user_data(cls, user_id: int) -> bool:
        """사용자 삭제 (하드 삭제)"""
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute("DELETE FROM sessions WHERE user_id = %s", (user_id,))
            cur.execute("UPDATE users SET deleted_at = NOW() WHERE id = %s", (user_id,))
            affected = cur.rowcount
        conn.commit()
        return affected > 0

    @classmethod
    def revoke_all_sessions_for_user(cls, user_id: int) -> int:
        """해당 사용자의 모든 세션 삭제"""
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute("DELETE FROM sessions WHERE user_id = %s", (user_id,))
            count = cur.rowcount
        conn.commit()
        return count

    @classmethod
    def email_exists(cls, email: str) -> bool:
        """이메일 중복 확인"""
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM users WHERE email = %s AND deleted_at IS NULL LIMIT 1",
                (email.lower(),),
            )
            return cur.fetchone() is not None

    @classmethod
    def nickname_exists(cls, nickname: str) -> bool:
        """닉네임 중복 확인"""
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM users WHERE nickname = %s AND deleted_at IS NULL LIMIT 1",
                (nickname,),
            )
            return cur.fetchone() is not None

    @classmethod
    def verify_password(cls, user_id: int, password: str) -> bool:
        """비밀번호 검증"""
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT password FROM users WHERE id = %s AND deleted_at IS NULL",
                (user_id,),
            )
            row = cur.fetchone()
        return (
            cls._verify_password(password, row["password"])
            if row and row.get("password")
            else False
        )

    @classmethod
    def create_session(cls, user_id: int) -> str:
        """세션 생성 후 세션 ID 반환"""
        session_id = secrets.token_urlsafe(32)
        expires_at = datetime.now() + timedelta(seconds=cls.SESSION_EXPIRY_TIME)

        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO sessions (session_id, user_id, expires_at)
                VALUES (%s, %s, %s)
                """,
                (session_id, user_id, expires_at),
            )
        conn.commit()
        return session_id

    @classmethod
    def get_user_id_by_session(cls, session_id: Optional[str]) -> Optional[int]:
        """세션 ID로 user_id 조회. 만료 시 None"""
        if not session_id:
            return None
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT user_id FROM sessions
                WHERE session_id = %s AND expires_at > NOW()
                """,
                (session_id,),
            )
            row = cur.fetchone()
        return row["user_id"] if row else None

    @classmethod
    def revoke_session(cls, session_id: Optional[str]) -> bool:
        """세션 삭제 (로그아웃)"""
        if not session_id:
            return False
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute("DELETE FROM sessions WHERE session_id = %s", (session_id,))
            affected = cur.rowcount
        conn.commit()
        return affected > 0

    @classmethod
    def cleanup_expired_sessions(cls) -> int:
        """만료된 세션 정리"""
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute("DELETE FROM sessions WHERE expires_at <= NOW()")
            count = cur.rowcount
        conn.commit()
        return count

    # 하위 호환 별칭
    create_token = create_session
    verify_token = get_user_id_by_session
    revoke_token = revoke_session
    revoke_all_user_tokens = revoke_all_sessions_for_user
