# -----------------------------------------------------------------------------
# Stage 1: Builder (uv: PEP 621 + hatchling)
# -----------------------------------------------------------------------------
FROM python:3.11-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

COPY pyproject.toml README.md ./
RUN uv lock && uv sync --frozen --no-install-project --no-dev

COPY app ./app/
COPY migrations ./migrations/
COPY alembic.ini ./
RUN uv sync --frozen --no-dev

# -----------------------------------------------------------------------------
# Stage 2: Runtime
# -----------------------------------------------------------------------------
FROM python:3.11-slim AS runtime

WORKDIR /app

RUN groupadd -r appgroup && useradd -r -m -g appgroup -u 1000 appuser

COPY --chown=appuser:appgroup --from=builder /app/.venv /app/.venv
COPY --chown=appuser:appgroup --from=builder /app/app ./app
COPY --chown=appuser:appgroup --from=builder /app/migrations ./migrations
COPY --chown=appuser:appgroup --from=builder /app/alembic.ini ./

ENV PATH="/app/.venv/bin:$PATH"
ENV VIRTUAL_ENV=/app/.venv

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /app/upload && chown -R appuser:appgroup /app/upload

COPY --chown=appuser:appgroup scripts/entrypoint.sh /app/scripts/entrypoint.sh
RUN chmod +x /app/scripts/entrypoint.sh

ENV PYTHONUNBUFFERED=1
ARG PORT=8000
ENV PORT=${PORT}
EXPOSE ${PORT}

USER appuser

ENTRYPOINT ["/app/scripts/entrypoint.sh"]
CMD ["gunicorn", "app.main:app", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "-b", "0.0.0.0:8000"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://127.0.0.1:${PORT}/v1/health || exit 1
