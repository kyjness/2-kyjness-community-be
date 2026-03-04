# 로깅 설정. request_id는 app/core/middleware/request_id.py에서 contextvars에 설정. RequestIdFilter가 record.request_id 주입 → 포맷 [%(request_id)s].
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.core.config import settings
from app.core.middleware.request_id import request_id_ctx

_LOG_DATEFMT = "%Y-%m-%d %H:%M:%S"
_LOG_FMT = "%(asctime)s - [%(request_id)s] - %(levelname)s - %(name)s - %(message)s"
_configured = False


class RequestIdFilter(logging.Filter):
    """contextvars request_id → LogRecord.request_id → 포맷 [%(request_id)s]."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx.get() or ""
        return True


def setup_logging() -> None:
    global _configured
    if _configured:
        return
    level = getattr(logging, settings.LOG_LEVEL, logging.INFO)
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()

    formatter = logging.Formatter(_LOG_FMT, datefmt=_LOG_DATEFMT)
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
