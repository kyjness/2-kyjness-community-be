#!/bin/sh
# ECS/VPC 내 DB URL(WRITER_DB_URL 등)은 런타임 env로 주입. Alembic env.py가 settings를 로드함.
# Windows에서 편집 시 CRLF 금지 — LF만 사용(스크립트 실행 오류 방지).
set -e
cd /app
alembic upgrade head
exec "$@"
