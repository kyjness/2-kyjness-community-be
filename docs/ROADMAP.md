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
- [ ] **auth / users** ← **다음**
  - [ ] #9 bcrypt 이중 실행 (pepper 빈값)
  - [ ] #3 회원가입 TOCTOU (중복 IntegrityError 처리)
  - [ ] #7 인증 캐싱 적용 (ADR 0004; pyright `auth.py:128` 동반 해소)
  - [ ] #8 정지 시 토큰 즉시 무효화
- [ ] **media** — #1 스토리지 삭제 실패 시 고아 방지 · 업로드 멱등성(ADR 0008)
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

> 백로그 번호(#n)는 [`../analysis.md`](../analysis.md) 기준.
