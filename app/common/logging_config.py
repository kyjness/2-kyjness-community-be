# 로깅 설정. request_id는 request_id.py의 contextvars → RequestIdFilter가 주입.
# 프로덕션: JSON 구조화 로그(필드 쿼리용). 개발: 사람이 읽는 console + extra는 key=val.
import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.core.config import settings
from app.core.middleware.request_id import request_id_ctx

_LOG_DATEFMT = "%Y-%m-%d %H:%M:%S"
_LOG_FMT = "%(asctime)s - [%(request_id)s] - %(levelname)s - %(name)s - %(message)s"
_configured = False

# LogRecord 기본 속성 — extra(구조화 필드) 추출 시 제외.
_RESERVED = frozenset(
    {
        "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
        "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
        "created", "msecs", "relativeCreated", "thread", "threadName",
        "processName", "process", "taskName", "message", "asctime",
        "request_id", "color_message",
    }
)  # fmt: skip


def _extract_extras(record: logging.LogRecord) -> dict[str, object]:
    """로깅 호출의 extra={...}로 넘어온 커스텀 필드만."""
    return {k: v for k, v in record.__dict__.items() if k not in _RESERVED}


class RequestIdFilter(logging.Filter):
    """contextvars request_id → LogRecord.request_id."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx.get() or ""
        return True


class JsonFormatter(logging.Formatter):
    """구조화 로그: 기본 필드 + extra + 예외를 JSON 한 줄로."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": self.formatTime(record, _LOG_DATEFMT),
            "level": record.levelname,
            "logger": record.name,
            "request_id": getattr(record, "request_id", ""),
            "message": record.getMessage(),
        }
        payload.update(_extract_extras(record))
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


class ConsoleFormatter(logging.Formatter):
    """사람이 읽는 포맷 + extra 필드를 key=val로 덧붙임."""

    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)
        extras = _extract_extras(record)
        if extras:
            base += " " + " ".join(f"{k}={v}" for k, v in extras.items())
        return base


def _build_formatter() -> logging.Formatter:
    if settings.ENVIRONMENT in ("production", "prod"):
        return JsonFormatter()
    return ConsoleFormatter(_LOG_FMT, datefmt=_LOG_DATEFMT)


def setup_logging() -> None:
    global _configured
    if _configured:
        return
    level = getattr(logging, settings.LOG_LEVEL, logging.INFO)
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()

    formatter = _build_formatter()
    request_id_filter = RequestIdFilter()

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    console.addFilter(request_id_filter)
    root.addHandler(console)

    if settings.LOG_FILE_PATH:
        log_path = Path(settings.LOG_FILE_PATH)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=5 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        file_handler.addFilter(request_id_filter)
        root.addHandler(file_handler)

    _configured = True
