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
| **패키지 관리** | uv |
| **프레임워크** | FastAPI, Starlette |
| **실시간** | WebSocket |
| **서버** | Uvicorn, Gunicorn |
| **DB** | PostgreSQL, psycopg3 (async) |
| **ORM** | SQLAlchemy 2.x |
| **마이그레이션** | Alembic |
| **캐시·메시징** | Redis |
| **스토리지** | 로컬 파일, AWS S3 (boto3) |
| **검증** | Pydantic v2 |
| **식별자** | PostgreSQL `uuid`, UUID v7, Base62(공개 ID), ULID(`jti`·요청 ID 등) |
| **인증** | JWT (PyJWT), bcrypt |

---

## 폴더 구조

**app/** 단일 패키지 아래에 공용 레이어(api·common·core·db·infra)와 **domain/** 기능 도메인이 계층화되어 있습니다. 각 도메인은 **router → service → model → schema** 순으로 요청이 흐르며, 엔드포인트·비즈니스 로직·데이터 접근·DTO가 명확히 분리된 구조를 갖습니다. 

```
2-kyjness-community-be/
├── app/                                    # 백엔드 패키지 루트
│   ├── __init__.py                         # domain 패키지를 app.auth, app.chat 등으로 sys.modules 주입
│   ├── main.py                             # FastAPI 앱, lifespan(조회수 flush·채팅 Redis 구독 등), 미들웨어·라우터
│   ├── api/                                # HTTP·WS 라우터 조립
│   │   ├── v1/                             # /v1 prefix: v1_router, 도메인 라우터 include + chat REST·WS
│   │   │   └── chat/                       # DM: rest.py(/v1/chat/*), ws.py(/v1/ws/chat)
│   │   └── dependencies/                   # 인증, DB 세션(get_master_db/get_slave_db), 권한, 쿼리 파싱
│   ├── common/                             # API 코드·Enum·ApiResponse·validators·exceptions·로깅
│   ├── core/                               # config, ids, security, exception_handlers, cleanup, openapi_camel 등
│   │   └── middleware/                     # RequestId, ProxyHeaders, RateLimit, GZip, AccessLog, SecurityHeaders
│   ├── db/                                 # SQLAlchemy Base·엔진·세션·연결
│   ├── domain/                             # 기능별 도메인 (router → service → model → schema)
│   │   ├── admin/                          # 관리자: 신고된 게시글·댓글 통합 목록, 블라인드/신고 무시/삭제, 유저 정지·해제
│   │   ├── auth/                           # 회원가입·로그인·로그아웃·리프레시
│   │   ├── chat/                           # 1:1 DM: 방·메시지, WebSocket 핸들러·Redis Pub/Sub(런타임 import: app.chat)
│   │   ├── comments/                       # 댓글 CRUD·페이지네이션
│   │   ├── dogs/                           # 강아지 프로필
│   │   ├── likes/                          # 게시글·댓글 좋아요
│   │   ├── media/                          # 이미지 업로드(로컬/S3), Redis Upload Token, 미사용 이미지 sweeper
│   │   ├── notifications/                  # 알림 영속(PostgreSQL)·Redis Pub/Sub·SSE 스트림(/v1/notifications/*)
│   │   ├── posts/                          # 게시글 CRUD·피드·조회수·해시태그 등
│   │   ├── reports/                        # 신고 접수(POST/COMMENT)·누적 Insert·자동 블라인드
│   │   └── users/                          # 프로필·비밀번호·탈퇴·차단
│   └── infra/                              # Redis(Refresh·RateLimit·채팅), storage(로컬/S3)
├── docs/                                   # 아키텍처·API 코드·인프라 설계 문서
├── migrations/                             # Alembic env.py, versions(리비전)
│   ├── env.py                              # Alembic 실행 환경(경로/엔진/metadata) 구성, offline/online 모드
│   └── versions/                           # 마이그레이션
├── scripts/                                # pip-audit용 requirements export, 배포 entrypoint 등
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

이 섹션은 “무슨 기능을, 어떤 방식으로 구현했는지”를 **엔드포인트·도메인 코드 위치·핵심 구현 포인트** 기준으로 정리했습니다. (상세 로직은 `app/domain/*` 및 `docs/architecture.md`에 연결됩니다.)\n+
| 기능 | 대표 엔드포인트 | 구현 위치(도메인/라우터) | 구현 방식(핵심 포인트) |
|------|------------------|--------------------------|------------------------|
| **인증(회원가입/로그인/로그아웃/리프레시)** | `/v1/auth/*` | `app/domain/auth/`, `app/api/v1/*` | **JWT Access/Refresh**를 사용하고, Refresh는 **HttpOnly 쿠키 + Redis 기반 RTR**로 회전합니다. 동시 `/auth/refresh`는 Redis **Lua CAS**로 1건만 성공하도록 원자성을 확보했고, 로그아웃은 Access의 **`jti`를 Redis 블랙리스트**에 등록해 TTL 동안 즉시 무효화했습니다. 비밀번호 해시는 bcrypt를 **`asyncio.to_thread`**로 오프로딩했고, 신규/변경 시 **`PASSWORD_PEPPER`**를 적용해 보안 강도를 보강했습니다. |
| **게시글(피드/검색/상세/작성·수정·삭제)** | `/v1/posts/*` | `app/domain/posts/` | 피드는 무한 스크롤에서 **`has_more`** 패턴을 사용했고, 검색·피드 성능은 PostgreSQL 인덱스(GIN, 부분 인덱스 등)와 맞물리도록 설계했습니다. |
| **댓글(CRUD/페이지네이션)** | `/v1/comments/*` | `app/domain/comments/` | 댓글 목록은 페이지네이션을 적용해 응답 크기와 DB 부하를 제어했습니다. |
| **좋아요(게시글/댓글)** | `/v1/likes/*` (POST/DELETE) | `app/domain/likes/` | ON CONFLICT + RETURNING 조합으로 **멱등성**을 확보하고, `like_count` 동기화를 안정적으로 처리했습니다. |
| **신고/관리자 모더레이션** | `/v1/reports/*`, `/v1/admin/*` | `app/domain/reports/`, `app/domain/admin/` | 신고는 **항상 Insert 누적**(동일 유저 재신고 허용)으로 감사 가능성을 남겼고, “신고 무시” 시에만 `reports` soft delete 및 `report_count`를 초기화하도록 분기했습니다. 관리자는 신고된 게시글/댓글의 통합 목록·블라인드·유저 정지/해제를 제공합니다. |
| **채팅(DM, 1:1)** | REST: `/v1/chat/*` / WS: `/v1/ws/chat?token=...` | `app/domain/chat/`, `app/api/v1/chat/` | 실시간은 **WebSocket**으로 처리하고, 다중 인스턴스 확장을 위해 **Redis Pub/Sub Fan-out**으로 메시지를 전달합니다. DB 영속은 마이그레이션 **`006_chat_dm_tables`** 기준 테이블로 관리하며, 메시지 처리 시 DB 세션은 **짧은 트랜잭션**으로 유지해 Connection Pool 고갈 리스크를 줄였습니다. |
| **알림(실시간 + 목록/읽음)** | SSE: `/v1/notifications/stream`<br/>목록: `/v1/notifications`<br/>읽음: `/v1/notifications/read` | `app/domain/notifications/` | 이벤트 발생 시 `notifications` 행을 **트랜잭션 커밋 후** Redis 채널(`notif:user:{userId}`)로 발행합니다. 스트림은 **SSE(text/event-stream)** 로 제공하며, Redis 미구성 시 스트림은 503으로 제한하되 **DB 기록은 유지**하도록 설계했습니다. |
| **이미지 업로드(로컬/S3) + 임시 업로드 토큰** | `/v1/media/*` | `app/domain/media/`, `app/infra/storage.py` | 업로드는 “미리 업로드 → 본문/가입 연결” 흐름이며, 가입 전 임시 업로드는 **Redis Upload Token(단회성·TTL)** 로 검증했습니다. 24시간 경과 고아 이미지는 sweeper로 정리했습니다. 로컬/S3 등 동기 스토리지 I/O는 필요 시 **`asyncio.to_thread`**로 오프로딩했습니다. |
| **조회수(중복 방지 + Flush)** | `/v1/posts/{id}`(상세 조회 시) | `app/domain/posts/` + Redis | 조회수는 Redis **`SET NX EX`** 로 중복 증가를 방지한 뒤, Writer DB에 반영하고 응답에도 낙관적으로 반영했습니다. 조회수 버퍼는 주기적으로 DB로 Flush됩니다(lifespan). |
| **Cleanup(주기 작업)** | (백그라운드 태스크) | `app/core/cleanup.py`, `app/main.py` | 회원가입 임시 이미지·고아 이미지·탈퇴 유저 정리를 주기적으로 수행합니다. 멀티 인스턴스 환경에서는 **Redis 잡 락**으로 중복 실행을 억제했습니다. |
| **DB 읽기/쓰기 분리 + 트랜잭션 규율** | (DI/서비스 레이어) | `app/api/dependencies/`, `app/db/*` | `get_master_db`/`get_slave_db`, `WRITER_DB_URL`/`READER_DB_URL`로 읽기/쓰기 분리를 고려했고, CUD는 서비스에서 **`async with db.begin():`** 단위로 트랜잭션을 관리하도록 일관성을 유지했습니다. |
| **요청 추적(request_id)·로그 상관관계** | 전 구간 | `RequestIdMiddleware`, `app/common/*` | 요청마다 ULID 기반 `request_id`를 발급해 **`X-Request-ID`**로 반환하고(에러 포함), 로그에도 자동 포함되도록 구성했습니다. |
| **에러 응답 포맷 통일** | 전 구간 | `app/core/exception_handlers.py` | 모든 에러를 `{ code, message, data }`로 통일했고, 500에서는 스택/쿼리 노출 없이 마스킹해 반환했습니다. |
| **응답 압축·Rate Limit** | 전 구간 | `GZipMiddleware`, `RateLimitMiddleware` | 1KB 이상 응답만 gzip 압축했고, Rate Limit은 Redis **Fixed Window**로 경로별 제한을 적용했습니다. Redis 장애 시에는 Fail-open으로 서비스 전체 중단을 피했습니다. |
| **Redis JSON 직렬화·멱등성 캐시** | 일부 엔드포인트(캐시/멱등) | `TypeAdapter` 기반 유틸 | 캐시는 Pydantic v2 **`TypeAdapter.validate_json`/`dump_json`**으로 직렬화 계약을 고정했고, 스키마 불일치/손상 시 캐시 미스로 처리하여 정상 플로우로 폴백했습니다. |

---

## 로컬 실행 방법

로컬에서 서버를 띄우려면 **Python 3.11+**가 필요합니다.

- **DB(PostgreSQL) / Redis는 Docker 사용을 권장**합니다. (OS/WSL 환경차, 포트/유저/서비스 관리 이슈를 줄이고 팀 환경을 동일하게 맞출 수 있음)
- 로컬(네이티브) 설치로도 가능하지만, 설치/서비스 기동/계정/소켓 이슈로 트러블슈팅 비용이 커질 수 있습니다.
- **코드를 최신으로 가져온 뒤에는 반드시 아래 3번 단계(DB 스키마 마이그레이션)**로 테이블을 현재 리비전에 맞춥니다. (서버만 띄우면 스키마 불일치로 실패할 수 있음)
- **설계 문서(MkDocs)**: `docs/` 마크다운은 **`mkdocs serve`**(로컬 미리보기 서버; `service` 아님)로 띄웁니다. API(8000)와 포트 분리 등은 **아래 5번** 참고.

### 1. 저장소 클론 및 패키지 설치

**uv**로 가상환경·의존성을 관리합니다. ([설치 안내](https://docs.astral.sh/uv/getting-started/installation/))

```bash
cd 2-kyjness-community-be
uv lock                    # pyproject.toml 변경 시 (또는 최초 1회) lock 갱신
uv sync --extra dev        # 런타임 + dev(테스트·ruff·pyright·vulture·poe 등)
```

실행 시에는 `uv run …`으로 프로젝트 환경의 Python을 쓰거나, `uv run poe <task>`로 Poe 태스크를 돌립니다.

### 2. 환경 변수 설정

[`.env.example`](https://github.com/kyjness/2-kyjness-community-be/blob/main/.env.example)을 복사한 뒤 DB·JWT·Redis 등 필수 값을 채웁니다.

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
| `uv run poe migrate` | **`python3 -m alembic upgrade head`와 동일**(권장, `pyproject.toml` [tool.poe.tasks]). 최신 스키마까지 한 번에 적용. |
| `uv run python3 -m alembic upgrade head` | 위와 동일(직접 Alembic 호출). |
| `uv run python3 -m alembic current` | 현재 DB에 적용된 리비전 확인. |
| `uv run python3 -m alembic history` | 리비전 목록 확인. |

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

기본적으로 `app.core.config`의 **`API_PREFIX`(기본값 `/v1`)**에 맞춰 Swagger·ReDoc·OpenAPI JSON 경로가 잡힙니다(로컬 예: `/v1/docs`). 설계 문서 사이트만 따로 보려면 **아래 5번(MkDocs)**을 사용하세요(API와 포트 분리).

### 5. 문서 사이트 (MkDocs)

`docs/`의 아키텍처·인프라 설명을 [MkDocs](https://www.mkdocs.org/) **Material** 테마로 묶어 둔 설정이 루트 [`mkdocs.yml`](mkdocs.yml)입니다(네비·Mermaid 등).

 `source .venv/bin/activate` 실행 후

| 하위 명령 | 용도 |
|-----------|------|
| **`mkdocs serve`** | 로컬에서 문서 사이트 미리보기(개발 서버) |
| **`mkdocs build`** | 정적 HTML을 `site/`에 생성. |

```bash
uv pip install mkdocs-material          # 최초 1회
uv run mkdocs serve -a 127.0.0.1:8001   # 미리보기 — API(8000)와 포트 분리 권장
uv run mkdocs build                     # 정적 빌드 → site/
```

미리보기 URL: **http://127.0.0.1:8001**

### 6. 개발 도구 (Ruff, Pyright, Vulture, pip-audit)

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

### 7. 테스트 실행 (Pytest)

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

### 8. 관리자 기능 (Admin)

관리자 전용 API(`/v1/admin/*`)와 프론트 대시보드(`/admin/dashboard`)는 **role이 `ADMIN`인 유저만** 사용할 수 있습니다.

**관리자 계정 만들기**  
   DB에서 해당 유저의 `role`을 `ADMIN`으로 변경합니다.

   ```sql
   -- users.id는 DB에서 uuid 타입입니다. 아래는 이메일로 지정하는 예시입니다.
   UPDATE users SET role = 'ADMIN' WHERE email = 'your-admin@example.com';
   ```

---

## 확장 전략

### 기능

- **데이터 무결성(페이로드 계약)**: 메시지 큐·외부 브로커를 붙일 때도 Redis 캐시와 같이 Pydantic V2 **`TypeAdapter` / `validate_json`(또는 동등한 스키마 검증)**으로 메시지 형태를 고정하는 패턴을 권장. (현재 코드베이스는 Redis 캐시·멱등성 응답에 적용.)
- **비동기 태스크**: Celery 기반의 대용량 비동기 작업 처리.
- **검색 레이어 확장**: PostgreSQL 단일 스토어를 유지한 채 **`pg_trgm` GIN**과 쿼리·인덱스 튜닝으로 키워드·부분 일치 검색을 고도화한다. AI 모델 연동 시에는 같은 DB에 **`pgvector`**를 두어 임베딩 기반 **벡터 검색**을 붙이고, 기존 GIN 경로는 걷어내지 않은 채 키워드 일치와 벡터 유사도를 함께 쓰는 **하이브리드 검색**으로 의미 기반 정밀도와 고유명사·키워드 매칭 성능을 동시에 끌어올린다.

### AI

- **RAG 기반 '우리 아이 건강 척척박사'**  
  커뮤니티 지식 베이스와 LLM을 결합한 실시간 스트리밍(StreamingResponse) 챗봇 구축. Vercel AI SDK를 활용한 인터랙티브한 UI와 Context Window 최적화를 통한 답변 정확도 향상.

- **하이브리드 추천 시스템 (GraphQL Hybrid)**  
  - **지능형 피드**: 사용자 행동 로그 및 클릭 기반의 무한 스크롤 추천 피드 구현.  
  - **데이터 최적화**: 추천·복합 쿼리 증가 시 전송 효율을 위해 GraphQL을 부분 도입하여, 추천 피드와 도메인 데이터를 조합해 제공하는 하이브리드 아키텍처 검토.  
  - **동네 친구 제안**: 위치 정보(Distance Badge)와 견종 유사도를 결합한 맞춤형 친구 추천 서비스.

### 인프라

- **성능 가속**: 메시지 큐(SQS/Kafka)를 활용한 시스템 간 결합도 완화 검토.
- **Presigned URL 기반 스토리지 확장**: 서버를 업로드/다운로드 데이터 경로에서 분리하기 위해, S3 Presigned URL을 발급하여 클라이언트가 S3에 직접 업로드(POST/PUT)·다운로드(GET)하도록 전환. 업로드 완료 후에는 메타데이터만 서버에 등록하고, URL은 짧은 TTL·콘텐츠 타입/사이즈 조건·키 네이밍 정책으로 보안 제어.

### 구독 및 비즈니스 운영

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
| [architecture.md](https://github.com/kyjness/2-kyjness-community-be/blob/main/docs/architecture.md) | 요청 생명주기, 미들웨어, DB, 인증·보안, 전역 에러 포맷, 데이터 정합성, N+1·FK 인덱스 등 성능 최적화 |
| [api-codes.md](https://github.com/kyjness/2-kyjness-community-be/blob/main/docs/api-codes.md) | API 응답 코드와 HTTP 상태 코드 매핑 |
| [infrastructure-reliability-design.md](https://github.com/kyjness/2-kyjness-community-be/blob/main/docs/infrastructure-reliability-design.md) | 인프라·신뢰성 설계 (Redis Fail-open 등) |
| [kubernetes-cicd-pipeline-report.md](https://github.com/kyjness/2-kyjness-community-be/blob/main/docs/kubernetes-cicd-pipeline-report.md) | 쿠버네티스·CI/CD 파이프라인 (GitHub Actions, Jenkins, EKS) |
| [puppytalkdb.sql](https://github.com/kyjness/2-kyjness-community-be/blob/main/docs/puppytalkdb.sql) | 참고용 DDL (수동 테이블 생성 시) |
| [clear_db.sql](https://github.com/kyjness/2-kyjness-community-be/blob/main/docs/clear_db.sql) | DB 데이터만 비우기 (테이블 유지, 시퀀스 리셋) |
