# 사용자 CRUD. User ORM 반환, Controller에서 Schema.model_validate(user)로 직렬화. 프로필 이미지는 profile_image_id(FK).
from typing import List, Optional

from sqlalchemy import select, update, delete, String, Integer, BigInteger, DateTime, Date, ForeignKey, Boolean
from sqlalchemy.orm import Session, mapped_column, relationship, joinedload, selectinload

from app.common.enums import UserStatus
from app.db import Base, utc_now


class DogProfile(Base):
    __tablename__ = "dog_profiles"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = mapped_column(String(100), nullable=False)
    breed = mapped_column(String(100), nullable=False)
    gender = mapped_column(String(20), nullable=False)
    birth_date = mapped_column(Date, nullable=False)
    profile_image_id = mapped_column(BigInteger, ForeignKey("images.id", ondelete="SET NULL"), nullable=True)
    is_representative = mapped_column(Boolean, nullable=False, default=False)
    created_at = mapped_column(DateTime, nullable=False)
    updated_at = mapped_column(DateTime, nullable=False)

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
    profile_image_id = mapped_column(Integer, ForeignKey("images.id", ondelete="SET NULL"), nullable=True)
    status = mapped_column(String(20), nullable=False, default=UserStatus.ACTIVE.value)
    created_at = mapped_column(DateTime, nullable=False)
    updated_at = mapped_column(DateTime, nullable=False)
    deleted_at = mapped_column(DateTime, nullable=True)

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
    def create_user(
        cls,
        email: str,
        hashed_password: str,
        nickname: str,
        profile_image_id: Optional[int] = None,
        *,
        db: Session,
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
        db.flush()
        return user

    @classmethod
    def get_user_by_id(cls, user_id: int, db: Session) -> Optional[User]:
        stmt = (
            select(User)
            .where(User.id == user_id, User.deleted_at.is_(None))
            .options(joinedload(User.profile_image))
        )
        return db.execute(stmt).unique().scalars().one_or_none()

    @classmethod
    def get_user_by_id_with_dogs(cls, user_id: int, db: Session) -> Optional[User]:
        stmt = (
            select(User)
            .where(User.id == user_id, User.deleted_at.is_(None))
            .options(
                joinedload(User.profile_image),
                selectinload(User.dogs).joinedload(DogProfile.profile_image),
            )
        )
        return db.execute(stmt).unique().scalars().one_or_none()

    @classmethod
    def get_users_by_ids(cls, user_ids: List[int], db: Session) -> dict[int, User]:
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
    def get_user_by_email(cls, email: str, db: Session) -> Optional[User]:
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
        """탈퇴(Soft Delete). email/nickname에 suffix 추가해 UNIQUE 재가입 충돌 방지(puppytalkdb.sql 주석 참고)."""
        user = cls.get_user_by_id(user_id, db=db)
        if not user:
            return False
        ts = int(utc_now().timestamp())
        suffix = f"_deleted_{user_id}_{ts}"
        max_prefix = max(0, 255 - len(suffix))
        new_email = (user.email[:max_prefix] + suffix)[:255]
        new_nickname = (user.nickname[:max_prefix] + suffix)[:255]
        r = db.execute(
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


class DogProfilesModel:
    @classmethod
    def create(
        cls,
        owner_id: int,
        name: str,
        breed: str,
        gender: str,
        birth_date,
        profile_image_id: Optional[int] = None,
        is_representative: bool = False,
        *,
        db: Session,
    ) -> DogProfile:
        now = utc_now()
        dog = DogProfile(
            owner_id=owner_id,
            name=name,
            breed=breed,
            gender=gender,
            birth_date=birth_date,
            profile_image_id=profile_image_id,
            is_representative=is_representative,
            created_at=now,
            updated_at=now,
        )
        db.add(dog)
        db.flush()
        return dog

    @classmethod
    def get_by_id(cls, dog_id: int, owner_id: int, db: Session) -> Optional[DogProfile]:
        stmt = (
            select(DogProfile)
            .where(DogProfile.id == dog_id, DogProfile.owner_id == owner_id)
            .options(joinedload(DogProfile.profile_image))
        )
        return db.execute(stmt).unique().scalars().one_or_none()

    @classmethod
    def get_by_owner_id(cls, owner_id: int, db: Session) -> List[DogProfile]:
        stmt = (
            select(DogProfile)
            .where(DogProfile.owner_id == owner_id)
            .options(joinedload(DogProfile.profile_image))
            .order_by(DogProfile.id)
        )
        return list(db.execute(stmt).unique().scalars().all())

    @classmethod
    def update(
        cls,
        dog_id: int,
        owner_id: int,
        *,
        db: Session,
        name: Optional[str] = None,
        breed: Optional[str] = None,
        gender: Optional[str] = None,
        birth_date=None,
        profile_image_id: Optional[int] = None,
        is_representative: Optional[bool] = None,
    ) -> bool:
        values = {}
        if name is not None:
            values["name"] = name
        if breed is not None:
            values["breed"] = breed
        if gender is not None:
            values["gender"] = gender
        if birth_date is not None:
            values["birth_date"] = birth_date
        if profile_image_id is not None:
            values["profile_image_id"] = profile_image_id
        if is_representative is not None:
            values["is_representative"] = is_representative
        values["updated_at"] = utc_now()
        if not values:
            return True
        r = db.execute(
            update(DogProfile).where(DogProfile.id == dog_id, DogProfile.owner_id == owner_id).values(**values)
        )
        return r.rowcount > 0

    @classmethod
    def delete(cls, dog_id: int, owner_id: int, db: Session) -> bool:
        r = db.execute(delete(DogProfile).where(DogProfile.id == dog_id, DogProfile.owner_id == owner_id))
        return r.rowcount > 0

    @classmethod
    def set_representative(cls, owner_id: int, dog_id: int, db: Session) -> bool:
        """해당 유저의 대표 강아지를 dog_id로 설정. 나머지는 is_representative=False."""
        db.execute(
            update(DogProfile).where(DogProfile.owner_id == owner_id).values(is_representative=False)
        )
        r = db.execute(
            update(DogProfile)
            .where(DogProfile.id == dog_id, DogProfile.owner_id == owner_id)
            .values(is_representative=True, updated_at=utc_now())
        )
        return r.rowcount > 0
