# 리팩토링 백로그 (Refactoring Backlog)

> 도메인 재건(Construction)이 소비하는 작업 소스. 각 항목의 **#번호**를
> [`00`](00-operating-envelope-and-scope.md)·[`ROADMAP`](ROADMAP.md)·[`adr/`](adr/)·커밋이 참조한다.
> **진행 상태는 [ROADMAP](ROADMAP.md)** 에서 추적하고, 여기서는 *항목·근거·수정 방향*을 담는다.
> (최초 인벤토리: 2026-06-06, `main` 기준 코드 분석.)

---

## P0 — 버그 (데이터 정합성·보안)

### 1. `cleanup_expired_signup_images` — 스토리지 삭제 실패해도 DB 레코드 삭제됨

**파일**: `app/domain/media/service.py`

```python
for img in rows:
    try:
        await asyncio.to_thread(storage_delete, img.file_key)
    except Exception as e:
        failed_file_keys.append(img.file_key)
    await MediaModel.delete_image_record(img, db=db)  # ← 실패해도 항상 실행됨
```

`storage_delete`가 예외를 던져도 `delete_image_record`가 호출된다. S3/로컬에는 파일이 남고 DB 레코드는 사라져 영구적인 고아 파일이 생긴다. `failed_file_keys`를 반환하지만 재시도 메커니즘이 없어 사실상 데이터 소실이다.

**수정**: 스토리지 삭제 실패 시 `continue` 추가.

```python
for img in rows:
    try:
        await asyncio.to_thread(storage_delete, img.file_key)
    except Exception as e:
        logger.warning(...)
        failed_file_keys.append(img.file_key)
        continue  # DB 삭제 건너뜀
    await MediaModel.delete_image_record(img, db=db)
```

---

### 2. View Flush 분산 락 — CAS 없는 삭제

**파일**: `app/domain/posts/services/post_service.py`

```python
finally:
    if lock_acquired:
        await redis_client.delete(VIEW_FLUSH_LOCK_KEY)  # ← CAS 없음
```

락 TTL(`VIEW_FLUSH_LOCK_SECONDS`)이 만료된 후 다른 워커가 락을 획득했을 때, 첫 번째 워커의 `finally`가 새 워커의 락을 삭제한다. 결과적으로 두 워커가 동시에 flush를 실행해 `view_count`가 두 배 증가할 수 있다.

`media/service.py`의 `_release_job_lock`은 Lua CAS로 정확히 구현했으나 여기서만 빠져 있다.

**수정**: `_release_job_lock` 패턴 동일 적용 — `SET NX`로 `lock_value`를 저장하고 Lua CAS로 해제.

---

### 3. `AuthService.signup` — TOCTOU 경쟁 조건

**파일**: `app/domain/auth/service.py`

```python
if await UsersModel.email_exists(data.email, db=db):
    raise EmailAlreadyExistsException()
if await UsersModel.nickname_exists(data.nickname, db=db):
    raise NicknameAlreadyExistsException()
# ...
created = await UsersModel.create_user(...)  # ← 여기서 IntegrityError 발생 가능
```

두 체크 사이 또는 체크-생성 사이에 동일 이메일/닉네임으로 동시 요청이 들어오면 `db.flush()`에서 `IntegrityError(23505)`가 발생한다. 현재 이를 잡는 코드가 없어 500 에러로 터진다.

**수정**: `create_user` / `db.flush()`를 `try/except IntegrityError`로 감싸고 `pgcode == "23505"` 시 적절한 예외로 변환.

---

### 4. ILIKE 패턴에 `%`, `_` 이스케이프 미적용

**파일**: `app/domain/posts/repository.py`

```python
pattern = f"%{token}%"
Post.title.ilike(pattern)
```

사용자가 `50%` 또는 `_abc_`를 검색하면 SQLAlchemy가 파라미터화하지만 ILIKE 와일드카드 문자는 이스케이프되지 않는다. `50%`는 "50으로 시작하는 모든 것"으로 동작해 의도와 다른 검색 결과가 반환된다.

**수정**:

```python
token_esc = token.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
pattern = f"%{token_esc}%"
Post.title.ilike(pattern, escape="\\")
```

---

## P1 — 높은 심각도 (잘못된 동작, 데이터 노출 위험)

### 5. `AdminService.get_reported_posts` — 메모리 기반 페이지네이션 버그

**파일**: `app/domain/admin/service.py`

```python
fetch_size = min(500, max(size * 2, page * size))
posts, total_posts = await PostsModel.get_reported_posts(page=1, size=fetch_size, db=db)
# ...
total = total_posts + total_comments  # DB에서 정확한 값
items = merged[start : start + size]  # 메모리에서 500건 범위 내 슬라이스
```

`total`은 DB에서 정확히 반환되지만 `items`는 최대 500+500건만 메모리에 올린 뒤 자른다. 예) size=20, 신고된 게시글 300건: page 26부터(`start=500`) 신고 데이터가 없어지고 API는 `total=300`을 보고하면서 빈 items를 반환한다.

**수정**: DB 쪽에서 합산 정렬 쿼리를 구성하거나(UNION), 게시글·댓글 신고 엔드포인트를 분리.

> **수정 완료(reports/admin 도메인)**: 두 테이블을 DB-side `UNION ALL`로 합쳐 `report_count DESC, created_at DESC, id DESC` 단일 정렬·`LIMIT/OFFSET` + `count(*) over union`으로 페이지·total을 DB에서 산출(`AdminReportsModel.page_reported_targets`). 페이지의 `(type, id)`만 받아 id 배치로 하이드레이션해 UNION 순서 그대로 조립 — 인메모리 병합·500 cap·정렬 축 불일치 제거. offset+total은 저트래픽 admin 전제에서 의도적으로 유지([ADR 0012](adr/0012-admin-report-feed-pagination.md)). 부수: `reports(target_type, target_id) WHERE deleted_at IS NULL` 부분 인덱스(마이그레이션 011)로 집계 스캔 제거, 저자 없는(SET NULL) 신고 콘텐츠를 total·목록에서 일치 제외.

---

### 6. 댓글 트리 500건 하드 리밋 + 인메모리 페이지네이션

**파일**: `app/domain/comments/model.py`, `app/domain/comments/service.py`

```python
# model.py
if fetch_all_for_tree:
    stmt = stmt.limit(500)  # ← 초과 시 무음 소실

# service.py
roots = _build_comment_tree(comments, ...)
total_count = len(roots)   # DB 실제 수가 아니라 메모리 루트 수
result = roots[start:end]
```

인기 게시글에 댓글 500건 초과 시: 500건만 로드해 트리를 구성하므로 나머지는 무음으로 사라진다. `total_count`도 실제 DB 수가 아니라 잘린 후 루트 수다. 5페이지 이상에서 실제로 존재하는 댓글이 보이지 않을 수 있다.

---

### 7. `get_current_user` — 매 요청마다 DB 조회 (인증 미캐싱)

**파일**: `app/api/dependencies/auth.py`

```python
async with db.begin():
    user = await UsersModel.get_user_by_id(user_id, db=db)  # JOIN 포함, 매 요청 실행
```

모든 인증된 요청이 `users` 테이블(+ profile_image JOIN)을 조회한다. `refresh_tokens`에는 `user:status:{user_id}` 캐시(TTL 240초)가 있는데 `get_current_user`에는 적용하지 않았다. 고트래픽 시 `users` 테이블이 핫스팟이 된다.

---

### 8. `suspend_user` — 기존 Access Token 즉시 무효화 안 됨

**파일**: `app/domain/admin/service.py`

`suspend_user`는 `invalidate_user_status_cache`만 호출한다. 정지된 유저의 Access Token은 최대 30분(`ACCESS_TOKEN_EXPIRE_SECONDS=1800`)간 유효하다. `revoke_refresh_for_user`가 존재하지만 `suspend_user`에서 호출되지 않는다.

**수정**: `suspend_user` 내에서 `AuthService.revoke_refresh_for_user` 호출 추가.

---

### 9. bcrypt 이중 실행 — pepper 기본값이 빈 문자열일 때

**파일**: `app/core/security.py`

```python
async def verify_password_with_legacy_fallback(plain: str, hashed_password: str) -> bool:
    if await verify_password(password_with_pepper(plain), hashed_password):
        return True
    return await verify_password(plain, hashed_password)
```

`PASSWORD_PEPPER`가 비어 있으면(기본값 `""`) `password_with_pepper(plain)`은 `plain`과 동일하다. 즉 첫 번째 시도가 실패하면 동일한 값으로 두 번 bcrypt를 실행한다. bcrypt는 의도적으로 느리므로 로그인 레이턴시가 두 배가 된다.

**수정**: `PASSWORD_PEPPER`가 비어 있으면 폴백 없이 단일 검증.

```python
async def verify_password_with_legacy_fallback(plain: str, hashed_password: str) -> bool:
    if settings.PASSWORD_PEPPER:
        if await verify_password(password_with_pepper(plain), hashed_password):
            return True
    return await verify_password(plain, hashed_password)
```

---

## P2 — 중간 심각도 (성능, 코드 구조)

### 10. `get_posts_count` — 커서 페이지네이션과 `COUNT(*)` 비용

**파일**: `app/domain/posts/services/post_service.py`

```python
total = await PostsModel.get_posts_count(db=db, search_q=search_q, ...)
```

커서 기반 페이지네이션에서 `total`은 의미가 제한적이다. 검색어가 있으면 `COUNT(*)`에도 `pg_trgm` 검색 필터가 적용돼 비용이 높다. 요청마다 목록 쿼리 + COUNT 쿼리 두 번을 실행한다.

---

### 11. `get_all_posts` — Dog 관계 과잉 로드

**파일**: `app/domain/posts/repository.py`

```python
joinedload(Post.user).selectinload(User.dogs).joinedload(DogProfile.profile_image),
```

게시글 목록에서 작성자의 모든 강아지 프로필 + 이미지를 전체 로드한다. 대표견 1마리만 필요한데 소유자별 강아지 전체를 가져온다. `User.representative_dog` 프로퍼티가 있어도 이미 모든 강아지가 메모리에 올라온다.

> **심화(감사 중 발견)**: 단순 과잉 로드에 더해, `dogs.and_(is_representative)` 필터 로드는 `User.dogs` **컬렉션 자체를 대표견 1마리로 truncate**해 세션에 캐시하는 **부분 컬렉션 트랩**이 있다 — 전체 `dogs`를 기대하는 프로필 경로가 조용히 누락된 데이터를 본다.
>
> **수정 방향**: 대표견을 `dogs`와 분리된 전용 `representative_dog` 뷰 관계로 로드(트랩 소멸)하고, 소유자당 대표견 1마리 불변식을 부분 유니크 인덱스로 DB 승격. → posts(#11)·comments(#11 twin)·dogs 도메인에서 구현. 근거: [ADR 0011](adr/0011-representative-dog-view-relationship.md).

---

### 12. `sync_post_hashtags` — 5회 왕복 쿼리

**파일**: `app/domain/posts/repository.py`

게시글 생성/수정마다 다음 5번의 DB 왕복이 발생한다:
1. `DELETE post_hashtags WHERE post_id = ...`
2. `SELECT Hashtag WHERE name IN (...)`
3. `INSERT INTO hashtags ... ON CONFLICT DO NOTHING`
4. `SELECT Hashtag WHERE name IN (...)` (재조회)
5. `INSERT INTO post_hashtags ... ON CONFLICT DO NOTHING`

3번에서 `RETURNING`을 사용하면 4번 재조회를 제거할 수 있다.

---

### 13. `UserBlock` — 복합 PK + UniqueConstraint 중복

**파일**: `app/domain/users/model.py`

```python
class UserBlock(Base):
    __table_args__ = (
        UniqueConstraint("blocker_id", "blocked_id", name="uq_user_blocks_blocker_blocked"),
    )
    blocker_id: Mapped[UUID] = mapped_column(..., primary_key=True)
    blocked_id: Mapped[UUID] = mapped_column(..., primary_key=True)
```

복합 PK가 이미 유니크를 보장하므로 `UniqueConstraint`는 중복된 인덱스다. 불필요한 인덱스를 마이그레이션으로 제거.

> **수정 완료(정리 도메인)**: `UserBlock.__table_args__`의 중복 `UniqueConstraint` 제거(복합 PK가 유니크 보장, 형제 `PostLike`·`CommentLike`와 동형). 마이그레이션 `012`에서 `drop_constraint("uq_user_blocks_blocker_blocked")`(head `011`에서 체인). block_user는 plain INSERT라 이 제약을 참조하는 upsert 없음을 확인.

---

### 14. `Settings` — pydantic-settings 미사용

**파일**: `app/core/config.py`

`Settings`는 일반 Python 클래스다:
- 환경 변수 타입 불일치 시 `ValueError` 발생 (컨텍스트 없음)
- 테스트에서 환경 변수 모킹이 어려움 (클래스 변수가 임포트 시 확정됨)
- `validate_settings_for_environment`가 `JWT_SECRET_KEY`만 검증하고 `DB_PASSWORD`, `COOKIE_SECURE` 등은 미검증

프로덕션 환경 추가 검증 권장:
- `COOKIE_SECURE=true`
- `TRUSTED_HOSTS != ["*"]`
- `DB_PASSWORD` 비어있지 않음
- `CORS_ORIGINS`에 `localhost` 미포함

---

### 15. `CommentLikesModel`과 `CommentsModel` 메서드 중복

**파일**: `app/domain/comments/model.py`

`CommentsModel.increment_like_count` / `decrement_like_count`와 `CommentLikesModel.increment_like_count` / `decrement_like_count`가 동일한 쿼리로 중복 정의되어 있다. `LikeService`에서 `CommentLikesModel` 버전을 사용해 일관성도 없다.

---

### 16. Chat `list_recent_rooms` — 미읽음 카운트 전체 테이블 스캔

**파일**: `app/domain/chat/service.py`

```python
unread = (
    select(...)
    .where(
        ChatMessage.is_read.is_(False),
        ChatMessage.sender_id != user_id,
    )
    .group_by(ChatMessage.room_id)
    .subquery()
)
```

`WHERE ChatMessage.room_id IN (user's rooms)` 조건 없이 전체 `chat_messages` 테이블을 스캔해 GROUP BY한다. 메시지가 쌓일수록 성능이 저하된다.

> **수정 완료(chat 도메인)**: `unread`·`last_msg` 두 서브쿼리를 `room_id IN (내 방)` 세미조인으로 한정하고, 미읽음 부분 인덱스 `ix_chat_messages_unread(room_id) WHERE is_read IS false`를 추가(술어를 쿼리의 `.is_(False)`와 동형으로 맞춰 플래너 매칭 보장). 실시간 전달 설계는 [ADR 0009](adr/0009-realtime-delivery.md).

---

## P3 — 낮은 심각도 (코드 품질, 마이너)

### 17. `VIEW_BUFFER_KEY` 리터럴 `{v}` — Redis Cluster 해시 태그 미작동

**파일**: `app/domain/posts/services/post_service.py`

```python
VIEW_BUFFER_KEY = "views:{v}:buffer"
VIEW_FLUSH_LOCK_KEY = "views:{v}:flush:lock"
```

Redis Cluster 해시 슬롯 제어를 위한 `{}` 문법처럼 보이지만 Python 포맷 스트링이 아니라 리터럴이다. `view:post:{post_id}:viewer:{viewer_key}` 키들과 다른 슬롯에 배치된다. Redis Cluster 도입 시 문제가 된다.

---

### 18. `_PG_UUID` 중복 정의

`app/domain/users/model.py`, `app/domain/comments/model.py`, `app/domain/posts/model.py`에 각각 `_PG_UUID = PG_UUID(as_uuid=True)`가 별도로 정의된다. `app/db/base_class.py`에 한 번만 정의하고 임포트.

> **수정 완료(정리 도메인)**: 실제로는 7개 모델 파일(`users·comments·posts·notifications·media·likes·chat`)에 복제돼 있었다. `base_class.PG_UUID` 하나로 정의하고 전부 임포트로 교체 — `as_uuid=True` 불변식을 한 곳에서 보장(동일 타입 인스턴스 공유는 SQLAlchemy에서 안전).

---

### 19. `chat/service.py:get_room_peer_info` — 채팅방 중복 조회

```python
rres = await db.execute(select(ChatRoom)...)  # 1차 조회 (멤버 확인)
# ...
stmt = select(...).where(ChatRoom.id == room_id)  # 2차 조회 (데이터)
res = await db.execute(stmt)
```

같은 `room_id`로 두 번 쿼리한다. 멤버 권한 확인과 데이터 조회를 단일 쿼리로 합칠 수 있다.

> **수정 완료(chat 도메인)**: 멤버십을 projection `WHERE`에 접어넣고(`or_(user1==me, user2==me)`) `one_or_none()→None→403`으로 1쿼리화. `list_room_messages`·`mark_room_read`의 가드는 서로 다른 연산 앞의 authz 단계라 403 시맨틱상 유지하되 전체 엔티티 대신 두 컬럼만 로드하도록 좁힘. 별건: 감사 중 `notifications` 목록이 offset+`count(*)`로 ADR 0002를 벗어나 있어 comments와 동형 id keyset(CursorPage)으로 정합화하고 인덱스 드리프트(004↔ORM)를 해소.

---

### 20. `from __future__ import annotations` 불일치

일부 파일(`auth/service.py`, `notifications/service.py` 등)에는 있고 다른 파일(`users/model.py`, `comments/model.py` 등)에는 없다. Python 3.11+에서는 대부분 불필요하지만 일관성 부족이다.

> **수정 완료(정리 도메인)**: 35개 파일에만 있던 future import를 **제거로 통일**(88개가 이미 부재, `target-version=py311`, `TYPE_CHECKING` 사용처 없음). 제거로 드러난 미따옴표 forward-ref(`posts.model`의 `Mapped[list["Post"]]`·`Mapped[list["PostImage"]]`, `users.schema`의 self 반환 애노테이션)는 따옴표로 명시. 전 모듈 import 스모크로 NameError 부재 확인.

---

### 21. 댓글 대댓글 배치 로드에 상한 없음 (대댓글 페이지네이션 부재)

**파일**: `app/domain/comments/model.py` (`get_replies_for_roots`)

#6 수정으로 루트는 keyset 페이지네이션되지만, 한 페이지의 루트들에 달린 대댓글은 `parent_id IN (root_ids)` 배치 1쿼리로 **전부** 로드한다(부모별 상한 없음). 인기글의 한 루트에 대댓글이 수천 건 달리면 한 응답이 그만큼의 행 + 작성자 eager load를 끌어온다. 옛 코드는 오히려 500 cap으로 대댓글을 무음 절단했으므로 정확성은 개선됐지만, 운영 봉투(인기 스레드)에선 상한이 필요하다.

**수정**: 루트당 대댓글 preview(top-N) + 별도 "대댓글 더보기" keyset 엔드포인트로 분리. 기능 확장이라 #6과 별개 단위로 다룬다.

---

## 2차 전면 감사 (2026-07-13) — #22~#36

> Construction/Transition 완료 후 전체 코드 재감사에서 나온 항목. 기준은 [`00`](00-operating-envelope-and-scope.md)의
> 운영 봉투와 "정당화된 복잡도" 원칙. 진행 순서는 [ROADMAP](ROADMAP.md) 2차 감사 섹션.

### 22. Celery 파이프라인이 실경로에 미배선 (장식화) — P1

**파일**: `app/core/celery.py`, `app/worker/*`, `app/domain/notifications/router.py`

프로덕션 코드에서 태스크를 enqueue하는 곳이 `POST /notifications/{id}/dispatch`(사용자가 자기 알림 재전달을 큐잉하는 합성 API) 하나뿐이다. 실제 알림 배송은 서비스에서 인라인 Redis publish + fire-and-forget SNS(`to_thread`)로 수행되어, ADR 0009의 "Celery 오프로드"와 실코드가 불일치한다. 현 상태는 스택 전체(celery.py·async_bridge·worker/·큐 라우팅·설정 13개)가 사실상 전시물이다.

**수정 방향**: (a) SNS publish·오프라인 배송을 Celery로 실배선하고 dispatch 엔드포인트 제거, 또는 (b) Celery 전체 제거 + "쓰기 초당 수십 규모에선 인라인 발행으로 충분"을 ADR로 기록. 채택안은 착수 시 결정.

> **수정 완료 — (a) 실배선 채택**: 알림 생성 시 `publish_after_commit`이 SNS 배송을
> `deliver_notification_sns`(high_priority)로 enqueue(비동기 컨텍스트 블록 방지 위해 `to_thread`,
> 결정적 멱등키 `sns:{notification_id}`). `CELERY_ENABLED=false`·브로커 장애는 기존 인라인
> fire-and-forget으로 폴백. 워커 잡은 DB 행에서 페이로드 재구성, SNS client 프로세스당 재사용,
> **publish 성공 후에만 멱등 마킹**(#34 첫 항목 선반영 — 선마킹이면 실패 재시도가 skip으로 유실).
> 합성 dispatch 엔드포인트·미배선 `mark_notifications_read_job`·구 재전달 잡 제거. ADR 0009 갱신.

---

### 23. SSE 알림 pubsub가 공유 풀 연결 점유 (풀 고갈 → 전면 fail-open) — P1

**파일**: `app/domain/notifications/service.py` (`sse_subscribe`)

SSE 연결마다 `app.state.redis` 공유 풀(128)에서 pubsub 연결을 점유한다. 동시 SSE가 풀 한도에 근접하면 rate limit·인증 상태 캐시·조회수 버퍼가 연결 고갈로 일제히 fail-open된다(수천 DAU 전제에서 현실적). chat은 동일 문제를 단일 채널 + 인스턴스당 전용 구독 1개 + 로컬 팬아웃으로 이미 풀었다 — 같은 문제를 두 패턴으로 유지 중.

**수정 방향**: 알림도 chat 동형으로 통일(인스턴스당 전용 연결 구독 1개 → 로컬 SSE 클라이언트 팬아웃). ADR 0009 갱신.

---

### 24. 업로드 경로 2벌 공존 (direct multipart + presigned) — P2

**파일**: `app/domain/media/router.py`, `app/domain/media/image_policy.py`

ADR 0010이 "S3 단일 경로"를 선언했지만, direct 업로드(`/media/images`, `/media/images/signup`)와 presigned 3단(presign→S3 직접→confirm)이 인증/비인증 각각 풀셋으로 공존한다(엔드포인트 6개, 파이프라인 2벌). direct는 최대 20MB를 서버 메모리로 태운다.

**수정 방향**: presigned로 단일화하고 direct 제거(FE 전환 포함). direct를 유지한다면 사유를 ADR 0010에 추가.

---

### 25. 조회수 기록 경로 2벌 (GET 상세 자동 증가 + POST /view) — P2

**파일**: `app/domain/posts/routers/post_router.py`

`GET /posts/{id}`가 조회수를 자동 증가시키는데 `POST /posts/{id}/view`도 따로 있다. dedup 키가 이중 집계는 막지만 동일 기능 API가 둘.

**수정 방향**: FE 사용 경로 확인 후 한쪽 제거.

---

### 26. ORM 클래스 소속 도메인 불일치 — P3

**파일**: `app/domain/users/model.py` 외

`Report`·`DogProfile` ORM이 `users/model.py`에 정의되어 있고 reports/·dogs/ 도메인엔 쿼리 클래스만 있다. 또 posts만 `repository.py + services/ + routers/` 분리이고 나머지 도메인은 `model.py`가 ORM+쿼리 이중 역할.

**수정 방향**: ORM 배치 규약을 하나로 통일(각 도메인 model.py 복귀 또는 `app/db/models/` 집결). 대규모 이동이라 순서 마지막.

---

### 27. 429 응답이 CORS·메트릭·접근로그 바깥에서 종료 — P1

**파일**: `app/main.py`(미들웨어 등록 순서), `app/core/middleware/rate_limit.py`

등록 순서상 RateLimit이 CORS/metrics/access_log보다 바깥 껍질이다. 브라우저 FE는 429를 CORS 에러로 수신해 `retry_after_seconds`를 읽지 못하고, 429가 RED 메트릭(`http_requests_total`)·접근로그에서 누락된다 — "rate limit 발동을 실측한다"(ADR 0006)와 모순.

**수정 방향**: RateLimit을 관측·CORS 미들웨어 안쪽으로 재배치(또는 `_send_429`에 CORS 헤더 부착). 순서 주석 갱신.

---

### 28. `get_client_identifier`가 X-Forwarded-For 무검증 신뢰 (조회수 조작 벡터) — P0

**파일**: `app/api/dependencies/client.py`

`ProxyHeadersMiddleware`가 신뢰 프록시 검증 후 `scope["client"]`를 갱신하는데, 이 함수는 원시 XFF 헤더를 우선한다. 요청마다 위조 XFF를 넣으면 viewer_key가 매번 달라져 조회수(→트렌딩 랭킹)를 무한 부풀릴 수 있고, signup 업로드 멱등 스코프도 위조된다.

**수정 방향**: 검증 완료 값(`request.client.host`)만 사용.

---

### 29. `record_post_view` 존재확인이 풀 eager-load + master 세션 — P1

**파일**: `app/domain/posts/services/post_service.py`, `post_router.py`

가장 뜨거운 쓰기 엔드포인트가 존재/가시성 확인용으로 상세 eager-load 4종(`get_post_by_id`)을 실행하고, 라우터가 master 세션을 준다. 조회 폭주 1순위 봉투와 정면 배치.

**수정 방향**: `post_is_visible`(EXISTS 1쿼리) + slave 세션으로 교체.

---

### 30. chat pubsub 리스너 재연결 부재 — P1

**파일**: `app/domain/chat/pubsub.py` (`run_chat_subscribe_listener`)

기동 시 `ping()` 실패나 루프 밖 예외 1회면 리스너 태스크가 조용히 종료되고, 해당 인스턴스의 크로스 인스턴스 DM 수신이 프로세스 재시작까지 죽는다(내부 `get_message` 예외만 재시도).

**수정 방향**: 백오프 재연결 루프로 감싸기 — 멀티 인스턴스 3~10대·99.9% 전제에서 정당한 복잡도.

---

### 31. presign 남용 방어·pending/ 객체 GC 부재 — P1

**파일**: `app/core/middleware/rate_limit.py`, `app/infra/storage.py`, ADR 0010

signup 전용 한도(10/시간)가 `/media/images/signup` 정확 일치라 presign/confirm 경로엔 미적용(글로벌 100/분만). confirm되지 않은 `pending/` S3 객체는 DB 행이 없어 어떤 sweeper도 지우지 못한다 → 비로그인 IP당 분당 100회 presign×10MB 업로드가 영구 잔존 가능.

**수정 방향**: presign·confirm 경로를 signup 한도에 포함 + `pending/` prefix에 S3 lifecycle(예: 1일 만료)을 infra 요건으로 ADR 0010에 명시.

---

### 32. WebSocket DM에 rate limit·차단 검사 부재 — P1

**파일**: `app/core/middleware/rate_limit.py`(ws scope 통과), `app/domain/chat/service.py`

rate limit 미들웨어는 `scope["type"] != "http"`를 그대로 통과시켜 WS 접속 1회로 무제한 DB 쓰기+팬아웃이 가능하다. `send_dm_from_ws`는 UserBlock을 확인하지 않아 차단한 상대에게서 DM이 온다.

**수정 방향**: WS 수신 루프에 유저 단위 한도(Redis fixed-window 재사용) + 차단 관계 검사 추가.

---

### 33. 트렌딩 캐시 wait-timeout이 빈 목록 반환 — P2

**파일**: `app/infra/cache.py`, `trending_post_service.py` (`on_wait_timeout=[]`)

락 경합으로 2초 대기 후 타임아웃되면 사용자에게 빈 인기글이 내려간다. 가용성 우선이라 해도 "틀린 데이터"보다 loader(DB) 폴백이 봉투에 부합(대기자 수만큼의 쿼리는 감내 가능).

**수정 방향**: timeout 시 loader 폴백으로 변경, 또는 현행 유지 근거를 ADR 0004에 명시.

---

### 34. 소품 모음 (정확성·표기 드리프트) — P2

- `worker/jobs/notification_delivery.py`: idempotency 키를 publish **전에** 선점 → publish 실패 재시도가 멱등 skip으로 유실. 성공 후 마킹으로 순서 교체.
- `notifications/service.py`: SNS publish마다 boto3 client 신규 생성 + `create_task` 참조 미보관(GC 유실 가능). 모듈 client 재사용 + task 참조 보관.
- `rate_limit.py` `_SKIP_PATHS`의 `"/health"`가 실경로 `/v1/health`와 불일치.
- `docker-compose.yml` `VIEW_CACHE_TTL_SECONDS: "0"` — dedup 끔 의도로 보이나 코드는 0→3600 폴백이라 로컬 조회수가 안 오름. 의도 정렬.
- `docker-compose.yml` 폐기 설정 `STORAGE_BACKEND` 잔재 제거.

---

### 35. 죽은 코드 일괄 — P3

- `core/exception_handlers.py`: MySQL 잔재(errno 1062/1451/1452, `"key 'email'"` 메시지 파싱) — PostgreSQL 전용 스택에서 도달 불가. pgcode·constraint_name 기반으로 정리.
- `db/base_class.py`: `Base.update()`·`soft_delete()` 호출처 없음.
- `likes/service.py`: `except IntegrityError` 분기 — create가 `ON CONFLICT DO NOTHING`이라 도달 불가(도달 시 별도 커넥션까지 여는 무거운 처리).
- `comments/model.py`: `CommentsModel.get_liked_comment_ids_for_user` 단순 위임 잔재.
- `posts/services/post_service.py`: `_VIEW_REDIS_EX_SECONDS <= 0` 분기 도달 불가(폴백이 3600 보장).
- `api/dependencies/auth.py`: auth 서비스의 `_`프라이빗 헬퍼 3개 크로스 모듈 임포트 → 공용 모듈로 승격.

---

### 36. 제품 결정 문서화 — P3

코드 수정이 아니라 "의도"를 남기는 항목.

- refresh 토큰 유저당 단일 키 = 단일 세션 정책(두 번째 기기 로그인 시 첫 기기 refresh 무효) 명시.
- WS 인증 토큰 쿼리스트링(`?token=`) 노출 트레이드오프.
- 트렌딩 `window_hours` 1~48 클라이언트 제어 → 캐시 키 분화. FE 사용값(24) 고정 검토.
- `get_current_user_optional`은 status 캐시 미적용(필수 인증 경로와 비대칭) — 의도 확인.
- 고아 해시태그 행 미GC(무해) 인지.

---

## 요약표

| 우선순위 | # | 항목 | 파일 |
|---------|---|------|------|
| **P0** | 1 | 스토리지 삭제 실패 시 DB 레코드도 삭제 | `app/domain/media/service.py` |
| **P0** | 2 | View flush 락 CAS 미적용 | `app/domain/posts/services/post_service.py` |
| **P0** | 3 | 회원가입 이메일/닉네임 중복 IntegrityError 미처리 | `app/domain/auth/service.py` |
| **P0** | 4 | ILIKE `%`/`_` 이스케이프 누락 | `app/domain/posts/repository.py` |
| **P1** | 5 | Admin 신고 목록 메모리 페이지네이션 버그 | `app/domain/admin/service.py` |
| **P1** | 6 | 댓글 트리 500건 하드 리밋 + 인메모리 페이지네이션 | `app/domain/comments/model.py`, `service.py` |
| **P1** | 7 | get_current_user 매 요청 DB 조회 미캐싱 | `app/api/dependencies/auth.py` |
| **P1** | 8 | 정지 시 Access Token 미즉시 무효화 | `app/domain/admin/service.py` |
| **P1** | 9 | bcrypt 이중 실행 (pepper 기본값 `""`) | `app/core/security.py` |
| **P2** | 10 | 커서 페이지네이션 + COUNT(*) 중복 비용 | `app/domain/posts/services/post_service.py` |
| **P2** | 11 | 게시글 목록에서 Dog 전체 로드 | `app/domain/posts/repository.py` |
| **P2** | 12 | `sync_post_hashtags` 5회 왕복 | `app/domain/posts/repository.py` |
| **P2** | 13 | `UserBlock` 중복 인덱스 | `app/domain/users/model.py` |
| **P2** | 14 | `Settings` 비pydantic + 검증 범위 협소 | `app/core/config.py` |
| **P2** | 15 | `CommentLikesModel` 메서드 중복 | `app/domain/comments/model.py` |
| **P2** | 16 | 미읽음 카운트 전체 테이블 스캔 | `app/domain/chat/service.py` |
| **P3** | 17 | `{v}` 리터럴 Redis 해시 태그 미작동 | `app/domain/posts/services/post_service.py` |
| **P3** | 18 | `_PG_UUID` 중복 정의 | `users/model.py`, `comments/model.py`, `posts/model.py` |
| **P3** | 19 | `get_room_peer_info` 채팅방 중복 조회 | `app/domain/chat/service.py` |
| **P3** | 20 | `from __future__ import annotations` 불일치 | 전역 |
| **P2** | 21 | 대댓글 배치 로드 상한 없음(대댓글 페이지네이션 부재) | `app/domain/comments/model.py` |
| **P1** | 22 | Celery 실경로 미배선(장식화) | `app/core/celery.py`, `app/worker/*` |
| **P1** | 23 | SSE pubsub 공유 풀 점유 → 풀 고갈 시 전면 fail-open | `app/domain/notifications/service.py` |
| **P2** | 24 | 업로드 경로 2벌(direct + presigned) | `app/domain/media/router.py` |
| **P2** | 25 | 조회수 기록 경로 2벌(GET 자동 + POST /view) | `app/domain/posts/routers/post_router.py` |
| **P3** | 26 | ORM 클래스 소속 도메인 불일치 | `app/domain/users/model.py` 외 |
| **P1** | 27 | 429가 CORS·메트릭·접근로그 바깥에서 종료 | `app/main.py` |
| **P0** | 28 | XFF 무검증 신뢰 → 조회수 조작 벡터 | `app/api/dependencies/client.py` |
| **P1** | 29 | record_post_view 풀 eager-load + master | `app/domain/posts/services/post_service.py` |
| **P1** | 30 | chat pubsub 리스너 재연결 부재 | `app/domain/chat/pubsub.py` |
| **P1** | 31 | presign 남용 방어·pending/ GC 부재 | `rate_limit.py`, `storage.py`, ADR 0010 |
| **P1** | 32 | WS DM rate limit·차단 검사 부재 | `rate_limit.py`, `chat/service.py` |
| **P2** | 33 | 트렌딩 wait-timeout 빈 목록 반환 | `app/infra/cache.py` |
| **P2** | 34 | 소품 모음(멱등 순서·SNS client·경로 표기 등) | 여러 파일 |
| **P3** | 35 | 죽은 코드 일괄(MySQL 잔재 등) | 여러 파일 |
| **P3** | 36 | 제품 결정 문서화(단일 세션 refresh 등) | docs |
