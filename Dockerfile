# PuppyTalk API - Docker 이미지
# 비루트 사용자, 멀티스테이지, 최소 패키지, 시크릿은 런타임 주입

# -----------------------------------------------------------------------------
# Stage 1: Builder (의존성 설치, 최종 이미지에 포함 안 함)
# -----------------------------------------------------------------------------
FROM python:3.11-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

ENV POETRY_VERSION=1.8.3
ENV POETRY_HOME=/opt/poetry
ENV PATH="$POETRY_HOME/bin:$PATH"
RUN pip install --no-cache-dir poetry==$POETRY_VERSION
ENV POETRY_VIRTUALENVS_CREATE=false

COPY pyproject.toml poetry.lock* ./
RUN poetry install --no-root --no-dev --no-interaction

COPY app/ ./app/

# -----------------------------------------------------------------------------
# Stage 2: Runtime (최소 패키지, 비루트 사용자)
# -----------------------------------------------------------------------------
FROM python:3.11-slim AS runtime

WORKDIR /app

# 시크릿/환경변수는 이미지에 넣지 않고 런타임에 -e 또는 외부 설정으로 주입
RUN groupadd -r appgroup && useradd -r -g appgroup -u 1000 appuser

COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /app/app ./app

RUN mkdir -p /app/upload && chown -R appuser:appgroup /app

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

USER appuser

CMD ["gunicorn", "app.main:app", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "-b", "0.0.0.0:8000"]
