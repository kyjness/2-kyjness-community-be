# ROADMAP — 재건 진행 트래커 (living)

> 세션 인수인계·진행 추적용. 상세 근거는 각 **커밋 메시지**와 [`adr/`](adr/)에.
> 전제·범위는 [`00`](00-operating-envelope-and-scope.md), 횡단 결정은 [`01`](01-architecture.md).

## 단계
- [x] **Inception** — 운영 봉투·범위 (`00`)
- [x] **Elaboration** — 횡단 결정 (`01`) + ADR 0001~0006 + `/adr` 커맨드
- [x] **Construction** — 도메인 재건 (아래) **완료**
- [ ] **Transition** — 배포·모니터링 ← **다음**

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
  - [x] #11 심화(전용 `representative_dog` 뷰 관계로 `author.dogs` 부분 컬렉션 트랩 제거)는 **dogs 도메인에서 완료**
- [x] **comments / likes** — #11 twin 대표견만 로드 · #6 트리 페이지네이션 · #15 좋아요 카운터 중복
  - [x] #11 twin: 댓글 작성자 대표견만 로드(`_comment_author_loads`, posts와 동형)
  - [x] #6: 루트 keyset + 대댓글 부모별 배치 로드 + `CursorPage`(ADR 0002 결정을 코드로). 인메모리 슬라이스·500 cap·부정확 total 제거. 좋아요 keyset 드리프트 부정당 → 인기순(popular) 정렬 제거
  - [x] #15: 좋아요 카운터를 `CommentsModel`로 일원화(`CommentLikesModel` 중복 제거, posts 패턴 정합)
  - [x] 별건: 게시글 목록 `is_liked` 항상 False 버그 수정(배치 조회)
  - [x] 테스트: 트리 조립 단위(`test_comment_tree`) + keyset·삭제 시맨틱·is_liked·무이중집계 통합(`test_comments`·`test_posts`)
  - [x] 마감: `/code-review`(정리 3건 → 가시성 술어 공용화·중복 정렬 제거·is_liked 관용구 통일) · `/security-review`(취약점 0)
  - [~] 대댓글 자체 페이지네이션(루트당 preview + 더보기)은 기능 확장이라 backlog #21로 이연
- [x] **dogs** — #11 대표견 로딩 정리(전용 `representative_dog` 관계로 모델째 정리)
  - [x] #11 심화: 대표견을 `dogs`와 분리된 전용 `representative_dog` 뷰 관계(viewonly·uselist=False)로 로드해 부분 컬렉션 트랩(dogs 필터 로드가 컬렉션을 truncate) 제거. 프로퍼티→관계 단일 출처화, posts·comments 로더 전환
  - [x] 단일 대표견 불변식을 부분 유니크 인덱스(`owner_id WHERE is_representative`)로 DB 승격 + 마이그레이션(dedup 후 생성). upsert 대표 배정을 `set_representative`로 정규화(인덱스 안전). 근거 [ADR 0011](adr/0011-representative-dog-view-relationship.md)
  - [x] 테스트: 관계·인덱스 DDL·트랩 회귀 단위 + 프로필 dogs·대표견 공존·전환·인덱스 거부 통합
  - [x] 마감: `/code-review`(정확성 0 · 정리 1건 → 미사용 단일-행 CRUD 제거) · `/security-review`(취약점 0)
- [x] **chat / notifications** — #16 미읽음 스캔 · #19 방 중복조회 · 실시간(ADR 0009)
  - [x] #16: `list_recent_rooms`의 `unread`·`last_msg` 서브쿼리를 `room_id IN (내 방)`으로 스코프(전역 테이블 스캔 제거) + 미읽음 부분 인덱스(`ix_chat_messages_unread ... WHERE is_read IS false`). 마이그레이션 009
  - [x] #19: `get_room_peer_info` 방 이중 조회를 멤버십 접은 단일 쿼리로 병합. `list_room_messages`·`mark_room_read` 가드는 403 시맨틱 유지하며 2컬럼만 로드. `_is_room_member` 인라인화 제거
  - [x] 별건(감사): `notifications` 목록을 offset+`count(*)` → comments 동형 id keyset `CursorPage`로 정합화(ADR 0002). 인덱스 드리프트(004 `created_at` ↔ ORM) 해소, `(user_id, id DESC)`+미읽음 부분 인덱스. 마이그레이션 010
  - [x] **ADR 0009 실시간 전달** — 기구현된 WebSocket(chat)·SSE(notifications)×Redis Pub/Sub·fail-open·Celery 오프로드 설계를 소급 근거화
  - [x] 테스트: chat 미읽음 집계·멤버십 가드, notifications keyset·total 부재·전체읽음(무커버리지 해소)
  - [x] 마감: `/code-review`(정확성 2건 → 부분 인덱스 술어 정합·id keyset 전환) · `/security-review`(취약점 0)
- [x] **reports / admin** — #5 신고 목록 페이지네이션
  - [x] #5: 신고된 게시글·댓글을 DB-side `UNION ALL`로 합쳐 `report_count DESC, created_at DESC, id DESC` 단일 정렬·`LIMIT/OFFSET` + `count(*) over union`로 페이지·total을 DB 산출(`AdminReportsModel.page_reported_targets`). 페이지 `(type, id)`만 id 배치 하이드레이션해 UNION 순서 유지 — 인메모리 병합·500 cap·정렬 축 불일치 제거. 관리자 단독 offset 로더를 by-ids 로더로 대체(불필요 eager-load 축소)
  - [x] **ADR 0012 페이지네이션 전략** — offset+total을 저트래픽 admin 전제로 유지(공개 피드=cursor와 의도적 비대칭). ADR 0002의 인메모리 슬라이스 지적은 이행하되 메커니즘만 분기
  - [x] 부수: `reports(target_type, target_id) WHERE deleted_at IS NULL` 부분 인덱스(마이그레이션 011)로 집계 스캔 제거, 저자 없는(SET NULL) 신고 콘텐츠를 total·목록에서 일치 제외
  - [x] 테스트: UNION 페이지 컴파일·인덱스 존재·offset 로더 대체 단위 + 신고 피드 interleave·페이지 경계 무중복 통합(무커버리지 해소)
  - [x] 마감: `/code-review`(정확성 0·정리 0) · `/security-review`(취약점 0)
- [x] **정리(글로벌)** — #13 UserBlock 중복 인덱스 · #18 `_PG_UUID` 중복 · #20 `__future__` 일관성
  - [x] #13: `UserBlock`의 복합 PK와 중복인 `UniqueConstraint` 제거(형제 `PostLike`·`CommentLike`와 동형). 마이그레이션 `012`(head `011`에서 체인). block_user는 plain INSERT라 제약 참조 upsert 없음
  - [x] #18: 7개 모델 파일에 복제된 `_PG_UUID`를 `base_class.PG_UUID` 하나로 중앙화 — `as_uuid=True` 불변식 단일화(타입 인스턴스 공유는 SQLAlchemy에서 안전)
  - [x] #20: 35개 파일에만 있던 `from __future__ import annotations`를 **제거로 통일**(88개 이미 부재·`py311`·`TYPE_CHECKING` 없음). 드러난 미따옴표 forward-ref는 따옴표로 명시, 전 모듈 import 스모크로 NameError 부재 확인
  - [x] 마감: `/code-review`(정확성 0·정리 0 — 순수 정리라 복잡도 미추가) · ADR 불필요(load-bearing 결정 아님)

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
| comments/likes docs 반영 | `7b819295` |
| dogs 대표견 전용 뷰 관계·트랩 제거(#11) | `b2ba3000` |
| dogs 대표견 부분 유니크 인덱스·마이그레이션(#11) | `37f0b4db` |
| dogs 대표견 테스트 보강 | `a232b7e6` |
| dogs 미사용 단일-행 CRUD 제거(리뷰) | `d0a8bdbe` |
| chat 미읽음·최근메시지 스캔 방 스코프(#16) | `a3080e33` |
| chat get_room_peer_info 이중조회 병합(#19) | `065ab645` |
| notifications keyset CursorPage·인덱스(ADR 0002) | `97489a93` |
| ADR 0009 실시간 전달 근거화 | `b8052887` |
| chat/notifications 테스트 보강 | `f6661b31` |
| chat/notif 리뷰 반영(인덱스 술어·id keyset) | `d3a4a05e` |
| 신고 목록 DB-side UNION ALL 페이지네이션(#5) | `b357850c` |
| reports (target_type, target_id) 부분 인덱스 | `af448bba` |
| ADR 0012 관리자 신고 피드 페이지네이션 | `137d806b` |
| reports/admin 테스트 보강 | `9c25cf37` |
| user_blocks 중복 UNIQUE 제거·마이그레이션 012(#13) | `170a5817` |
| _PG_UUID base_class 공용 타입 중앙화(#18) | `e03876d5` |
| `__future__` annotations 제거로 통일(#20) | `818444a6` |

> 백로그 번호(#n)는 [`backlog.md`](backlog.md) 기준.
