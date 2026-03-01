# 사용자 CRUD. User ORM 반환, Controller에서 Schema.model_validate(user)로 직렬화. 프로필 이미지는 profile_image_id(FK).
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select, update, String, Integer, DateTime, ForeignKey
from sqlalchemy.orm import Session, mapped_column, relationship, joinedload

from app.db import Base
from app.media.model import Image


class User(Base):
    __tablename__ = "users"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    email = mapped_column(String(255), unique=True, nullable=False)
    password = mapped_column(String(999), nullable=False)
    nickname = mapped_column(String(255), unique=True, nullable=False)
    profile_image_id = mapped_column(Integer, ForeignKey("images.id", ondelete="SET NULL"), nullable=True)
    created_at = mapped_column(DateTime, nullable=False)
    updated_at = mapped_column(DateTime, nullable=False)
    deleted_at = mapped_column(DateTime, nullable=True)

    profile_image = relationship("Image", foreign_keys=[profile_image_id])

    @property
    def profile_image_url(self) -> Optional[str]:
        if self.profile_image:
            return self.profile_image.file_url
        return None


class UsersModel:
    @classmethod
    def create_user(
        cls,
        email: str,
        hashed_password: str,
        nickname: str,
        profile_image_id: Optional[int] = None,
        *,
        db: Session,
    ) -> User:
        now = datetime.now(timezone.utc)
        user = User(
            email=email.lower(),
            password=hashed_password,
            nickname=nickname,
            profile_image_id=profile_image_id,
            created_at=now,
            updated_at=now,
            deleted_at=None,
        )
        db.add(user)
        db.flush()
        return user

    @classmethod
    def find_user_by_id(cls, user_id: int, db: Session) -> Optional[User]:
        stmt = (
            select(User)
            .where(User.id == user_id, User.deleted_at.is_(None))
            .options(joinedload(User.profile_image))
        )
        return db.execute(stmt).unique().scalars().one_or_none()

    @classmethod
    def find_users_by_ids(cls, user_ids: List[int], db: Session) -> dict[int, User]:
        if not user_ids:
            return {}
        stmt = (
            select(User)
            .where(User.id.in_(user_ids), User.deleted_at.is_(None))
            .options(joinedload(User.profile_image))
        )
        rows = db.execute(stmt).unique().scalars().all()
        return {r.id: r for r in rows}

    @classmethod
    def find_user_by_email(cls, email: str, db: Session) -> Optional[User]:
        stmt = (
            select(User)
            .where(User.email == email.lower(), User.deleted_at.is_(None))
            .options(joinedload(User.profile_image))
        )
        return db.execute(stmt).unique().scalars().one_or_none()

    @classmethod
    def get_password_hash(cls, user_id: int, db: Session) -> Optional[str]:
        return db.execute(select(User.password).where(User.id == user_id, User.deleted_at.is_(None))).scalar_one_or_none()

    @classmethod
    def email_exists(cls, email: str, db: Session) -> bool:
        return db.execute(select(User.id).where(User.email == email.lower(), User.deleted_at.is_(None)).limit(1)).first() is not None

    @classmethod
    def nickname_exists(cls, nickname: str, db: Session) -> bool:
        return db.execute(select(User.id).where(User.nickname == nickname, User.deleted_at.is_(None)).limit(1)).first() is not None

    @classmethod
    def update_nickname(cls, user_id: int, new_nickname: str, db: Session) -> bool:
        r = db.execute(update(User).where(User.id == user_id, User.deleted_at.is_(None)).values(nickname=new_nickname))
        return r.rowcount > 0

    @classmethod
    def update_password(cls, user_id: int, hashed_password: str, db: Session) -> bool:
        r = db.execute(update(User).where(User.id == user_id, User.deleted_at.is_(None)).values(password=hashed_password))
        return r.rowcount > 0

    @classmethod
    def update_profile_image_id(cls, user_id: int, profile_image_id: Optional[int], db: Session) -> bool:
        r = db.execute(update(User).where(User.id == user_id, User.deleted_at.is_(None)).values(profile_image_id=profile_image_id))
        return r.rowcount > 0

    @classmethod
    def delete_user(cls, user_id: int, db: Session) -> bool:
        r = db.execute(update(User).where(User.id == user_id).values(deleted_at=datetime.now(timezone.utc)))
        return r.rowcount > 0
