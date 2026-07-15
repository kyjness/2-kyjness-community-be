#!/usr/bin/env bash
# 루트 진입점 — 실제 구현은 scripts/dev.sh (옵션·사용법 동일).
exec "$(dirname "${BASH_SOURCE[0]}")/scripts/dev.sh" "$@"
