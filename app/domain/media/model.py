# 이미지 CRUD. Image ORM 반환, Controller에서 Schema로 직렬화.
import hmac
import logging
import secrets
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select, update
from sqlalchemy.orm import Session, mapped_column
from sqlalchemy import String, Integer, DateTime, ForeignKey

from app.db import Base, utc_now
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
    ref_count = mapped_column(Integer, nullable=False, default=0)
    signup_token_hash = mapped_column(String(64), nullable=True)
    signup_expires_at = mapped_column(DateTime, nullable=True)
    created_at = mapped_column(DateTime, nullable=False)


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
            created_at=utc_now(),
        )
        db.add(img)
        db.flush()
        return img

    @classmethod
    def get_signup_image(cls, image_id: int, db: Session) -> Optional[Image]:
        stmt = select(Image).where(Image.id == image_id)
        return db.execute(stmt).scalars().one_or_none()

    @classmethod
    def verify_signup_token(cls, image_id: int, token: str, db: Session) -> Optional[Image]:
        image = cls.get_signup_image(image_id, db)
        if not image or image.uploader_id is not None:
            return None
        expected_hash = hash_token(token)
        if not hmac.compare_digest(image.signup_token_hash or "", expected_hash):
            return None
        if image.signup_expires_at is None:
            return None
        now = utc_now()
        expires_at = image.signup_expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at <= now:
            return None
        return image

    @classmethod
    def get_image_by_id(cls, image_id: int, db: Session) -> Optional[Image]:
        stmt = select(Image).where(Image.id == image_id)
        return db.execute(stmt).scalars().one_or_none()

    @classmethod
    def get_images_by_ids(cls, image_ids: List[int], db: Session) -> List[Image]:
        if not image_ids:
            return []
        stmt = select(Image).where(Image.id.in_(image_ids))
        return list(db.execute(stmt).scalars().all())

    @classmethod
    def attach_signup_image(cls, image_id: int, user_id: int, db: Session) -> bool:
        r = db.execute(
            update(Image)
            .where(Image.id == image_id)
            .values(
                uploader_id=user_id,
                ref_count=Image.ref_count + 1,
                signup_token_hash=None,
                signup_expires_at=None,
            )
        )
        db.flush()
        return r.rowcount > 0

    @classmethod
    def increment_ref_count(cls, image_id: int, db: Session) -> bool:
        r = db.execute(
            update(Image).where(Image.id == image_id).values(ref_count=Image.ref_count + 1)
        )
        return r.rowcount > 0

    @classmethod
    def decrement_ref_count(cls, image_id: int, db: Session) -> bool:
        image = db.execute(
            select(Image).where(Image.id == image_id).with_for_update()
        ).scalars().one_or_none()
        if not image:
            return False
        image.ref_count = max(0, image.ref_count - 1)
        db.flush()
        if image.ref_count <= 0:
            try:
                storage_delete(image.file_key)
            except Exception as e:
                logger.warning("Image file delete failed image_id=%s file_key=%s: %s", image_id, image.file_key, e)
            db.delete(image)
        return True

    @classmethod
    def delete_image_by_owner(cls, image_id: int, uploader_id: int, db: Session) -> bool:
        image = cls.get_image_by_id(image_id, db)
        if not image or image.uploader_id != uploader_id:
            return False
        if image.ref_count > 0:
            raise ValueError("IMAGE_IN_USE")
        try:
            storage_delete(image.file_key)
        except Exception as e:
            logger.warning("Image file delete failed image_id=%s file_key=%s: %s", image_id, image.file_key, e)
        db.delete(image)
        db.flush()
        return True

    @classmethod
    def cleanup_expired_signup_images(cls, db: Session) -> tuple[int, List[str]]:
        now = utc_now()
        rows = db.execute(
            select(Image).where(
                Image.uploader_id.is_(None),
                Image.signup_token_hash.is_not(None),
                Image.signup_expires_at.is_not(None),
                Image.signup_expires_at < now,
            )
        ).scalars().all()
        if not rows:
            return 0, []
        failed_file_keys: List[str] = []
        for img in rows:
            try:
                storage_delete(img.file_key)
            except Exception as e:
                logger.warning(
                    "Signup image storage delete failed image_id=%s file_key=%s: %s",
                    img.id,
                    img.file_key,
                    e,
                    exc_info=True,
                )
                failed_file_keys.append(img.file_key)
            db.delete(img)
        return len(rows), failed_file_keys

