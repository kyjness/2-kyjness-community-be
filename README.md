# PuppyTalk Backend

반려견 커뮤니티 서비스의 백엔드. **FastAPI(Full-Async)** 기반 REST API에 **WebSocket(DM)**·
**SSE(알림)** 를 더한 서버입니다.

이 저장소의 초점은 기능의 개수가 아니라 **"현실적 트래픽을 가정한 운영 등급 백엔드 설계"** 입니다.
초당 수백~수천 조회의 핫스팟, 멀티 인스턴스(3~10대), 무중단 배포를 **의도적으로 전제**하고,
그 전제로 정당화되는 복잡도만 남겼습니다. **정당화되지 않는 과잉은 의식적으로 걷어냈고**, 그 판단
근거를 전부 [ADR](docs/adr/)로 남겼습니다. → *"쓸 데와 안 쓸 데를 구분했다"* 가 핵심입니다.

**관련 링크**

- 프론트엔드: [PuppyTalk Frontend](https://github.com/kyjness/2-kyjness-community-fe)
- 인프라·배포: [PuppyTalk Infra](https://github.com/kyjness/2-kyjness-community-infra) (Terraform·ECS)

---

## 설계 논지 — 정당화된 복잡도

모든 설계 결정은 아래 **운영 봉투(Operating Envelope)** 위에서만 정당화됩니다. 봉투 밖은 과잉으로
판정해 채택하지 않았습니다. 전문은 [`docs/00-operating-envelope-and-scope.md`](docs/00-operating-envelope-and-scope.md).

| 축 | 전제 | 설계 함의 |
|----|------|----------|
| 핫스팟 | 인기글 1건에 **초당 수백~수천 조회** | 조회 경로 최적화 1순위 → 버퍼링·캐시 |
| 쓰기 | 신규 write는 초당 수십 | 강정합성 write는 정직하게 트랜잭션으로 |
| 서버 | 멀티 인스턴스 **3~10대** | 상태는 인스턴스 밖(Redis/DB), 로컬 상태 금지 |
| 배포 | 무중단 롤링 / 블루-그린 | 마이그레이션 하위호환, graceful shutdown, 헬스 분리 |
| 가용성 | **99.9%** | 외부 I/O는 fallback 우선(가용성 > 순간 정합성) |

**상한(넘으면 과잉으로 판정 — 일부러 하지 않은 것):** 멀티리전 · 금융권 강정합성 · 99.99%+ ·
초당 수만 건 *신규 write* · exactly-once 배송 · **AI 기능**(이번 범위에서 완전히 배제).

### 핵심 설계 결정 (ADR)

각 ADR은 *맥락 → 결정 → 트레이드오프 → 고려한 대안 → **일부러 하지 않은 것*** 순으로 남겼습니다.
마지막 "안 한 것"이 정당화된 복잡도의 핵심 전시물입니다.

| # | 결정 | 무엇을 안 했나 |
|---|------|----------------|
| [0001](docs/adr/0001-identifier-strategy.md) | 식별자 3분할 — 내부 PK `UUIDv7` / 공개 ID `Base62` / `ULID`(jti·request_id) | 순차 정수 PK 노출(열거·IDOR 표면) |
| [0002](docs/adr/0002-cursor-pagination.md) | 목록 = **keyset 커서**, `total` 제거 | offset 페이지네이션(deep-offset 스캔 비용) |
| [0003](docs/adr/0003-distributed-rate-limit.md) | 분산 Rate Limit — Redis **Lua fixed-window** + smart fail-open | 인스턴스 로컬 카운터(멀티 인스턴스에서 무의미) |
| [0004](docs/adr/0004-cache-strategy.md) | 캐시는 **읽기 폭주 경로만**, fail-open | 전방위 캐시(무효화 복잡도 대비 이득 없음) |
| [0005](docs/adr/0005-resilience-no-circuit-breaker.md) | 복원력 표준 = **fail-open** | Circuit Breaker(이 규모엔 상태 관리 부담이 과잉) |
| [0006](docs/adr/0006-observability.md) | 구조화 로그 + 얇은 **RED 메트릭** + 헬스 분리 | 분산 트레이싱 백엔드(request_id 상관으로 충분) |
| [0007](docs/adr/0007-view-count-buffering.md) | 조회수 = Redis **버퍼링 + 비동기 flush + 분산락(CAS)** | 매 조회 DB write(핫스팟 폭발) |
| [0008](docs/adr/0008-idempotency-keys.md) | POST 멱등성 — `X-Idempotency-Key` + 결과 캐시 | 중복 제출 방치 / 클라이언트 책임 전가 |
| [0009](docs/adr/0009-realtime-delivery.md) | 실시간 = WebSocket·SSE × **Redis Pub/Sub** fan-out, fail-open | 인스턴스 고정(sticky) 커넥션, 브로커 상시 의존 |
| [0010](docs/adr/0010-storage-backend-strategy.md) | 스토리지 = **S3 API 단일 경로** + dev/CI는 MinIO 패리티 | 로컬 디스크 백엔드(코드 분기·prod 불일치) |
| [0011](docs/adr/0011-representative-dog-view-relationship.md) | 대표견 = 전용 **뷰 관계** + 부분 유니크 인덱스 | 컬렉션 필터 로드(부분 컬렉션 트랩) |
| [0012](docs/adr/0012-admin-report-feed-pagination.md) | 관리자 신고 피드 = DB-side **UNION ALL** + offset·total 유지 | 커서 강제(0002의 *의도적 예외* — 저트래픽·변동 정렬·total 필요) |

> 횡단 관심사 종합은 [`docs/01-architecture.md`](docs/01-architecture.md), 리팩토링 진행·완료
> 이력은 [`docs/ROADMAP.md`](docs/ROADMAP.md), 버그·최적화 백로그와 각 항목 근거는
> [`docs/backlog.md`](docs/backlog.md)에 있습니다.

---

## 기술 스택

| 구분 | 기술 |
|------|------|
| 언어 / 패키지 | Python 3.11+ · uv |
| 프레임워크 | FastAPI · Starlette · Pydantic v2 |
| 서버 | Uvicorn (dev) · Gunicorn + Uvicorn worker (prod) |
| DB / ORM | PostgreSQL · psycopg3(async) · SQLAlchemy 2.x · Alembic |
| 캐시·메시징 | Redis (asyncio) |
| 비동기 작업(선택) | Celery — 알림 dispatch 등 큐 오프로딩 (`CELERY_ENABLED`) |
| 스토리지 | S3 단일 경로 — 실서비스 AWS S3 / dev·CI는 MinIO (boto3, `run_in_threadpool`) |
| 인증 | JWT(PyJWT) · bcrypt(+ pepper) |
| 실시간 | WebSocket(DM) · SSE(알림) × Redis Pub/Sub |
| 관측성 | Prometheus 메트릭 · 구조화 JSON 로그 · `/livez`·`/readyz` |
| 컨테이너·CI | Docker(멀티스테이지) · GitHub Actions · GHCR |

---

## 아키텍처 · 폴더 구조

`app/` 단일 패키지 아래에 공용 레이어(`api`·`common`·`core`·`db`·`infra`)와 기능 도메인(`domain/`)이
계층화돼 있습니다. 도메인은 **router → service → \[repository →] model → schema** 로 요청이 흐릅니다.
도메인 import는 항상 `app.domain.<영역>` 경로만 사용합니다.

```
app/
├── main.py            # FastAPI 앱, lifespan(설정 검증·조회수 flush·채팅 Redis 구독), 미들웨어·라우터
│                      # 헬스/관측성 엔드포인트: /v1/health · /livez · /readyz · /metrics
├── api/
│   ├── v1/            # /v1 prefix — 도메인 라우터 include + chat REST·WS
│   └── dependencies/  # 인증, DB 세션(get_master_db/get_slave_db), 권한, 쿼리 파싱
├── common/            # ApiResponse·ApiCode·Enum·validators·exceptions·로깅
├── core/
│   ├── config.py      # 설정 + 환경별 프로덕션 가드
│   ├── metrics.py     # 도메인 메트릭(rate-limit 429·캐시 hit/miss·조회수 flush)
│   └── middleware/    # RequestId · ProxyHeaders · RateLimit · GZip · AccessLog · Metrics · SecurityHeaders
├── db/                # SQLAlchemy Base·엔진·세션 (PG_UUID 등 공용 타입)
├── domain/            # admin · auth · chat · comments · dogs · likes · media
│                      # · notifications · posts · reports · users
├── infra/             # Redis(refresh·rate limit·채팅·캐시), storage(S3/MinIO)
└── worker/            # Celery 태스크(선택)

docs/                  # 00(봉투)·01(아키텍처)·adr/·ROADMAP·backlog
migrations/            # Alembic env.py + versions/
tests/                 # unit/(DB 불필요) · integration/(PostgreSQL + pg_trgm)
Dockerfile             # uv 멀티스테이지 · 비루트 · Gunicorn+Uvicorn
.github/workflows/ci.yml
```

---

## 기능 맵

| 기능 | 대표 엔드포인트 | 구현 위치 | 핵심 포인트 |
|------|----------------|-----------|-------------|
| 인증 | `/v1/auth/*` | `domain/auth` | JWT Access/Refresh. Refresh는 **HttpOnly 쿠키 + Redis RTR**, 동시 refresh는 **Lua CAS**로 1건만 성공. 로그아웃은 Access `jti` 블랙리스트. bcrypt는 스레드 오프로딩 + pepper ([0003](docs/adr/0003-distributed-rate-limit.md)) |
| 게시글 | `/v1/posts/*` | `domain/posts` | **커서** 무한 스크롤([0002](docs/adr/0002-cursor-pagination.md)), `q` 검색은 검증 후 **pg_trgm GIN** ILIKE(와일드카드 이스케이프), 해시태그 연동, 생성은 **멱등**([0008](docs/adr/0008-idempotency-keys.md)) |
| 조회수 | `POST /v1/posts/{id}/view` | `domain/posts` + Redis | `SET NX EX` 중복 방지 → Redis 버퍼 누적 → 백그라운드 **flush(분산락 CAS)** ([0007](docs/adr/0007-view-count-buffering.md)) |
| 인기 게시글 | `GET /v1/posts/trending` | `domain/posts` | time-decay 랭킹 + 3단 fallback. **차단 무관 랭킹 풀을 캐시**하고 차단은 요청별 오버레이(사용자별 캐시 폭발 회피) ([0004](docs/adr/0004-cache-strategy.md)) |
| 인기 해시태그 | `GET /v1/posts/trending-hashtags` | `domain/posts` | 빈도 집계 + Redis `TypeAdapter` 캐시(TTL·락), fail-open DB 폴백. 캐시 로직은 `infra/cache.py` 공용 헬퍼 ([0004](docs/adr/0004-cache-strategy.md)) |
| 댓글 | `/v1/comments/*` | `domain/comments` | 루트 **keyset** + 대댓글 배치 로드로 트리 조립(인메모리 슬라이스·하드리밋 제거) |
| 좋아요 | `/v1/likes/*` | `domain/likes` | `ON CONFLICT ... RETURNING` 멱등, `like_count` 동기화, `post_is_visible` 경량 EXISTS |
| 유저 | `/v1/users/*` | `domain/users` | 프로필·비밀번호·탈퇴·차단 목록/토글 |
| 강아지 | `/v1/dogs/*` | `domain/dogs` | 대표견은 전용 뷰 관계 + 부분 유니크 인덱스로 1마리 불변식 보장 ([0011](docs/adr/0011-representative-dog-view-relationship.md)) |
| 채팅(DM) | REST `/v1/chat/*` · WS `/v1/ws/chat` | `domain/chat` | WebSocket + **Redis Pub/Sub fan-out**(멀티 인스턴스), 짧은 트랜잭션으로 커넥션 풀 보호 ([0009](docs/adr/0009-realtime-delivery.md)) |
| 알림 | SSE `/v1/notifications/stream` | `domain/notifications` | 커밋 후 Redis 채널 발행 → **SSE** 스트림. Redis 미구성 시 스트림 503, DB 기록은 유지 |
| 이미지 업로드 | `/v1/media/*` | `domain/media` + `infra/storage` | 선업로드 → 본문/가입 연결. 가입 전은 **1회성 Upload Token**, 멱등 지원, 고아 이미지 sweeper ([0010](docs/adr/0010-storage-backend-strategy.md)) |
| 신고·모더레이션 | `/v1/reports/*` · `/v1/admin/*` | `domain/reports`·`domain/admin` | 신고는 항상 Insert 누적(감사), 임계 초과 자동 블라인드. 관리자 신고 피드는 DB-side **UNION ALL** ([0012](docs/adr/0012-admin-report-feed-pagination.md)) |

**횡단 규약**: 응답은 `{ code, message, data, requestId }` camelCase 통일 · 요청마다 `request_id`(ULID)
발급·`X-Request-ID` 헤더·로그 상관 · CUD는 서비스에서 `async with db.begin():` 단일 트랜잭션 ·
읽기/쓰기 세션 분리(`get_master_db`/`get_slave_db`) · Rate Limit·캐시·Pub/Sub 등 외부 I/O는 fail-open.

---

## 관측성 · 운영

- **헬스 분리** — `/livez`(의존성 무관 liveness, 실패=재시작) · `/readyz`(readiness — **DB=hard→503**,
  **Redis=soft→report만**). 기존 ALB 경로 `/v1/health`는 하위호환 유지 ([0006](docs/adr/0006-observability.md)).
- **메트릭** — `/metrics`(Prometheus). HTTP RED(`http_requests_total`·`http_request_duration_seconds`·
  in-flight, 라벨 `path`는 라우트 템플릿으로 카디널리티 제한) + 도메인 메트릭(rate-limit 429·캐시
  hit/miss·조회수 flush).
- **로그** — prod=구조화 JSON(stdout), dev=console. `request_id` 상관. 수집(stdout→CloudWatch)은 ECS 몫.
- **컨테이너** — 멀티스테이지 `Dockerfile`, `uv sync --frozen --no-dev`, 비루트 유저, `HEALTHCHECK`=`/livez`.
- **CI/CD** (`.github/workflows/ci.yml`) — quality(lint·format·type·vulture) · test(`postgres:15`+`minio`로
  unit+integration) · security(`pip-audit`) · docker(통과 시 build, `main` push면 **GHCR** push)를 병렬 잡으로.
  실제 배포 대상(ECS)·인프라(ALB·RDS·ElastiCache·CloudWatch)는 인프라 레포(Terraform)에서 관리합니다.

---

## 로컬 실행

Python 3.11+ 필요. DB(PostgreSQL)·Redis는 Docker 사용을 권장합니다.

```bash
# 1. 의존성
uv sync --extra dev            # 런타임 + dev(pytest·ruff·pyright·vulture·poe)

# 2. 환경 변수
cp .env.example .env           # DB_*, JWT_SECRET_KEY, REDIS_URL 등을 채움
#  - ENVIRONMENT=development(기본) | production — production 계열은 강한 JWT_SECRET_KEY(32자+) 필수
#  - 스토리지: dev는 MinIO(S3_ENDPOINT_URL 지정), prod는 실제 S3 자격 필수

# 3. DB 스키마 (git pull 후 새 마이그레이션이 생기면 다시 실행)
uv run poe migrate             # = alembic upgrade head

# 4. 서버
uv run poe run                 # http://localhost:8000 — 문서는 /v1/docs, 헬스는 /v1/health

# (선택) Celery — CELERY_ENABLED=true 일 때만
uv run poe celery-worker
uv run poe celery-beat
```

프로덕션 기동 시 `validate_settings_for_environment()`가 `JWT_SECRET_KEY`(placeholder 금지·32자+)와
S3 자격 등을 검사하며, 위반 시 프로세스를 중단합니다.

### API 문서

| 환경 | Swagger UI | ReDoc | OpenAPI JSON |
|------|-----------|-------|--------------|
| 로컬 | `/v1/docs` | `/v1/redoc` | `/v1/openapi.json` |
| 프로덕션 | `https://api.puppytalk.shop/v1/docs` | `/v1/redoc` | `/v1/openapi.json` |

응답·스펙 필드는 프론트 OpenAPI codegen 계약을 위해 **camelCase**로 노출됩니다.

### 검사 · 테스트

```bash
uv run poe quality   # lint(--fix) + format
uv run poe check     # lint-check + format-check + typecheck + vulture-check + audit (CI와 동일)

# 테스트 — 통합 테스트는 puppytalk_test DB 필요
export TEST_DB_URL="postgresql+psycopg://postgres:PASSWORD@localhost:5432/puppytalk_test"
uv run pytest                      # 전체
uv run pytest tests/unit           # DB 불필요(검색 검증·트렌드 쿼리·조회수 버퍼·도메인 메트릭 등)
uv run pytest tests/integration    # PostgreSQL + pg_trgm (스키마는 conftest가 세션 시작 시 생성)
```

통합 스위트는 세션 스코프 스키마를 공유하며(테스트 간 롤백 없음), Redis 저장소가 필요한 RTR·멱등성
테스트는 Redis 미연결 시 자동 skip합니다. 컨테이너로 CI를 재현하려면:

```bash
docker run -d --name pg -e POSTGRES_PASSWORD=PASSWORD -e POSTGRES_DB=puppytalk_test -p 5432:5432 postgres:15
```

### Docker

```bash
docker build -t puppytalk-be .
# 실행에는 DB·Redis·S3(호환) 스토리지가 필요합니다. 인프라 레포의 compose로 전체 스택을 함께 띄우세요.
# 배포 command 예: alembic upgrade head && gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000
```

### 관리자 계정

관리자 API(`/v1/admin/*`)는 `role='ADMIN'` 유저만 사용할 수 있습니다.

```sql
UPDATE users SET role = 'ADMIN' WHERE email = 'your-admin@example.com';
```

---

## 문서

| 문서 | 설명 |
|------|------|
| [00 · 운영 봉투와 범위](docs/00-operating-envelope-and-scope.md) | 모든 설계·복잡도 판정의 단일 근거(전제·과제·재건 순서) |
| [01 · 아키텍처](docs/01-architecture.md) | 횡단 관심사 결정(식별자·API·트랜잭션·캐시·페이지네이션·관측성·인덱스) |
| [ADR](docs/adr/) | 핵심 설계 결정 12건 — 각 결정의 트레이드오프와 *안 한 것* |
| [ROADMAP](docs/ROADMAP.md) | RUP-lite 리팩토링 진행·완료 이력(도메인 단위 + 커밋) |
| [backlog](docs/backlog.md) | 버그·최적화 백로그와 각 항목의 근거·수정 방향 |
