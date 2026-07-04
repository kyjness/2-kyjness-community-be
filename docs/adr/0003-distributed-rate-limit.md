# ADR 0003 — 분산 Rate Limit: Redis Lua Fixed-Window + Smart Fail-open

- **상태**: 채택됨 (Accepted)
- **관련 코드**: `app/core/middleware/rate_limit.py`(`RateLimitMiddleware`,
  `_check_redis_fixed_window`, `_check_memory_fixed_window`)

## 맥락 (Context)

Rate limit이 필요하다: 로그인 brute-force, 회원가입 이미지 업로드 남용, 전역 남용 방어.
[운영 봉투](../00-operating-envelope-and-scope.md)상 **인스턴스가 3~10대**라, 프로세스 로컬 카운터는
인스턴스마다 따로 세어 실제 한도의 3~10배를 허용해버린다 — 분산 카운터가 필수다.
동시에 Redis가 죽었다고 로그인이 막히면 안 된다(99.9% 가용성).

## 결정 (Decision)

**Redis Lua fixed-window + 스마트 fail-open**을 순수 ASGI 미들웨어로 둔다.

1. **원자 카운트** — Lua로 `INCR` → (첫 요청 시)`EXPIRE` → `TTL`을 한 번에. 네트워크 왕복 1회,
   경합 없는 원자 증가.
2. **Fixed-window** — IP+경로 기준 고정 창(로그인/업로드/전역 각기 다른 한도).
3. **스마트 fail-open** — Redis 장애 시: **중요 경로(로그인·회원가입 업로드)만** 인메모리 fixed-window로
   폴백(OOM 방지 eviction 포함), 나머지 경로는 **통과**(가용성 우선).

## 트레이드오프 (Consequences)

**얻은 것**
- 멀티 인스턴스에서 **일관된 전역 한도** — 인스턴스 수와 무관.
- Lua 원자성으로 카운트 경합·초과 방지.
- Redis 장애에도 로그인 보호는 인메모리로 유지, 서비스 전체는 계속 동작.

**치른 비용**
- **Fixed-window 경계 버스트** — 창 경계에서 순간 최대 2배 허용 가능(봉투상 허용 오차).
- 인메모리 폴백은 인스턴스 로컬이라 장애 중엔 분산 정확도가 떨어짐(중요 경로 한정, 단기).

## 고려한 대안 (Alternatives)

| 대안 | 기각 사유 |
|------|-----------|
| 프로세스 로컬 카운터만 | 멀티 인스턴스에서 한도가 인스턴스 배수로 새어나감 |
| Sliding window log | 요청마다 타임스탬프 집합 저장 → 메모리·복잡도 증가, 요구 대비 과함 |
| Token bucket | 버킷 상태 관리가 더 복잡, fixed-window로 요구 충족 |
| 전 경로 fail-open 없이 fail-closed | Redis 장애가 곧 서비스 장애 → 99.9% 목표와 충돌 |

## 일부러 하지 않은 것 (Non-goals)

- **Sliding window / token bucket**: 경계 버스트 정밀 제어는 이 서비스 요구가 아니다. fixed-window로 충분.
- **전 경로 인메모리 폴백**: 중요 경로만 보호하면 된다. 전역까지 폴백하면 인스턴스별 부정확만 늘 뿐.
