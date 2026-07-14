# SQLAlchemy DeclarativeBase. utc_now, before_update(updated_at 자동).
from datetime import UTC, datetime

from sqlalchemy import event
from sqlalchemy.dialects.postgresql import UUID as _PgUUID
from sqlalchemy.orm import DeclarativeBase

# 모든 UUID PK·FK 컬럼이 공유하는 타입. as_uuid=True 불변식을 한 곳에서 보장한다.
PG_UUID = _PgUUID(as_uuid=True)


def utc_now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


@event.listens_for(Base, "before_update")
def _set_updated_at(_mapper, _connection, target) -> None:
    if hasattr(target, "updated_at"):
        target.updated_at = utc_now()
