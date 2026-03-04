# PuppyTalk Backend

**PuppyTalk**는 반려견을 키우는 사람들을 위한 커뮤니티 서비스의 백엔드로, **FastAPI** 기반의 **RESTful API**로 설계·구현된 서버입니다.
커뮤니티 운영에 필요한 아래 핵심 기능들을 제공합니다.

- **인증** — 회원가입·로그인·로그아웃 (JWT Access/Refresh, Refresh Token은 Redis·HttpOnly 쿠키)
- **사용자** — 프로필 조회·수정, 비밀번호 변경
- **게시글** — CRUD, 무한 스크롤 피드, 조회수·좋아요
- **댓글** — 페이지네이션, 작성자 검증
- **미디어** — 이미지 업로드 (로컬/S3), 회원가입 전 프로필 첨부

- **프론트엔드**: [PuppyTalk Frontend](https://github.com/kyjness/2-kyjness-community-fe)
- **인프라·배포**: [PuppyTalk Infra](https://github.com/kyjness/2-kyjness-community-infra)

---

## 기술 스택

| 구분 | 기술 |
|------|------|
| **언어** | Python 3.8+ |
| **패키지 관리** | Poetry 2.x |
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
│   │   ├── response.py      # 공통 응답 포맷·에러 처리
│   │   ├── validators.py    # 닉네임·비밀번호 형식 검증
│   │   └── logging_config.py # 로깅 설정
│   ├── core/
│   │   ├── config.py        # 환경 변수 설정
│   │   ├── middleware/      # 프록시·요청 ID·접근 로그·속도 제한·보안 헤더
│   │   ├── security.py      # JWT Access/Refresh 토큰 생성·검증, 비밀번호 해시
│   │   ├── storage.py       # 로컬/S3 파일 업로드
│   │   ├── exception_handlers.py  # 전역 예외 → 공통 응답 형식
│   │   └── cleanup.py       # 만료 세션·미사용 이미지 정리
│   ├── db/                  # 엔진·세션·연결·Base
│   ├── domain/
│   │   ├── auth/            # 로그인·로그아웃·회원가입
│   │   ├── users/           # 프로필 조회·수정
│   │   ├── media/           # 이미지 업로드
│   │   ├── posts/           # 게시글 CRUD·피드·좋아요
│   │   └── comments/        # 댓글 CRUD
│   └── main.py              # 앱 진입점·미들웨어·라우터 등록
├── alembic/                 # DB 스키마 마이그레이션 스크립트
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
poetry run alembic stamp head
```

### 4. 서버 실행

```bash
poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

실행 후 **Swagger**: http://localhost:8000/docs · **ReDoc**: http://localhost:8000/redoc · **Health**: http://localhost:8000/health

### 5. 테스트 (선택)

```bash
poetry run pytest test/ -v
```

Docker·프로덕션 배포는 [PuppyTalk Infra](https://github.com/kyjness/2-kyjness-community-infra) 레포를 참고하면 됩니다.

---

## 확장 전략

### 기능

- **검색/필터**: 견종·지역·태그로 게시글 검색
- **신고/차단**: 게시글 신고, 사용자 차단 (차단한 사람 글 숨김)
- **알림**: 내 글에 댓글 달리면 알림 리스트
- **관리자**: 신고 누적 글 숨김, 유저 제재 (ROLE 기반) — 미도입. 추후 도입 시 아래 인증·권한 확장 패턴 적용.
- **인증·권한 확장 (실무 패턴)**:  
  - **탈퇴 vs 정지 구분**: `deleted_at`은 탈퇴(Soft Delete, 로그인 불가). `is_active`는 이메일 인증 등(로그인은 되나 기능 제한). `status`(정상/정지/휴면) 도입 시 정지 유저는 "관리자에게 문의" 등 별도 처리.  
  - **의존성 체인**: `get_current_user`(로그인만) → `get_current_active_user`(활성만, `is_active` 체크) → `get_admin_user`(관리자만, `role` 체크). API마다 필요한 수준만 `Depends(...)`로 지정하면 됨.  
  - **Redis 캐싱**: 매 요청마다 DB로 사용자 상태 조회 대신, 사용자 상태를 Redis에 짧게(예: 5분) 캐싱해 `get_current_user` 단계에서 활용하면 고트래픽 시 부하 감소.
- **비밀번호 찾기·이메일 인증** (Future Scope): 이메일 재설정 링크 발송, 가입 시 이메일 인증 — 현재 미구현, 추후 도입 시 auth·users 도메인 확장 예정
- **BackgroundTasks**: 회원가입 후 축하 메일 발송, 로그·감사 기록 저장 등 응답과 무관한 작업은 FastAPI `BackgroundTasks`로 응답 즉시 반환 후 백그라운드 실행 검토. (가벼운 I/O 위주 권장, 무거운 CPU 연산은 Celery 등 별도 워커 고려)
- **Pydantic V2 model_validate_json**: Redis·메시지 큐·파일 등에서 **JSON 문자열**을 받아 Pydantic 모델로 만들 때 `MyModel.model_validate_json(json_str)` 사용 시 기존 `json.loads`+생성자 대비 파싱 성능 이점 (V2 Rust 기반 파서). 대용량·고빈도 파싱 구간에 적용하면 좋음.
- **response_model로 필터링**: ORM을 직접 반환하는 라우트를 둘 때(예: `return db_user`) 해당 라우트에 `response_model=UserPublic`처럼 **비밀번호 등 미포함 스키마**를 지정하면, FastAPI가 응답 직렬화 시 해당 필드만 내보내서 민감 정보 노출을 막는 안전장치가 됨.

### 인프라 (규모 확대 시)

- **인증**: 이미 JWT·Redis(Refresh Token 저장) 적용됨. 확장 시 블랙리스트·토큰 폐기 정책 등 검토.
- **세션/토큰 저장소**: 멀티 인스턴스·멀티 리전에선 **Redis 클러스터**를 토큰 저장소로 사용해 일관된 인증 상태 유지.
- **로드밸런서**: EC2/컨테이너 인스턴스를 수평 확장할 때 ALB/NLB 등 **로드밸런서 앞단 배치**로 라우팅·헬스체크·SSL 종료를 맡기고, 백엔드는 무상태 API 서버에 집중시킵니다.
- **기타**: CloudFront/CDN, 캐시 계층(Redis), 메시지 큐(SQS/Kafka 등)는 트래픽·요구사항에 따라 단계적으로 도입합니다.

---

## 문서

| 문서 | 설명 |
|------|------|
| [architecture.md](docs/architecture.md) | 요청 생명주기, DB Master/Slave·READ ONLY, 인증·보안, 데이터 정합성, 성능 최적화 |
| [api-codes.md](docs/api-codes.md) | API 응답 코드와 HTTP 상태 코드 매핑 |
| [puppytalkdb.sql](docs/puppytalkdb.sql) | 참고용 DDL (수동 테이블 생성 시) |
| [jwt-auth-frontend.md](docs/jwt-auth-frontend.md) | JWT 연동 (Next.js + Axios, Access/Refresh·TOKEN_EXPIRED 처리) |
