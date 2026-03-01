# 로깅 설정. setup_logging으로 레벨·파일·포맷 설정.
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.core.config import settings

_LOG_FMT = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
_LOG_DATEFMT = "%Y-%m-%d %H:%M:%S"
_configured = False


def setup_logging() -> None:
    global _configured
    if _configured:
        return
    level = getattr(logging, settings.LOG_LEVEL, logging.INFO)
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()
    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter(_LOG_FMT, datefmt=_LOG_DATEFMT))
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
        file_handler.setFormatter(logging.Formatter(_LOG_FMT, datefmt=_LOG_DATEFMT))
        root.addHandler(file_handler)
    _configured = True
