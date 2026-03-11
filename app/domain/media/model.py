# 이미지 CRUD. DB 쿼리·형상만. 비즈니스·I/O는 MediaService. AsyncSession.
import secrets
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import mapped_column

from app.core.security import hash_token
from app.db import Base, utc_now


class Image(Base):
    __tablename__ = "images"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    file_key = mapped_column(String(255), nullable=False)
    file_url = mapped_column(String(999), nullable=False)
    content_type = mapped_column(String(255), nullable=True)
    size = mapped_column(Integer, nullable=True)
    uploader_id = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
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
        content_type: str | None,
        size: int | None,
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
        content_type: str | None = None,
        size: int | None = None,
        uploader_id: int | None = None,
        signup_token_hash: str | None = None,
        signup_expires_at: datetime | None = None,
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
    async def get_signup_image(cls, image_id: int, db: AsyncSession) -> Image | None:
        stmt = select(Image).where(Image.id == image_id)
        result = await db.execute(stmt)
        return result.scalars().one_or_none()

    @classmethod
    async def get_image_by_id(cls, image_id: int, db: AsyncSession) -> Image | None:
        stmt = select(Image).where(Image.id == image_id)
        result = await db.execute(stmt)
        return result.scalars().one_or_none()

    @classmethod
    async def get_images_by_ids(cls, image_ids: list[int], db: AsyncSession) -> list[Image]:
        if not image_ids:
            return []
        stmt = select(Image).where(Image.id.in_(image_ids))
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @classmethod
    async def attach_signup_image(cls, image_id: int, user_id: int, db: AsyncSession) -> bool:
        r = await db.execute(
            update(Image)
            .where(Image.id == image_id)
            .values(
                uploader_id=user_id,
                ref_count=Image.ref_count + 1,
                signup_token_hash=None,
                signup_expires_at=None,
            )
            .returning(Image.id)
        )
        await db.flush()
        return r.scalar_one_or_none() is not None

    @classmethod
    async def increment_ref_count(cls, image_id: int, db: AsyncSession) -> bool:
        r = await db.execute(
            update(Image)
            .where(Image.id == image_id)
            .values(ref_count=Image.ref_count + 1)
            .returning(Image.id)
        )
        await db.flush()
        return r.scalar_one_or_none() is not None

    @classmethod
    async def increment_ref_count_bulk(cls, image_ids: list[int], db: AsyncSession) -> int:
        if not image_ids:
            return 0
        r = await db.execute(
            update(Image)
            .where(Image.id.in_(image_ids))
            .values(ref_count=Image.ref_count + 1)
            .returning(Image.id)
        )
        await db.flush()
        return len(list(r.scalars().all()))

    @classmethod
    async def decrement_ref_count(cls, image_id: int, db: AsyncSession) -> Image | None:
        result = await db.execute(select(Image).where(Image.id == image_id).with_for_update())
        image = result.scalars().one_or_none()
        if not image:
            return None
        image.ref_count = max(0, image.ref_count - 1)
        await db.flush()
        return image

    @classmethod
    async def delete_image_record(cls, image: Image, db: AsyncSession) -> None:
        await db.delete(image)
        await db.flush()

    @classmethod
    async def get_expired_signup_images(cls, db: AsyncSession) -> list[Image]:
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
