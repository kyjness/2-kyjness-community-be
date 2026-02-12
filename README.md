# PuppyTalk API

강아지 커뮤니티 서비스를 위한 백엔드 API 서버입니다.  
회원가입, 게시글, 댓글, 좋아요 등 커뮤니티 기능을 제공하며, 웹/앱 프론트엔드에서 이 API를 호출해 사용합니다.

---

## 기능

| 기능 | 설명 |
|------|------|
| **인증 (Auth)** | 회원가입, 로그인, 로그아웃. 로그인 시 쿠키에 세션 저장, 이후 요청에 쿠키 포함. 비밀번호는 bcrypt 암호화 |
| **사용자 (Users)** | 프로필 조회·수정, 비밀번호 변경, 프로필 사진 업로드. `/users/me` 경로 |
| **게시글 (Posts)** | 작성·조회·수정·삭제, 이미지 첨부. 목록은 페이지 단위 조회 |
| **댓글 (Comments)** | 게시글별 댓글 작성·조회·수정·삭제 |
| **좋아요 (Likes)** | 게시글 좋아요 추가·취소 |

---

## 기술 스택

| 구분 | 기술 |
|------|------|
| **언어** | Python 3.8+ |
| **프레임워크** | FastAPI |
| **DB** | MySQL |
| **검증** | Pydantic |
| **암호화** | bcrypt (비밀번호) |

---

## 실행 방법

### 1. 사전 준비

- **Python 3.8 이상** 설치
- **MySQL** 설치·실행 후 `puppytalk` DB 생성 및 테이블 생성

```bash
mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS puppytalk;"
mysql -u root -p puppytalk < docs/puppyytalkdb.sql
```

테이블 관계는 `docs/erd.png`를, DDL은 `docs/puppyytalkdb.sql`을 참고합니다.

### 2. 가상환경 및 패키지

```bash
cd 2-kyjness-community-be
python -m venv venv

# 활성화
# Windows CMD:        venv\Scripts\activate
# Windows PowerShell: .\venv\Scripts\Activate.ps1
# Git Bash:           source venv/Scripts/activate

pip install .
```

테스트까지 포함: `pip install ".[dev]"`

### 3. 환경 변수

**앱이 읽는 파일은 루트의 `.env` 하나뿐입니다.** 저장소에는 견본인 `.env.example`만 올라가며, 로컬/배포 시 `.env.example`을 복사해 `.env`로 저장한 뒤 값을 채우면 됩니다.

루트에 `.env`를 생성합니다 (`.env.example`을 복사한 뒤 값을 채웁니다). MySQL에는 `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`을 사용합니다.

| 변수 | 용도 |
|------|------|
| `HOST`, `PORT`, `DEBUG` | 서버 설정 |
| `CORS_ORIGINS` | 프론트 주소 (쉼표 구분, credentials 시 `*` 불가) |
| `SESSION_EXPIRY_TIME` | 세션 유효 시간(초) |
| `RATE_LIMIT_WINDOW`, `RATE_LIMIT_MAX_REQUESTS` | Rate limiting (추후 미들웨어에서 사용 시) |
| `MAX_FILE_SIZE`, `ALLOWED_IMAGE_TYPES` | 파일 업로드 |
| `BE_API_URL` | API 기본 URL (local 저장 시 이미지 URL 접두사) |
| `STORAGE_BACKEND` | `local`(기본) 또는 `s3`. 배포 시 S3 권장 |
| `S3_BUCKET_NAME`, `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | S3 사용 시 필수 |
| `S3_PUBLIC_BASE_URL` | S3 공개 URL 접두사(선택). 비우면 버킷 기본 URL 사용. CloudFront 사용 시 여기 설정 |
| `LOG_LEVEL` | 로그 레벨: `DEBUG`, `INFO`, `WARNING`, `ERROR` (기본 `INFO`) |
| `LOG_FILE_PATH` | 비우면 콘솔만. 경로 지정 시 해당 파일로 로테이팅 로그 기록 (예: `logs/app.log`) |

**배포 시 반드시 수정할 항목** (`.env.example`에 `# [배포 시 수정]` 표시됨)

| 변수 | 배포 시 설정 |
|------|--------------|
| `DEBUG` | `False` |
| `CORS_ORIGINS` | 실제 프론트엔드 URL(쉼표 구분) |
| `BE_API_URL` | 실제 API 서버 URL (이미지·파일 링크에 사용) |
| `STORAGE_BACKEND` | `s3` 권장 (로컬은 `local`) |
| `S3_BUCKET_NAME`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` 등 | S3 사용 시 실제 값 입력 |

### 4. 서버 실행

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

---

## 아키텍처

### 1. 전체 흐름

```
[프론트엔드 / 클라이언트]  HTTP 요청 (JSON body, Cookie)
    │
    ▼
┌──────────────────────────────────────────────────────────────────────┐
│  백엔드 (FastAPI)                                                     │
│                                                                      │
│  ① Lifespan (앱 시작)     → init_database() : DB 연결 확인            │
│                                                                      │
│  ② 미들웨어 (요청 진입, 역순 적용)                                    │
│     └─ CORS → Origin 검사, credentials 허용                           │
│     └─ add_security_headers → X-Frame-Options, X-Content-Type-Options │
│                                                                      │
│  ③ 라우터 매칭           → /posts, /auth/login 등 URL·메서드 분기     │
│                                                                      │
│  ④ 의존성 (Depends)      → get_current_user(쿠키 → 세션 → user_id)    │
│                           → require_post_author (작성자 확인)          │
│                                                                      │
│  ⑤ Pydantic 검증         → PostCreateRequest 등 body 검증 → 400       │
│                                                                      │
│  ⑥ Route 핸들러          → posts_controller.create_post() 등          │
│                                                                      │
│  ⑦ Controller            → Model 호출, 응답 포맷 생성                  │
│                                                                      │
│  ⑧ Model                 → get_connection() → SQL 실행 → commit       │
│                           → autocommit=False, 명시적 commit           │
│                                                                      │
│  ⑨ 예외 핸들러           → IntegrityError, HTTPException → {code,data}│
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
    │
    ▼
HTTP 응답  { "code": "POST_UPLOADED", "data": { "postId": 1 } }
```

### 2. 계층 역할

| 계층 | 역할 |
|------|------|
| Lifespan | 서버 시작 시 DB 연결 확인 |
| Middleware | CORS, 기본 보안 헤더 |
| Router | URL·HTTP 메서드별 API 분기 |
| Dependencies | 인증(session_id), 권한 검사 |
| Schema | 요청 데이터 검증 (Pydantic) |
| Controller | 비즈니스 로직 처리 |
| Model | SQL 실행 및 트랜잭션 관리 |
| Exception Handler | 에러 응답 포맷 통일 |

### 3. 인증·응답

- **인증**: 로그인 시 `session_id`를 Set-Cookie로 전달. 이후 요청 시 브라우저가 자동으로 쿠키 포함.
- **응답**: 성공·실패 모두 `{ "code": "문자열", "data": ... }` 형식으로 통일.

### 4. 요청 처리 예시 (게시글 작성)

- 인증: Cookie의 `session_id`로 사용자 식별
- 검증: Pydantic 스키마로 요청 body 검증
- 처리: Controller → Model → DB 트랜잭션
- 응답: `{ "code": "POST_UPLOADED", "data": { "postId": 5 } }`

---

## 폴더 구조

```
2-kyjness-community-be/
│
├── app/
│   ├── core/                      # 여러 도메인에서 공통으로 쓰는 코드
│   │   ├── __init__.py
│   │   ├── config.py              # .env에서 읽어오는 설정값 (HOST, PORT, DB_* 등)
│   │   ├── database.py            # MySQL 연결 (get_connection, init_database)
│   │   ├── dependencies.py        # 인증·권한 의존성 (get_current_user, require_post_author 등)
│   │   ├── exception_handlers.py  # 예외 처리 (RequestValidationError, HTTPException → {code, data} 변환)
│   │   ├── file_upload.py         # 프로필/게시글 이미지·비디오 검증·저장·URL 생성
│   │   ├── response.py            # success_response, raise_http_error
│   │   └── validators.py          # 비밀번호/닉네임/URL 형식 검증 (DTO에서 사용)
│   │
│   ├── auth/                      # 인증 (회원가입, 로그인, 로그아웃)
│   │   ├── auth_route.py          # POST /auth/signup, /login, /logout, GET /auth/me
│   │   ├── auth_controller.py     # signup, login, logout, get_me
│   │   ├── auth_model.py          # users, sessions 테이블 접근
│   │   └── auth_schema.py         # SignUpRequest, LoginRequest 등
│   │
│   ├── users/                     # 사용자 프로필
│   │   ├── users_route.py         # GET/PATCH/DELETE /users/me, PATCH /users/me/password, POST /users/me/profile-image
│   │   ├── users_controller.py    # get_user, update_user, update_password, upload_profile_image
│   │   ├── users_model.py         # AuthModel 래핑 (닉네임/비밀번호/프로필 수정)
│   │   └── users_schema.py        # UpdateUserRequest, UpdatePasswordRequest, CheckUserExistsQuery
│   │
│   ├── posts/                     # 게시글
│   │   ├── posts_route.py         # GET/POST /posts, GET/PATCH/DELETE /posts/{id}, POST /posts/{id}/image, /posts/{id}/video
│   │   ├── posts_controller.py    # create_post, get_posts, get_post, update_post, delete_post, upload_post_image, upload_post_video
│   │   ├── posts_model.py         # posts, post_files 테이블 접근
│   │   └── posts_schema.py        # PostCreateRequest, PostUpdateRequest
│   │
│   ├── comments/                  # 댓글
│   │   ├── comments_route.py      # GET/POST /posts/{post_id}/comments, PATCH/DELETE /posts/{post_id}/comments/{comment_id}
│   │   ├── comments_controller.py # create_comment, get_comments, update_comment, delete_comment
│   │   ├── comments_model.py      # comments 테이블 접근
│   │   └── comments_schema.py     # CommentCreateRequest, CommentUpdateRequest
│   │
│   └── likes/                     # 좋아요
│       ├── likes_route.py         # POST/DELETE /posts/{post_id}/likes
│       ├── likes_controller.py    # create_like, delete_like
│       ├── likes_model.py         # likes 테이블 접근
│       └── likes_schema.py
│
├── docs/                          # 문서
│   ├── erd.png                    # 데이터베이스 ERD
│   └── puppyytalkdb.sql           # DB 테이블 생성 스크립트
│
├── main.py                        # 앱 진입점, lifespan, 미들웨어(CORS, 보안헤더), 라우터 등록
├── upload/                         # STORAGE_BACKEND=local 시 업로드 파일 저장 (실행 시 생성, git 제외)
│   ├── image/
│   │   ├── profile/                # 프로필 사진
│   │   └── post/                   # 게시글 이미지
│   └── video/
│       └── post/                   # 게시글 비디오
├── pyproject.toml                 # 의존성 패키지 목록
├── .env.example                   # 환경 변수 견본 (복사 → .env 로 저장 후 값 채우기)
├── .env                           # 환경 변수 (직접 생성, git 제외, 앱이 읽는 파일)
└── README.md
```

**도메인별 파일 역할**

| 파일 | 역할 |
|------|------|
| `*_route.py` | URL·메서드 라우팅, 의존성 주입 |
| `*_controller.py` | 비즈니스 로직 |
| `*_model.py` | DB 조회·저장 (SQL) |
| `*_schema.py` | 요청/응답 형식 (Pydantic) |

---

## 설정

### 환경 변수 (.env)

**앱은 `.env`만 로드합니다.** 저장소에는 `.env.example`(견본)만 올라가고, `.env`는 git에 올리지 않습니다. `.env.example`을 복사해 `.env`로 저장한 뒤 값을 채워 사용합니다. 배포 시에는 서버 또는 플랫폼 환경 변수에 같은 키로 설정하면 됩니다.

필수: DB 연결 정보, `CORS_ORIGINS`(프론트 주소).

### 배포 시 파일 저장 (S3)

기본값(`STORAGE_BACKEND=local`)은 프로젝트 내 `upload/image/`에 저장됩니다. 배포 시 서버 재시작·스케일 아웃 시 파일이 사라지거나 인스턴스마다 달라질 수 있으므로 **S3 사용을 권장**합니다.

- `.env`에 `STORAGE_BACKEND=s3` 설정 후 `S3_BUCKET_NAME`, `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`를 입력합니다.
- S3 버킷에서 해당 객체를 공개 읽기 허용(버킷 정책 또는 객체 ACL)하거나, CloudFront를 사용하면 `S3_PUBLIC_BASE_URL`에 CloudFront URL을 넣으면 됩니다.

### 프론트엔드 연동 (크로스 오리진)

프론트(예: http://localhost:5500)와 API(예: http://localhost:8000)가 **다른 주소**일 때:

1. **CORS_ORIGINS**에 프론트 URL 추가 (예: `http://localhost:5500`)
2. **API 요청 시 credentials 포함**  
   - `fetch`: `credentials: 'include'`  
   - `axios`: `withCredentials: true`
3. 로그인 성공 시 `session_id`를 Set-Cookie로 전달 → 이후 요청에 브라우저가 자동으로 쿠키 포함

---

## 문제 해결

| 현상 | 확인 사항 |
|------|-----------|
| DB 연결 실패 | 1) MySQL 실행 여부 2) `.env` DB 설정 3) `puppytalk` DB·테이블 생성 여부 |
| CORS 에러 | `CORS_ORIGINS`에 프론트 주소(포트 포함)가 들어갔는지 |
| 로그인 안 됨 | 1) 프론트에서 `credentials: 'include'` 사용 여부 2) 같은 도메인/서브도메인인지(CORS credentials 제한) |

---

## 확장 전략

- **DB 샤딩**: user_id/post_id 기준으로 테이블 분산
- **읽기 레플리카**: 쓰기 Primary, 조회 Replica 분리
- **캐시 (Redis)**: 자주 조회되는 게시글·댓글 캐싱
- **메시지 큐**: 이미지 업로드·알림 등 비동기 작업 (Celery/RQ + Redis)
- **API 게이트웨이**: Kong, Nginx로 인증·로드밸런싱·레이트리밋 중앙화
