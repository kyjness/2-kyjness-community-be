# 알림 API 스키마. BaseSchema로 camelCase 직렬화.
from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.common.enums import NotificationKind
from app.common.schemas import BaseSchema


class NotificationItem(BaseSchema):
    id: str
    kind: NotificationKind
    actor_id: str | None = None
    post_id: str | None = None
    comment_id: str | None = None
    read_at: datetime | None = None
    created_at: datetime


class MarkNotificationsReadRequest(BaseSchema):
    """비어 있으면 해당 유저의 미읽음 전체를 읽음 처리."""

    ids: list[str] = Field(default_factory=list)


class MarkNotificationsReadData(BaseSchema):
    updated_count: int
