# PuppyTalk API - 커뮤니티 백엔드

FastAPI 기반의 커뮤니티 백엔드 API 서버입니다. **Route → Controller → Model(RCM)** 패턴과 전역 예외/미들웨어 정책을 적용했습니다.

---

## 아키텍처 개요

```
[클라이언트] → [CORS] → [Security Headers] → [Rate Limit + Duration 로깅]
    → [Route] → [Controller] → [Model(인메모리 저장소)]
    ← [응답: { "code": "...", "data": ... }]
```

- **미들웨어**: CORS, HTTP 보안 헤더, 전역 Rate Limiting(인메모리), 요청 처리 시간(X-Process-Time 헤더 + 로깅).
- **예외**: RequestValidationError → 400 `INVALID_REQUEST_BODY`, HTTPException → 상태코드 유지 + `{code, data}`, 500 → `INTERNAL_SERVER_ERROR`.
- **인증**: Dependency `get_current_user(session_id: Cookie)` → user_id. 세션은 인메모리.

---

## 폴더 구조 (2단계 유지)

```
.
├── app/
│   ├── core/                    # 공통
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── dependencies.py      # get_current_user (Cookie → user_id)
│   │   ├── exception_handlers.py
│   │   ├── logging_config.py
│   │   └── middleware.py        # CORS, Security, Rate Limit, Duration
│   ├── auth/
│   │   ├── auth_route.py
│   │   ├── auth_controller.py
│   │   ├── auth_model.py        # 인메모리 사용자/세션
│   │   └── auth_schema.py
│   ├── users/
│   │   ├── users_route.py
│   │   ├── users_controller.py
│   │   ├── users_model.py       # AuthModel 래핑
│   │   └── users_schema.py
│   ├── posts/
│   │   ├── posts_route.py
│   │   ├── posts_controller.py
│   │   ├── posts_model.py
│   │   └── posts_schema.py
│   ├── comments/
│   │   ├── comments_route.py
│   │   ├── comments_controller.py
│   │   ├── comments_model.py
│   │   └── comments_schema.py
│   └── likes/
│       ├── likes_route.py
│       ├── likes_controller.py
│       ├── likes_model.py
│       └── likes_schema.py
├── main.py
├── pyproject.toml
├── .env.example
├── .gitignore
└── README.md
```

---

## 점검 체크리스트 (현업 스타일)

| 항목 | 적용 여부 |
|------|-----------|
| 미들웨어: CORS | ✅ CORSMiddleware, allow_credentials |
| 미들웨어: Rate Limiting | ✅ 인메모리, IP 기반 |
| 미들웨어: 요청 처리 시간 | ✅ X-Process-Time 헤더 + duration 로깅 |
| Dependency: 인증/현재 사용자 | ✅ get_current_user(Cookie session_id) → user_id |
| RCM 흐름 | ✅ Route → Controller → Model (Controller에서 DB 직접 접근 없음) |
| Path 검증 | ✅ 타입 힌트만 (Path(..., description=...)) |
| Query 검증 | ✅ Query(ge=1 등) 사용 |
| Optional Body(None) 금지 | ✅ 요청 Body는 Pydantic 모델로 수신 |
| 예외 응답 포맷 | ✅ { "code": "CODE", "data": null } 통일 (RequestValidationError, HTTPException, 500) |

---

## 꼭 필요한 개념 vs 제외한 개념

- **적용**: CORS, Rate Limiting, 전역 예외 핸들러, 쿠키 세션(인메모리), RCM, Pydantic 검증, HTTP 보안 헤더, 요청 duration 로깅.
- **제외(간단 커뮤니티 범위 밖)**: ETag/HTTP 캐시, Redis 세션, GraphQL, WebSocket, Timeout 미들웨어.

---

## Postman 테스트 시나리오 (최소 10개)

**Base URL**: `http://localhost:8000`  
**공통**: 인증 필요 API는 로그인 후 쿠키 `session_id` 자동 저장된 환경에서 호출.

### 정상 플로우

1. **회원가입**  
   `POST /auth/signup`  
   Body (JSON): `{"email":"test@example.com","password":"Abc123!@#","passwordConfirm":"Abc123!@#","nickname":"테스트"}`  
   기대: 201, `{"code":"SIGNUP_SUCCESS","data":null}`

2. **로그인**  
   `POST /auth/login`  
   Body: `{"email":"test@example.com","password":"Abc123!@#"}`  
   기대: 200, `{"code":"LOGIN_SUCCESS","data":{...}}`, 응답 헤더/쿠키에 `session_id` 설정됨.

3. **쿠키 유지 확인**  
   `GET /auth/me` (Cookie에 `session_id` 포함)  
   기대: 200, `{"code":"AUTH_SUCCESS","data":{...}}`

4. **게시글 작성**  
   `POST /posts`  
   Body: `{"title":"제목","content":"본문"}`  
   기대: 201, `{"code":"POST_UPLOADED","data":{"postId":1}}`

5. **게시글 목록 조회**  
   `GET /posts?page=1&size=10`  
   기대: 200, `{"code":"POSTS_RETRIEVED","data":[...]}`

6. **게시글 상세 조회**  
   `GET /posts/1`  
   기대: 200, `{"code":"POST_RETRIEVED","data":{...}}`

7. **게시글 수정**  
   `PATCH /posts/1`  
   Body: `{"title":"수정제목","content":"수정본문"}`  
   기대: 200, `{"code":"POST_UPDATED","data":null}`

8. **댓글 작성**  
   `POST /posts/1/comments`  
   Body: `{"content":"댓글 내용"}`  
   기대: 201

9. **좋아요 추가**  
   `POST /posts/1/likes`  
   기대: 201

10. **로그아웃**  
    `POST /auth/logout` (Cookie 포함)  
    기대: 200, `{"code":"LOGOUT_SUCCESS","data":null}`

### 예외 케이스 (재현 방법)

| 코드 | 재현 방법 |
|------|-----------|
| **400** | `POST /auth/signup` Body 필드 누락/형식 오류 → `INVALID_REQUEST_BODY` |
| **401** | `GET /auth/me` Cookie 없음 또는 잘못된 session_id → `UNAUTHORIZED` |
| **403** | `PATCH /users/2` 로 user_id=1로 로그인한 뒤 타인(2) 수정 시도 → `FORBIDDEN` |
| **404** | `GET /posts/99999` 존재하지 않는 post_id → `POST_NOT_FOUND` |
| **409** | 동일 이메일로 다시 `POST /auth/signup` → `EMAIL_ALREADY_EXISTS` |
| **429** | 짧은 시간에 동일 IP로 11회 이상 API 호출 → `RATE_LIMIT_EXCEEDED` |
| **500** | 서버 내부 오류(예: Model 예외) → `INTERNAL_SERVER_ERROR`, data: null |

모든 실패 응답은 `{"code": "CODE_STRING", "data": null}` 형태입니다.

---

## 설치 및 실행

### 1. 가상환경 생성 및 활성화

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python -m venv venv
source venv/bin/activate
```

### 2. 의존성 설치

```bash
# pip를 사용하는 경우
pip install -e ".[dev]"

# 또는 Poetry를 사용하는 경우 (선택사항)
poetry install
```

### 3. 환경 변수 설정

`.env.example` 파일을 참고하여 `.env` 파일을 생성하세요.

```bash
# Windows
copy .env.example .env

# Linux/Mac
cp .env.example .env

# 또는 직접 .env 파일 생성 후 아래 내용 입력
```

### 4. 서버 실행

```bash
# 개발 모드 (자동 리로드)
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 프로덕션 모드
uvicorn main:app --host 0.0.0.0 --port 8000

# 환경 변수 사용 (config.py의 설정값 사용)
uvicorn main:app --host ${HOST} --port ${PORT}
```

### 5. API 문서 확인

서버 실행 후 다음 URL에서 API 문서를 확인할 수 있습니다:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### 6. 테스트 실행 (선택사항)

테스트 코드는 `tests/` 디렉토리에 작성할 수 있습니다.

```bash
# 모든 테스트 실행
pytest

# 특정 테스트 파일 실행
pytest tests/test_auth.py

# 상세 출력과 함께 실행
pytest -v

# 커버리지 포함 실행
pytest --cov=app
```

## 주요 기능

- **인증 (Auth)**: 회원가입, 로그인, 로그아웃, 세션 관리 (bcrypt 비밀번호 해싱)
- **사용자 (Users)**: 프로필 조회/수정, 비밀번호 변경, 프로필 이미지 업로드
- **게시글 (Posts)**: 게시글 작성/조회/수정/삭제, 이미지 업로드
- **댓글 (Comments)**: 댓글 작성/조회/수정/삭제
- **좋아요 (Likes)**: 좋아요 추가/취소
- **보안 기능**: Rate Limiting, 전역 예외 핸들러, CORS 설정
- **로깅**: 에러 추적 및 보안 이벤트 모니터링

## 기술 스택

- **FastAPI**: 웹 프레임워크
- **Pydantic**: 데이터 검증 및 설정 관리
- **Uvicorn**: ASGI 서버
- **Python-dotenv**: 환경 변수 관리
- **bcrypt**: 비밀번호 해싱 (보안)
- **Python logging**: 로깅 시스템 (에러 추적 및 모니터링)
- **pytest**: 테스트 프레임워크

## 환경 변수

`.env` 파일에서 다음 설정을 관리할 수 있습니다:

- `HOST`: 서버 호스트 (기본값: 0.0.0.0)
- `PORT`: 서버 포트 (기본값: 8000)
- `DEBUG`: 디버그 모드 (기본값: True)
- `CORS_ORIGINS`: CORS 허용 오리진 (기본값: *)
- `SESSION_EXPIRY_TIME`: 세션 만료 시간 (초, 기본값: 86400)
- `RATE_LIMIT_WINDOW`: Rate limiting 윈도우 (초, 기본값: 60)
- `RATE_LIMIT_MAX_REQUESTS`: 최대 요청 수 (기본값: 10)
- `MAX_FILE_SIZE`: 최대 파일 크기 (바이트, 기본값: 10485760 = 10MB)
- `ALLOWED_IMAGE_TYPES`: 허용된 이미지 타입 (쉼표로 구분, 기본값: image/jpeg,image/jpg,image/png)
- `BE_API_URL`: API 기본 URL (파일 업로드 URL 생성용, 예: http://localhost:8000 또는 https://api.example.com)

## 데이터 저장

현재는 인메모리 저장소를 사용합니다. 서버 재시작 시 모든 데이터가 초기화됩니다.

## 라이선스

이 프로젝트는 학습 목적으로 제작되었습니다.
