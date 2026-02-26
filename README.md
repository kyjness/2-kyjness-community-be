# PuppyTalk API

**PuppyTalk**는 반려견을 키우는 사람들을 위한 커뮤니티 서비스의 백엔드 REST API 서버입니다.
사용자는 회원가입·로그인 후 게시글 작성, 댓글, 좋아요, 이미지 업로드 기능을 이용할 수 있습니다.

---

## 개요

### 기술 스택

| 구분 | 기술 |
|------|------|
| **언어** | Python 3.8+ |
| **패키지 관리** | Poetry 2.x |
| **프레임워크** | FastAPI |
| **DB** | MySQL (pymysql 드라이버) |
| **ORM** | SQLAlchemy 2.x |
| **검증** | Pydantic v2 |
| **암호화** | bcrypt (비밀번호) |

### 설계 포인트

| 선택 | 이유 |
|------|------|
| **무한 스크롤 vs 페이지네이션** | 게시글 목록은 피드 형태로 스크롤하며 읽는 UX가 자연스럽고, "다음 페이지" 클릭 없이 계속 로드 가능. 커뮤니티 피드는 새 글 보는 흐름이 중요해 무한 스크롤(hasMore) 선택. 댓글은 "몇 페이지인지", "총 몇 개인지"가 중요해 페이지 번호(totalCount, totalPages) 선택. 특정 댓글 찾기·목록 전체 파악이 용이함. |
| **세션 저장소: MySQL** | Redis 없이도 단일 DB로 세션·유저·게시글 일괄 관리 가능. 소규모 서비스에서 운영 부담을 줄이기 위해 MySQL `sessions` 테이블 사용. 규모 확장 시 Redis로 이전 가능. |
| **쿠키-세션 방식** | JWT는 클라이언트 저장·전송 시 XSS·CSRF 관리 부담. 쿠키(HttpOnly, SameSite)로 세션 ID만 전달하면 브라우저가 자동 전송하고, 서버에서 세션 검증으로 보안 부담을 줄임. |
| **조회수(view) 전용 엔드포인트** | 조회수 증가를 GET 상세와 분리해 두었음. GET `/{post_id}`는 멱등·캐시 친화적으로 두고, 상세 페이지 진입 시에만 클라이언트가 POST `/{post_id}/view`를 호출해 조회수 증가. 목록 프리페치·상세 재요청 시 조회수가 불어나지 않음. |
| **이미지 미리 업로드** | 회원가입·프로필·게시글에서 이미지는 먼저 `/media/images`로 업로드한 뒤 반환된 `imageId`만 본문에 넣음. 멀티파트와 JSON을 분리하고, 동일 이미지 재사용·클라이언트 캐시 제어가 쉬움. |

---

## 폴더 구조

`app` 내 각 도메인 폴더는 **router → controller → model** 계층 구조로 구성되어 있습니다. 요청·응답 데이터는 **schema (Pydantic DTO)** 를 통해 검증·직렬화됩니다.

**도메인 폴더 공통 역할**

| 파일 | 역할 |
|------|------|
| **router** | HTTP 엔드포인트 정의, 요청/응답 매핑, Depends 주입 |
| **controller** | 비즈니스 로직 (유효성·권한·트랜잭션 흐름) |
| **model** | DB 접근 (CRUD, 쿼리) |
| **schema** | 요청/응답 DTO (Pydantic v2, 검증·alias) |

※ 주기 정리(세션·회원가입용 이미지 TTL)는 `core/cleanup.py`에서 run_once/run_loop로 처리. media는 schema 없이 router·controller·model·`image_policy.py`로 두고, posts는 ORM→응답 변환을 위한 `mapper.py`를 둠.

```
2-kyjness-community-be/
│
├── app/
│   ├── api/                       # API 버전별 라우터 조립
│   │   └── v1.py                  # /v1 prefix, auth·users·media·posts·comments include
│   │
│   ├── common/                    # 프레임워크 무관 공통 (코드·응답·검증·로깅)
│   │   ├── codes.py
│   │   ├── logging_config.py
│   │   ├── response.py
│   │   └── validators.py
│   │
│   ├── core/                      # FastAPI·인프라 연동
│   │   ├── config.py
│   │   ├── cleanup.py             # 주기 정리 (세션·회원가입용 이미지 TTL)
│   │   ├── database.py
│   │   ├── dependencies/
│   │   ├── exception_handlers.py
│   │   ├── middleware/
│   │   ├── security.py
│   │   └── storage.py
│   │
│   ├── auth/                      # 인증 (회원가입·로그인·로그아웃)
│   │                               # 파일: router.py, controller.py, model.py, schema.py
│   ├── users/                     # 사용자 (프로필·비밀번호·탈퇴)
│   │                               # 파일: router.py, controller.py, model.py, schema.py
│   ├── media/                     # 미디어 (이미지 업로드·철회)
│   │                               # 파일: router.py, controller.py, model.py, image_policy.py(용도·검증·키). schema 없음
│   ├── posts/                     # 게시글 (CRUD·좋아요·조회수·무한스크롤)
│   │                               # 파일: router.py, controller.py, model.py, schema.py, mapper.py(ORM→응답 변환)
│   ├── comments/                  # 댓글 (CRUD·페이지네이션)
│   │                               # 파일: router.py, controller.py, model.py, schema.py
│
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
├── pyproject.toml                 # 의존성 (Poetry)
├── poetry.lock                    # 의존성 잠금 (커밋 유지)
├── .env.example                   # 환경 변수 견본
├── test/                          # pytest 테스트
└── README.md
```

---

## API 문서

모든 API는 **`/v1` prefix**를 사용합니다. 도메인별 구성은 아래와 같습니다.

```
┌─────────────────────────────────────────────────────────────────────────┐
│  media │  /v1/media/...     (이미지 업로드 — 회원가입·프로필·게시글)        │
├────────┼────────────────────────────────────────────────────────────────┤
│  POST  │  /images/signup    회원가입용 프로필 업로드 (비로그인, IP rate limit) → imageId, url, signupToken (201) │
│  POST  │  /images            이미지 1건 업로드 (쿼리: type=profile|post) → imageId, url (201) │
│  DELETE│  /images/{image_id} 본인 업로드 이미지 철회 (204)                 │
└────────┴────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│  auth  │  /v1/auth/...                                                  │
├────────┼────────────────────────────────────────────────────────────────┤
│  POST  │  /signup             회원가입 (프로필 사진 시 profileImageId·signupToken은 /media/images/signup 업로드 후 사용) │
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
│  GET   │  /                   게시글 목록 (무한 스크롤. 쿼리: page, size. 응답: data(목록), hasMore) │
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

**문서 보기**: 아래 명령으로 서버를 실행한 뒤, 브라우저에서 문서 주소로 접속하면 Swagger/ReDoc API 문서를 볼 수 있습니다.

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```
| 문서 | 주소 |
|------|------|
| **Swagger UI** | http://localhost:8000/docs |
| **ReDoc** | http://localhost:8000/redoc |

API 베이스 URL: `http://localhost:8000/v1`

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
│     → init_database()로 DB 연결 확인. core.cleanup run_once(시작 1회) + run_loop(주기 스레드). 종료 시 stop_event 후 close_database() │
│                                                                      │
│  GET /health  → DB ping. 성공 시 200, 실패 시 503 (로드밸런서·배포 검사용) │
│                                                                      │
│  ② 미들웨어 (요청마다, 바깥→안: CORS → request_id → access_log → rate_limit → 보안헤더) │
│     → request_id: X-Request-ID 생성/전달, 응답 헤더·4xx/5xx 로그에 포함 (추적용) │
│     → rate_limit: IP당 요청 수 제한, 초과 시 429. 로그인 API는 별도 check_login_rate_limit (IP당 분당 5회) │
│     → access_log: 4xx/5xx 시 request_id, Method, Path, Status, 소요 시간 로깅 (DEBUG 시 X-Process-Time) │
│     → 보안헤더: X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy (HSTS는 설정으로) │
│     → CORSMiddleware: Origin 검사, allow_credentials=True (쿠키 전송 허용) │
│                                                                      │
│  ③ 라우터 매칭                                                        │
│     → URL·HTTP 메서드별 분기. /v1/media, /v1/auth, /v1/users, /v1/posts, /v1/posts/.../comments 등 │
│                                                                      │
│  ④ 의존성 (Depends)                                                   │
│     → get_db: 요청마다 Session 주입 (성공 시 commit, 예외 시 rollback)  │
│     → (원칙) 요청 1개 = Session 1개. model은 commit 하지 않고 get_db 스코프에서만 commit/rollback 처리. │
│     → get_current_user: Cookie session_id → 세션 조회 → CurrentUser 반환 │
│     → require_post_author / require_comment_author: 게시글·댓글 수정/삭제 시 작성자 본인 여부 확인 │
│                                                                      │
│  ⑤ Pydantic (Schema)                                                  │
│     → 요청 body·쿼리를 DTO로 검증. 실패 시 400 + code                     │
│                                                                      │
│  ⑥ Route 핸들러                                                       │
│     → auth.controller.signup_user(), posts.controller.create_post() 등 호출│
│                                                                      │
│  ⑦ Controller                                                        │
│     → 비즈니스 로직·예외만. commit/rollback은 get_db(세션 스코프)에서 담당   │
│                                                                      │
│  ⑧ Model                                                              │
│     → Depends(get_db)로 받은 Session 사용, db.execute()만. commit 없음. 게시글 목록·상세는 joinedload로 N+1 방지 │
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

- **Python 3.8 이상** 필요. `python --version`으로 확인.
- **MySQL** 설치·실행 중. 로컬 또는 사용 가능한 DB 주소 준비.
- 아래 순서대로 실행 → `puppytalk` DB 및 테이블 생성.

```bash
mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS puppytalk;"
mysql -u root -p puppytalk < docs/puppytalkdb.sql
```

- 데이터만 비우기: `docs/clear_db.sql` 실행.

### 2. 패키지 설치 및 가상환경

- 프로젝트 폴더로 이동 후 **Poetry**로 의존성 설치. (Poetry 없으면 `pip install poetry` 먼저 실행.)

```bash
cd 2-kyjness-community-be
poetry install
```

- `poetry install` 하면 이 프로젝트 전용 **가상환경**이 생김.
- 테스트 의존성까지 쓰려면: `poetry install --with dev` 한 번 더 실행.

### 3. 환경 변수

- **`ENV`** 값에 따라 `.env.development` 또는 `.env.production` 로드. `ENV` 없으면 development.
- **로컬**: `.env.example` 복사 → `.env.development` 로 저장 후 DB 주소·비밀번호 등만 채우기.
- **배포**: `.env.production` 에 실제 값 넣어 두고, 실행 시 **`ENV=production`** 지정.
- 각 변수 설명: `.env.example` 주석 참고.

### 4. 서버 실행

```bash
poetry run uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

- `--reload`: 코드 수정 시 자동 재시작.
- 프로덕션: Gunicorn + Uvicorn worker 권장. **Dockerfile** 참고.
- 테스트: `poetry run pytest test/ -v` (MySQL·env 설정 필요).

### 5. Docker Compose로 실행

- compose 파일을 이 프로젝트 **한 단계 위 폴더**에 두고 아래 실행. 백엔드는 이 폴더 `.env.production` 참조.
- 파일 여러 개일 때: `docker compose -f docker-compose.ec2.yml up -d` 처럼 `-f`로 지정.

```bash
docker compose up -d
docker compose up --build -d   # 이미지 다시 빌드 시
docker compose stop
```

## 확장 전략

### 기능

- **검색/필터**: 견종·지역·태그로 게시글 검색
- **신고/차단**: 게시글 신고, 사용자 차단 (차단한 사람 글 숨김)
- **알림**: 내 글에 댓글 달리면 알림 리스트
- **관리자**: 신고 누적 글 숨김, 유저 제재 (ROLE 기반)

### 인프라 (규모 확대 시)

- **Redis 도입 검토**: 세션·캐시·Rate limit은 현재 MySQL/메모리 사용. 규모 확대·멀티 워커·다중 인스턴스 배포 시 Redis로 이전 검토.
- **메시지 큐**: 알림·이미지 처리 등 비동기 작업
