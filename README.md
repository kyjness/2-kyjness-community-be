# PuppyTalk API

강아지 커뮤니티 서비스를 위한 백엔드 API 서버입니다.  
회원가입, 게시글, 댓글, 좋아요 등 커뮤니티 기능을 제공하며, 웹/앱 프론트엔드에서 이 API를 호출해 사용합니다.

---

## 이 API가 하는 일

| 기능 | 설명 |
|------|------|
| **인증 (Auth)** | 회원가입, 로그인, 로그아웃. 로그인하면 쿠키에 세션 정보가 저장되고, 이후 요청에 이 쿠키가 함께 전달됩니다. 비밀번호는 bcrypt로 암호화해 저장합니다. |
| **사용자 (Users)** | 로그인한 사용자 본인의 프로필 조회·수정, 비밀번호 변경, 프로필 사진 업로드. API 경로는 `/users/me` 입니다. |
| **게시글 (Posts)** | 게시글 작성·조회·수정·삭제, 게시글에 이미지 첨부. 목록은 페이지 단위로 조회합니다. |
| **댓글 (Comments)** | 게시글에 댓글 작성·조회·수정·삭제 |
| **좋아요 (Likes)** | 게시글에 좋아요 추가·취소 |

---

## 사용 기술

- **Python 3.8+** – 서버 개발 언어
- **FastAPI** – HTTP API를 쉽게 만들 수 있는 웹 프레임워크
- **MySQL** – 회원·게시글·댓글·좋아요 데이터를 저장하는 데이터베이스
- **Pydantic** – 요청/응답 데이터 형식 검증
- **bcrypt** – 비밀번호 암호화

## 실행 전 준비

- **Python 3.8 이상**이 설치되어 있어야 합니다.
- **MySQL**이 설치·실행 중이어야 합니다. `puppytalk` 데이터베이스와 필요한 테이블(users, posts, comments 등)을 미리 만들어 두어야 합니다. (DBeaver 등 DB 도구로 생성)

---

## ERD (데이터베이스 구조)

![ERD](docs/erd.png)

테이블 관계는 `docs/erd.png`를 참고하세요.

---

## 요청이 처리되는 흐름

```
[프론트엔드/클라이언트] 
    → CORS 체크 (다른 도메인에서 오는 요청 허용 여부)
    → 보안 헤더 추가
    → Route (URL에 따른 분기) → Controller (비즈니스 로직) → Model (DB 접근)
    ← { "code": "성공코드", "data": 결과데이터 }
```

- **Route → Controller → Model**: URL 요청을 받아 라우트에서 분기하고, 컨트롤러에서 로직을 처리한 뒤, 모델을 통해 DB에 접근하는 구조입니다.
- **로그인 인증**: 로그인하면 `session_id`가 쿠키로 저장되고, 인증이 필요한 API는 이 쿠키를 확인해 누가 요청했는지 판단합니다.
- **응답 형식**: 성공·실패 모두 `{ "code": "문자열", "data": ... }` 형태로 통일됩니다.

---

## 폴더 구조

```
.
├── app/
│   ├── core/                      # 여러 도메인에서 공통으로 쓰는 코드
│   │   ├── __init__.py
│   │   ├── config.py              # .env에서 읽어오는 설정값 (HOST, PORT, DB_* 등)
│   │   ├── database.py            # MySQL 연결 (get_connection, init_database)
│   │   ├── dependencies.py        # 인증·권한 의존성 (get_current_user, require_post_author 등)
│   │   ├── exception_handlers.py  # 예외 처리 (RequestValidationError, HTTPException → {code, data} 변환)
│   │   ├── file_upload.py         # 프로필/게시글 이미지 검증·저장·URL 생성
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
│   │   ├── posts_route.py         # GET/POST /posts, GET/PATCH/DELETE /posts/{id}, POST /posts/{id}/image
│   │   ├── posts_controller.py    # create_post, get_posts, get_post, update_post, delete_post, upload_post_image
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
├── public/                        # 업로드 이미지 저장 (실행 시 자동 생성)
│   ├── image/
│   │   ├── profile/               # 프로필 사진
│   │   └── post/                  # 게시글 이미지
│
├── docs/                          # 문서
│   └── erd.png                    # 데이터베이스 ERD
│
├── main.py                        # 앱 진입점, lifespan, 미들웨어(CORS, 보안헤더), 라우터 등록, StaticFiles(/public)
├── pyproject.toml                 # 의존성 패키지 목록
├── .env                           # 환경 변수 (직접 생성)
└── README.md
```

**각 도메인 파일 역할**

| 파일 | 역할 |
|------|------|
| `*_route.py` | URL과 HTTP 메서드에 따른 라우팅, 의존성 주입 |
| `*_controller.py` | 비즈니스 로직 처리 |
| `*_model.py` | DB 조회·저장 (SQL 실행) |
| `*_schema.py` | 요청/응답 데이터 형식 정의 (Pydantic) |

---

## 실행 방법

### 1. 패키지 설치

이 프로젝트 폴더에서 아래 명령을 실행합니다.

```bash
pip install -e ".[dev]"
```

### 2. 환경 변수 파일 만들기

프로젝트 **루트 폴더**(`main.py`가 있는 위치)에 `.env` 파일을 만들고, 아래 변수들을 설정합니다. 값은 환경에 맞게 수정하세요.

| 변수 | 설명 | 예시 |
|------|------|------|
| `HOST` | 서버가 바인딩할 주소 | 0.0.0.0 |
| `PORT` | 서버 포트 | 8000 |
| `DEBUG` | 디버그 모드 여부 | True |
| `CORS_ORIGINS` | API를 호출할 수 있는 프론트 주소들. 쉼표로 구분. credentials 사용 시 `*`는 사용할 수 없습니다. | http://localhost:3000,http://127.0.0.1:3000 |
| `SESSION_EXPIRY_TIME` | 세션 유효 시간(초) | 86400 (24시간) |
| `MAX_FILE_SIZE` | 파일 업로드 최대 크기(바이트) | 10485760 (10MB) |
| `ALLOWED_IMAGE_TYPES` | 허용 이미지 타입 | image/jpeg,image/jpg,image/png |
| `BE_API_URL` | 이 API 서버의 기본 URL (업로드된 파일 URL 생성에 사용) | http://localhost:8000 |
| `DB_HOST` | MySQL 호스트 | localhost |
| `DB_PORT` | MySQL 포트 | 3306 |
| `DB_USER` | MySQL 사용자명 | root |
| `DB_PASSWORD` | MySQL 비밀번호 | (본인 설정값) |
| `DB_NAME` | 사용할 DB 이름 | puppytalk |

### 3. 서버 실행

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

`--reload`는 코드 수정 시 자동으로 서버를 다시 실행하는 개발용 옵션입니다.

### 4. API 문서 보기

서버가 실행된 상태에서 아래 주소로 접속하면 API 목록과 사용법을 확인할 수 있습니다.

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

---

## 프론트엔드에서 이 API를 호출할 때 (크로스 오리진)

프론트엔드(예: http://localhost:3000)와 이 API 서버(예: http://localhost:8000)가 **서로 다른 주소/포트**일 때를 “크로스 오리진”이라고 합니다. 이 경우 아래를 지켜야 로그인·인증이 정상 동작합니다.

1. **CORS_ORIGINS**에 프론트엔드 URL을 넣어 두세요. (예: `http://localhost:3000`)
2. **API 요청 시 credentials 포함**
   - `fetch` 사용 시: `credentials: 'include'` 옵션 추가
   - `axios` 사용 시: `withCredentials: true` 설정
3. 로그인 성공 시 서버가 `session_id`를 **Set-Cookie**로 보내므로, 이후 요청에는 브라우저가 자동으로 이 쿠키를 붙여 보냅니다.
