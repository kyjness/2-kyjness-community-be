# Celery autodiscover: 태스크 모듈을 import 해 등록.
from app.worker.tasks import notifications as notifications  # noqa: F401
