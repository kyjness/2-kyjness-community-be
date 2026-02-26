import secrets
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.orm import Session, mapped_column
from sqlalchemy import String, Integer, DateTime, ForeignKey

from app.core.database import Base
from app.core.security import hash_token
from app.core.storage import storage_delete


class Image(Base):
    __tablename__ = "images"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    file_key = mapped_column(String(255), nullable=False)
    file_url = mapped_column(String(999), nullable=False)
    content_type = mapped_column(String(255), nullable=True)
    size = mapped_column(Integer, nullable=True)
    uploader_id = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    signup_token_hash = mapped_column(String(64), nullable=True)
    signup_expires_at = mapped_column(DateTime, nullable=True)
    created_at = mapped_column(DateTime, nullable=True)
    deleted_at = mapped_column(DateTime, nullable=True)


class MediaModel:
    @classmethod
    def create_image(
        cls,
        file_key: str,
        file_url: str,
        content_type: Optional[str] = None,
        size: Optional[int] = None,
        uploader_id: Optional[int] = None,
        signup_token_hash: Optional[str] = None,
        signup_expires_at: Optional[datetime] = None,
        *,
        db: Session,
    ) -> dict:
        img = Image(
            file_key=file_key,
            file_url=file_url,
            content_type=content_type,
            size=size,
            uploader_id=uploader_id,
            signup_token_hash=signup_token_hash,
            signup_expires_at=signup_expires_at,
        )
        db.add(img)
        db.flush()
        return {"id": img.id, "file_url": file_url}

    @classmethod
    def create_signup_image(
        cls,
        file_key: str,
        file_url: str,
        content_type: Optional[str],
        size: Optional[int],
        expires_at: datetime,
        *,
        db: Session,
    ) -> dict:
        """회원가입용 이미지 1건 저장. 반환: id, file_url, signup_token."""
        token = secrets.token_urlsafe(32)
        token_hash = hash_token(token)
        row = cls.create_image(
            file_key=file_key,
            file_url=file_url,
            content_type=content_type,
            size=size,
            uploader_id=None,
            signup_token_hash=token_hash,
            signup_expires_at=expires_at,
            db=db,
        )
        return {"id": row["id"], "file_url": row["file_url"], "signup_token": token}

    @classmethod
    def get_url_by_id(cls, image_id: int, db: Session) -> Optional[str]:
        row = db.execute(select(Image.file_url).where(Image.id == image_id, Image.deleted_at.is_(None))).scalar_one_or_none()
        return row

    @classmethod
    def withdraw_image_by_owner(cls, image_id: int, user_id: int, db: Session) -> bool:
        r = db.execute(
            update(Image)
            .where(Image.id == image_id, Image.uploader_id == user_id, Image.deleted_at.is_(None))
            .values(deleted_at=datetime.now())
        )
        return r.rowcount > 0

    @classmethod
    def set_uploader(cls, image_id: int, user_id: int, db: Session) -> bool:
        r = db.execute(
            update(Image)
            .where(Image.id == image_id, Image.deleted_at.is_(None))
            .values(uploader_id=user_id)
        )
        return r.rowcount > 0

    @classmethod
    def withdraw_by_url(cls, file_url: str, db: Session) -> bool:
        if not file_url or not file_url.strip():
            return False
        row = db.execute(select(Image.file_key).where(Image.file_url == file_url.strip(), Image.deleted_at.is_(None))).scalar_one_or_none()
        if not row:
            return False
        try:
            storage_delete(row)
        except Exception:
            pass
        r = db.execute(update(Image).where(Image.file_url == file_url.strip(), Image.deleted_at.is_(None)).values(deleted_at=datetime.now()))
        return r.rowcount > 0

    @classmethod
    def attach_signup_image_to_user(
        cls, token: str, image_id: int, user_id: int, db: Session
    ) -> tuple[Optional[str], Optional[str]]:
        """원자적 UPDATE로 검증+소비+uploader 지정. 성공 시 (file_url, None), 실패 시 (None, 에러코드)."""
        now = datetime.now()
        token_hash = hash_token(token)
        r = db.execute(
            update(Image)
            .where(
                Image.id == image_id,
                Image.deleted_at.is_(None),
                Image.uploader_id.is_(None),
                Image.signup_token_hash.is_not(None),
                Image.signup_token_hash == token_hash,
                Image.signup_expires_at.is_not(None),
                Image.signup_expires_at > now,
            )
            .values(uploader_id=user_id, signup_token_hash=None, signup_expires_at=None)
        )
        if r.rowcount != 1:
            row = db.execute(
                select(Image.uploader_id, Image.signup_token_hash).where(
                    Image.id == image_id,
                    Image.deleted_at.is_(None),
                )
            ).first()
            if not row:
                return (None, "SIGNUP_IMAGE_TOKEN_INVALID")
            if row[0] is not None:
                return (None, "SIGNUP_IMAGE_TOKEN_ALREADY_USED")
            return (None, "SIGNUP_IMAGE_TOKEN_INVALID")
        db.flush()
        file_url = db.execute(select(Image.file_url).where(Image.id == image_id)).scalar_one()
        return (file_url, None)

    @classmethod
    def cleanup_expired_signup_images(cls, db: Session, ttl_seconds: int = 3600) -> int:
        """만료된 회원가입용 이미지 스토리지 삭제 후 soft-delete. 삭제 건수 반환."""
        now = datetime.now()
        rows = db.execute(
            select(Image.id, Image.file_key).where(
                Image.uploader_id.is_(None),
                Image.signup_token_hash.is_not(None),
                Image.signup_expires_at.is_not(None),
                Image.signup_expires_at < now,
                Image.deleted_at.is_(None),
            )
        ).all()
        for (img_id, file_key) in rows:
            try:
                storage_delete(file_key)
            except Exception:
                pass
            db.execute(update(Image).where(Image.id == img_id).values(deleted_at=now))
        return len(rows)
