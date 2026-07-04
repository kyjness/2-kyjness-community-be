# ADR 0005 — 복원력: Fail-open 표준 & Circuit Breaker 미채택

- **상태**: 채택됨 (Accepted)
- **관련 코드**: `app/infra/redis.py`, `app/core/middleware/rate_limit.py`,
  `app/domain/posts/services/post_service.py`(view buffer), `app/infra/storage.py`

## 맥락 (Context)

외부 I/O 의존(Redis·S3)이 있다. [운영 봉투](../00-operating-envelope-and-scope.md)의 가용성 목표는
**99.9%**이고 상한은 멀티리전·강정합성이 아니다. 즉 외부 의존 하나가 흔들릴 때 **전체 가용성을
지키는 것**이 순간 정합성보다 우선이다. 관건은 "어디까지 방어 장치를 넣는가"다.

## 결정 (Decision)

**Fail-open을 복원력 표준으로 명문화**하고, **Circuit Breaker는 채택하지 않는다.**

1. **Fail-open 표준** — Redis 장애 시: 조회수 dedup/버퍼를 건너뛰고 DB 직접 증가, rate limit은
   통과/인메모리 폴백([ADR 0003](0003-distributed-rate-limit.md)), 캐시는 DB 폴백([ADR 0004](0004-cache-strategy.md)).
   "성능·보호 계층은 없어도 서비스는 돈다."
2. **경계 타임아웃** — 사용자 대면 외부 I/O(S3 업로드 등)엔 **타임아웃 + 명확한 실패 응답**을 둬
   무한 대기를 막는다.
3. **Circuit Breaker 미채택** — 아래 Non-goals 참조.

## 트레이드오프 (Consequences)

**얻은 것**
- 외부 의존 장애가 **전체 장애로 전파되지 않음** — 99.9% 목표에 직결.
- 상태 기계(CB의 open/half-open) 없이 단순 — 추론·운영이 쉬움.

**치른 비용**
- 장애 중 **보호 계층 약화** — 예: Redis 다운 시 조회수 dedup이 잠깐 사라져 수치가 부풀 수 있음.
  조회수는 비임계 지표라 봉투상 허용.
- CB가 주는 "장애 대상 빠른 차단·자동 회복"은 없음 — 타임아웃+재시도로 대체.

## 고려한 대안 (Alternatives)

| 대안 | 기각 사유 |
|------|-----------|
| Fail-closed | 외부 의존 장애 = 서비스 장애 → 99.9% 목표와 정면충돌 |
| Circuit Breaker 도입 | open/half-open 상태·임계 튜닝의 복잡도. 봉투 규모에선 타임아웃+fail-open으로 충분 |
| 재시도 큐/사가 | 조회수·캐시 같은 비임계 경로엔 불필요한 인프라 |

## 일부러 하지 않은 것 (Non-goals)

- **Circuit Breaker**: 이 서비스의 외부 의존은 소수(Redis·S3)이고, 각기 fail-open + 타임아웃으로
  방어된다. CB의 상태 기계는 봉투 상한(멀티리전·초당 수만) 아래에서 정당화되지 않는 복잡도 —
  **의식적으로 배제한다.** ("쓸 데와 안 쓸 데를 구분했다"의 대표 사례.)
- **분산 트랜잭션 / Saga**: 강정합성은 봉투 상한 밖. 비임계 경로는 최종 일관성으로 충분.
