# PuppyTalk Backend

**PuppyTalk**는 반려견을 키우는 사람들을 위한 커뮤니티 서비스의 백엔드로, **FastAPI** 기반의 **RESTful API**로 설계·구현된 서버입니다.

**제공 기능**

- **인증** — 회원가입·로그인·로그아웃 (JWT Access/Refresh, Refresh Token은 Redis·HttpOnly 쿠키)
- **사용자** — 프로필 조회·수정, 비밀번호 변경
- **게시글** — CRUD, 무한 스크롤 피드, 조회수·좋아요
- **댓글** — 페이지네이션, 작성자 검증
- **미디어** — 이미지 업로드 (로컬/S3), 회원가입 전 프로필 첨부

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
| **DB** | MySQL (pymysql) |
| **ORM** | SQLAlchemy 2.x |
| **마이그레이션** | Alembic |
| **스토리지** | 로컬 파일 / AWS S3 (boto3) |
| **검증** | Pydantic v2 |
| **인증** | JWT (PyJWT), bcrypt (비밀번호), Redis (Refresh Token·Rate Limit) |

---

## 폴더 구조

- **루트** — 실행·배포 설정, 테스트·문서를 두며, 애플리케이션 코드는 **app/** 패키지에 둡니다.
- **app/** — 공통·인프라와 기능 단위 **domain**으로 구분합니다.
- **도메인** — **router**(엔드포인트) → **controller**(비즈니스 로직) → **model**(DB 접근) → **schema**(요청·응답 DTO) 흐름으로 처리합니다.

```
2-kyjness-community-be/
├── app/
│   ├── api/
│   │   ├── dependencies/    # 인증·DB 세션·권한·쿼리 파싱 (통합 DI)
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
│   │   ├── auth/            # 로그인·로그아웃·회원가입
│   │   ├── users/           # 프로필 조회·수정
│   │   ├── media/           # 이미지 업로드
│   │   ├── posts/           # 게시글 CRUD·피드·좋아요
│   │   └── comments/        # 댓글 CRUD
│   └── main.py              # 앱 진입점·미들웨어·라우터 등록
├── docs/                    # 상세 문서·참고용 SQL
├── test/                    # pytest
├── alembic.ini              # Alembic 설정 (DB URL 등)
├── pyproject.toml            # Poetry 의존성·스크립트 정의
├── poetry.lock               # 의존성 잠금 (poetry install 시 참조)
├── Dockerfile                # 프로덕션 이미지 빌드
└── .env.example              # 환경 변수 예시 (복사 후 .env.development,.env.production 으로 사용)
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
| **피드·댓글** | 게시글은 무한 스크롤, 댓글은 페이지네이션으로 UX·참조성을 맞춤. |
| **인증** | JWT Access/Refresh. Refresh는 Redis·HttpOnly 쿠키. 만료 시 TOKEN_EXPIRED로 프론트에서 Refresh 호출 유도. |
| **조회수** | GET 멱등성 유지 위해 전용 POST 엔드포인트로 분리. |
| **이미지** | 미리 업로드 후 본문/가입 연결. 가입 전 이미지는 signupToken·ref_count로 소유·참조 관리. |
| **DB 읽기/쓰기 분리** | WRITER/READER 분리·풀 튜닝으로 조회 부하 분산. |
| **트랜잭션** | 복수 모델 조작 시 controller에서 with db.begin()로 원자성 보장. |
| **요청 추적** | contextvars·RequestIdFilter로 로그에 request_id 자동 포함. |
| **Rate Limit** | Redis Fixed Window, 경로별 제한. Redis 장애 시 Fail-open. |

---

## 로컬 실행 방법

로컬에서 서버를 띄우려면 **Python 3.8+**, **MySQL 8.x**가 필요합니다. Redis는 선택이며, 없으면 Rate Limit이 비활성(Fail-open)됩니다.

### 1. 저장소 클론 및 패키지 설치

```bash
cd 2-kyjness-community-be
poetry install
```

### 2. 환경 변수 설정

[`.env.example`](.env.example)을 복사한 뒤 DB·JWT·Redis 등 필수 값을 채웁니다.

```bash
cp .env.example .env.development
# .env.development 편집 (DB_*, JWT_SECRET_KEY, REDIS_URL 등)
```

### 3. DB 생성 및 스키마 적용

```bash
mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS puppytalk CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
mysql -u root -p puppytalk < docs/puppytalkdb.sql
poetry run alembic stamp head  # DB가 이미 최신일 때 버전만 맞춤
poetry run alembic upgrade head # 최신 마이그레이션까지 적용
```

**DB 데이터만 비우기(초기화)** 

```bash
mysql -u root -p puppytalk < docs/clear_db.sql
```

### 4. 서버 실행

```bash
poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 5. 테스트 (선택)

```bash
poetry run pytest test/ -v
```

### 6. 린트·포맷 (Ruff)

```bash
poetry run ruff check . --fix    # 린트 자동 수정 (미사용 import 등)
poetry run ruff format .         # 코드 포맷
```

Docker·프로덕션 배포는 [PuppyTalk Infra](https://github.com/kyjness/2-kyjness-community-infra) 레포를 참고하면 됩니다.

---

## 확장 전략

### 기능 (요약: 검색·신고·알림·관리자·이메일 인증·BackgroundTasks 등)

- **검색/필터**: 견종·지역·태그로 게시글 검색
- **신고/차단**: 게시글 신고, 사용자 차단(차단한 사람 글 숨김)
- **알림**: 내 글에 댓글 달리면 알림 리스트
- **관리자**: 신고 누적 글 숨김, 유저 제재(ROLE). 추후 `get_current_user` → `get_current_active_user`(활성만) → `get_admin_user`(관리자만) 의존성 체인·Redis 사용자 상태 캐싱 검토
- **탈퇴 vs 정지**: `deleted_at`(탈퇴·로그인 불가), `is_active`/`status`(정지·휴면) 구분 시 정지 유저 별도 처리
- **비밀번호 찾기·이메일 인증**: 미구현, 추후 auth·users 도메인 확장
- **BackgroundTasks**: 축하 메일·로그 저장 등 응답과 무관한 작업은 FastAPI BackgroundTasks; 무거운 작업은 Celery 등 워커 검토
- **Pydantic V2**: 라우터에서 `response_model=ApiResponse` 등으로 응답 스키마 지정해 사용 중. 추후 Redis·큐 등 JSON 파싱 구간에는 `model_validate_json` 적용 검토

### 인프라 (요약: Redis 클러스터·로드밸런서·CDN·메시지 큐)

- **인증**: JWT·Redis(Refresh) 적용됨. 확장 시 블랙리스트·토큰 폐기 검토
- **세션/토큰**: 멀티 인스턴스·리전 시 Redis 클러스터로 인증 상태 일관 유지
- **로드밸런서**: 수평 확장 시 ALB/NLB로 라우팅·헬스체크·SSL, 백엔드는 무상태에 집중
- **기타**: CloudFront/CDN·캐시·메시지 큐(SQS/Kafka)는 트래픽에 따라 단계 도입

---

## 문서

| 문서 | 설명 |
|------|------|
| [architecture.md](docs/architecture.md) | 요청 생명주기, DB Master/Slave·READ ONLY, 인증·보안, 데이터 정합성, 성능 최적화 |
| [api-codes.md](docs/api-codes.md) | API 응답 코드와 HTTP 상태 코드 매핑 |
| [infrastructure-reliability-design.md](docs/infrastructure-reliability-design.md) | 인프라·신뢰성 설계 (Redis Fail-open 등) |
| [puppytalkdb.sql](docs/puppytalkdb.sql) | 참고용 DDL (수동 테이블 생성 시) |
| [clear_db.sql](docs/clear_db.sql) | DB 데이터만 비우기 (테이블 유지, AUTO_INCREMENT 초기화) |
