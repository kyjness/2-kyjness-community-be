# 이미지 CRUD. Image ORM 반환, Controller에서 Schema로 직렬화.
import logging
import secrets
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select, update
from sqlalchemy.orm import Session, mapped_column
from sqlalchemy import String, Integer, DateTime, ForeignKey

from app.db import Base
from app.core.security import hash_token
from app.core.storage import storage_delete

logger = logging.getLogger(__name__)


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
    created_at = mapped_column(DateTime, nullable=False)
    deleted_at = mapped_column(DateTime, nullable=True)


class MediaModel:
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
    ) -> tuple[Image, str]:
        token = secrets.token_urlsafe(32)
        token_hash = hash_token(token)
        img = cls.create_image(
            file_key=file_key,
            file_url=file_url,
            content_type=content_type,
            size=size,
            uploader_id=None,
            signup_token_hash=token_hash,
            signup_expires_at=expires_at,
            db=db,
        )
        return img, token

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
    ) -> Image:
        img = Image(
            file_key=file_key,
            file_url=file_url,
            content_type=content_type,
            size=size,
            uploader_id=uploader_id,
            signup_token_hash=signup_token_hash,
            signup_expires_at=signup_expires_at,
            created_at=datetime.now(timezone.utc),
        )
        db.add(img)
        db.flush()
        return img

    @classmethod
    def get_signup_image_for_update(cls, image_id: int, db: Session) -> Optional[Image]:
        stmt = (
            select(Image)
            .where(Image.id == image_id, Image.deleted_at.is_(None))
            .with_for_update()
        )
        return db.execute(stmt).scalars().one_or_none()

    @classmethod
    def get_image_by_id(cls, image_id: int, db: Session) -> Optional[Image]:
        stmt = select(Image).where(
            Image.id == image_id,
            Image.deleted_at.is_(None),
        )
        return db.execute(stmt).scalars().one_or_none()

    @classmethod
    def get_images_by_ids(cls, image_ids: List[int], db: Session) -> List[Image]:
        if not image_ids:
            return []
        stmt = select(Image).where(
            Image.id.in_(image_ids),
            Image.deleted_at.is_(None),
        )
        return list(db.execute(stmt).scalars().all())

    @classmethod
    def finalize_signup_image(cls, image_id: int, user_id: int, db: Session) -> bool:
        r = db.execute(
            update(Image)
            .where(Image.id == image_id, Image.deleted_at.is_(None))
            .values(
                uploader_id=user_id,
                signup_token_hash=None,
                signup_expires_at=None,
            )
        )
        return r.rowcount > 0

    @classmethod
    def cleanup_expired_signup_images(cls, db: Session) -> tuple[int, List[str]]:
        now = datetime.now(timezone.utc)
        rows = db.execute(
            select(Image.id, Image.file_key).where(
                Image.uploader_id.is_(None),
                Image.signup_token_hash.is_not(None),
                Image.signup_expires_at.is_not(None),
                Image.signup_expires_at < now,
                Image.deleted_at.is_(None),
            )
        ).all()
        if not rows:
            return 0, []
        ids = [r[0] for r in rows]
        db.execute(update(Image).where(Image.id.in_(ids)).values(deleted_at=now))
        failed_file_keys: List[str] = []
        for (image_id, file_key) in rows:
            try:
                storage_delete(file_key)
            except Exception as e:
                logger.warning(
                    "Signup image storage delete failed image_id=%s file_key=%s: %s",
                    image_id,
                    file_key,
                    e,
                    exc_info=True,
                )
                failed_file_keys.append(file_key)
        return len(rows), failed_file_keys

    @classmethod
    def delete_image_by_owner(cls, image_id: int, user_id: int, db: Session) -> bool:
        r = db.execute(
            update(Image)
            .where(
                Image.id == image_id,
                Image.uploader_id == user_id,
                Image.deleted_at.is_(None),
            )
            .values(deleted_at=datetime.now(timezone.utc))
        )
        return r.rowcount > 0
