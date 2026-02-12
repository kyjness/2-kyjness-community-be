# PuppyTalk API - 아키텍처

시스템 구조, 요청 흐름, 계층 역할을 정리한 문서입니다.

---

## 1. 시스템 개요

```
[클라이언트(프론트엔드)]
        │
        │  HTTP (JSON, Cookie)
        ▼
┌─────────────────────┐
│   FastAPI 백엔드     │
│   - CORS, 보안헤더   │
│   - 라우팅           │
│   - 세션 기반 인증   │
└─────────────────────┘
        │
        ├──► MySQL (사용자, 게시글, 댓글, 좋아요, 세션)
        └──► 로컬(upload/) 또는 S3 (이미지)
```

---

## 2. 계층 구조

| 계층 | 역할 | 위치 |
|------|------|------|
| **Lifespan** | 앱 시작/종료 시 DB 연결 확인 | `main.py` |
| **Middleware** | CORS, 보안 헤더 | `main.py` |
| **Router** | URL·메서드별 분기 | `*_route.py` |
| **Dependencies** | 인증·권한 검사 | `dependencies.py` |
| **Schema** | 요청/응답 검증 (Pydantic) | `*_schema.py` |
| **Controller** | 비즈니스 로직 | `*_controller.py` |
| **Model** | DB 접근 (SQL) | `*_model.py` |
| **Exception Handler** | 에러 응답 포맷 통일 | `exception_handlers.py` |

---

## 3. 요청 처리 흐름

```
① HTTP 요청 수신
        │
② CORS, 보안헤더 (미들웨어)
        │
③ 라우터 매칭 (/auth, /users, /posts ...)
        │
④ 의존성: get_current_user (쿠키 → session_id → user_id)
        │
⑤ Pydantic: 요청 body 검증
        │
⑥ Controller: 비즈니스 로직 처리
        │
⑦ Model: DB 조회·저장 (get_connection → SQL → commit)
        │
⑧ 응답: { "code": "...", "data": ... }
```

---

## 4. 도메인별 구조

### Auth (인증)

- **Route**: `/auth/signup`, `/auth/login`, `/auth/logout`, `/auth/me`
- **인증 방식**: 쿠키 기반 세션 (`session_id`)
- **테이블**: `users`, `sessions`

### Users (사용자)

- **Route**: `/users/me` (GET, PATCH, DELETE), `/users/me/password`, `/users/me/profile-image`
- **의존성**: `get_current_user` (인증 필요)

### Posts (게시글)

- **Route**: `/posts`, `/posts/{id}`, `/posts/{id}/image`
- **의존성**: `get_current_user`, `require_post_author` (작성자 확인)

### Comments (댓글)

- **Route**: `/posts/{post_id}/comments`, `/posts/{post_id}/comments/{comment_id}`
- **의존성**: `get_current_user`, `require_comment_author`

### Likes (좋아요)

- **Route**: `/posts/{post_id}/likes` (POST, DELETE)
- **의존성**: `get_current_user`

---

## 5. 공통 모듈 (core)

| 모듈 | 역할 |
|------|------|
| `config` | .env 기반 설정 (DB, CORS, S3 등) |
| `database` | MySQL 연결 (get_connection, init_database) |
| `dependencies` | 인증·권한 의존성 |
| `file_upload` | 이미지 검증·저장 (로컬/S3) |
| `response` | success_response, raise_http_error |
| `validators` | 비밀번호, 닉네임, URL 검증 |
| `exception_handlers` | 예외 → { code, data } 변환 |

---

## 6. 데이터 흐름

### 이미지·비디오 업로드

```
이미지: 클라이언트 (multipart/form-data)
    → file_upload (타입·크기 검증)
    → STORAGE_BACKEND=local: upload/image/{profile|post}/
    → STORAGE_BACKEND=s3: S3 버킷 image/{profile|post}/
    → URL 반환

비디오: POST /posts/{id}/video (게시글 비디오)
    → file_upload.save_post_video (타입·크기 검증, mp4/webm)
    → STORAGE_BACKEND=local: upload/video/post/
    → STORAGE_BACKEND=s3: S3 버킷 video/post/
    → URL 반환 (post_files.file_url에 저장)
```

### 인증 흐름

```
로그인: POST /auth/login
    → 비밀번호 bcrypt 검증
    → sessions 테이블에 session_id 저장
    → Set-Cookie: session_id

이후 요청: Cookie에 session_id 포함
    → get_current_user: session_id → user_id 조회
    → 없거나 만료 시 401
```

---

## 7. 폴더 구조

```
app/
├── core/           # 공통 (config, database, dependencies, file_upload, validators ...)
├── auth/           # 인증 (signup, login, logout)
├── users/          # 사용자 프로필
├── posts/          # 게시글
├── comments/       # 댓글
└── likes/          # 좋아요

각 도메인: *_route, *_controller, *_model, *_schema
```
