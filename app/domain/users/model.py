# 사용자 CRUD. User ORM 반환, Controller에서 Schema.model_validate(user)로 직렬화. 프로필 이미지는 profile_image_id(FK). AsyncSession.
from typing import List, Optional

from sqlalchemy import (
    select,
    update,
    String,
    Integer,
    DateTime,
    Date,
    ForeignKey,
    Boolean,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import mapped_column, relationship, joinedload, selectinload

from app.common.enums import UserStatus
from app.db import Base, utc_now


class DogProfile(Base):
    __tablename__ = "dog_profiles"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name = mapped_column(String(100), nullable=False)
    breed = mapped_column(String(100), nullable=False)
    gender = mapped_column(String(20), nullable=False)
    birth_date = mapped_column(Date, nullable=False)
    profile_image_id = mapped_column(
        Integer, ForeignKey("images.id", ondelete="SET NULL"), nullable=True
    )
    is_representative = mapped_column(Boolean, nullable=False, default=False)
    created_at = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at = mapped_column(DateTime(timezone=True), nullable=False)

    owner = relationship("User", back_populates="dogs", foreign_keys=[owner_id])
    profile_image = relationship("Image", foreign_keys=[profile_image_id])

    @property
    def profile_image_url(self) -> Optional[str]:
        if self.profile_image:
            return self.profile_image.file_url
        return None


class User(Base):
    __tablename__ = "users"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    email = mapped_column(String(255), unique=True, nullable=False)
    password = mapped_column(String(255), nullable=False)
    nickname = mapped_column(String(255), unique=True, nullable=False)
    profile_image_id = mapped_column(
        Integer, ForeignKey("images.id", ondelete="SET NULL"), nullable=True
    )
    status = mapped_column(String(20), nullable=False, default=UserStatus.ACTIVE.value)
    created_at = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at = mapped_column(DateTime(timezone=True), nullable=False)
    deleted_at = mapped_column(DateTime(timezone=True), nullable=True)

    profile_image = relationship("Image", foreign_keys=[profile_image_id])
    dogs = relationship(
        "DogProfile",
        back_populates="owner",
        foreign_keys=[DogProfile.owner_id],
        order_by="DogProfile.id",
    )

    @property
    def profile_image_url(self) -> Optional[str]:
        if self.profile_image:
            return self.profile_image.file_url
        return None

    @property
    def is_active(self) -> bool:
        # 하위호환: 레거시 코드에서 user.is_active를 계속 사용할 수 있게 유지
        return UserStatus.is_active_value(self.status)

    @property
    def representative_dog(self) -> Optional[DogProfile]:
        for d in self.dogs or []:
            if getattr(d, "is_representative", False):
                return d
        return None


class UsersModel:
    @classmethod
    async def create_user(
        cls,
        email: str,
        hashed_password: str,
        nickname: str,
        profile_image_id: Optional[int] = None,
        *,
        db: AsyncSession,
    ) -> User:
        now = utc_now()
        user = User(
            email=email.lower(),
            password=hashed_password,
            nickname=nickname,
            profile_image_id=profile_image_id,
            status=UserStatus.ACTIVE.value,
            created_at=now,
            updated_at=now,
            deleted_at=None,
        )
        db.add(user)
        await db.flush()
        return user

    @classmethod
    async def get_user_by_id(cls, user_id: int, db: AsyncSession) -> Optional[User]:
        stmt = (
            select(User)
            .where(User.id == user_id, User.deleted_at.is_(None))
            .options(joinedload(User.profile_image))
        )
        result = await db.execute(stmt)
        return result.unique().scalars().one_or_none()

    @classmethod
    async def get_user_by_id_with_dogs(
        cls, user_id: int, db: AsyncSession
    ) -> Optional[User]:
        stmt = (
            select(User)
            .where(User.id == user_id, User.deleted_at.is_(None))
            .options(
                joinedload(User.profile_image),
                selectinload(User.dogs).joinedload(DogProfile.profile_image),
            )
        )
        result = await db.execute(stmt)
        return result.unique().scalars().one_or_none()

    @classmethod
    async def get_users_by_ids(
        cls, user_ids: List[int], db: AsyncSession
    ) -> dict[int, User]:
        if not user_ids:
            return {}
        stmt = (
            select(User)
            .where(User.id.in_(user_ids), User.deleted_at.is_(None))
            .options(joinedload(User.profile_image))
        )
        result = await db.execute(stmt)
        rows = result.unique().scalars().all()
        return {r.id: r for r in rows}

    @classmethod
    async def get_user_by_email(cls, email: str, db: AsyncSession) -> Optional[User]:
        stmt = (
            select(User)
            .where(User.email == email.lower(), User.deleted_at.is_(None))
            .options(joinedload(User.profile_image))
        )
        result = await db.execute(stmt)
        return result.unique().scalars().one_or_none()

    @classmethod
    async def get_password_hash(cls, user_id: int, db: AsyncSession) -> Optional[str]:
        result = await db.execute(
            select(User.password).where(User.id == user_id, User.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    @classmethod
    async def email_exists(cls, email: str, db: AsyncSession) -> bool:
        result = await db.execute(
            select(User.id)
            .where(User.email == email.lower(), User.deleted_at.is_(None))
            .limit(1)
        )
        return result.first() is not None

    @classmethod
    async def nickname_exists(cls, nickname: str, db: AsyncSession) -> bool:
        result = await db.execute(
            select(User.id)
            .where(User.nickname == nickname, User.deleted_at.is_(None))
            .limit(1)
        )
        return result.first() is not None

    @classmethod
    async def update_nickname(
        cls, user_id: int, new_nickname: str, db: AsyncSession
    ) -> bool:
        r = await db.execute(
            update(User)
            .where(User.id == user_id, User.deleted_at.is_(None))
            .values(nickname=new_nickname, updated_at=utc_now())
        )
        return r.rowcount > 0

    @classmethod
    async def update_password(
        cls, user_id: int, hashed_password: str, db: AsyncSession
    ) -> bool:
        r = await db.execute(
            update(User)
            .where(User.id == user_id, User.deleted_at.is_(None))
            .values(password=hashed_password)
        )
        return r.rowcount > 0

    @classmethod
    async def update_profile_image_id(
        cls, user_id: int, profile_image_id: Optional[int], db: AsyncSession
    ) -> bool:
        r = await db.execute(
            update(User)
            .where(User.id == user_id, User.deleted_at.is_(None))
            .values(profile_image_id=profile_image_id, updated_at=utc_now())
        )
        return r.rowcount > 0

    @classmethod
    async def delete_user(cls, user_id: int, db: AsyncSession) -> bool:
        """탈퇴(Soft Delete). email/nickname에 suffix 추가해 UNIQUE 재가입 충돌 방지(puppytalkdb.sql 주석 참고)."""
        user = await cls.get_user_by_id(user_id, db=db)
        if not user:
            return False
        ts = int(utc_now().timestamp())
        suffix = f"_deleted_{user_id}_{ts}"
        max_prefix = max(0, 255 - len(suffix))
        new_email = (user.email[:max_prefix] + suffix)[:255]
        new_nickname = (user.nickname[:max_prefix] + suffix)[:255]
        r = await db.execute(
            update(User)
            .where(User.id == user_id, User.deleted_at.is_(None))
            .values(
                email=new_email,
                nickname=new_nickname,
                status=UserStatus.WITHDRAWN.value,
                profile_image_id=None,
                deleted_at=utc_now(),
            )
        )
        return r.rowcount > 0
