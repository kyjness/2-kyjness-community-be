# PuppyTalk Backend

**PuppyTalk**는 반려견을 키우는 사람들을 위한 커뮤니티 서비스의 백엔드로, **FastAPI** 기반의 **RESTful API**로 설계·구현된 서버입니다.

**제공 기능**

- **인증** — 회원가입·로그인·로그아웃·리프레시 (JWT Access/Refresh, Refresh Token은 Redis·HttpOnly 쿠키)
- **사용자** — 프로필 조회·수정(GET/PATCH /users/me), 비밀번호 변경, 탈퇴
- **게시글** — CRUD, 무한 스크롤 피드, 조회수(중복 방지 캐시), 상세 조회
- **좋아요** — 게시글·댓글 좋아요/취소 (POST·DELETE 명시적 API, 멱등)
- **댓글** — 페이지네이션, 작성자 검증, 게시글 댓글 수 자동 동기화
- **미디어** — 이미지 업로드 (로컬/S3), 회원가입 전 프로필 첨부(signupToken·ref_count)

**관련 링크**

- **프론트엔드**: [PuppyTalk Frontend](https://github.com/kyjness/2-kyjness-community-fe)
- **인프라·배포**: [PuppyTalk Infra](https://github.com/kyjness/2-kyjness-community-infra)

---

## 기술 스택

| 구분 | 기술 |
|------|------|
| **언어** | Python 3.8+ |
| **패키지 관리** | Poetry 2.x |
| **프레임워크** | FastAPI (Starlette 기반) |
| **서버** | Uvicorn (개발), Gunicorn + Uvicorn worker (프로덕션) |
| **DB** | PostgreSQL (psycopg3, Full-Async) |
| **ORM** | SQLAlchemy 2.x (AsyncSession, autobegin=False) |
| **마이그레이션** | Alembic |
| **스토리지** | 로컬 파일 / AWS S3 (boto3) |
| **검증** | Pydantic v2 |
| **인증** | JWT (PyJWT), bcrypt (비밀번호), Redis (Refresh Token·Rate Limit) |

---

## 폴더 구조

- **루트** — 실행·배포 설정, 테스트·문서를 두며, 애플리케이션 코드는 **app/** 패키지에 둡니다.
- **app/** — 공통·인프라와 기능 단위 **domain**으로 구분합니다.
- **도메인** — **router**(엔드포인트·HTTP·ApiResponse) → **service**(비즈니스 로직·`async with db.begin():` 트랜잭션) → **model**(DB 접근, commit/rollback 없음) → **schema**(요청·응답 DTO) 4계층으로 처리합니다.

```
2-kyjness-community-be/
├── app/
│   ├── api/
│   │   ├── dependencies/    # 인증·DB 세션·권한·쿼리 파싱·클라이언트 식별자 (통합 DI)
│   │   │   ├── auth.py      # Bearer 검증, CurrentUser
│   │   │   ├── client.py    # get_client_identifier (조회수 등)
│   │   │   ├── db.py        # get_master_db, get_slave_db
│   │   │   ├── permissions.py
│   │   │   └── query.py
│   │   └── v1.py            # /v1 경로에 라우터 묶어서 등록
│   ├── common/
│   │   ├── codes.py         # API 응답 코드 상수
│   │   ├── enums.py         # UserStatus, DogGender 등 공통 Enum
│   │   ├── response.py      # 에러 응답 (raise_http_error)
│   │   ├── schema.py        # BaseSchema, ApiResponse[T] 등 공통 스키마
│   │   ├── validators.py    # 닉네임·비밀번호 형식 검증
│   │   └── logging_config.py # 로깅 설정
│   ├── core/
│   │   ├── config.py        # 환경 변수 설정
│   │   ├── middleware/      # 프록시·요청 ID·접근 로그·속도 제한·보안 헤더
│   │   ├── security.py      # JWT Access/Refresh 토큰 생성·검증, 비밀번호 해시
│   │   ├── exception_handlers.py  # 전역 예외 → 공통 응답 형식
│   │   └── cleanup.py       # 만료 세션·미사용 이미지 정리
│   ├── db/                  # 엔진·세션·연결·Base·Alembic 마이그레이션
│   │   └── alembic/         # DB 스키마 마이그레이션 (versions, env.py)
│   ├── infra/               # Redis, 스토리지(로컬/S3) 등 인프라 연동
│   ├── domain/
│   │   ├── auth/            # 로그인·로그아웃·리프레시·회원가입 (AuthService)
│   │   ├── users/           # 프로필 조회·수정·비밀번호·탈퇴 (UserService)
│   │   ├── media/           # 이미지 업로드 (signupToken·ref_count)
│   │   ├── posts/           # 게시글 CRUD·피드·조회수 (PostService)
│   │   ├── comments/        # 댓글 CRUD·목록 (CommentService, 게시글 comment_count 조율)
│   │   └── likes/           # 게시글·댓글 좋아요 (LikeService, POST/DELETE 명시적)
│   └── main.py              # 앱 진입점·미들웨어·라우터 등록
├── docs/                    # 상세 문서·참고용 SQL
├── test/                    # pytest
├── alembic.ini              # Alembic 설정 (DB URL 등)
├── pyproject.toml           # Poetry 의존성·poe 태스크 정의
├── poetry.lock              # 의존성 잠금 (poetry install 시 참조)
├── Dockerfile               # 프로덕션 이미지 빌드
└── .env.example             # 환경 변수 예시 (복사 후 .env.development,.env.production 으로 사용)
```

---

## API 문서

서버를 실행한 뒤, 브라우저에서 **아래 주소**로 접속하시면 API 명세를 보실 수 있습니다.  
(Swagger UI는 요청 테스트용, ReDoc은 읽기용 정리 문서입니다.)

| 문서 | 주소 |
|------|------|
| **Swagger UI** | http://localhost:8000/docs |
| **ReDoc** | http://localhost:8000/redoc |

---

## 설계 포인트

이 커뮤니티 백엔드의 설계상 핵심 포인트만 정리한 것입니다.

| 포인트 | 설명 |
|--------|------|
| **서비스 레이어** | auth·users·posts·comments·likes 도메인에 Service 클래스 도입. Controller는 요청 수신·Service 호출·ApiResponse 반환만 담당. 비즈니스 로직·도메인 간 조율(댓글 수 동기화, 좋아요, 이미지 ref_count)은 Service에서 수행. |
| **피드·댓글** | 게시글은 무한 스크롤, 댓글은 페이지네이션으로 UX·참조성을 맞춤. |
| **인증** | JWT Access/Refresh. Refresh는 Redis·HttpOnly 쿠키. AuthService에서 Redis 저장·무효화. 만료 시 TOKEN_EXPIRED로 프론트에서 Refresh 호출 유도. |
| **좋아요** | 게시글·댓글 좋아요는 likes 도메인에서 POST/DELETE로 명시적 처리. ON CONFLICT DO NOTHING + RETURNING·UPDATE RETURNING으로 삽입/갱신 검증. 멱등·응답 형식 통일(is_liked, like_count). |
| **조회수** | GET 멱등성 유지 위해 전용 POST 엔드포인트. PostService에서 인메모리 캐시(용량 한계+TTL)로 중복 방지, 추후 Redis 전환 가능. |
| **이미지** | 미리 업로드 후 본문/가입 연결. 가입 전 이미지는 signupToken·ref_count로 소유·참조 관리. |
| **DB 읽기/쓰기 분리** | get_master_db(get_slave_db)·WRITER_DB_URL(READER_DB_URL) 분리·풀 튜닝으로 조회 부하 분산. 트랜잭션은 서비스의 async with db.begin()으로만 관리. |
| **요청 추적** | contextvars·RequestIdFilter로 로그에 request_id 자동 포함. |
| **Rate Limit** | Redis Fixed Window, 경로별 제한. Redis 장애 시 Fail-open. |

---

## 로컬 실행 방법

로컬에서 서버를 띄우려면 **Python 3.8+**, **PostgreSQL**이 필요합니다. Redis는 선택이며, 없으면 Rate Limit이 비활성(Fail-open)됩니다.

### 1. 저장소 클론 및 패키지 설치

**Poetry**가 가상환경을 자동으로 생성·사용하므로 별도 `python -m venv`는 필요 없습니다. (`poetry run`으로 실행하거나, 가상환경 안에서 쓰려면 `poetry shell` 입력.)

```bash
cd 2-kyjness-community-be
poetry install
# 의존성 추가/변경 후: poetry lock → poetry install
```

### 2. 환경 변수 설정

[`.env.example`](.env.example)을 복사한 뒤 DB·JWT·Redis 등 필수 값을 채웁니다.

```bash
cp .env.example .env.development
# .env.development 편집 (DB_*, JWT_SECRET_KEY, REDIS_URL 등)
# PostgreSQL: DB_HOST=postgres (Docker 시), DB_PORT=5432, DB_USER=postgres
# 단일 URL: WRITER_DB_URL=postgresql+psycopg://postgres:PW@postgres:5432/puppytalk
# 같은 PC에 PostgreSQL 직접 설치 시 DB_HOST=localhost
```

### 3. DB 생성 및 스키마 적용

```bash
# PostgreSQL DB 생성 (psql 또는 GUI)
createdb -U postgres puppytalk
# 또는: psql -U postgres -c "CREATE DATABASE puppytalk;"

poetry run poe migrate   # 최신 마이그레이션까지 적용 (또는 poetry run alembic upgrade head)
# DB가 이미 최신일 때 버전만 맞춤: poetry run alembic stamp head
```

**DB 데이터만 비우기(초기화)** 

```bash
psql -U postgres -d puppytalk -f docs/clear_db.sql
```

### 4. 서버 실행

**추천** — poethepoet (pyproject.toml에 등록된 스크립트):

```bash
poetry run poe run
```

`poetry install` 후 가상환경 안에서만 동작하며, `python -m uvicorn`을 사용해 Device Guard 환경에서도 동작합니다.

### 5. 테스트 (선택)

```bash
poetry run poe test
```

### 6. 린트·포맷 (Ruff)

```bash
poetry run poe lint    # ruff check --fix
poetry run poe format  # ruff format
```

Docker·프로덕션 배포는 [PuppyTalk Infra](https://github.com/kyjness/2-kyjness-community-infra) 레포를 참고하면 됩니다.

---

## 확장 전략

### 기능

- **사용자 보호 및 관리**: 게시글 신고, 사용자 차단(콘텐츠 필터링) 기능 및 관리자 전용 제재 로직(RBAC) 구현.
- **실시간 알림**: 댓글 및 상호작용 발생 시 실시간 알림 리스트 제공.
- **비동기 태스크**: FastAPI BackgroundTasks를 활용한 가벼운 로그 기록부터, Celery 기반의 대용량 비동기 작업 처리까지 단계적 확장.
- **데이터 무결성**: Pydantic V2의 `model_validate_json` 등을 활용해 Redis/Queue와의 데이터 교환 시 타입 검증·성능 최적화 (추후 적용 예정).

### AI

- **RAG 기반 '우리 아이 건강 척척박사'**  
  커뮤니티 지식 베이스와 LLM을 결합한 실시간 스트리밍 챗봇 구축.  
  Vercel AI SDK를 활용한 인터랙티브한 UI와 출처(Grounding) 제시 기능 강화.

- **하이브리드 추천 시스템 (GraphQL Hybrid)**  
  - **지능형 피드**: 사용자 행동 로그 및 클릭 기반의 무한 스크롤 추천 피드 구현.  
  - **데이터 최적화**: 추천·복합 쿼리 증가 시 전송 효율을 위해 GraphQL을 부분 도입하여, 추천 피드와 도메인 데이터를 조합해 제공하는 하이브리드 아키텍처 검토.  
  - **동네 친구 제안**: 위치 정보(Distance Badge)와 견종 유사도를 결합한 맞춤형 친구 추천 서비스.

### 인프라

- **인증 및 세션 고도화**: Redis를 활용한 Refresh Token 관리 및 보안 강화를 위한 토큰 블랙리스트 시스템 구축.
- **분산 환경 최적화**: 멀티 인스턴스 환경에서 Redis 클러스터를 통한 인증 상태 일관성 유지 및 Stateless 아키텍처 준수.
- **고가용성 확보**: 로드밸런서(ALB)를 통한 수평 확장(Scale-out) 대응 및 SSL/헬스체크 기반의 안정적인 라우팅.
- **성능 가속**: 트래픽 증가에 따른 CloudFront(CDN) 도입 및 메시지 큐(SQS/Kafka)를 활용한 시스템 간 결합도 완화.

---

## 문서

| 문서 | 설명 |
|------|------|
| [architecture.md](docs/architecture.md) | 요청 생명주기, DB Master/Slave·READ ONLY, 인증·보안, 데이터 정합성, 성능 최적화 |
| [api-codes.md](docs/api-codes.md) | API 응답 코드와 HTTP 상태 코드 매핑 |
| [infrastructure-reliability-design.md](docs/infrastructure-reliability-design.md) | 인프라·신뢰성 설계 (Redis Fail-open 등) |
| [puppytalkdb.sql](docs/puppytalkdb.sql) | 참고용 DDL (수동 테이블 생성 시) |
| [clear_db.sql](docs/clear_db.sql) | DB 데이터만 비우기 (테이블 유지, 시퀀스 리셋) |
