# 아키텍처

이 문서는 PuppyTalk 백엔드의 **도메인 레이어 역할**, **폴더 구조**, **요청·인증 흐름**을 정리합니다.

---

## 도메인 레이어 역할

`app/domain` 아래 각 기능 폴더(auth, users, posts, comments, media)는 같은 패턴을 따릅니다.  
요청이 들어오면 **router → controller → model** 순으로 처리되고, 요청·응답은 **schema(Pydantic)** 로 검증·직렬화합니다.

| 파일 | 역할 |
|------|------|
| **router** | HTTP 엔드포인트 정의. `Depends(get_db, get_current_user)` 등으로 DB 세션·로그인 유저 주입. controller 호출 후 schema로 응답 매핑. |
| **controller** | 비즈니스 로직(유효성 검사·권한 확인·트랜잭션 흐름). DB 접근은 model에 위임. |
| **model** | DB 접근(CRUD·쿼리). `Depends(get_db)` 로 받은 Session만 사용. commit/rollback은 세션을 제공하는 `get_db` 스코프에서 처리. |
| **schema** | 요청/응답 DTO. Pydantic v2로 검증·alias. 400 에러 시 공통 형식으로 반환. |

- **의존성 방향**: router는 controller를 호출하고, controller는 model을 호출. model은 `app.db`의 Session만 사용. 도메인끼리는 직접 import하지 않고, 공통·인프라(common, core, db)만 공유.

---

## 폴더 구조

`app` 하위는 **공통/인프라**(api, common, core, db)와 **도메인**(domain)으로 구분됩니다.  
(마이그레이션 스크립트는 프로젝트 루트 `alembic/`에 두는 것이 관례입니다.)

```
2-kyjness-community-be/
├── app/
│   ├── api/
│   │   └── v1.py            # /v1 경로에 라우터 묶어서 등록
│   ├── common/
│   │   ├── codes.py         # API 응답 코드 상수
│   │   ├── response.py      # 공통 응답 포맷·에러 처리
│   │   ├── validators.py    # 닉네임·비밀번호 형식 검증
│   │   └── logging_config.py # 로깅 설정
│   ├── core/
│   │   ├── config.py        # 환경 변수 설정 (ENV에 따라 .env.development / .env.production)
│   │   ├── cleanup.py       # 만료 세션·회원가입용 이미지 TTL 정리
│   │   ├── exception_handlers.py  # 전역 예외 → { code, data } 통일
│   │   ├── security.py      # 비밀번호 해시·세션 ID 생성
│   │   ├── storage.py       # 로컬/S3 파일 업로드
│   │   ├── dependencies/
│   │   │   ├── availability.py    # 쿼리 파싱 (가용성 등)
│   │   │   ├── comment_author.py  # 댓글 작성자 검증
│   │   │   ├── current_user.py   # 쿠키 세션 → CurrentUser
│   │   │   └── post_author.py    # 게시글 작성자 검증
│   │   └── middleware/
│   │       ├── access_log.py     # 4xx/5xx 접근 로그
│   │       ├── rate_limit.py     # IP당 요청 제한
│   │       ├── request_id.py     # X-Request-ID 생성·전달
│   │       └── security_headers.py # 보안 헤더
│   ├── db/
│   │   ├── base.py          # SQLAlchemy DeclarativeBase
│   │   ├── connection.py    # init_database, check_database, close_database
│   │   ├── engine.py        # DB 엔진·SessionLocal
│   │   └── session.py       # get_db, get_connection
│   └── domain/
│       ├── auth/            # 로그인·로그아웃·회원가입
│       │   ├── controller.py     # 인증 비즈니스 로직 (회원가입·로그인·로그아웃)
│       │   ├── model.py          # 세션 CRUD, AuthSession 모델
│       │   ├── router.py         # 인증 엔드포인트 (login, logout, signup, /me)
│       │   └── schema.py         # 인증 요청/응답 DTO
│       ├── users/            # 프로필 조회·수정
│       │   ├── controller.py     # 사용자 비즈니스 로직 (프로필·비밀번호)
│       │   ├── model.py          # 사용자 CRUD, User 모델
│       │   ├── router.py         # 사용자 엔드포인트 (/users/me)
│       │   └── schema.py         # 사용자 요청/응답 DTO
│       ├── media/            # 이미지 업로드
│       │   ├── controller.py     # 이미지 업로드 비즈니스 로직
│       │   ├── image_policy.py   # 회원가입용/일반 업로드 정책·signup token 검증
│       │   ├── model.py          # 이미지 CRUD, Image 모델
│       │   └── router.py         # 이미지 업로드 (POST /media/images, ?purpose=profile|post / POST /media/images/signup)
│       ├── posts/            # 게시글 CRUD·피드·좋아요
│       │   ├── controller.py     # 게시글 비즈니스 로직 (생성·수정·삭제·피드·좋아요·조회수)
│       │   ├── mapper.py          # 모델 → PostResponse 변환
│       │   ├── model.py          # 게시글·좋아요·post_images CRUD
│       │   ├── router.py         # 게시글 엔드포인트 (CRUD, 피드, 상세, 댓글 목록)
│       │   └── schema.py         # 게시글 요청/응답 DTO
│       └── comments/         # 댓글 CRUD
│           ├── controller.py     # 댓글 비즈니스 로직 (생성·수정·삭제·목록)
│           ├── model.py          # 댓글 CRUD, Comment 모델
│           ├── router.py         # 댓글 엔드포인트 (CRUD, 목록 페이지네이션)
│           └── schema.py         # 댓글 요청/응답 DTO
│   └── main.py               # 앱 진입점·미들웨어·라우터 등록
├── alembic/                 # DB 스키마 마이그레이션
│   ├── env.py               # 마이그레이션 환경 (DB URL·모델 로드)
│   ├── README               # Alembic 사용법 요약
│   ├── script.py.mako       # 리비전 스크립트 템플릿
│   └── versions/            # 마이그레이션 리비전 파일
├── docs/                    # 상세 문서·참고용 SQL
│   ├── api-codes.md         # API 응답 code · HTTP 상태 매핑
│   ├── architecture.md     # 이 문서 (아키텍처·폴더 구조·요청·인증 흐름)
│   ├── clear_db.sql         # 데이터만 비우기
│   ├── deploy.md            # Docker·환경 변수·Alembic
│   └── puppytalkdb.sql      # 참고용 DDL
├── test/                    # pytest
│   ├── auth.py              # 인증 API 테스트
│   ├── comments.py          # 댓글 API 테스트
│   ├── conftest.py          # pytest 픽스처·공통 설정
│   ├── health.py            # /health 엔드포인트 테스트
│   ├── media.py             # 미디어(이미지 업로드) API 테스트
│   ├── posts.py             # 게시글 API 테스트
│   └── users.py             # 사용자 API 테스트
├── alembic.ini              # Alembic 설정
├── pyproject.toml           # Poetry 의존성·스크립트
├── poetry.lock              # 의존성 잠금
├── Dockerfile               # 프로덕션 이미지 빌드
├── docker-compose.yml       # 로컬·배포용 Compose
├── docker-compose.ec2.yml   # EC2 배포용 Compose
└── .env.example             # 환경 변수 예시
```

---

## 미들웨어 순서 (바깥 → 안)

`app/main.py`에 등록된 순서대로, **요청**은 아래에서 위로, **응답**은 위에서 아래로 통과합니다.

| 순서 | 이름 | 설명 |
|------|------|------|
| 1 | **CORS** | 허용 Origin 검사. `allow_credentials=True`로 쿠키 전송 허용. |
| 2 | **security_headers** | X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy. HSTS는 설정으로 켜기. |
| 3 | **rate_limit** | IP당 요청 수 제한. 초과 시 429. 로그인 API는 별도 제한(IP당 분당 5회). |
| 4 | **access_log** | 4xx/5xx 응답 시 request_id, Method, Path, Status, 소요 시간 로깅. DEBUG 시 X-Process-Time 헤더. |
| 5 | **request_id** | X-Request-ID 생성·전달. 응답 헤더·로그에 포함해 요청 추적. |

---

## 요청 흐름

```
[클라이언트]  HTTP 요청 (JSON body, Cookie)
    │
    ▼
① Lifespan (앱 시작 1회)
   → init_database() 로 DB 연결 확인
   → cleanup run_once + run_loop (만료 세션·회원가입용 이미지 TTL 정리). 종료 시 stop_event 후 close_database()

② GET /health
   → DB ping. 성공 200, 실패 503 (로드밸런서·배포 검사용)

③ 미들웨어 (요청마다, 위 순서)
   CORS → security_headers → rate_limit → access_log → request_id

④ 라우터 매칭 (v1_router prefix=/v1)
   auth, users, media, posts, comments 순으로 include. 예: /v1/auth/login, /v1/users/me, /v1/posts, /v1/posts/{id}/comments

⑤ 의존성 (Depends)
   → get_db: 요청마다 Session 주입. 성공 시 commit, 예외 시 rollback (session.py)
   → get_current_user: Cookie session_id → 세션 조회 → CurrentUser 반환
   → require_post_author / require_comment_author: 게시글·댓글 수정/삭제 시 작성자 본인 여부

⑥ Pydantic (Schema)
   요청 body·쿼리 검증. 실패 시 400 + code

⑦ Route 핸들러 → Controller → Model
   Model은 Session만 사용. commit/rollback은 get_db 스코프

⑧ 예외 핸들러 (전역)
   RequestValidationError, HTTPException, DB 예외 → { code, data } 통일
    │
    ▼
HTTP 응답  { "code": "...", "data": { ... } }
```

---

## 인증 흐름

| 단계 | 설명 |
|------|------|
| **로그인** | POST /v1/auth/login → 세션 생성 후 `session_id` 쿠키 설정 (HttpOnly, SameSite) |
| **이후 요청** | Cookie로 `session_id` 전송 → `get_current_user`에서 세션 조회 → CurrentUser 주입 |
| **로그아웃** | POST /v1/auth/logout → 해당 세션 삭제 |

세션 저장소는 MySQL(`sessions` 테이블).

- **확장 전략**(추가 기능·인프라)은 README의 "확장 전략" 섹션을 참고하면 됩니다. architecture·deploy 문서에는 별도로 적지 않습니다.
