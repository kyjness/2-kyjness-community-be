#!/usr/bin/env bash
# 전체 스택 로컬 실행: 백엔드(docker compose — db·redis·minio·API) 기동 후
# 프론트(pnpm dev)를 포그라운드로 띄운다. 순서(백엔드→프론트)와 health 대기를 자동 처리.
#
# 사용:
#   ./scripts/dev.sh                 # 백엔드 스택 + 프론트 dev 서버
#   ./scripts/dev.sh --backend-only  # 백엔드 스택만
#   ./scripts/dev.sh --down          # 백엔드 스택 종료(docker compose down)
#   FE_DIR=/path/to/fe ./scripts/dev.sh   # 프론트 경로 지정(기본: ../2-kyjness-community-fe)
set -euo pipefail

BE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FE_DIR="${FE_DIR:-$BE_DIR/../2-kyjness-community-fe}"
HEALTH_URL="${HEALTH_URL:-http://localhost:8000/v1/health}"
HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-90}"

compose() { docker compose -f "$BE_DIR/docker-compose.yml" "$@"; }

case "${1:-}" in
  --down)
    echo "▶ 백엔드 스택 종료…"
    compose down
    exit 0
    ;;
  -h|--help)
    sed -n '2,9p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
    exit 0
    ;;
esac

BACKEND_ONLY=false
[[ "${1:-}" == "--backend-only" ]] && BACKEND_ONLY=true

command -v docker >/dev/null || { echo "✗ docker가 필요합니다."; exit 1; }

echo "▶ 백엔드 스택 기동 (docker compose up --build -d)…"
compose up --build -d

echo "▶ API health 대기: $HEALTH_URL (최대 ${HEALTH_TIMEOUT}s)"
for ((i = 1; i <= HEALTH_TIMEOUT; i++)); do
  if curl -sf "$HEALTH_URL" >/dev/null 2>&1; then
    echo "  ✓ API ready"
    break
  fi
  if ((i == HEALTH_TIMEOUT)); then
    echo "  ✗ API가 ${HEALTH_TIMEOUT}s 내 준비되지 않음. 로그: docker compose logs backend" >&2
    exit 1
  fi
  sleep 1
done

if $BACKEND_ONLY; then
  echo "백엔드만 실행 중. 종료하려면: ./scripts/dev.sh --down"
  exit 0
fi

if [[ ! -d "$FE_DIR" ]]; then
  echo "⚠ 프론트 디렉터리를 찾지 못함: $FE_DIR"
  echo "  FE_DIR=/path/to/fe 로 지정하거나, 백엔드만 쓰려면 --backend-only 사용."
  echo "  백엔드 스택은 계속 실행 중입니다(종료: ./scripts/dev.sh --down)."
  exit 0
fi

echo "▶ 프론트 개발 서버 (pnpm dev) — Ctrl+C로 종료 (백엔드 스택은 계속 실행)"
echo "  백엔드 종료는 별도로: ./scripts/dev.sh --down"
cd "$FE_DIR"
command -v pnpm >/dev/null || { echo "✗ pnpm이 필요합니다. corepack enable 후 재시도."; exit 1; }
[[ -d node_modules ]] || pnpm install
exec pnpm dev
