# -----------------------------------------------------------------------------
# Stage 1: Builder 
# -----------------------------------------------------------------------------
    FROM python:3.11-slim AS builder

    WORKDIR /app
    
    RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        && rm -rf /var/lib/apt/lists/*
    
    ENV POETRY_VERSION=2.0.1
    RUN pip install --no-cache-dir poetry==$POETRY_VERSION
    
    # 가상 환경(.venv) 프로젝트 내부에 생성하도록 강제
    ENV POETRY_VIRTUALENVS_CREATE=true
    ENV POETRY_VIRTUALENVS_IN_PROJECT=true
    
    COPY pyproject.toml poetry.lock* ./
    RUN poetry install --no-root --only main --no-interaction
    
    # 앱 코드와 루트에 있는 alembic.ini 복사
    COPY app/ ./app/
    COPY alembic.ini ./
    
    # -----------------------------------------------------------------------------
    # Stage 2: Runtime (실무 최적화: 보안 및 경량화)
    # -----------------------------------------------------------------------------
    FROM python:3.11-slim AS runtime
    
    WORKDIR /app
    
    # 비루트 사용자 생성
    RUN groupadd -r appgroup && useradd -r -g appgroup -u 1000 appuser
    
    # 빌더에서 생성된 가상 환경과 소스 코드를 가져오며 소유권(chown) 즉시 부여
    # (app/ 내부에 db/alembic 폴더가 이미 포함되어 있으므로 별도 복사 불필요)
    COPY --chown=appuser:appgroup --from=builder /app/.venv /app/.venv
    COPY --chown=appuser:appgroup --from=builder /app/app ./app
    COPY --chown=appuser:appgroup --from=builder /app/alembic.ini ./
    
    # PATH를 가상 환경으로 고정하여 poetry 없이 명령어(alembic, gunicorn) 직접 실행 가능
    ENV PATH="/app/.venv/bin:$PATH"
    ENV VIRTUAL_ENV=/app/.venv
    
    RUN apt-get update && apt-get install -y --no-install-recommends curl \
        && rm -rf /var/lib/apt/lists/*
    
    # 업로드 폴더 생성 및 소유권 부여
    RUN mkdir -p /app/upload && chown -R appuser:appgroup /app/upload
    
    ENV PYTHONUNBUFFERED=1
    ARG PORT=8000
    ENV PORT=${PORT}
    EXPOSE ${PORT}
    
    # 철저한 권한 분리: 이제부터 appuser로 실행
    USER appuser
    
    CMD ["sh", "-c", "exec gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:${PORT}"]
    
    HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
        CMD curl -f http://127.0.0.1:${PORT}/v1/health || exit 1