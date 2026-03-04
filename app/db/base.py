# SQLAlchemy DeclarativeBase. utc_now, soft_delete, update(Partial Update), before_update(updated_at 자동).
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import event
from sqlalchemy.orm import DeclarativeBase


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    def soft_delete(self) -> None:
        if hasattr(self, "deleted_at"):
            self.deleted_at = utc_now()

    def update(self, **kwargs: Any) -> None:
        """Partial Update. PK 제외, 테이블에 있는 컬럼만 setattr."""
        cols = {c.name for c in self.__table__.c}
        pk_names = {c.name for c in self.__table__.primary_key.columns}
        for key, value in kwargs.items():
            if key in cols and key not in pk_names and hasattr(self, key):
                setattr(self, key, value)


@event.listens_for(Base, "before_update")
def _set_updated_at(mapper, connection, target) -> None:
    if hasattr(target, "updated_at"):
        target.updated_at = utc_now()
