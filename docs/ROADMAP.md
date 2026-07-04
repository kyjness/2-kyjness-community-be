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
- [x] **media** — #1 고아 방지·업로드 멱등성 기적용 확인
  - [x] signup/orphan 정리를 트랜잭션 밖 스토리지 I/O + 배치로 정렬(형제 sweep와 통일)
  - [x] 리뷰 지적 수정: 정리 배치를 keyset(id>last_id) 전진으로 → 실패 머리 starvation·중복 로그 제거
  - [x] ADR 0008(POST 멱등성) 작성 · media 테스트 보강(멱등성 재생·409·정리 고아 방지·keyset 전진)
  - [x] 스토리지 전략 확정 — ADR 0010(S3 API 단일 경로·dev MinIO 패리티·local 폐기, 배선은 Ops)
  - [x] 마감: `/security-review`(취약점 0) · `/code-review`(정리 5건 → 헬퍼 추출·dead code 제거·설정 개명)
- [x] **posts** (핵심) — #2 CAS·#4 ILIKE 이스케이프·#17 해시태그는 기적용 확인(#17은 `{v}`가 load-bearing)
  - [x] #11 대표견만 로드 + 중복 eager-load 헬퍼 통합 · #12 해시태그 동기화 5→4왕복(upsert→조회)
  - [x] #10 커서 목록 `total` 제거 — `CursorPage` 분리(ADR 0002 결정을 코드로 구현)
  - [x] 조회수 write-behind 버퍼링 단위 테스트 보강(dedup·flush delta·CAS·재병합) + ADR 0007 작성
  - [x] 마감: `/code-review`(정확성 1건 → flush 커밋후 drain 삭제 실패 이중집계 수정) · `/security-review`(취약점 0)
  - [~] #11 심화(전용 `representative_dog` 뷰 관계로 `author.dogs` 부분 컬렉션 트랩 제거)는 **dogs 도메인으로 이연**
- [x] **comments / likes** — #11 twin 대표견만 로드 · #6 트리 페이지네이션 · #15 좋아요 카운터 중복
  - [x] #11 twin: 댓글 작성자 대표견만 로드(`_comment_author_loads`, posts와 동형)
  - [x] #6: 루트 keyset + 대댓글 부모별 배치 로드 + `CursorPage`(ADR 0002 결정을 코드로). 인메모리 슬라이스·500 cap·부정확 total 제거. 좋아요 keyset 드리프트 부정당 → 인기순(popular) 정렬 제거
  - [x] #15: 좋아요 카운터를 `CommentsModel`로 일원화(`CommentLikesModel` 중복 제거, posts 패턴 정합)
  - [x] 별건: 게시글 목록 `is_liked` 항상 False 버그 수정(배치 조회)
  - [x] 테스트: 트리 조립 단위(`test_comment_tree`) + keyset·삭제 시맨틱·is_liked·무이중집계 통합(`test_comments`·`test_posts`)
  - [x] 마감: `/code-review`(정리 3건 → 가시성 술어 공용화·중복 정렬 제거·is_liked 관용구 통일) · `/security-review`(취약점 0)
  - [~] 대댓글 자체 페이지네이션(루트당 preview + 더보기)은 기능 확장이라 backlog #21로 이연
- [ ] **dogs** — #11 대표견 로딩 정리(전용 `representative_dog` 관계로 모델째 정리)
- [ ] **chat / notifications** — #16 미읽음 스캔 · #19 방 중복조회 · 실시간(ADR 0009)
- [ ] **reports / admin** — #5 신고 목록 페이지네이션
- [ ] **정리(글로벌)** — #13 UserBlock 중복 인덱스 · #18 `_PG_UUID` 중복 · #20 `__future__` 일관성

## Transition (Ops)
- [ ] 관측성 인프라 — `/metrics`(prometheus) · 헬스 liveness/readiness 분리
- [ ] 스토리지 — docker-compose+CI에 MinIO 배선 → 통합테스트 MinIO 대상 전환 → **local 디스크 백엔드 제거**([ADR 0010](adr/0010-storage-backend-strategy.md))
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
| media signup 정리 트랜잭션 위생 | `b2579690` |
| media 멱등성·정리 테스트 | `f7edcd1b` |
| ADR 0008 멱등성 | `ecaf12c7` |
| media 정리 keyset 전진(리뷰 수정) | `7fedfd9e` |
| ADR 0010 스토리지 전략 | `80fa9049` |
| 백로그 docs/backlog.md 편입 | `d63c6ead` |
| media 정리 헬퍼 추출·dead code·개명(리뷰 수정) | `2b77838d` |
| posts 대표견만 로드·eager-load 헬퍼(#11) | `710c8d78` |
| posts 해시태그 5→4왕복(#12) | `3c4482b6` |
| posts 커서 목록 total 제거·CursorPage(#10) | `51b19c30` |
| posts 조회수 버퍼링 단위 테스트 | `4fa970be` |
| ADR 0007 조회수 write-behind | `4d73d07e` |
| posts flush 커밋후 삭제실패 이중집계 수정(리뷰) | `26947d41` |
| comments 대표견만 로드(#11 twin) | `8b4827cb` |
| comments 트리 루트 keyset+대댓글 배치·CursorPage(#6) | `ca8816ed` |
| 좋아요 카운터 중복 제거(#15) | `5cd35f57` |
| posts 목록 is_liked 계산 | `ad8ac277` |
| comments 트리 테스트 보강 | `8d5d5208` |
| comments 가시성 술어 공용화(리뷰) | `c777ae6e` |

> 백로그 번호(#n)는 [`backlog.md`](backlog.md) 기준.
