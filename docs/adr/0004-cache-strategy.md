# ADR 0004 — 캐시 전략: 읽기 폭주 경로 · Fail-open · 명시적 무효화

- **상태**: 채택됨 (Accepted)
- **관련 코드**: `app/domain/auth/service.py`(`user:status` 캐시),
  `app/api/dependencies/auth.py`(`get_current_user`)

## 맥락 (Context)

인증된 **모든** 요청이 `get_current_user`에서 `users` 테이블을 조회한다(profile_image JOIN 포함,
[analysis #7](../backlog.md)). [운영 봉투](../00-operating-envelope-and-scope.md)상 조회가 폭주하면
`users`가 통째로 핫스팟이 된다. 흥미롭게도 `user:status` 캐시는 **이미 존재하는데 이 핫 경로에는
연결돼 있지 않다** — 부채이자 바로 잡을 지점이다.

## 결정 (Decision)

**"읽기 폭주 경로에만, fail-open으로, 명시적으로 무효화"** 를 캐시 원칙으로 한다.

1. **핫 경로 연결** — 인증 상태 캐시(`user:status:{id}`, 짧은 TTL)를 `get_current_user`에 실제로 적용.
   요청당 DB 조회 → 캐시 히트로 대체.
2. **Fail-open** — 캐시 GET 실패(Redis 장애) 시 예외 없이 DB로 폴백. 캐시는 성능 계층일 뿐 진실의
   원천이 아니다.
3. **명시적 무효화** — 상태 변경(정지·역할 변경) 시 캐시 DEL + refresh 토큰 revoke를 **함께**
   수행([analysis #8](../backlog.md))해 stale 권한을 끊는다.
4. **범용 캐시 추상화 배제** — 데코레이터형 범용 캐시 계층 대신, 얇은 `get-or-set + fail-open` 헬퍼만.

## 트레이드오프 (Consequences)

**얻은 것**
- 인증 핫스팟 완화 — 조회 폭주에도 `users` DB 부하가 캐시로 흡수.
- Redis 장애에도 인증은 DB 폴백으로 계속 동작.

**치른 비용**
- **무효화 누락 시 stale** — 정지가 TTL만큼 늦게 반영될 수 있음. TTL을 짧게 + 상태 변경 시 즉시 DEL로 완화.
- 캐시-DB 이중 경로의 미세한 복잡도.

## 고려한 대안 (Alternatives)

| 대안 | 기각 사유 |
|------|-----------|
| 캐시 없음(매 요청 DB) | 조회 폭주 봉투에서 `users` 핫스팟 — 문제의 원인 그대로(#7) |
| 범용 데코레이터 캐시 계층 | 대상(인증상태·멱등성·조회수)이 성격이 제각각 → 무효화가 어렵고 과한 추상화 |
| 전 조회 write-through 캐시 | 무효화 지점이 폭증, 봉투 대비 과잉 |

## 일부러 하지 않은 것 (Non-goals)

- **범용/데코레이터 캐시 프레임워크**: 캐시가 필요한 지점이 소수라 얇은 헬퍼로 충분. 추상화 자체가 부채.
- **전면 write-through 캐싱**: 대부분 조회는 DB로 충분히 빠르다. 캐시는 *증명된 핫 경로*에만.
