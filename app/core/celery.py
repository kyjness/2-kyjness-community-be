# Celery 앱: Redis broker + result backend, 큐 라우팅, 워커 프로세스 DB 풀 초기화.

from celery import Celery
from celery.signals import worker_process_init, worker_process_shutdown

from app.core.config import settings
from app.worker.async_bridge import on_worker_process_init, on_worker_process_shutdown

_TASK_ROUTES = {
    "app.worker.tasks.notifications.*": {"queue": "high_priority"},
    "app.worker.tasks.*": {"queue": "default"},
}


def _redis_url_with_db(base: str, db_index: int) -> str:
    base = (base or "").strip().rstrip("/")
    if not base:
        return f"redis://127.0.0.1:6379/{db_index}"
    if base.endswith(f"/{db_index}"):
        return base
    # redis://host:6379 또는 redis://host:6379/0 형태 정규화
    if "/" in base.split("://", 1)[-1]:
        prefix = base.rsplit("/", 1)[0]
        return f"{prefix}/{db_index}"
    return f"{base}/{db_index}"


def _broker_url() -> str:
    if settings.CELERY_BROKER_URL:
        return settings.CELERY_BROKER_URL
    return _redis_url_with_db(settings.REDIS_URL, settings.CELERY_BROKER_DB)


def _result_backend_url() -> str:
    if settings.CELERY_RESULT_BACKEND:
        return settings.CELERY_RESULT_BACKEND
    return _redis_url_with_db(settings.REDIS_URL, settings.CELERY_RESULT_DB)


celery_app = Celery(  # pyright: ignore[reportCallIssue]  # celery lazy import → 스텁 미비 오탐
    "puppytalk",
    broker=_broker_url(),
    backend=_result_backend_url(),
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_default_queue="default",
    task_queues={
        "default": {"exchange": "default", "routing_key": "default"},
        "high_priority": {"exchange": "high_priority", "routing_key": "high_priority"},
    },
    task_routes=_TASK_ROUTES,
    task_soft_time_limit=settings.CELERY_TASK_SOFT_TIME_LIMIT,
    task_time_limit=settings.CELERY_TASK_TIME_LIMIT,
    broker_transport_options={
        "visibility_timeout": settings.CELERY_BROKER_VISIBILITY_TIMEOUT,
    },
    result_expires=settings.CELERY_RESULT_EXPIRES_SECONDS,
)

celery_app.autodiscover_tasks(["app.worker.tasks"])


@worker_process_init.connect
def _celery_worker_process_init(**_kwargs: object) -> None:
    on_worker_process_init()


@worker_process_shutdown.connect
def _celery_worker_process_shutdown(**_kwargs: object) -> None:
    on_worker_process_shutdown()
