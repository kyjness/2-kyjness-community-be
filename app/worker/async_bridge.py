# Celery(sync) 워커 ↔ FastAPI(async) SQLAlchemy 브릿지. 프로세스당 단일 이벤트 루프 유지.
from __future__ import annotations

import asyncio
import logging
from collections.abc import Coroutine
from typing import TypeVar

from app.db import close_database, init_database

log = logging.getLogger(__name__)

T = TypeVar("T")
_worker_loop: asyncio.AbstractEventLoop | None = None


def get_worker_loop() -> asyncio.AbstractEventLoop:
    """프리포크 워커 프로세스당 하나의 루프. 태스크마다 asyncio.run() 하지 않음(풀·루프 충돌 방지)."""
    global _worker_loop
    if _worker_loop is None or _worker_loop.is_closed():
        _worker_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_worker_loop)
    return _worker_loop


async def init_worker_runtime() -> None:
    ok = await init_database()
    if not ok:
        raise RuntimeError("Celery worker: PostgreSQL connection failed")


async def shutdown_worker_runtime() -> None:
    await close_database()


def run_async_task(coro: Coroutine[None, None, T]) -> T:
    """동기 Celery 태스크 본문에서 async UoW·ORM 호출."""
    loop = get_worker_loop()
    return loop.run_until_complete(coro)


def on_worker_process_init() -> None:
    log.info("celery_worker_process_init: initializing async DB pools")
    run_async_task(init_worker_runtime())


def on_worker_process_shutdown() -> None:
    log.info("celery_worker_process_shutdown: disposing async DB pools")
    global _worker_loop
    if _worker_loop is None or _worker_loop.is_closed():
        return
    try:
        run_async_task(shutdown_worker_runtime())
    finally:
        _worker_loop.close()
        _worker_loop = None
