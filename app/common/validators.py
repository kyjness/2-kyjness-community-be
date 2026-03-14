# 범용 UTC datetime 검증. DB naive datetime → API Z 포함. 도메인 전용 검증은 각 domain/*/schema.py 상단에 둠.
from datetime import UTC, datetime
from typing import Annotated

from pydantic import AfterValidator


def ensure_utc_datetime(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


UtcDatetime = Annotated[datetime, AfterValidator(ensure_utc_datetime)]
