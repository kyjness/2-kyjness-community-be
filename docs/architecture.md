# 아키텍처 (Architecture)

이 문서는 PuppyTalk 백엔드의 **내부 동작 원리**를 깊이 이해할 수 있도록, 설계 의도(Why)와 실제 코드 흐름(How)을 단계별로 정리한 딥다이브 가이드입니다.  
기능 나열이 아니라 **요청이 어떻게 검증·제한·라우팅되는지**, **DB·인증·정합성·성능이 어떤 이유로 설계되었는지**를 중심으로 서술합니다.

### FastAPI + REST API를 선택한 이유

#### FastAPI: AI/ML 파이프라인 통합 및 고성능 비동기 아키텍처

- **Unified ML Ecosystem**: 백엔드와 AI/ML 모델링 언어를 Python으로 통일하여, 별도의 인터페이스 계층 없이 **TensorFlow, PyTorch 등의 모델을 즉시 서빙(Inference)**할 수 있는 최적의 환경을 구축함.
- **Asynchronous Concurrency**: uvloop 기반의 비동기 I/O 처리를 통해 대규모 동시 접속 상황에서도 낮은 지연 시간(Latency)과 높은 처리량(Throughput)을 보장함.
- **Data Integrity via Pydantic V2**: Pydantic을 활용한 엄격한 타입 힌트와 자동 검증으로 데이터 엔지니어링 단계에서의 무결성을 확보하며, 이는 추천 알고리즘 및 데이터 분석 시 신뢰성 있는 입출력을 보장함. [cite: 2026-03-04]

#### REST API: 리소스 지향 설계 및 유연한 확장성

- **Resource-Centric Design**: 유저, 게시글, 댓글 등 서비스 도메인을 독립적인 리소스로 관리하여 API 가독성과 유지보수 편의성을 극대화함.
- **Stateless Architecture**: 서버의 상태를 공유하지 않는 설계를 통해 트래픽 급증 시 컨테이너 기반의 **수평 확장(Scale-out)**에 최적화된 구조를 유지함.

---

## 목차

1. [폴더 구조 및 의존성](#1-폴더-구조-및-의존성)
2. [요청 흐름 (Request Lifecycle)](#2-요청-흐름-request-lifecycle)
3. [데이터베이스 아키텍처](#3-데이터베이스-아키텍처)
4. [인증·보안](#4-인증보안)
5. [데이터 정합성](#5-데이터-정합성)
6. [성능 최적화](#6-성능-최적화)
7. [이미지: signupToken·ref_count](#7-이미지-signuptokenref_count)
8. [게시글 피드: 검색·정렬·차단·신고](#8-게시글-피드-검색정렬차단신고)

---

## 1. 폴더 구조 및 의존성

### 1.1 의존성 단일화

요청 스코프에서 쓰는 **인증·DB 세션·권한·쿼리 파싱·클라이언트 식별자**는 dependencies 한 곳에서 제공한다. 라우터·핸들러는 여기서만 주입받아, "DB·유저가 어디서 오는지"를 한눈에 파악할 수 있다.  
비요청 스코프(cleanup, 예외 핸들러 등)용 DB 연결은 별도 컨텍스트 매니저로만 사용한다.

### 1.2 폴더 구조 요약

| 파일 | 역할 |
|------|------|
| **router** | HTTP 엔드포인트 정의. `Depends(...)`로 DB·유저·클라이언트 식별자 주입. **Service** 호출 후 반환값을 ApiResponse로 포장·예외(ValueError)를 HTTP 에러로 변환. |
| **service** | 비즈니스 로직·도메인 간 조율(Orchestration). 순수 데이터 반환 또는 ValueError. Redis·토큰·카운트 동기화·이미지 ref_count 등 처리. ApiResponse·ApiCode·raise_http_error 미사용. |
| **model** | DB 접근(CRUD·쿼리). AsyncSession만 사용. **commit/rollback은 하지 않으며**, 트랜잭션 경계는 서비스의 `async with db.begin():` 블록에서만 둠. |
| **schema** | 요청/응답 DTO. Pydantic v2 검증·alias. |

도메인 레이어는 **router → service → model → schema** 4계층 패턴을 따른다. 복합 연산·도메인 간 협업은 Service에서 수행한다.

**common**에는 `ApiCode`(응답 code), `TargetType`(신고 대상: POST/COMMENT), `UserStatus` 등 StrEnum이 정의되어 있다. `ApiResponse.code`는 `ApiCode | str`을 받으며, `use_enum_values=True`로 직렬화 시 문자열로 내려가므로 라우터에서는 `ApiCode.OK` 등 enum만 전달하면 된다.

### 1.3 도메인 의존성 (Domain Dependency)

요청 흐름(섹션 2.2)과 별도로, **도메인 간 참조 관계**만 아래 다이어그램으로 정리한다. 화살표 A → B는 "A 도메인의 Router/Service가 B 도메인의 Model·Service를 참조한다"는 의미다. 단방향으로 유지하며, 순환 참조 방지를 위해 필요한 경우 함수 내부 임포트를 사용한다.

**요약 (도메인 → 참조 대상)**

```mermaid
flowchart LR
    subgraph 도메인["도메인"]
        auth[auth]
        users[users]
        posts[posts]
        comments[comments]
        likes[likes]
        media[media]
        reports[reports]
        admin[admin]
        dogs[dogs]
    end

    auth --> users
    auth --> media
    users --> media
    users -.->|revoke_refresh| auth
    posts --> media
    posts --> likes
    comments --> posts
    likes --> posts
    likes --> comments
    reports --> posts
    reports --> comments
    admin --> posts
    admin --> comments
    admin --> users
    admin --> reports
    dogs --> users
```

**상세 (계층별·참조 대상 명시)**

```mermaid
flowchart TB
    subgraph auth["auth"]
        direction TB
        A_R[router]
        A_S[AuthService]
        A_M["(인증 전용 DB 테이블 없음)"]
        A_R --> A_S
    end

    subgraph users["users"]
        direction TB
        U_R[router]
        U_S[UserService]
        U_M["UsersModel, DogProfilesModel"]
        U_R --> U_S
        U_S --> U_M
    end

    subgraph media["media"]
        direction TB
        M_R[router]
        M_S[MediaService]
        M_M["MediaModel (Image)"]
        M_R --> M_S
        M_S --> M_M
    end

    subgraph posts["posts"]
        direction TB
        P_R[router]
        P_S[PostService]
        P_M["PostsModel (Post, PostImage)"]
        P_R --> P_S
        P_S --> P_M
    end

    subgraph comments["comments"]
        direction TB
        C_R[router]
        C_S[CommentService]
        C_M["CommentsModel, CommentLikesModel"]
        C_R --> C_S
        C_S --> C_M
    end

    subgraph likes["likes"]
        direction TB
        L_R[router]
        L_S[LikeService]
        L_M[PostLikesModel]
        L_R --> L_S
        L_S --> L_M
    end

    A_S -->|"UsersModel · 가입·이메일/닉네임·create_user"| U_M
    A_S -->|"MediaModel · signupToken 검증·첨부"| M_M

    U_R -->|"AuthService.revoke_refresh_for_user"| A_S
    U_S -->|"MediaModel · ref_count·삭제"| M_M
    U_S --> U_M

    P_S -->|"MediaModel · 이미지 ref_count"| M_M
    P_S -->|"LikeService.is_post_liked"| L_S
    P_S --> P_M

    C_S -->|"PostsModel · 댓글수 증감·get_post_by_id"| P_M
    C_S --> C_M

    L_R -->|"게시글 존재 확인"| P_M
    L_R -->|"댓글 존재 확인"| C_M
    L_S -->|"PostsModel · like_count 증감·조회"| P_M
    L_S -->|"CommentsModel·CommentLikesModel · like_count"| C_M
    L_S --> L_M
```

- **auth**: 회원가입·로그인 시 `UsersModel`, `MediaModel`(signupToken 검증·첨부) 사용. Redis는 서비스 내부에서만 사용.
- **users**: 라우터가 비밀번호 변경·탈퇴 시 `AuthService.revoke_refresh_for_user` 호출. `UserService`는 프로필/강아지·이미지 ref_count에 `MediaModel` 사용.
- **posts**: `PostService`는 이미지 ref_count·상세 조회 시 `is_liked`를 위해 `MediaModel`, `LikeService` 참조.
- **comments**: `CommentService`는 댓글 수 동기화를 위해 `PostsModel`만 참조(함수 내부 임포트).
- **likes**: 라우터가 게시글/댓글 존재 여부 확인에 `PostsModel`, `CommentsModel` 사용. `LikeService`는 `PostLikesModel`, `CommentsModel`(get_like_count), `CommentLikesModel`(create/delete·like_count 갱신), `PostsModel`(like_count 갱신) 사용.
- **media**: 다른 도메인을 참조하지 않음.
- **reports**: `ReportService`가 게시글·댓글 신고 시 `ReportsModel.create_report`(Insert만, 누적)·`PostsModel`/`CommentsModel`의 `report_count` 증가·임계값 도달 시 `blinded` 설정. `reports` 테이블은 `target_type`(TargetType: POST/COMMENT), `reason`(자유 문자열), `deleted_at`(신고 무시 시 soft delete)만 사용하며, `status` 컬럼은 제거됨.
- **admin**: 관리자 전용. 신고된 게시글·댓글 통합 목록(`GET /admin/reported-posts`, `target_type`·`content_preview` 포함), 게시글/댓글 각각 블라인드 해제·블라인드 처리·신고 무시·삭제, 유저 정지/해제 API 제공. 내부적으로 `PostsModel`·`CommentsModel`·`ReportsModel`·`UsersModel` 사용.
- **dogs**: `UserService`·`UsersModel`에서 `DogProfile` 관리. users 도메인에 포함.

---

## 2. 요청 흐름 (Request Lifecycle)

모든 HTTP 요청은 **미들웨어 파이프라인**을 거친 뒤 라우터·컨트롤러·모델로 전달됩니다. Starlette는 **나중에 등록한 미들웨어가 요청 시 먼저** 실행되므로, 아래 순서는 “요청이 들어올 때” 통과하는 순서입니다.

**요청 흐름**

```
[클라이언트]  HTTP 요청 (JSON body, Cookie)
    │
    ▼
① Lifespan (앱 시작 1회)
   → DB 연결 확인. 실패 시 log 후 요청 시점에 재시도.
   → REDIS_URL 있으면 Redis 연결 풀 생성·저장. 실패 시 Fail-open.
   → cleanup_once 1회 실행 후, SESSION_CLEANUP_INTERVAL > 0 이면 주기적 정리 태스크 시작.
   → yield 이후(종료 시): 정리 태스크 종료 대기 → Redis 연결 종료 → DB 연결 종료.

② GET /health
   → check_database() 호출. 성공 200 + { code, data: { status: "ok", database: "connected" } }, 실패 503 + { code: DB_ERROR, data: { status: "degraded", database: "disconnected" } }.

③ 미들웨어 (요청마다)
   **순수 ASGI**(add_middleware): RequestIdMiddleware, ProxyHeadersMiddleware, RateLimitMiddleware, GZipMiddleware. LIFO이므로 **코드상 최하단에 등록한 RequestIdMiddleware**가 요청 진입 시 **가장 먼저** 실행되어 UUID4 발급·scope["state"]["request_id"] 주입. GZip은 안쪽에 두어 응답 body만 압축(1KB 미만은 미압축).
   **함수형**(middleware("http")): security_headers, access_log.
   실행 순서: request_id → proxy_headers → rate_limit → gzip → access_log → security_headers (2.1 미들웨어 순서 참고).

④ 라우터 매칭
   v1_router = APIRouter(prefix="/v1"). include 순서: auth → users → dogs → media → posts → comments → likes → reports → admin.
   예: /v1/auth/login, /v1/users/me, /v1/posts, /v1/posts/{id}/comments, /v1/reports, /v1/admin/reported-posts.

⑤ 의존성 (Depends)
   → get_master_db / get_slave_db: 요청마다 AsyncSession 주입. 트랜잭션은 서비스에서 `async with db.begin():`으로만 시작·커밋(autobegin=False). finally에서 세션 close.
   → get_current_user: Authorization Bearer 검증 → CurrentUser. 만료 시 401 + TOKEN_EXPIRED.
   → require_post_author / require_comment_author: 게시글·댓글 수정/삭제 시 작성자 본인 여부.

⑥ Pydantic (Schema)
   요청 body·쿼리 검증. 실패 시 400 + code (exception_handlers에서 RequestValidationError 처리).

⑦ Route 핸들러 → Service → Model
   라우터가 Service를 호출하고 반환값을 ApiResponse로 포장. 비즈니스 로직·도메인 간 조율은 Service에서 수행. Model은 AsyncSession만 사용하며, 트랜잭션은 Service의 `async with db.begin():` 블록에서만 시작·커밋됨.

⑧ 예외 핸들러
   RequestValidationError → 400. HTTPException → status_code. DB 예외·Exception(catch-all) → 500/503. 모든 에러 응답은 { code, message, data } 형식 통일. 500 시 클라이언트에는 스택/쿼리 노출 없이 "Internal Server Error" 등 마스킹 메시지만 반환, 서버 로그에 request_id와 함께 기록.
    │
    ▼
HTTP 응답  { "code": "...", "message": "...", "data": ... }  (에러 시에도 X-Request-ID 헤더 포함)
```

### 2.1 미들웨어 순서

**등록 방식**: RequestId·ProxyHeaders·RateLimit·GZip은 **순수 ASGI**로 `add_middleware()` 등록. Starlette LIFO이므로 **코드상 가장 마지막에 등록한 미들웨어**가 요청 진입 시 **가장 먼저** 실행된다. RequestIdMiddleware를 **최하단**에 두어 맨 먼저 ID를 발급하고, 이어서 ProxyHeaders(IP) → RateLimit → GZip 순으로 실행된다. 나머지(security_headers, access_log)는 `app.middleware("http")(...)`로 함수형 등록.

| 순서 | 단계 | 의도(Why) |
|------|------|-----------|
| 1 | **Request ID** | 순수 ASGI. 요청 진입 시 UUID4 발급 → `scope.setdefault("state", {})["request_id"]` 저장(FastAPI의 `request.state.request_id`와 동일). `send`를 래핑해 `http.response.start` 시 **응답 헤더에 X-Request-ID 주입**하므로 4xx/5xx 예외 응답에도 헤더가 포함되어 프론트에서 에러 리포트 시 ID를 첨부할 수 있다. contextvars에 설정되어 로그 포맷 `[%(request_id)s]`로 **요청 단위 추적** 가능. |
| 2 | **Proxy Headers** | 순수 ASGI(scope/receive/send). Nginx/ALB 뒤에서 실제 클라이언트 IP를 쓰기 위해 `X-Forwarded-For`를 사용할 수 있으나, **직접 파싱하면 IP 스푸핑**에 취약하다. **신뢰할 수 있는 프록시 IP**(`TRUSTED_PROXY_IPS`)에서 온 요청일 때만 첫 번째 값을 `scope["client"]`에 반영한다. Rate Limit·접근 로그는 **이후 항상 `request.client.host`만** 사용해, 한 번 검증된 IP만 신뢰한다. |
| 3 | **Rate Limit** | 순수 ASGI. Redis 기반 **Fixed Window**. 경로별 키: 전역·로그인·회원가입 업로드. Lua로 INCR+EXPIRE 원자 처리. **Fail-open**: Redis 장애 시 로그인·회원가입 업로드만 **인메모리 Fallback**(10,000키, eviction) 적용, 나머지 경로는 제한 없이 통과(가용성 우선). OPTIONS·`/health`는 제외. |
| 4 | **GZip** | Starlette `GZipMiddleware`. 응답 body가 **1KB 이상**일 때만 gzip 압축하여 전송(작은 JSON·에러 응답은 CPU 낭비 방지). `Accept-Encoding: gzip` 클라이언트에만 적용. |
| 5 | **Access Log** | 요청 전 구간 시간 측정 → `call_next` 실행. 4xx는 WARNING, 5xx·미처리 예외는 ERROR·traceback 기록. DEBUG 시 응답에 `X-Process-Time` 헤더 추가. |
| 6 | **Security Headers** | X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy, CSP(설정 시) 등으로 클릭재킹·MIME 스니핑 등을 완화한다. |

이후 **라우터 매칭** → **의존성 주입**(get_master_db / get_slave_db, get_current_user, get_client_identifier, 권한 체크) → **Route 핸들러** → **Service** → **Model** 순으로 진행한다.

### 2.2 요청 흐름 다이어그램

```mermaid
flowchart LR
    subgraph 미들웨어
        A[request_id<br/>순수 ASGI] --> B[proxy_headers<br/>순수 ASGI]
        B --> C[rate_limit<br/>순수 ASGI]
        C --> D[gzip]
        D --> E[access_log]
        E --> F[security_headers]
    end
    F --> G[라우터]
    G --> H[의존성: DB·CurrentUser·권한]
    H --> I[Service]
    I --> J[Model]
    J --> K[응답]
```

- **IP 일관성**: Rate Limit·Access Log 모두 **ProxyHeadersMiddleware에서 검증된 `request.client.host`**만 사용하므로, 헤더를 직접 파싱하는 코드는 두지 않는다(스푸핑 방어).

---

## 3. 데이터베이스 아키텍처

### 3.1 Master / Slave 분리 원리

| 구분 | 의존성 | URL | 용도 |
|------|--------|-----|------|
| **쓰기(CUD)** | `get_master_db()` | `WRITER_DB_URL` (미설정 시 `DB_*` 단일 URL) | 회원가입·로그인 제외한 모든 생성·수정·삭제 |
| **읽기(Read)** | `get_slave_db()` | `READER_DB_URL` (미설정 시 Writer와 동일) | 목록·상세·가용성 조회 등 읽기 전용 |

- **의도**: 조회 부하를 Reader 풀으로 분산하고, Writer 풀은 쓰기 전용으로 유지한다. 단일 URL 구성 시에도 **의존성만 나누어** 추후 Read Replica 도입 시 URL만 바꾸면 된다.

### 3.2 READ ONLY 세션 적용 메커니즘

Reader 엔진은 Writer와 **별도 풀**로 분리되어 있으며, 동일 URL(또는 `READER_DB_URL`)로 읽기 전용 복제본에 연결할 수 있다. PostgreSQL에서는 필요 시 트랜잭션 시작 시 `SET TRANSACTION READ ONLY`를 적용해 쓰기 방지할 수 있다. 애플리케이션에서는 `get_slave_db()`로 Reader 세션만 사용하므로, 쓰기 로직이 Reader에 주입되지 않도록 의존성 구분을 유지한다.

### 3.3 풀 및 세션 (Full-Async)

- 엔진은 **psycopg3** (`postgresql+psycopg://`) + **create_async_engine**으로 생성하며, `async_sessionmaker`로 AsyncSession 팩토리(autobegin=False, expire_on_commit=False)를 둔다.
- 풀 설정은 환경 변수로 조정한다.
- 요청 스코프: **get_master_db**·**get_slave_db**에서 AsyncSession을 yield한 뒤 finally에서 close. **트랜잭션은 서비스에서만** `async with db.begin():`으로 시작·커밋한다(모델에서 commit/rollback 금지).
- 비요청 스코프(cleanup, 예외 핸들러 등): 별도 연결 컨텍스트 매니저를 사용하고, 호출부에서 `async with db.begin():`으로 트랜잭션을 관리한다.

---

## 4. 인증·보안

### 4.1 JWT + Redis를 조합한 토큰 무효화(Revocation) 전략

- **Access Token**: Stateless. `Authorization: Bearer <token>`으로 전달. 서버에 저장하지 않아 **수평 확장·멀티 인스턴스**에 유리하다. 만료 시 401 + `TOKEN_EXPIRED`로 프론트에서 Refresh 호출을 유도한다.
- **Refresh Token**: HttpOnly 쿠키 + **Redis Set** `rt:{user_id}` 저장. 토큰은 **SHA256 해시**로 저장·검증하여 원문 노출을 방지한다. **멀티 디바이스 지원**: `SADD`(로그인), `SISMEMBER`(리프레시), `SREM`(단일 기기 로그아웃), `DEL`(전체 무효화—탈퇴·비밀번호 변경). XSS로부터 토큰 값을 읽기 어렵게 하고, 즉시 무효화 가능하다.
- 로그인 시 Access는 JSON body, Refresh는 쿠키(HttpOnly, Secure, SameSite=Lax)로 내려준다. Refresh 요청 시 쿠키의 토큰 해시가 Redis Set에 있는지 확인한 뒤, 통과 시 새 Access Token만 JSON으로 반환한다.

### 4.2 Magic Byte 기반 이미지 업로드 검증

**Content-Type 헤더만 믿으면** 악의적으로 조작된 파일이 이미지로 저장될 수 있다.  
업로드 시 **파일 시그니처(매직 바이트)**로 실제 포맷을 검증한다. 허용 타입(JPEG, PNG, WebP)이어도 **바이트 스트림 앞부분**이 해당 포맷 시그니처와 일치하지 않으면 거부한다. 용량은 청크 단위로 읽으며 `MAX_FILE_SIZE` 초과 시 중단한다.

### 4.3 Pydantic을 활용한 XSS 방어

요청·응답 DTO는 **Pydantic v2** 스키마로 검증·직렬화된다. 문자열 필드는 이스케이프 등으로 안전하게 다루며, 응답은 항상 스키마를 거쳐 내려가므로 **임의 HTML/스크립트 주입**을 줄이는 데 기여한다. (추가로 CSP 등 보안 헤더는 security_headers 미들웨어에서 설정한다.)

---

## 5. 데이터 정합성

- **게시글(Post)**: `deleted_at`으로 **Soft Delete**. `blinded_at`은 신고 누적으로 자동 블라인드 시 설정. 목록·상세 조회 시 `deleted_at IS NULL`만 노출하며, 삭제 시 댓글(Comment)·좋아요(Like)·post_images·이미지 ref_count를 함께 정리한다.
- **좋아요(Like)**: 좋아요 버튼을 **두 번 눌러도** 에러가 나지 않도록, INSERT 시 `ON CONFLICT DO NOTHING`을 사용한다. RETURNING으로 실제 삽입 여부를 확인해 **새로 추가된 경우에만** like_count를 증가시킨다. 취소 시에는 DELETE 후 like_count 감소. 한 요청당 단일 트랜잭션으로 묶어 정합성을 유지한다. 게시글 삭제 시 좋아요 행은 함께 Hard Delete한다.
- **댓글(Comment)**: 루트·대댓글 모두 **Soft Delete**. **루트 댓글**을 삭제하면 목록에는 남겨 두되 "삭제된 댓글입니다"로 표시한다. **대댓글**을 삭제하면 목록에서 아예 제외한다. 자식이 하나도 없는 삭제된 루트는 트리 빌드 시 제외해 빈 껍데기가 안 보이게 한다.

### 5.2 회원가입–이미지 참조 무결성(ref_count)

회원가입 시 **유저 생성**과 **프로필 이미지 소유권 이전**을 한 트랜잭션에서 처리한다.

1. 유저 생성.
2. 프로필 이미지가 있으면: signupToken 검증 → 이미지 `uploader_id` 설정, `ref_count` +1, 토큰 필드 NULL 처리.

이미지가 없으면 2단계를 건너뛰고 정상 가입된다. 트랜잭션은 서비스의 `async with db.begin():` 블록 종료 시 자동 커밋된다.

### 5.3 복수 테이블 조율

**여러 테이블을 함께 갱신해야 하는 로직**은 Service에서 한 트랜잭션으로 처리한다.

- **댓글 생성/삭제** → 게시글의 `comment_count` 증감
- **게시글 삭제** → 댓글·좋아요·이미지 링크·이미지 ref_count 정리 후 soft delete
- **프로필 수정(강아지·이미지)** → 강아지 테이블 동기화 + 기존/신규 이미지 ref_count 증감
- **신고 무시(관리자)** → `reports` 해당 target 행들 soft delete(`deleted_at`) 후, 글/댓글의 `report_count`·`is_blinded` 초기화

---

## 6. 성능 최적화

### 6.1 selectinload를 활용한 N+1 쿼리 방어

게시글 목록처럼 **1:N 컬렉션**(예: `post_images`)을 함께 불러올 때, **joinedload**만 쓰면 LIMIT이 “행 기준”으로 적용되어, 조인 결과 행이 폭증한 뒤 애플리케이션에서 unique로 줄이는 형태가 된다.  
**`selectinload(Post.post_images)`**를 사용하면:

- 메인 쿼리: Post에 **LIMIT/OFFSET**이 정확히 적용되고, N:1인 `Post.user`는 **joinedload**로 유지해도 행 수를 부풀리지 않는다.
- 보조 쿼리 1회: `post_id IN (...)`으로 해당 포스트들의 `post_images`(및 필요 시 `PostImage.image`)만 추가 로드한다.

따라서 **N+1**을 막으면서도 **페이지네이션**이 DB 레벨에서 올바르게 동작한다. **FK 인덱스**: `selectinload`가 발생시키는 `WHERE foreign_key_id IN (...)` 쿼리 성능을 위해, PostImage.post_id·Comment.post_id·DogProfile.owner_id 등 1:N 자식 측 FK 컬럼에는 `index=True`를 두어 인덱스가 생성되도록 했다.

### 6.2 S3 클라이언트 싱글톤

S3 사용 시 **매 요청마다 클라이언트를 새로 만들지 않는다**.  
첫 호출 시에만 생성해 전역에 캐시하고, 이후 업로드·삭제는 모두 해당 클라이언트를 재사용한다. 연결·인증 오버헤드를 줄인다.  
로컬 저장소(`STORAGE_BACKEND=local`) 환경에서는 S3 코드를 아예 타지 않으므로 boto3 의존성이 로드되지 않는다.

### 6.3 조회수 중복 방지

GET이 멱등해야 하므로 조회수는 **전용 POST 엔드포인트**로만 증가시킨다.

**동작**: 같은 (게시글ID, 클라이언트 식별자) 조합으로 TTL(24시간) 내 재요청이 오면 조회수를 올리지 않는다. 인메모리 dict로 `(post_id, client_identifier)` → 만료 시각을 저장하고, 50,000키 초과 시 오래된 항목을 evict한다.

**클라이언트 식별자**: Rate Limit·Access Log는 ProxyHeaders가 검증한 `request.client`만 쓰지만, 조회수는 X-Forwarded-For를 직접 참조한다. 조회수 조작 영향이 제한적이어서 가용성을 우선한다. 추후 Redis로 분산 전환 가능하다.

---

## 7. 이미지: signupToken·ref_count

이미지는 **미리 업로드한 뒤** 본문·가입과 연결하는 방식이다. 가입 전 이미지는 **signupToken**으로 소유를 증명하고, **ref_count**로 참조 수를 관리해 0이 되면 파일·DB 레코드를 정리한다.

- **signupToken**: 업로드 시 토큰 발급, DB에는 해시만 저장. 회원가입 요청 시 `profileImageId`·`signupToken`을 보내 서버가 검증한 뒤 `attach_signup_image`로 `uploader_id`·ref_count 갱신 및 토큰 필드 NULL 처리.
- **ref_count**: 게시글 첨부·프로필·가입 시 +1, 제거·삭제 시 -1. **0 이하가 되면** `storage_delete` 후 Image 레코드 삭제. 사용 중인 이미지(`ref_count > 0`)는 `delete_image_by_owner`에서 삭제를 거부(409 CONFLICT)하여 **엑스박스·정합성 깨짐**을 방지한다.

저장소는 `STORAGE_BACKEND=local`이면 프로젝트 `upload/`, `s3`이면 S3이며 `build_url`로 URL을 만든다.

---

## 8. 게시글 피드: 검색·정렬·차단·신고

### 8.1 검색

게시글 목록 API의 `q` 쿼리 파라미터로 **제목·본문 검색**을 한다.

**동작**: `q`가 있으면 `title ILIKE %pattern%` OR `content ILIKE %pattern%` 조건을 추가한다. 한글·부분 일치가 가능하다. PostgreSQL `pg_trgm` 확장과 GIN 인덱스로 `ILIKE` 패턴 검색 성능을 보완한다.

### 8.2 정렬

게시글 목록: `sort`에 따라 `latest`(최신순, 기본)·`oldest`·`popular`(좋아요순)·`views`(조회수순) 적용.  
댓글 목록: `latest`·`oldest`·`popular` 지원.

### 8.3 차단(Block) 필터

유저가 다른 유저를 차단하면, **피드·댓글**에서 차단한 유저의 게시글·댓글이 보이지 않는다.

**동작**: 로그인한 유저가 목록/상세를 조회할 때, 쿼리에 "현재 유저가 차단한 유저의 콘텐츠 제외" 조건을 넣는다. 비로그인 사용자에게는 적용하지 않는다.

### 8.4 신고·블라인드

게시글·댓글을 신고할 수 있다. 신고는 **항상 새 행(Insert)**으로 누적되며, 동일 유저가 같은 대상을 다시 신고해도 별도 레코드가 추가된다.

**동작**:
- 신고 시 `reports` 테이블에 `target_type`(POST/COMMENT), `target_id`, `reason`(자유 문자열)으로 행을 삽입하고, 해당 글/댓글의 `report_count`를 1 증가시킨다.
- `report_count`가 임계값(기본 5) 이상이면 **자동 블라인드**된다.
- **신고 무시**(관리자 초기화) 시에만 해당 target의 `reports` 행을 **soft delete**(`deleted_at` 설정)하고, 글/댓글의 `report_count`·`is_blinded`를 초기화한다. 이후 같은 유저가 다시 신고하면 새 행이 생성되어 목록에 다시 노출된다.
- `reports` 테이블에는 `status` 컬럼을 두지 않으며, 애플리케이션에서는 `TargetType` enum(POST, COMMENT)으로 `target_type`을 다룬다.

블라인드된 콘텐츠는 관리자 화면에서 검토·블라인드 해제·신고 무시·삭제(글/댓글)할 수 있다.

---
