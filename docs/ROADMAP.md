# ROADMAP — 재건 진행 트래커 (living)

> 세션 인수인계·진행 추적용. 상세 근거는 각 **커밋 메시지**와 [`adr/`](adr/)에.
> 전제·범위는 [`00`](00-operating-envelope-and-scope.md), 횡단 결정은 [`01`](01-architecture.md).

## 단계
- [x] **Inception** — 운영 봉투·범위 (`00`)
- [x] **Elaboration** — 횡단 결정 (`01`) + ADR 0001~0006 + `/adr` 커맨드
- [ ] **Construction** — 도메인 재건 (아래) ← **진행 중**
- [ ] **Transition** — 배포·모니터링

## Construction 체크리스트 (재건 순서)

- [x] **기반층** — 설정 pydantic-settings + 프로덕션 가드 · 식별자 레거시 제거 · 구조화 로그(JSON/console)
- [x] **auth / users** — 감사 결과 P0/P1은 이전 하드닝으로 기적용, 마무리만
  - [x] #3 TOCTOU · #8 정지 토큰 무효화 · #9 bcrypt — 기적용 확인
  - [x] #7 인증 캐싱 — status 캐시 fast-fail 확정(ACTIVE는 PK+JOIN 유지; ADR 0004 근거), `auth.py:128` 타이핑 해소
  - [x] 테스트 보강 — #9 단위 · #8 통합
  - [x] 마감: `/security-review`(취약점 0) · `/code-review`(회귀 1건 발견→수정: `.env` 전용 `VIEW_CACHE_TTL_SECONDS`를 Settings 필드로 승격)
- [ ] **media** ← **다음** — #1 스토리지 삭제 실패 시 고아 방지 · 업로드 멱등성(ADR 0008)
- [ ] **posts** (핵심) — #2 view flush CAS · #4 ILIKE 이스케이프 · #10 COUNT · #11 대표견만 · #12 해시태그 왕복 · #17 redis 해시태그 · cursor(ADR 0002) · 조회수(ADR 0007) · 멱등성(ADR 0008)
- [ ] **comments / likes** — #6 트리 페이지네이션 · #15 좋아요 카운트 중복
- [ ] **dogs** — #11 대표견 로딩 정리
- [ ] **chat / notifications** — #16 미읽음 스캔 · #19 방 중복조회 · 실시간(ADR 0009)
- [ ] **reports / admin** — #5 신고 목록 페이지네이션
- [ ] **정리(글로벌)** — #13 UserBlock 중복 인덱스 · #18 `_PG_UUID` 중복 · #20 `__future__` 일관성

## Transition (Ops)
- [ ] 관측성 인프라 — `/metrics`(prometheus) · 헬스 liveness/readiness 분리
- [ ] 배포 — Docker · ECS · CI/CD (재정의)
- [ ] 모니터링 · 로그 수집

## 완료 유닛 (커밋)
| 단위 | 커밋 |
|------|------|
| 설정 pydantic-settings | `919d0cbd` |
| 식별자 레거시 제거 | `99e72306` |
| 구조화 로그 | `2dd828e9` |
| auth 캐시 타이핑 정리 | `77ebdeae` |
| auth bcrypt·정지 테스트 | `ca952cde` |

> 백로그 번호(#n)는 [`../analysis.md`](../analysis.md) 기준.
