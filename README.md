# PuppyTalk Backend

**PuppyTalk**는 반려견을 키우는 사람들을 위한 커뮤니티 서비스의 백엔드로, **FastAPI** 기반의 **RESTful API**로 설계·구현된 서버입니다. 

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

**app/** 단일 패키지 아래에 공용 레이어(api·common·core·db·infra)와 **domain/** 기능 도메인이 계층화되어 있습니다. 각 도메인은 **router → service → model → schema** 순으로 요청이 흐르며, 엔드포인트·비즈니스 로직·데이터 접근·DTO가 명확히 분리된 구조를 갖습니다.

```
2-kyjness-community-be/
├── app/                                    # 백엔드 패키지 루트
│   ├── main.py                             # FastAPI 앱 생성, 미들웨어·라우터 등록, 진입점
│   ├── api/                                # HTTP 레이어
│   │   ├── v1.py                           # /v1 prefix 라우터 묶음
│   │   └── dependencies/                   # 인증, DB 세션(get_master_db/get_slave_db), 권한, 쿼리 파싱
│   ├── common/                             # API 코드·Enum·ApiResponse·validators·exceptions·로깅
│   ├── core/                               # config, security(JWT·비밀번호), exception_handlers, cleanup
│   │   └── middleware/                     # RequestId, ProxyHeaders, RateLimit, GZip, AccessLog, SecurityHeaders
│   ├── db/                                 # SQLAlchemy Base·엔진·세션·연결
│   │   └── alembic/                        # 마이그레이션 env, versions(리비전)
│   ├── domain/                             # 기능별 도메인 (router → service → model → schema)
│   │   ├── admin/                          # 관리자: 신고된 게시글·댓글 통합 목록, 블라인드/신고 무시/삭제, 유저 정지·해제
│   │   ├── auth/                           # 회원가입·로그인·로그아웃·리프레시
│   │   ├── comments/                       # 댓글 CRUD·페이지네이션
│   │   ├── dogs/                           # 강아지 프로필
│   │   ├── likes/                          # 게시글·댓글 좋아요
│   │   ├── media/                          # 이미지 업로드(로컬/S3), signupToken·ref_count
│   │   ├── posts/                          # 게시글 CRUD·피드·조회수
│   │   ├── reports/                        # 신고 접수(POST/COMMENT)·누적 Insert·자동 블라인드
│   │   └── users/                          # 프로필·비밀번호·탈퇴·차단
│   └── infra/                              # Redis(Refresh·RateLimit), storage(로컬/S3)
├── docs/                                   # 아키텍처·API 코드·인프라 설계 문서
├── alembic.ini                             # Alembic 설정(script_location 등)
├── pyproject.toml                         # Poetry 의존성·스크립트(poe run, migrate, test 등)
└── Dockerfile                              # 멀티스테이지 빌드·Gunicorn+Uvicorn
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
| **피드·댓글** | 게시글 무한 스크롤(has_more), 댓글 페이지네이션. |
| **인증** | JWT Access/Refresh. Refresh는 Redis·HttpOnly 쿠키, 멀티 디바이스(SADD/SREM). 만료 시 TOKEN_EXPIRED로 프론트 Refresh 유도. |
| **좋아요** | POST/DELETE 명시적 API. ON CONFLICT DO NOTHING + RETURNING으로 멱등·like_count 동기화. |
| **조회수** | GET 멱등 유지 위해 전용 POST `/view`. 인메모리 캐시(TTL·용량 한계)로 중복 방지, 추후 Redis 전환 가능. |
| **이미지** | 미리 업로드 후 본문/가입 연결. 가입 전 이미지는 signupToken·ref_count로 소유·참조 관리. |
| **DB 읽기/쓰기 분리** | get_master_db / get_slave_db, WRITER_DB_URL / READER_DB_URL 분리(확장성 고려). 트랜잭션은 서비스의 `async with db.begin():`으로만 관리. |
| **요청 추적** | 순수 ASGI RequestIdMiddleware로 UUID4 발급·scope.state·X-Request-ID 응답 헤더(4xx/5xx 포함). contextvars·RequestIdFilter로 로그에 request_id 자동 포함. |
| **에러 응답** | 전역 예외 핸들러로 모든 에러를 { code, message, data } 형식 통일. 500 시 클라이언트에는 스택/쿼리 노출 없이 마스킹 메시지만 반환. |
| **API 응답 code** | `ApiResponse.code`는 `ApiCode` enum 또는 str. 라우터에서는 `ApiCode.OK` 등 enum만 전달하며, `BaseSchema`의 `use_enum_values=True`로 직렬화 시 문자열로 내려감. |
| **신고** | 신고는 항상 새 행(Insert) 누적. 동일 유저 재신고도 허용. 신고 무시 시에만 `reports` soft delete·글/댓글 `report_count` 초기화. `reports` 테이블에는 `status` 컬럼 없음, `target_type`은 TargetType(POST/COMMENT). |
| **응답 압축** | GZip 미들웨어(minimum_size=1KB)로 1KB 이상 응답만 gzip 압축. |
| **Rate Limit** | Redis Fixed Window, 경로별 제한. Redis 장애 시 Fail-open. |

---

## 로컬 실행 방법

로컬에서 서버를 띄우려면 **Python 3.8+**, **PostgreSQL**이 필요합니다. Redis는 선택이며, 없으면 Rate Limit이 비활성(Fail-open)됩니다.

### 1. 저장소 클론 및 패키지 설치

**Poetry**가 가상환경을 자동으로 생성·사용하므로 별도 `python -m venv`는 필요 없습니다. (`poetry run`으로 실행하거나, 가상환경 안에서 쓰려면 `poetry shell` 입력.)

```bash
cd 2-kyjness-community-be
poetry lock    # pyproject.toml 변경 시 lock 파일 갱신
poetry install
```

### 2. 환경 변수 설정

[`.env.example`](.env.example)을 복사한 뒤 DB·JWT·Redis 등 필수 값을 채웁니다.

```bash
cp .env.example .env
# .env 편집: DB_PASSWORD, JWT_SECRET_KEY, REDIS_URL 등. Docker 사용 시 DB_HOST=postgres, 로컬 PostgreSQL이면 DB_HOST=localhost
```

### 3. DB 생성 및 스키마 적용

```bash
createdb -U postgres puppytalk

poetry run poe migrate
```

**DB 데이터만 비우기(초기화)** 

```bash
psql -U postgres -d puppytalk -f docs/clear_db.sql
```

### 4. 서버 실행

```bash
poetry run poe run
```

### 5. 테스트

```bash
poetry run poe test
```

### 6. 개발 도구 (Ruff, Pyright, pip-audit)

**수정/적용용** (코드를 직접 변경):

```bash
poetry run poe quality   # lint(--fix) + format 한 방에
poetry run poe lint      # ruff check . --fix (문법·미사용 import 등)
poetry run poe format    # ruff format . (포맷팅)
```

**검사용** (코드 수정 없이 리포트만, CI/CD용):

```bash
poetry run poe check        # lint-check + format-check + typecheck + audit (하나라도 실패 시 중단)
poetry run poe lint-check   # ruff check . (자동 수정 없음)
poetry run poe format-check # ruff format . --check (포맷 검사만)
poetry run poe typecheck    # pyright (타입 체크)
poetry run poe audit        # pip-audit (의존성 보안 취약점 스캔)
```

**보안·의존성 스캔**: `poe audit`은 현재 가상환경에 설치된 패키지(FastAPI, SQLAlchemy 등)를 [PyPA 알려진 취약점 DB](https://github.com/pypa/advisory-database) 기준으로 검사합니다. 취약 패키지가 있으면 목록과 조치 방법을 출력하고 종료 코드 1로 끝납니다.

### 7. 관리자 기능 (Admin)

관리자 전용 API(`/v1/admin/*`)와 프론트 대시보드(`/admin/dashboard`)는 **role이 `ADMIN`인 유저만** 사용할 수 있습니다.

1. **관리자 계정 만들기**  
   DB에서 해당 유저의 `role`을 `ADMIN`으로 변경합니다.

   ```sql
   UPDATE users SET role = 'ADMIN' WHERE id = 1;  -- 원하는 user id
   ```

2. **프론트에서 사용**  
   관리자 계정으로 로그인하면 헤더의 **프로필 드롭다운**에 **관리자 대시보드** 링크가 표시됩니다. 해당 링크로 이동하면 신고된 게시글·댓글 통합 목록과 [블라인드 해제/처리], [유저 정지/해제], [글 삭제]/[댓글 삭제], [신고 무시] 버튼을 사용할 수 있습니다.

Docker·프로덕션 배포는 [PuppyTalk Infra](https://github.com/kyjness/2-kyjness-community-infra) 레포를 참고하면 됩니다.

---

## 확장 전략

### 기능

- **콘텐츠 구조화 및 검색 최적화**: 카테고리(Category) 기반 분류와 해시태그(Hashtag) 인덱싱을 도입하여 게시글 탐색 편의성 및 검색 정확도 강화.
- **실시간 소통(1:1 DM)**: WebSocket 기반의 실시간 메시징 시스템 구축 및 대화 내역의 영속성(Persistence) 관리.
- **실시간 알림**: 댓글 및 상호작용 발생 시 실시간 알림 리스트 제공.
- **비동기 태스크**: FastAPI BackgroundTasks를 활용한 가벼운 로그 기록부터, Celery 기반의 대용량 비동기 작업 처리까지 단계적 확장.
- **데이터 무결성**: Pydantic V2의 `model_validate_json` 등을 활용해 Redis/Queue와의 데이터 교환 시 타입 검증·성능 최적화 (추후 적용 예정).

### AI

- **RAG 기반 '우리 아이 건강 척척박사'**  
  커뮤니티 지식 베이스와 LLM을 결합한 실시간 스트리밍(StreamingResponse) 챗봇 구축. Vercel AI SDK를 활용한 인터랙티브한 UI와 Context Window 최적화를 통한 답변 정확도 향상.

- **하이브리드 추천 시스템 (GraphQL Hybrid)**  
  - **지능형 피드**: 사용자 행동 로그 및 클릭 기반의 무한 스크롤 추천 피드 구현.  
  - **데이터 최적화**: 추천·복합 쿼리 증가 시 전송 효율을 위해 GraphQL을 부분 도입하여, 추천 피드와 도메인 데이터를 조합해 제공하는 하이브리드 아키텍처 검토.  
  - **동네 친구 제안**: 위치 정보(Distance Badge)와 견종 유사도를 결합한 맞춤형 친구 추천 서비스.

### 인프라

- **전역 캐싱 전략**: Redis를 활용해 DB 부하를 분산하고, 자주 조회되는 카테고리 메타데이터 및 실시간 인기 해시태그 랭킹의 응답 속도 최적화.
- **인증 및 세션 고도화**: Redis를 활용한 Refresh Token 관리 및 보안 강화를 위한 토큰 블랙리스트 시스템 구축.
- **분산 환경 최적화**: 멀티 인스턴스 환경에서 Redis 클러스터를 통한 인증 상태 일관성 유지 및 Stateless 아키텍처 준수.
- **고가용성 확보**: 로드밸런서(ALB)를 통한 수평 확장(Scale-out) 대응 및 SSL/헬스체크 기반의 안정적인 라우팅.
- **성능 가속**: 백엔드에 GZip 미들웨어(1KB 이상 응답 압축) 적용됨. 트래픽 증가 시 CloudFront(CDN)·Brotli 등 추가 적용 및 메시지 큐(SQS/Kafka)를 활용한 시스템 간 결합도 완화 검토.



---

## 문서

| 문서 | 설명 |
|------|------|
| [architecture.md](docs/architecture.md) | 요청 생명주기, 미들웨어, DB, 인증·보안, 전역 에러 포맷, 데이터 정합성, N+1·FK 인덱스 등 성능 최적화 |
| [api-codes.md](docs/api-codes.md) | API 응답 코드와 HTTP 상태 코드 매핑 |
| [infrastructure-reliability-design.md](docs/infrastructure-reliability-design.md) | 인프라·신뢰성 설계 (Redis Fail-open 등) |
| [puppytalkdb.sql](docs/puppytalkdb.sql) | 참고용 DDL (수동 테이블 생성 시) |
| [clear_db.sql](docs/clear_db.sql) | DB 데이터만 비우기 (테이블 유지, 시퀀스 리셋) |
