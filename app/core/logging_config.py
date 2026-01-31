import logging

from app.core.config import settings


def configure_logging() -> None:
    """앱 전역 로깅 설정.

    - 개발(DEBUG=True): INFO
    - 운영(DEBUG=False): WARNING 이상
    """
    logging.basicConfig(
        level=logging.DEBUG if settings.DEBUG else logging.WARNING,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

