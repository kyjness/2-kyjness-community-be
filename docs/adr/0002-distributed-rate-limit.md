# ADR 0002 — 분산 Rate Limit: Redis Lua Fixed-Window + 메모리 폴백

- **상태**: 채택됨 (Accepted)
- **관련 코드**: `app/core/middleware/rate_limit.py`

## 맥락 (Context)

로그인 브루트포스와 비로그인 업로드 남용을 방어해야 한다. [운영 봉투](README.md)상
서버는 멀티 인스턴스 3~10대 — **인스턴스 로컬 카운터로는 전역 제한이 불가능**하다
(공격자가 인스턴스를 갈아타며 한도를 우회).

## 결정 (Decision)

**Redis 기반 분산 Fixed-Window** rate limit을 순수 ASGI 미들웨어로 둔다.

1. **원자 카운팅**: Lua로 `INCR` + (첫 요청 시)`EXPIRE` + `TTL`을 한 번에 실행 → race 없는 윈도 카운트.
2. **경로별 한도**: 로그인 / 비로그인 업로드 / 전역(IP)별로 윈도·한도를 분리.
3. **스마트 폴백**: Redis 장애 시 **중요 경로(로그인·가입 업로드)** 만 In-memory fixed-window로
   계속 방어(최대 1만 키, OOM 방지 eviction). 일반 경로는 fail-open 통과(가용성 우선).
4. **표준 응답**: 초과 시 `429` + `Retry-After` 헤더.

## 트레이드오프 (Consequences)

**얻은 것**: 멀티 인스턴스 전역 한도 일관성, Lua 원자성으로 동시성 안전, 중요 경로는 Redis 없이도 보호.
**치른 비용**:
- **Fixed-window 경계 버스트** — 윈도 경계에서 짧은 초과 허용(sliding보다 단순함을 택함).
- **Redis 의존** — 중요 경로만 메모리 폴백, 일반 경로는 fail-open(보안보다 가용성 우선 구간).

## 고려한 대안 (Alternatives)

| 대안 | 기각 사유 |
|------|-----------|
| 인스턴스 로컬 카운터 | 멀티 인스턴스 전역 제한 불가(인스턴스 갈아타기로 우회) |
| Sliding-window log | 키당 타임스탬프 집합 유지로 메모리·연산 비용↑ — 봉투 대비 과함 |
| Token bucket | 상태가 더 복잡, fixed-window로 요구 충족 |

## 일부러 하지 않은 것 (Non-goals)

- 모든 엔드포인트 throttle(전역 IP 한도 외엔 적용 안 함 — 필요 경로만).
- 분산 sliding-window 정밀도: 브루트포스 방어엔 fixed-window로 충분.
