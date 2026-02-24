# PuppyTalk API

강아지 커뮤니티 서비스를 위한 백엔드 API 서버입니다.  
회원가입, 로그인, 이미지 업로드(미디어), 게시글, 댓글, 좋아요 등 커뮤니티 기능을 제공하며, 웹/앱 프론트엔드에서 이 API를 호출해 사용합니다.

---

## 개요

### 기능

| 기능 | 설명 |
|------|------|
| **인증 (Auth)** | 회원가입(프로필 이미지 ID 지정 가능), 로그인, 로그아웃. 로그인 시 쿠키에 세션 저장, 이후 요청에 쿠키 포함. 비밀번호 bcrypt 암호화. 로그인 API 전용 rate limit(IP당 분당 5회) |
| **사용자 (Users)** | 프로필 조회·수정, 비밀번호 변경. `/users/me` 경로. 프로필 사진은 미리 미디어 업로드 후 `profileImageId`로 지정 |
| **미디어 (Media)** | 프로필·게시글용 이미지 업로드. POST `/images` (쿼리 `type=profile`\|`post`) → `imageId`, `url` 반환(201 IMAGE_UPLOADED). 회원가입·프로필 수정·게시글 작성 시 해당 `imageId` 사용. DELETE `/images/{id}`로 본인 업로드 이미지 철회 |
| **게시글 (Posts)** | 작성·조회·수정·삭제, 이미지 최대 5장 첨부(imageIds). 좋아요 추가·취소. 목록은 무한 스크롤(응답 `hasMore`), 목록 응답은 `contentPreview`·썸네일 1개, 상세는 본문 전체·이미지 최대 5개 |
| **댓글 (Comments)** | 게시글별 댓글 작성·조회·수정·삭제. 목록은 페이지당 기본 10개(size 쿼리 가능), 응답에 `totalCount`, `totalPages`, `currentPage` |

### 기술 스택

| 구분 | 기술 |
|------|------|
| **언어** | Python 3.8+ |
| **프레임워크** | FastAPI |
| **DB** | MySQL (SQLAlchemy 2.x + pymysql 드라이버) |
| **검증** | Pydantic v2 |
| **암호화** | bcrypt (비밀번호) |

### 설계 배경

| 선택 | 이유 |
|------|------|
| **무한 스크롤 vs 페이지네이션** | 게시글 목록은 피드 형태로 스크롤하며 읽는 UX가 자연스럽고, "다음 페이지" 클릭 없이 계속 로드 가능. 커뮤니티 피드는 새 글 보는 흐름이 중요해 무한 스크롤(hasMore) 선택. 댓글은 "몇 페이지인지", "총 몇 개인지"가 중요해 페이지 번호(totalCount, totalPages) 선택. 특정 댓글 찾기·목록 전체 파악이 용이함. |
| **세션 저장소: MySQL** | Redis 없이도 단일 DB로 세션·유저·게시글 일괄 관리 가능. 소규모 서비스에서 운영 부담을 줄이기 위해 MySQL `sessions` 테이블 사용. 규모 확장 시 Redis로 이전 가능. |
| **쿠키-세션 방식** | JWT는 클라이언트 저장·전송 시 XSS·CSRF 관리 부담. 쿠키(HttpOnly, SameSite)로 세션 ID만 전달하면 브라우저가 자동 전송하고, 서버에서 세션 검증으로 보안 부담을 줄임. |
| **조회수(view) 전용 엔드포인트** | 조회수 증가를 GET 상세와 분리해 두었음. GET `/{post_id}`는 멱등·캐시 친화적으로 두고, 상세 페이지 진입 시에만 클라이언트가 POST `/{post_id}/view`를 호출해 조회수 증가. 목록 프리페치·상세 재요청 시 조회수가 불어나지 않음. |
| **이미지 미리 업로드** | 회원가입·프로필·게시글에서 이미지는 먼저 `/media/images`로 업로드한 뒤 반환된 `imageId`만 본문에 넣음. 멀티파트와 JSON을 분리하고, 동일 이미지 재사용·클라이언트 캐시 제어가 쉬움. |

---

## 폴더 구조

**도메인 폴더(auth, users, media, posts, comments) 공통 역할**

| 파일 | 역할 |
|------|------|
| **router** | HTTP 엔드포인트 정의, 요청/응답 매핑, Depends 주입 |
| **controller** | 비즈니스 로직 (유효성·권한·트랜잭션 흐름) |
| **model** | DB 접근 (CRUD, 쿼리) |
| **schema** | 요청/응답 DTO (Pydantic v2, 검증·alias) |

※ media는 도메인 정책(검증·용도 분기·키 생성)을 위한 `image_policy.py`를 추가로 둠.

```
2-kyjness-community-be/
│
├── app/
│   ├── api/                       # API 버전별 라우터 조립
│   │   └── v1.py                  # /v1 prefix, auth·users·media·posts·comments include
│   │
│   ├── core/                      # 공통 유틸·설정
│   │   ├── config.py              # 환경 변수 (포트, DB, CORS, 파일 업로드 등)
│   │   ├── codes.py               # 응답 코드 (ApiCode)
│   │   ├── database.py            # SQLAlchemy + MySQL (get_db Depends, Session 주입)
│   │   ├── dependencies.py        # 로그인 검증, 게시글/댓글 작성자 검증
│   │   ├── exception_handlers.py  # 에러 응답 포맷 통일 ({code, data})
│   │   ├── rate_limit.py          # 요청 제한 (전역 + 로그인 전용)
│   │   ├── response.py            # 성공/실패 응답 포맷
│   │   ├── security.py            # 비밀번호 해시·검증 (bcrypt)
│   │   ├── storage.py             # 스토리지 인프라 (storage_save, storage_delete, build_url, local|S3)
│   │   └── validators.py          # 비밀번호·닉네임 형식 검증
│   │
│   ├── auth/                      # 인증 (router, controller, model, schema)
│   ├── users/                     # 사용자 (router, controller, model, schema)
│   ├── media/                     # 미디어 (router, controller, model, schema, image_policy.py)
│   ├── posts/                     # 게시글 (router, controller, model, schema)
│   ├── comments/                  # 댓글 (router, controller, model, schema)
│   │
├── docs/                          # 문서
│   ├── puppytalkdb.sql           # 테이블 생성 스크립트
│   ├── clear_db.sql               # 데이터만 비우기 (테이블 구조 유지)
│   └── api-codes.md               # API 응답 code·HTTP 매핑 (내부 참고)
│
├── main.py                        # 앱 진입점
├── Dockerfile                     # 프로덕션 Docker 이미지 (Gunicorn + Uvicorn)
├── upload/                        # 업로드 파일 저장 (로컬 시, StaticFiles /upload 마운트)
│   ├── profile/                   # 프로필 이미지 (키 prefix)
│   └── post/                      # 게시글 이미지 (키 prefix)
├── pyproject.toml                 # 의존성 (pip install .)
├── .env.example                   # 환경 변수 견본
└── README.md
```

---

## API 문서

서버 실행 후 브라우저에서 아래 주소로 API 문서를 볼 수 있습니다.

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

| 문서 | 주소 (로컬 실행 시) |
|------|---------------------|
| Swagger UI | http://localhost:8000/docs |
| ReDoc | http://localhost:8000/redoc |

**모든 API는 `/v1` prefix를 사용합니다.** 프론트엔드에서는 베이스 URL을 `http://localhost:8000/v1`로 두고 호출하면 됩니다.

도메인별 API 구성은 다음과 같습니다.

```
┌─────────────────────────────────────────────────────────────────────────┐
│  media │  /v1/media/...     (이미지 업로드 — 회원가입·프로필·게시글 공통)   │
├────────┼────────────────────────────────────────────────────────────────┤
│  POST  │  /images            이미지 1건 업로드 (쿼리: type=profile|post) → imageId, url 반환 (201) │
│  DELETE│  /images/{image_id} 본인 업로드 이미지 철회 (204)                 │
└────────┴────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│  auth  │  /v1/auth/...                                                  │
├────────┼────────────────────────────────────────────────────────────────┤
│  POST  │  /signup             회원가입 (profileImageId는 미리 /media/images 업로드) │
│  POST  │  /login              로그인 (세션 쿠키 설정)                     │
│  POST  │  /logout             로그아웃                                    │
│  GET   │  /me                 세션 검증·로그인 여부 확인                    │
└────────┴────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│  users │  /v1/users/...                                                 │
├────────┼────────────────────────────────────────────────────────────────┤
│  GET   │  /availability       이메일/닉네임 중복 체크 (?email=... | ?nickname=...) │
│  GET   │  /me                 내 프로필 조회 (createdAt 등)               │
│  PATCH │  /me                 내 정보 수정 (profileImageId는 미리 /media/images 업로드) │
│  PATCH │  /me/password        비밀번호 변경                               │
│  DELETE│  /me                 회원 탈퇴                                  │
└────────┴────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│  posts │  /v1/posts/...                                                 │
├────────┼────────────────────────────────────────────────────────────────┤
│  POST  │  /                   게시글 작성 (imageIds는 미리 /media/images 업로드, 최대 5개) │
│  GET   │  /                   게시글 목록 (무한 스크롤 조회. 쿼리: page, size. 응답 data: { list, hasMore }) │
│  POST  │  /{post_id}/view     조회수 1 증가 (상세 페이지 진입 시 호출, 204 No Content) │
│  GET   │  /{post_id}          게시글 상세 (조회수 증가 없음)              │
│  PATCH │  /{post_id}          게시글 수정 (imageIds 최대 5개)             │
│  DELETE│  /{post_id}          게시글 삭제                                 │
│  POST  │  /{post_id}/likes    좋아요 추가 (201 새로 추가, 200 이미 있음)   │
│  DELETE│  /{post_id}/likes    좋아요 취소                                 │
└────────┴────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│comments│  /v1/posts/{post_id}/comments/...                               │
├────────┼────────────────────────────────────────────────────────────────┤
│  POST  │  /                   댓글 작성                                 │
│  GET   │  /                   댓글 목록 (쿼리: page, size. 기본 10개, totalCount·totalPages·currentPage) │
│  PATCH │  /{comment_id}       댓글 수정                                 │
│  DELETE│  /{comment_id}       댓글 삭제                                 │
└────────┴────────────────────────────────────────────────────────────────┘
```

---

## 전체 흐름

```
[프론트엔드 / 클라이언트]  HTTP 요청 (JSON body, Cookie)
    │
    ▼
┌──────────────────────────────────────────────────────────────────────┐
│  백엔드 (FastAPI)                                                     │
│                                                                      │
│  ① Lifespan (앱 시작 시 1회)                                          │
│     → init_database()로 DB 연결 확인. 만료 세션 정리(시작 1회 + 주기 백그라운드). 종료 시 close_database() │
│                                                                      │
│  ② 미들웨어 (요청마다, 마지막 등록된 것부터 실행: CORS → 보안헤더 → access_log → rate_limit) │
│     → CORSMiddleware: Origin 검사, allow_credentials=True (쿠키 전송 허용) │
│     → add_security_headers: X-Frame-Options, X-Content-Type-Options   │
│     → access_log: 4xx/5xx 시 Method, Path, Status, 소요 시간 로깅 (DEBUG 시 X-Process-Time) │
│     → rate_limit: IP당 요청 수 제한, 초과 시 429. 로그인 API는 별도 check_login_rate_limit (IP당 분당 5회) │
│                                                                      │
│  ③ 라우터 매칭                                                        │
│     → URL·HTTP 메서드별 분기. /v1/media, /v1/auth, /v1/users, /v1/posts, /v1/posts/.../comments 등 │
│                                                                      │
│  ④ 의존성 (Depends)                                                   │
│     → get_db: 요청마다 Session 주입 (성공 시 commit, 예외 시 rollback)  │
│     → get_current_user: Cookie session_id → 세션 조회 → CurrentUser 반환 │
│     → require_post_author / require_comment_author: 게시글·댓글 수정/삭제 시 작성자 본인 여부 확인 │
│                                                                      │
│  ⑤ Pydantic (Schema)                                                  │
│     → 요청 body·쿼리(PostListQuery 등)를 DTO로 검증. 실패 시 400 + code │
│                                                                      │
│  ⑥ Route 핸들러                                                       │
│     → auth.controller.signup_user(), posts.controller.create_post() 등 호출│
│                                                                      │
│  ⑦ Controller                                                        │
│     → 비즈니스 로직·예외만. commit/rollback은 get_db(세션 스코프)에서 담당   │
│                                                                      │
│  ⑧ Model                                                              │
│     → Depends(get_db)로 받은 Session 사용, db.execute()만. commit 없음     │
│                                                                      │
│  ⑨ 예외 핸들러 (전역)                                                 │
│     → RequestValidationError, HTTPException, DB 예외 → { code, data } 통일│
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
    │
    ▼
HTTP 응답  { "code": "POST_UPLOADED", "data": { "postId": 1 } }
```

---

## 실행 방법

### 1. 사전 준비

- **Python 3.8 이상** 설치
- **MySQL** 설치·실행 후 `puppytalk` DB 생성 및 테이블 생성

```bash
mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS puppytalk;"
mysql -u root -p puppytalk < docs/puppytalkdb.sql
```

DDL은 `docs/puppytalkdb.sql`을 참고합니다. **데이터만 비우기**(테이블 구조 유지)가 필요하면 `docs/clear_db.sql`을 실행하면 됩니다.  
애플리케이션은 **SQLAlchemy**로 MySQL에 접근합니다. 요청마다 `get_db()`가 세션을 주입하고, 성공 시 commit·예외 시 rollback을 처리합니다.  
`likes` 테이블은 `(post_id, user_id)` UNIQUE(로그인 유저만 좋아요)이며, 중복 좋아요 시 IntegrityError로 처리됩니다.  
스키마는 위 SQL 파일로 관리하며, 마이그레이션 도구(Alembic)는 사용하지 않습니다. 스키마 변경이 잦아지거나 운영 DB 보존이 필요하면 Alembic 도입을 검토하면 됩니다.

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

앱은 루트의 **`.env`** 하나만 읽습니다. **`.env.example`**을 복사해 `.env`로 저장한 뒤 값을 채우면 됩니다. 환경 변수(포트, DB, CORS, S3·파일 저장 등) 상세는 **`.env.example`** 주석을 참고하면 됩니다.

### 4. 서버 실행

```bash
# 로컬/개발 (Uvicorn 단독, --reload 시 코드 변경 반영)
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

프로덕션/Docker에서는 Gunicorn + Uvicorn worker 사용을 권장합니다. Docker 이미지는 루트의 **Dockerfile** 참고.

---

## 확장 전략

### 기능

- **검색/필터**: 견종·지역·태그로 게시글 검색
- **신고/차단**: 게시글 신고, 사용자 차단 (차단한 사람 글 숨김)
- **알림**: 내 글에 댓글 달리면 알림 리스트
- **관리자**: 신고 누적 글 숨김, 유저 제재 (ROLE 기반)

### 인프라 (규모 확대 시)

- **세션 (Redis)**: 현재 MySQL `sessions` 테이블 사용. 규모 확대 시 Redis로 이전 검토.
- **캐시 (Redis)**: 인기 게시글·댓글 캐싱
- **메시지 큐**: 알림·이미지 처리 등 비동기 작업
