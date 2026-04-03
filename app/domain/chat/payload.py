# WS Raw JSON → Pydantic 검증. TypeAdapter 단일 인스턴스로 스키마 재사용.
from __future__ import annotations

import logging
from typing import Any

from pydantic import TypeAdapter, ValidationError

from app.domain.chat.schema import ChatMessageSend, ChatWsErrorPayload

logger = logging.getLogger(__name__)

_send_adapter: TypeAdapter[ChatMessageSend] = TypeAdapter(ChatMessageSend)


def parse_incoming_message(raw_json: str | bytes) -> ChatMessageSend:
    """JSON 문자열/바이트를 ChatMessageSend로 검증.

    실패 시 ValidationError 발생 → WebSocket 핸들러에서 잡아 ChatWsErrorPayload로 응답하고
    연결은 유지하거나 정책에 따라 종료. 로깅 시 exc_info=False로 스팸 완화 가능.
    """
    return _send_adapter.validate_json(raw_json)


def try_parse_incoming_message(
    raw_json: str | bytes,
) -> ChatMessageSend | None:
    """크래시 없이 파싱만 시도할 때(백그라운드·메트릭). 실패 시 None + warning 로그."""
    try:
        return _send_adapter.validate_json(raw_json)
    except ValidationError as e:
        logger.warning("chat_ws_payload_invalid", extra={"errors": e.errors()})
        return None


def validation_error_to_ws_error(e: ValidationError) -> dict[str, Any]:
    """핸들러에서 json.dumps(..., default=str) 등으로 전송 가능한 camelCase dict."""
    first = e.errors()[0] if e.errors() else {}
    loc = ".".join(str(x) for x in first.get("loc", ()))
    msg = first.get("msg", "validation_error")
    detail = f"{loc}: {msg}" if loc else str(msg)
    return ChatWsErrorPayload(
        code="validation_error",
        message=detail[:500],
    ).model_dump(mode="json", by_alias=True)
