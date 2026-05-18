# 채팅 WS·REST DTO. 수신(send)·송신(broadcast) 분리, 공개 ID는 PublicId(Base62).
from __future__ import annotations

from datetime import date as DateType
from typing import Literal

from pydantic import Field, field_validator

from app.common import BaseSchema, PublicId, UtcDatetime


class ChatMessageSend(BaseSchema):
    """클라이언트 → 서버(예: WebSocket 텍스트 프레임 JSON)."""

    type: Literal["chat.send"] = Field(
        default="chat.send",
        description="향후 다른 액션과 구분하기 위한 구분자",
    )
    peer_user_id: PublicId = Field(..., description="1:1 상대방 공개 ID (Base62)")
    content: str = Field(
        ...,
        min_length=1,
        max_length=10_000,
        description="메시지 본문(앞뒤 공백 제거 후 비어 있으면 불가)",
    )

    @field_validator("content")
    @classmethod
    def strip_nonempty(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("content_empty")
        return s


class ChatMessageBroadcast(BaseSchema):
    """서버 → 구독 클라이언트 브로드캐스트."""

    type: Literal["chat.message"] = "chat.message"
    id: PublicId
    room_id: PublicId
    sender_id: PublicId
    content: str
    is_read: bool = False
    created_at: UtcDatetime


class ChatWsErrorPayload(BaseSchema):
    """검증 실패 등: 핸들러에서 JSON 직렬화 후 전송. 500 대신 계약된 에러 객체로 응답."""

    type: Literal["error"] = "error"
    code: str = Field(..., description="짧은 기계식 코드(예: validation_error)")
    message: str = Field(default="", description="사용자/디버그용 짧은 설명")


class ChatMessageItem(BaseSchema):
    id: PublicId
    room_id: PublicId
    sender_id: PublicId
    content: str
    is_read: bool
    created_at: UtcDatetime


class ChatMessagesPageData(BaseSchema):
    items: list[ChatMessageItem]
    next_cursor: str | None = Field(
        default=None,
        description="다음 페이지(더 과거) 조회 시 쿼리 cursor로 전달할 메시지 공개 ID(Base62)",
    )


class ChatDirectRoomData(BaseSchema):
    """1:1 방 조회·없으면 생성 후 공개 room id."""

    room_id: PublicId


class ChatRoomListItem(BaseSchema):
    room_id: PublicId
    peer_user_id: PublicId
    peer_nickname: str = Field(default="", description="상대방 닉네임(표시명)")
    peer_profile_image_url: str | None = Field(default=None, description="상대방 프로필 이미지 URL")
    peer_dog_profile_image_url: str | None = Field(
        default=None, description="상대 대표 강아지 프로필 이미지 URL"
    )
    peer_dog_name: str | None = Field(default=None, description="상대 대표견 이름")
    peer_dog_breed: str | None = Field(default=None, description="상대 대표견 견종")
    peer_dog_gender: str | None = Field(
        default=None, description="상대 대표견 성별 코드(male/female)"
    )
    peer_dog_birth_date: DateType | None = Field(default=None, description="상대 대표견 생년월일")
    last_message_preview: str = Field(default="", description="최근 메시지 미리보기(짧게)")
    unread_count: int = Field(default=0, ge=0, description="내 기준 미읽음 개수(상대가 보낸 것만)")
    updated_at: UtcDatetime | None = Field(default=None, description="최근 메시지 시각")


class ChatRoomsListData(BaseSchema):
    items: list[ChatRoomListItem]


class ChatRoomMarkedReadData(BaseSchema):
    ok: bool = True


class ChatRoomPeerInfoData(BaseSchema):
    room_id: PublicId
    peer_user_id: PublicId
    peer_nickname: str = Field(default="", description="상대방 닉네임(표시명)")
    peer_profile_image_url: str | None = Field(default=None, description="상대방 프로필 이미지 URL")
    peer_dog_name: str | None = Field(default=None, description="상대 대표 강아지 이름")
    peer_dog_profile_image_url: str | None = Field(
        default=None, description="상대 대표 강아지 프로필 이미지 URL"
    )
    peer_dog_breed: str | None = Field(default=None, description="상대 대표 강아지 견종")
    peer_dog_gender: str | None = Field(
        default=None, description="상대 대표 강아지 성별 코드(male/female)"
    )
    peer_dog_birth_date: DateType | None = Field(
        default=None, description="상대 대표 강아지 생년월일"
    )
