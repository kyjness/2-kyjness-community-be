# 이미지 CRUD. DB 쿼리·형상만. 비즈니스·I/O는 MediaService. AsyncSession.
import secrets
from datetime import datetime
from typing import List, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import mapped_column
from sqlalchemy import String, Integer, DateTime, ForeignKey

from app.db import Base, utc_now
from app.core.security import hash_token


class Image(Base):
    __tablename__ = "images"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    file_key = mapped_column(String(255), nullable=False)
    file_url = mapped_column(String(999), nullable=False)
    content_type = mapped_column(String(255), nullable=True)
    size = mapped_column(Integer, nullable=True)
    uploader_id = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    ref_count = mapped_column(Integer, nullable=False, default=0)
    signup_token_hash = mapped_column(String(64), nullable=True)
    signup_expires_at = mapped_column(DateTime(timezone=True), nullable=True)
    created_at = mapped_column(DateTime(timezone=True), nullable=False)


class MediaModel:
    @classmethod
    async def create_signup_image(
        cls,
        file_key: str,
        file_url: str,
        content_type: Optional[str],
        size: Optional[int],
        expires_at: datetime,
        *,
        db: AsyncSession,
    ):
        token = secrets.token_urlsafe(32)
        token_hash = hash_token(token)
        img = await cls.create_image(
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
    async def create_image(
        cls,
        file_key: str,
        file_url: str,
        content_type: Optional[str] = None,
        size: Optional[int] = None,
        uploader_id: Optional[int] = None,
        signup_token_hash: Optional[str] = None,
        signup_expires_at: Optional[datetime] = None,
        *,
        db: AsyncSession,
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
        await db.flush()
        return img

    @classmethod
    async def get_signup_image(cls, image_id: int, db: AsyncSession) -> Optional[Image]:
        stmt = select(Image).where(Image.id == image_id)
        result = await db.execute(stmt)
        return result.scalars().one_or_none()

    @classmethod
    async def get_image_by_id(cls, image_id: int, db: AsyncSession) -> Optional[Image]:
        stmt = select(Image).where(Image.id == image_id)
        result = await db.execute(stmt)
        return result.scalars().one_or_none()

    @classmethod
    async def get_images_by_ids(
        cls, image_ids: List[int], db: AsyncSession
    ) -> List[Image]:
        if not image_ids:
            return []
        stmt = select(Image).where(Image.id.in_(image_ids))
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @classmethod
    async def attach_signup_image(
        cls, image_id: int, user_id: int, db: AsyncSession
    ) -> bool:
        r = await db.execute(
            update(Image)
            .where(Image.id == image_id)
            .values(
                uploader_id=user_id,
                ref_count=Image.ref_count + 1,
                signup_token_hash=None,
                signup_expires_at=None,
            )
        )
        await db.flush()
        return r.rowcount > 0

    @classmethod
    async def increment_ref_count(cls, image_id: int, db: AsyncSession) -> bool:
        r = await db.execute(
            update(Image)
            .where(Image.id == image_id)
            .values(ref_count=Image.ref_count + 1)
        )
        await db.flush()
        return r.rowcount > 0

    @classmethod
    async def decrement_ref_count(
        cls, image_id: int, db: AsyncSession
    ) -> Optional[Image]:
        result = await db.execute(
            select(Image).where(Image.id == image_id).with_for_update()
        )
        image = result.scalars().one_or_none()
        if not image:
            return None
        image.ref_count = max(0, image.ref_count - 1)
        await db.flush()
        return image

    @classmethod
    async def delete_image_record(cls, image: Image, db: AsyncSession) -> None:
        db.delete(image)
        await db.flush()

    @classmethod
    async def get_expired_signup_images(cls, db: AsyncSession) -> List[Image]:
        now = utc_now()
        result = await db.execute(
            select(Image).where(
                Image.uploader_id.is_(None),
                Image.signup_token_hash.is_not(None),
                Image.signup_expires_at.is_not(None),
                Image.signup_expires_at < now,
            )
        )
        return list(result.scalars().all())
