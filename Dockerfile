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

ENV POETRY_VERSION=2.0.1
ENV POETRY_HOME=/opt/poetry
ENV PATH="$POETRY_HOME/bin:$PATH"
RUN pip install --no-cache-dir poetry==$POETRY_VERSION
ENV POETRY_VIRTUALENVS_CREATE=false

COPY pyproject.toml poetry.lock* ./
RUN poetry install --no-root --no-dev --no-interaction

COPY app/ ./app/
COPY alembic.ini ./

# -----------------------------------------------------------------------------
# Stage 2: Runtime (최소 패키지, 비루트 사용자)
# -----------------------------------------------------------------------------
FROM python:3.11-slim AS runtime

WORKDIR /app

# 시크릿/환경변수는 이미지에 넣지 않고 런타임에 -e 또는 외부 설정으로 주입
RUN groupadd -r appgroup && useradd -r -g appgroup -u 1000 appuser

# site-packages·bin만 복사하면 shared lib 등이 빠질 수 있으므로 /usr/local 통째 복사
COPY --from=builder /usr/local /usr/local

COPY --from=builder /app/app ./app

# HEALTHCHECK용 curl (경량)
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /app/upload && chown -R appuser:appgroup /app

ENV PYTHONUNBUFFERED=1
# PORT: 빌드 시 --build-arg, 런타임 시 -e PORT=9000 으로 오버라이드 가능
ARG PORT=8000
ENV PORT=${PORT}
EXPOSE ${PORT}

USER appuser

# PORT는 ENV로 런타임 주입 가능. shell 형식으로 ${PORT} 확장
CMD ["sh", "-c", "exec gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:${PORT}"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://127.0.0.1:${PORT}/health || exit 1
