# PuppyTalk Backend

**PuppyTalk**는 반려견을 키우는 사람들을 위한 커뮤니티 서비스의 백엔드로, **FastAPI** 기반의 **RESTful API**로 설계·구현된 서버입니다. 

**관련 링크**

- **프론트엔드**: [PuppyTalk Frontend](https://github.com/kyjness/2-kyjness-community-fe)
- **인프라·배포**: [PuppyTalk Infra](https://github.com/kyjness/2-kyjness-community-infra)

---

## 기술 스택

| 구분 | 기술 |
|------|------|
| **언어** | Python 3.11+ |
| **패키지 관리** | uv (Rust 기반 고성능 매니저, pyproject.toml 및 uv.lock 기반 결정적 빌드) |
| **프레임워크** | FastAPI (Starlette 기반) |
| **서버** | Uvicorn (개발), Gunicorn + Uvicorn worker (프로덕션) |
| **DB** | PostgreSQL (psycopg3, Full-Async). 게시글 제목·본문 **GIN**(`pg_trgm`), 미삭제·비블라인드 최신 피드용 **부분 복합 인덱스** `idx_posts_feed_latest` 등으로 조회 경로 최적화. |
| **ORM** | SQLAlchemy 2.x (AsyncSession, autobegin=False) |
| **마이그레이션** | Alembic |
| **스토리지** | 로컬 파일 / AWS S3 (boto3) |
| **검증** | Pydantic v2 |
| **식별자** | 엔티티 PK·대부분의 FK는 **ULID** 문자열(26자, DB `VARCHAR(26)`). `categories`·`hashtags` 등 시드 테이블은 **Integer** 유지. |
| **인증** | JWT (PyJWT), bcrypt는 **`asyncio.to_thread`**로 해시·검증. 비밀번호는 **`PASSWORD_PEPPER`**와 함께 저장. Redis: **RTR**(refresh 다이제스트 **Lua CAS** 원자 회전), Access **`jti` 블랙리스트**(로그아웃), Rate Limit, 백그라운드 잡 **분산 락**, **알림 Pub/Sub**(SSE 팬아웃). |

---

## 폴더 구조

**app/** 단일 패키지 아래에 공용 레이어(api·common·core·db·infra)와 **domain/** 기능 도메인이 계층화되어 있습니다. 각 도메인은 **router → service → model → schema** 순으로 요청이 흐르며, 엔드포인트·비즈니스 로직·데이터 접근·DTO가 명확히 분리된 구조를 갖습니다.

```
2-kyjness-community-be/
├── app/                                    # 백엔드 패키지 루트
│   ├── main.py                             # FastAPI 앱 생성, 미들웨어·라우터 등록, 진입점
│   ├── api/                                # HTTP 레이어
│   │   ├── v1.py                           # /v1 prefix 라우터 묶음
│   │   └── dependencies/                   # 인증, DB 세션(get_master_db/get_slave_db), 권한, 쿼리 파싱
│   ├── common/                             # API 코드·Enum·ApiResponse·validators·exceptions·로깅
│   ├── core/                               # config, ids(ULID), security(JWT·비밀번호), exception_handlers, cleanup
│   │   └── middleware/                     # RequestId, ProxyHeaders, RateLimit, GZip, AccessLog, SecurityHeaders
│   ├── db/                                 # SQLAlchemy Base·엔진·세션·연결
│   ├── domain/                             # 기능별 도메인 (router → service → model → schema)
│   │   ├── admin/                          # 관리자: 신고된 게시글·댓글 통합 목록, 블라인드/신고 무시/삭제, 유저 정지·해제
│   │   ├── auth/                           # 회원가입·로그인·로그아웃·리프레시
│   │   ├── comments/                       # 댓글 CRUD·페이지네이션
│   │   ├── dogs/                           # 강아지 프로필
│   │   ├── likes/                          # 게시글·댓글 좋아요
│   │   ├── media/                          # 이미지 업로드(로컬/S3), Redis Upload Token, 미사용 이미지 sweeper
│   │   ├── notifications/                  # 알림 영속(PostgreSQL)·Redis Pub/Sub·SSE 스트림(/v1/notifications/*)
│   │   ├── posts/                          # 게시글 CRUD·피드·조회수
│   │   ├── reports/                        # 신고 접수(POST/COMMENT)·누적 Insert·자동 블라인드
│   │   └── users/                          # 프로필·비밀번호·탈퇴·차단
│   └── infra/                              # Redis(Refresh·RateLimit), storage(로컬/S3)
├── docs/                                   # 아키텍처·API 코드·인프라 설계 문서
├── migrations/                             # Alembic env.py, versions(리비전)
│   ├── env.py                              # Alembic 실행 환경(경로/엔진/metadata) 구성, offline/online 모드
│   └── versions/                           # 마이그레이션 리비전 스크립트(순서대로 upgrade/downgrade)
├── alembic.ini                             # Alembic 설정 (script_location=migrations)
├── pyproject.toml                          # PEP 621 의존성·optional-dev·Poe 태스크
└── Dockerfile                              # uv 멀티스테이지 빌드·Gunicorn+Uvicorn
```

---

## API 문서

FastAPI는 API 프리픽스가 `/v1`이므로, **문서·OpenAPI JSON도 `/v1` 뒤에 붙는 경로**입니다. 로컬과 AWS에 배포한 환경 모두 동일한 패턴입니다.

| 환경 | Swagger UI (요청 테스트) | ReDoc (읽기용) | OpenAPI JSON |
|------|-------------------------|----------------|--------------|
| **로컬** | http://localhost:8000/v1/docs | http://localhost:8000/v1/redoc | http://localhost:8000/v1/openapi.json |
| **프로덕션 (AWS)** | https://api.puppytalk.shop/v1/docs | https://api.puppytalk.shop/v1/redoc | https://api.puppytalk.shop/v1/openapi.json |

배포 서버 루트 예시: [https://api.puppytalk.shop/v1/](https://api.puppytalk.shop/v1/) — 응답 `data.docs`에도 `/v1/docs` 안내가 포함됩니다.

---

## 기능 정리

도메인 기능과 그에 붙는 대표 동작·제약을 표로 압축해 둔 것입니다.

| 영역 | 설명 |
|------|------|
| **피드·댓글** | 게시글 무한 스크롤(has_more), 댓글 페이지네이션. 피드·검색은 DB 레벨에서 GIN·`idx_posts_feed_latest`(부분 인덱스) 등과 맞물리도록 설계. |
| **인증** | JWT Access/Refresh. Access 만료는 `ACCESS_TOKEN_EXPIRE_SECONDS`(기본 **30분**), Refresh는 `REFRESH_TOKEN_EXPIRE_DAYS`(기본 **7일**). Refresh는 HttpOnly 쿠키 + Redis와 **RTR**. 동일 유저·동일 구 refresh로 동시 `/auth/refresh`가 오면 Redis **Lua 스크립트 CAS**로 다이제스트 회전이 원자적으로 한 건만 성공하고, 패자는 **401**(재로그인 유도). 로그아웃 시 Access payload의 **`jti`**를 Redis 블랙리스트에 올려 남은 TTL 동안 즉시 무효화. 가입·비밀번호 변경 시 **`PASSWORD_PEPPER`**를 붙인 뒤 bcrypt 해시(기존 DB 해시는 pepper 없이 검증하는 폴백 유지). bcrypt 해시·검증은 **`asyncio.to_thread`**. |
| **좋아요** | POST/DELETE 명시적 API. ON CONFLICT DO NOTHING + RETURNING으로 멱등·like_count 동기화. |
| **알림(실시간)** | 댓글·게시글/댓글 좋아요 시 수신자에게 `notifications` 행을 **트랜잭션 커밋 후** Redis 채널 `notif:user:{userId}`로 발행. **`GET /v1/notifications/stream`**은 SSE(`text/event-stream`); Redis 미구성 시 스트림은 503, **DB 기록은 유지**. 목록·읽음: **`GET /v1/notifications`**, **`PATCH /v1/notifications/read`**. |
| **조회수** | 상세 조회(GET `/posts/{id}`)에서 조회수 증가를 처리하며, Redis `SET NX EX`로 중복을 방지합니다. (Writer DB에서 +1 반영 후 응답에도 낙관적 반영) |
| **이미지** | 미리 업로드 후 본문/가입 연결. 가입 전 임시 업로드는 Redis Upload Token(단회성·TTL)로 검증하고, 24시간 경과 고아 이미지는 sweeper로 정리합니다. 로컬/S3 등 동기 스토리지 I/O는 필요 시 **`asyncio.to_thread`**로 오프로딩합니다. |
| **Cleanup(정리)** | 회원가입 임시 이미지 정리 + 24시간 경과 고아 이미지 정리 + 탈퇴 30일 경과 유저 하드 삭제(청크) 작업을 주기적으로 수행합니다. 멀티 인스턴스 시 미사용 이미지 sweep·가입 임시 이미지 정리는 **Redis 잡 단위 락**으로 중복 실행을 억제합니다. |
| **DB 읽기/쓰기 분리** | get_master_db / get_slave_db, WRITER_DB_URL / READER_DB_URL 분리(확장성 고려). 트랜잭션은 서비스의 `async with db.begin():`으로만 관리. |
| **요청 추적** | 순수 ASGI RequestIdMiddleware로 ULID 발급·scope.state·X-Request-ID 응답 헤더(4xx/5xx 포함). contextvars·RequestIdFilter로 로그에 request_id 자동 포함. |
| **에러 응답** | 전역 예외 핸들러로 모든 에러를 { code, message, data } 형식 통일. 500 시 클라이언트에는 스택/쿼리 노출 없이 마스킹 메시지만 반환. |
| **API 응답 code** | `ApiResponse.code`는 `ApiCode` enum 또는 str. 라우터에서는 `ApiCode.OK` 등 enum만 전달하며, `BaseSchema`의 `use_enum_values=True`로 직렬화 시 문자열로 내려감. |
| **신고** | 신고는 항상 새 행(Insert) 누적. 동일 유저 재신고도 허용. 신고 무시 시에만 `reports` soft delete·글/댓글 `report_count` 초기화. `reports` 테이블에는 `status` 컬럼 없음, `target_type`은 TargetType(POST/COMMENT). |
| **응답 압축** | GZip 미들웨어(minimum_size=1KB)로 1KB 이상 응답만 gzip 압축. |
| **Rate Limit** | Redis Fixed Window, 경로별 제한. Redis 장애 시 Fail-open. |
| **Redis JSON·멱등성** | 트렌딩 해시태그 캐시는 **`TypeAdapter(list[...]).validate_json` / `dump_json`**으로 직렬화·역직렬화를 맞춤. 게시글 생성·이미지 업로드 **멱등성 캐시**는 엔드포인트별 **`TypeAdapter(ApiResponse[PostIdData])` 등**으로 검증하고, 스키마 불일치·손상 시 캐시 미스로 처리 후 정상 플로우로 폴백. |

---

## 로컬 실행 방법

로컬에서 서버를 띄우려면 **Python 3.11+**가 필요합니다.

- **DB(PostgreSQL) / Redis는 Docker 사용을 권장**합니다. (OS/WSL 환경차, 포트/유저/서비스 관리 이슈를 줄이고 팀 환경을 동일하게 맞출 수 있음)
- 로컬(네이티브) 설치로도 가능하지만, 설치/서비스 기동/계정/소켓 이슈로 트러블슈팅 비용이 커질 수 있습니다.
- **코드를 최신으로 가져온 뒤에는 반드시 아래 3번 단계(DB 스키마 마이그레이션)**로 테이블을 현재 리비전에 맞춥니다. (서버만 띄우면 스키마 불일치로 실패할 수 있음)

### 1. 저장소 클론 및 패키지 설치

**uv**로 가상환경·의존성을 관리합니다. ([설치 안내](https://docs.astral.sh/uv/getting-started/installation/))

```bash
cd 2-kyjness-community-be
uv lock                    # pyproject.toml 변경 시 (또는 최초 1회) lock 갱신
uv sync --extra dev        # 런타임 + dev(테스트·ruff·pyright·vulture·poe 등)
```

실행 시에는 `uv run …`으로 프로젝트 환경의 Python을 쓰거나, `uv run poe <task>`로 Poe 태스크를 돌립니다.

### 2. 환경 변수 설정

[`.env.example`](.env.example)을 복사한 뒤 DB·JWT·Redis 등 필수 값을 채웁니다.

```bash
cp .env.example .env
# .env 편집: DB_PASSWORD, JWT_SECRET_KEY, REDIS_URL, ACCESS_TOKEN_EXPIRE_SECONDS(기본 1800), REFRESH_TOKEN_EXPIRE_DAYS(기본 7) 등
# - Docker(DB/Redis) 권장: DB_HOST=postgres(또는 compose 서비스명), REDIS_URL=redis://redis:6379/0
# - 로컬(Postgres/Redis 직접 설치): DB_HOST=127.0.0.1(또는 localhost), REDIS_URL=redis://127.0.0.1:6379/0
```

### 3. DB 스키마 적용(마이그레이션)

**이 단계가 곧 “DB 업데이트”입니다.** Alembic으로 `migrations/versions/`에 정의된 변경을 PostgreSQL에 순서대로 반영합니다. **최초 1회**뿐 아니라, **git pull 이후 새 마이그레이션 파일이 생겼을 때마다** 다시 실행합니다.

| 명령 | 설명 |
|------|------|
| `uv run poe migrate` | **`python -m alembic upgrade head`와 동일**(권장). 현재 코드 기준 최신 스키마까지 한 번에 적용. |
| `uv run python -m alembic upgrade head` | 위와 동일(직접 Alembic 호출). |
| `uv run python -m alembic current` | 현재 DB에 적용된 리비전 확인. |
| `uv run python -m alembic history` | 리비전 목록 확인. |

#### 3-A. Docker로 DB/Redis 실행 (권장)

- Docker Compose 파일은 인프라 레포에 있습니다: [PuppyTalk Infra](https://github.com/kyjness/2-kyjness-community-infra)
- DB(및 실시간 알림·SSE를 쓰려면 Redis)를 기동한 뒤, `.env`의 `DATABASE_URL` / `WRITER_DB_URL` 등이 그 DB를 가리키는지 확인하고 아래를 실행합니다.

```bash
uv run poe migrate
```

#### 3-B. 로컬(PostgreSQL 직접 설치)로 실행 (선택)

```bash
createdb -U postgres puppytalk

uv run poe migrate
```

**DB 데이터만 비우기(초기화)** 

```bash
psql -U postgres -d puppytalk -f docs/clear_db.sql
```

### 4. 서버 실행

```bash
uv run poe run
```

- **실시간 알림 스트림**을 쓰려면 Redis가 떠 있고 `.env`에 **`REDIS_URL`**이 설정되어 있어야 합니다. Redis 없이도 API·DB 알림 기록은 동작하지만, **`GET /v1/notifications/stream`** 은 503을 반환합니다.

### 5. 개발 도구 (Ruff, Pyright, Vulture, pip-audit)

**수정/적용용** (코드를 직접 변경):

```bash
uv run poe quality   # lint(--fix) + format 한 방에
uv run poe lint      # ruff check . --fix (문법·미사용 import 등)
uv run poe format    # ruff format . (포맷팅)
```

**검사용** (코드 수정 없이 리포트만, CI/CD용):

```bash
uv run poe check        # lint-check + format-check + typecheck + vulture-check + audit (하나라도 실패 시 중단)
uv run poe lint-check   # ruff check . (자동 수정 없음)
uv run poe format-check # ruff format . --check (포맷 검사만)
uv run poe typecheck    # pyright (타입 체크)
uv run poe vulture-check # vulture (데드코드 탐지, 설정은 pyproject.toml [tool.vulture])
uv run poe audit        # pip-audit (의존성 보안 취약점 스캔)
```

**데드코드 스캔**: `poe vulture-check`는 [vulture](https://github.com/jendrikseipp/vulture)로 `app/`을 검사합니다. `pyproject.toml`의 `[tool.vulture]`에서 `min_confidence = 100`으로 두어 **신뢰도 100%로만 보고**하도록 했습니다(오탐은 줄고, 동적·프레임워크 마법 코드는 놓칠 수 있음). 오탐이 있으면 `vulture app --make-whitelist`로 화이트리스트를 만들거나 `ignore_names` 등으로 조정합니다.

**보안·의존성 스캔**: `poe audit`은 `pip freeze` 기반으로 `.audit-requirements.txt`를 생성한 뒤 `pip-audit`로 취약점을 검사합니다. 일부 환경(WSL 등)에서 `ensurepip`가 비활성화된 경우에도 동작하도록 `--no-deps --disable-pip` 모드로 실행합니다.

### 6. 테스트 실행 (Pytest)

테스트 DB를 사용하므로, 먼저 PostgreSQL에 `puppytalk_test` DB를 준비하고 연결 문자열을 설정하세요.

```bash
# 예시 (로컬)
export TEST_DB_URL="postgresql+psycopg://postgres:YOUR_PASSWORD@localhost:5432/puppytalk_test"
```

통합 테스트(`tests/integration/`)는 `tests/integration/conftest.py`에서 세션 시작 시 `pg_trgm` 확장 생성과 스키마 초기화를 수행합니다. 유닛 테스트(`tests/unit/`)는 DB 없이 동작합니다.

```bash
# 전체 테스트
uv run pytest -v

# 통합 테스트만
uv run pytest tests/integration -v

# 특정 테스트 파일만
uv run pytest tests/integration/test_auth.py -v

# 특정 테스트 함수만
uv run pytest tests/integration/test_auth.py::test_login_and_refresh_token -v
```

### 7. 관리자 기능 (Admin)

관리자 전용 API(`/v1/admin/*`)와 프론트 대시보드(`/admin/dashboard`)는 **role이 `ADMIN`인 유저만** 사용할 수 있습니다.

1. **관리자 계정 만들기**  
   DB에서 해당 유저의 `role`을 `ADMIN`으로 변경합니다.

   ```sql
   -- users.id는 ULID 문자열(26자)입니다. 이메일로 지정해도 됩니다.
   UPDATE users SET role = 'ADMIN' WHERE email = 'your-admin@example.com';
   ```

2. **프론트에서 사용**  
   관리자 계정으로 로그인하면 헤더의 **프로필 드롭다운**에 **관리자 대시보드** 링크가 표시됩니다. 해당 링크로 이동하면 신고된 게시글·댓글 통합 목록과 [블라인드 해제/처리], [유저 정지/해제], [글 삭제]/[댓글 삭제], [신고 무시] 버튼을 사용할 수 있습니다.

Docker·프로덕션 배포는 [PuppyTalk Infra](https://github.com/kyjness/2-kyjness-community-infra) 레포를 참고하면 됩니다.

---

## 확장 전략

### 기능

- **인앱 알림(구현됨)**: PostgreSQL 영속 + Redis Pub/Sub + SSE. (DM과는 별개.)
- **실시간 소통(1:1 DM)**: WebSocket 기반의 실시간 메시징 시스템 구축 및 대화 내역의 영속성(Persistence) 관리.
- **비동기 태스크**: Celery 기반의 대용량 비동기 작업 처리.
- **데이터 무결성(페이로드 계약)**: 메시지 큐·외부 브로커를 붙일 때도 Redis 캐시와 같이 Pydantic V2 **`TypeAdapter` / `validate_json`(또는 동등한 스키마 검증)**으로 메시지 형태를 고정하는 패턴을 권장. (현재 코드베이스는 Redis 캐시·멱등성 응답에 적용.)
- **검색 레이어 확장**: PostgreSQL 단일 스토어를 유지한 채 **`pg_trgm` GIN**과 쿼리·인덱스 튜닝으로 키워드·부분 일치 검색을 고도화한다. AI 모델 연동 시에는 같은 DB에 **`pgvector`**를 두어 임베딩 기반 **벡터 검색**을 붙이고, 기존 GIN 경로는 걷어내지 않은 채 키워드 일치와 벡터 유사도를 함께 쓰는 **하이브리드 검색**으로 의미 기반 정밀도와 고유명사·키워드 매칭 성능을 동시에 끌어올린다.

### AI

- **RAG 기반 '우리 아이 건강 척척박사'**  
  커뮤니티 지식 베이스와 LLM을 결합한 실시간 스트리밍(StreamingResponse) 챗봇 구축. Vercel AI SDK를 활용한 인터랙티브한 UI와 Context Window 최적화를 통한 답변 정확도 향상.

- **하이브리드 추천 시스템 (GraphQL Hybrid)**  
  - **지능형 피드**: 사용자 행동 로그 및 클릭 기반의 무한 스크롤 추천 피드 구현.  
  - **데이터 최적화**: 추천·복합 쿼리 증가 시 전송 효율을 위해 GraphQL을 부분 도입하여, 추천 피드와 도메인 데이터를 조합해 제공하는 하이브리드 아키텍처 검토.  
  - **동네 친구 제안**: 위치 정보(Distance Badge)와 견종 유사도를 결합한 맞춤형 친구 추천 서비스.

### 인프라

- **분산 환경 최적화**: 멀티 인스턴스 환경에서 Redis 클러스터를 통한 인증 상태 일관성 유지 및 Stateless 아키텍처 준수.
- **성능 가속**: 메시지 큐(SQS/Kafka)를 활용한 시스템 간 결합도 완화 검토.
- **Presigned URL 기반 스토리지 확장**: 서버를 업로드/다운로드 데이터 경로에서 분리하기 위해, S3 Presigned URL을 발급하여 클라이언트가 S3에 직접 업로드(POST/PUT)·다운로드(GET)하도록 전환. 업로드 완료 후에는 메타데이터만 서버에 등록하고, URL은 짧은 TTL·콘텐츠 타입/사이즈 조건·키 네이밍 정책으로 보안 제어.

---

## 구독 및 비즈니스 운영

- **AI 운영 비용 최적화**:
  - **Tiered Quota 관리**: Redis 기반의 실시간 사용량 제한(Rate Limiting) 로직을 구축하여, 사용자 등급별(Basic/Premium) AI 호출 횟수를 차등 제어하고 LLM 추론 비용(Token Cost) 리스크를 최소화.
  - **하이브리드 모델 라우팅**: 요청의 난이도에 따라 경량 모델(GPT-4o mini)과 고성능 모델(GPT-4o)을 동적으로 할당하는 인프라 구조를 설계하여 답변 품질과 운영 비용의 최적 균형 달성.
- **이벤트 기반 결제 및 권한 아키텍처**
  - **Webhook 기반 실시간 동기화**: 결제 대행사(Stripe/Toss)의 Webhook 이벤트를 비동기적으로 수신하여, 결제 상태 변화에 따른 유저 권한(RBAC) 및 서비스 접근성을 즉각적으로 업데이트하는 안정적인 결제 파이프라인 구축.
  - **결제 무결성 보장**: 분산 트랜잭션 상황에서의 결제 누락 방지를 위한 재시도(Retry) 로직 및 멱등성(Idempotency) 설계로 데이터 정합성 확보.
- **데이터 기반 건강 인사이트**
  - **자동화된 배치 리포트**: Celery Beat를 활용해 사용자의 활동 데이터(산책, 음수량 등)를 주기적으로 분석하고, AI가 생성한 '맞춤형 건강 분석 리포트'를 자동 발행하는 스케줄링 시스템 구현.
  - **개인화 푸시 알림**: 누적된 시계열 데이터의 통계적 유의미성을 분석하여, 이상 징후(Anomaly Detection) 감지 시 보호자에게 즉시 알림을 발송하는 사용자 유지(Retention) 전략 고도화.


---

## 문서

| 문서 | 설명 |
|------|------|
| [architecture.md](docs/architecture.md) | 요청 생명주기, 미들웨어, DB, 인증·보안, 전역 에러 포맷, 데이터 정합성, N+1·FK 인덱스 등 성능 최적화 |
| [api-codes.md](docs/api-codes.md) | API 응답 코드와 HTTP 상태 코드 매핑 |
| [infrastructure-reliability-design.md](docs/infrastructure-reliability-design.md) | 인프라·신뢰성 설계 (Redis Fail-open 등) |
| [puppytalkdb.sql](docs/puppytalkdb.sql) | 참고용 DDL (수동 테이블 생성 시) |
| [clear_db.sql](docs/clear_db.sql) | DB 데이터만 비우기 (테이블 유지, 시퀀스 리셋) |
