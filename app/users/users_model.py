# app/users/users_model.py
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
        """새 사용자 생성"""
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
        """이메일로 사용자 찾기 (비밀번호 포함, 로그인용)"""
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
        """사용자 정보 조회 (비밀번호 제외, createdAt 포함)"""
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
        """사용자 요약 조회. 4개 필드(userId, email, nickname, profileImageUrl)만 반환."""
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
        """ID로 사용자 찾기 (비밀번호 제외). 게시글/댓글 작성자 조회용."""
        return cls.get_user_by_id(user_id)

    @classmethod
    def update_nickname(cls, user_id: int, new_nickname: str) -> bool:
        """닉네임 수정"""
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
        """비밀번호 수정"""
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
        """프로필 이미지 URL 수정"""
        with get_connection() as conn:
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
    def delete_user(cls, user_id: int) -> bool:
        """회원 탈퇴 (users 테이블 soft delete만). 세션 삭제는 AuthModel.revoke_sessions_for_user 사용."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE users SET deleted_at = NOW() WHERE id = %s", (user_id,))
                affected = cur.rowcount
            conn.commit()
        return affected > 0

    @classmethod
    def email_exists(cls, email: str) -> bool:
        """이메일 중복 확인"""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM users WHERE email = %s AND deleted_at IS NULL LIMIT 1",
                    (email.lower(),),
                )
                return cur.fetchone() is not None

    @classmethod
    def nickname_exists(cls, nickname: str) -> bool:
        """닉네임 중복 확인"""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM users WHERE nickname = %s AND deleted_at IS NULL LIMIT 1",
                    (nickname,),
                )
                return cur.fetchone() is not None

    @classmethod
    def verify_password(cls, user_id: int, password: str) -> bool:
        """비밀번호 검증"""
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
    def soft_delete_old_profile_image(cls, user_id: int) -> None:
        """프로필 변경 전 이전 프로필 이미지를 images 테이블에서 soft delete."""
        user = cls.get_user_by_id(user_id)
        if not user or not user.get("profileImageUrl"):
            return
        from app.media.media_model import MediaModel
        MediaModel.soft_delete_by_url(user["profileImageUrl"])

    @classmethod
    def resolve_image_url(cls, image_id: int) -> Optional[str]:
        """images 테이블에서 image_id로 URL 조회 (프로필/게시글 연결용)."""
        from app.media.media_model import MediaModel
        return MediaModel.get_url_by_id(image_id)
