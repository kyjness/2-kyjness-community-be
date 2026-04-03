# 사용자 CRUD. User ORM 반환, Controller에서 Schema.model_validate(user)로 직렬화. 프로필 이미지는 profile_image_id(FK). AsyncSession.
from datetime import date as DateType
from datetime import datetime as DateTimeType
from datetime import timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    delete,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, joinedload, mapped_column, relationship, selectinload

from app.common.enums import UserStatus
from app.core.ids import new_uuid7
from app.db.base_class import Base, utc_now
from app.infra.storage import build_url
from app.media.model import Image

_PG_UUID = PG_UUID(as_uuid=True)


class DogProfile(Base):
    __tablename__ = "dog_profiles"

    id: Mapped[UUID] = mapped_column(_PG_UUID, primary_key=True, default=new_uuid7)
    owner_id: Mapped[UUID] = mapped_column(
        _PG_UUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    breed: Mapped[str] = mapped_column(String(100), nullable=False)
    gender: Mapped[str] = mapped_column(String(20), nullable=False)
    birth_date: Mapped[DateType] = mapped_column(Date, nullable=False)
    profile_image_id: Mapped[UUID | None] = mapped_column(
        _PG_UUID, ForeignKey("images.id", ondelete="SET NULL"), nullable=True, index=True
    )
    is_representative: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[DateTimeType] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[DateTimeType] = mapped_column(DateTime(timezone=True), nullable=False)

    owner: Mapped["User"] = relationship(
        "User", back_populates="dogs", foreign_keys=[owner_id], lazy="raise_on_sql"
    )
    profile_image: Mapped[Image | None] = relationship(
        "Image", foreign_keys=[profile_image_id], lazy="raise_on_sql"
    )

    @property
    def profile_image_url(self) -> str | None:
        if self.profile_image:
            return build_url(self.profile_image.file_key)
        return None


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(_PG_UUID, primary_key=True, default=new_uuid7)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    __mapper_args__ = {"version_id_col": version}
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password: Mapped[str] = mapped_column(String(255), nullable=False)
    nickname: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    profile_image_id: Mapped[UUID | None] = mapped_column(
        _PG_UUID, ForeignKey("images.id", ondelete="SET NULL"), nullable=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="USER")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=UserStatus.ACTIVE.value)
    created_at: Mapped[DateTimeType] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[DateTimeType] = mapped_column(DateTime(timezone=True), nullable=False)
    deleted_at: Mapped[DateTimeType | None] = mapped_column(DateTime(timezone=True), nullable=True)

    profile_image: Mapped[Image | None] = relationship(
        "Image", foreign_keys=[profile_image_id], lazy="raise_on_sql"
    )
    dogs: Mapped[list[DogProfile]] = relationship(
        "DogProfile",
        back_populates="owner",
        foreign_keys=[DogProfile.owner_id],
        order_by="DogProfile.id",
        lazy="raise_on_sql",
    )

    @property
    def profile_image_url(self) -> str | None:
        if self.profile_image:
            return build_url(self.profile_image.file_key)
        return None

    @property
    def is_active(self) -> bool:
        # 하위호환: 레거시 코드에서 user.is_active를 계속 사용할 수 있게 유지
        return UserStatus.is_active_value(self.status)

    @property
    def representative_dog(self) -> DogProfile | None:
        for d in self.dogs or []:
            if getattr(d, "is_representative", False):
                return d
        return None


class UserBlock(Base):
    __tablename__ = "user_blocks"
    __table_args__ = (
        UniqueConstraint("blocker_id", "blocked_id", name="uq_user_blocks_blocker_blocked"),
    )

    blocker_id: Mapped[UUID] = mapped_column(
        _PG_UUID, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    blocked_id: Mapped[UUID] = mapped_column(
        _PG_UUID, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[DateTimeType] = mapped_column(DateTime(timezone=True), nullable=False)

    blocker: Mapped["User"] = relationship("User", foreign_keys=[blocker_id], lazy="raise_on_sql")
    blocked: Mapped["User"] = relationship("User", foreign_keys=[blocked_id], lazy="raise_on_sql")


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[UUID] = mapped_column(_PG_UUID, primary_key=True, default=new_uuid7)
    reporter_id: Mapped[UUID] = mapped_column(
        _PG_UUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target_id: Mapped[UUID] = mapped_column(_PG_UUID, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[DateTimeType] = mapped_column(DateTime(timezone=True), nullable=False)
    deleted_at: Mapped[DateTimeType | None] = mapped_column(DateTime(timezone=True), nullable=True)

    reporter: Mapped["User"] = relationship("User", foreign_keys=[reporter_id], lazy="raise_on_sql")


class UsersModel:
    @classmethod
    async def create_user(
        cls,
        email: str,
        hashed_password: str,
        nickname: str,
        profile_image_id: UUID | None = None,
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
    async def get_user_by_id(cls, user_id: UUID, db: AsyncSession) -> User | None:
        stmt = (
            select(User)
            .where(User.id == user_id, User.deleted_at.is_(None))
            .options(joinedload(User.profile_image))
        )
        result = await db.execute(stmt)
        return result.unique().scalars().one_or_none()

    @classmethod
    async def get_user_by_id_including_deleted(cls, user_id: UUID, db: AsyncSession) -> User | None:
        stmt = select(User).where(User.id == user_id).options(joinedload(User.profile_image))
        result = await db.execute(stmt)
        return result.unique().scalars().one_or_none()

    @classmethod
    async def get_user_by_id_with_dogs(cls, user_id: UUID, db: AsyncSession) -> User | None:
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
    async def get_users_by_ids(cls, user_ids: list[UUID], db: AsyncSession) -> dict[UUID, User]:
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
    async def get_user_by_email(cls, email: str, db: AsyncSession) -> User | None:
        stmt = (
            select(User)
            .where(User.email == email.lower(), User.deleted_at.is_(None))
            .options(joinedload(User.profile_image))
        )
        result = await db.execute(stmt)
        return result.unique().scalars().one_or_none()

    @classmethod
    async def get_password_hash(cls, user_id: UUID, db: AsyncSession) -> str | None:
        result = await db.execute(
            select(User.password).where(User.id == user_id, User.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    @classmethod
    async def email_exists(cls, email: str, db: AsyncSession) -> bool:
        result = await db.execute(
            select(User.id).where(User.email == email.lower(), User.deleted_at.is_(None)).limit(1)
        )
        return result.first() is not None

    @classmethod
    async def nickname_exists(cls, nickname: str, db: AsyncSession) -> bool:
        result = await db.execute(
            select(User.id).where(User.nickname == nickname, User.deleted_at.is_(None)).limit(1)
        )
        return result.first() is not None

    _UPDATE_USER_ALLOWED = frozenset({"nickname", "profile_image_id", "status"})

    @classmethod
    async def update_user(
        cls,
        user_id: UUID,
        *,
        db: AsyncSession,
        **fields: Any,
    ) -> bool:
        allowed = {k: v for k, v in fields.items() if k in cls._UPDATE_USER_ALLOWED}
        if not allowed:
            return True
        allowed["updated_at"] = utc_now()
        r = await db.execute(
            update(User)
            .where(User.id == user_id, User.deleted_at.is_(None))
            .values(**allowed)
            .returning(User.id)
        )
        return r.scalar_one_or_none() is not None

    @classmethod
    async def update_password(cls, user_id: UUID, hashed_password: str, db: AsyncSession) -> bool:
        r = await db.execute(
            update(User)
            .where(User.id == user_id, User.deleted_at.is_(None))
            .values(password=hashed_password)
            .returning(User.id)
        )
        return r.scalar_one_or_none() is not None

    @classmethod
    async def get_blocked_users(cls, blocker_id: UUID, db: AsyncSession) -> list[User]:
        """내가 차단한 유저 목록 (삭제되지 않은 유저만, 차단 시점 최신순)."""
        stmt = (
            select(User)
            .join(UserBlock, User.id == UserBlock.blocked_id)
            .where(
                UserBlock.blocker_id == blocker_id,
                User.deleted_at.is_(None),
            )
            .options(joinedload(User.profile_image))
            .order_by(UserBlock.created_at.desc())
        )
        result = await db.execute(stmt)
        return list(result.unique().scalars().all())

    @classmethod
    async def block_exists(cls, blocker_id: UUID, blocked_id: UUID, db: AsyncSession) -> bool:
        result = await db.execute(
            select(UserBlock.blocker_id)
            .where(
                UserBlock.blocker_id == blocker_id,
                UserBlock.blocked_id == blocked_id,
            )
            .limit(1)
        )
        return result.first() is not None

    @classmethod
    async def block_user(cls, blocker_id: UUID, blocked_id: UUID, db: AsyncSession) -> None:
        db.add(
            UserBlock(
                blocker_id=blocker_id,
                blocked_id=blocked_id,
                created_at=utc_now(),
            )
        )
        await db.flush()

    @classmethod
    async def unblock_user(cls, blocker_id: UUID, blocked_id: UUID, db: AsyncSession) -> int:
        r = await db.execute(
            delete(UserBlock)
            .where(
                UserBlock.blocker_id == blocker_id,
                UserBlock.blocked_id == blocked_id,
            )
            .returning(UserBlock.blocker_id)
        )
        return len(list(r.scalars().all()))

    _DELETED_AT_MAX_LEN = 255

    @classmethod
    def _deleted_at_suffix(cls, user_id: UUID) -> str:
        ts = int(utc_now().timestamp())
        return f"_deleted_{user_id}_{ts}"

    @classmethod
    def _mask_for_withdrawal(cls, value: str, suffix: str) -> str:
        max_len = cls._DELETED_AT_MAX_LEN
        prefix_len = max(0, max_len - len(suffix))
        base = str(value)[:prefix_len] if value else ""
        return (base + suffix)[:max_len]

    @classmethod
    async def delete_user(cls, user_id: UUID, db: AsyncSession) -> bool:
        stmt = select(User.id, User.email, User.nickname).where(
            User.id == user_id, User.deleted_at.is_(None)
        )
        result = await db.execute(stmt)
        row = result.one_or_none()
        if not row:
            return False
        now = utc_now()
        suffix = cls._deleted_at_suffix(user_id)
        new_email = cls._mask_for_withdrawal(row.email, suffix)
        new_nickname = cls._mask_for_withdrawal(row.nickname, suffix)
        r = await db.execute(
            update(User)
            .where(User.id == user_id, User.deleted_at.is_(None))
            .values(
                email=new_email,
                nickname=new_nickname,
                status=UserStatus.WITHDRAWN.value,
                profile_image_id=None,
                deleted_at=now,
                updated_at=now,
            )
            .returning(User.id)
        )
        return r.scalar_one_or_none() is not None

    @classmethod
    async def purge_withdrawn_users_older_than(
        cls,
        *,
        older_than_days: int,
        limit: int,
        db: AsyncSession,
    ) -> list[UUID]:
        """탈퇴(WITHDRAWN) + deleted_at 기준 N일 경과 유저를 하드 삭제.

        - 대량 삭제로 인한 락을 줄이기 위해 limit 단위로 청크 처리한다.
        - FK ondelete(CASCADE/SET NULL)에 의존해 연관 데이터 정합성 유지.
        """
        cutoff = utc_now() - timedelta(days=older_than_days)
        id_stmt = (
            select(User.id)
            .where(
                User.status == UserStatus.WITHDRAWN.value,
                User.deleted_at.is_not(None),
                User.deleted_at < cutoff,
            )
            .limit(int(limit))
        )
        result = await db.execute(delete(User).where(User.id.in_(id_stmt)).returning(User.id))
        await db.flush()
        return list(result.scalars().all())
