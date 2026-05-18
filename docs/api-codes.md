# API 응답 code · HTTP status 매핑

API 응답 body의 `code` 값과 HTTP 상태 코드 매핑입니다. 프론트·백엔드 협의용이며 Swagger/ReDoc과 동일 enum을 씁니다.

**정본**: `app/common/codes.py` (`ApiCode`) · 응답 envelope: [architecture.md](architecture.md) · [request-and-api-contract.md](request-and-api-contract.md#4-apiresponse-계약) · 핸들러: `app/core/exception_handlers.py`

---

## 성공 응답 규격

- **대부분의 성공(200/201/202)** — 본문 `code`는 **`OK`** (CRUD·조회·관리자·알림·신고 등).
- **예외 (성공이지만 code 구분)**
  - Auth: `SIGNUP_SUCCESS`, `LOGIN_SUCCESS`, `LOGOUT_SUCCESS`, `AUTH_SUCCESS`
  - 좋아요 중복: `ALREADY_LIKED` (HTTP 200, `data`에 count 등)
  - 대표 강아지: `DOG_UPDATED` (`PATCH /users/me/dogs/representative`)
- **DELETE** — HTTP **200** + `ApiResponse` (`code: OK`, `data: null` 가능). 204는 사용하지 않음.

---

## 공통 · HTTP · DB

| HTTP | code | 상황 |
|------|------|------|
| 200 | OK | 대부분의 성공 |
| 400 | INVALID_REQUEST | 비즈니스상 잘못된 요청 |
| 400 | INVALID_REQUEST_BODY | Pydantic 검증 실패(기본) · `RequestValidationError` |
| 400 | MISSING_REQUIRED_FIELD | 필수 필드 누락(서비스/스키마) |
| 400 | INVALID_PASSWORD_FORMAT | 비밀번호 형식 |
| 400 | INVALID_FILE_FORMAT | 파일 형식(검증 msg에 code name 포함 시) |
| 400 | CONSTRAINT_ERROR 외 INVALID_REQUEST | 기타 IntegrityError |
| 401 | UNAUTHORIZED | 미인증 · 토큰 없음/무효/만료(만료도 **UNAUTHORIZED**로 통일) |
| 403 | FORBIDDEN | 권한 없음 · 비활성 유저 · 관리자 아님 |
| 404 | NOT_FOUND | 일반 404 (`HTTPException`) |
| 404 | POST_NOT_FOUND / USER_NOT_FOUND / … | 도메인 예외 |
| 409 | CONFLICT | 중복 키(이메일·닉네임 외) · **멱등 진행 중** · `ConcurrentUpdateException` |
| 409 | EMAIL_ALREADY_EXISTS / NICKNAME_ALREADY_EXISTS | 회원 중복 |
| 409 | CONSTRAINT_ERROR | FK 위반 등 (1451/1452) |
| 409 | IMAGE_IN_USE | 이미지 참조 중 |
| 413 | PAYLOAD_TOO_LARGE | 본문/업로드 크기 초과 |
| 429 | RATE_LIMIT_EXCEEDED | 일반 rate limit |
| 429 | LOGIN_RATE_LIMIT_EXCEEDED | 로그인 전용 limit |
| 500 | INTERNAL_SERVER_ERROR | 미처리 예외(메시지 마스킹) |
| 500 | DB_ERROR | DB OperationalError/DatabaseError |
| 503 | DB_ERROR | `GET /v1/health` DB ping 실패 |
| 503 | NOTIFICATION_SSE_UNAVAILABLE | Redis 없음 · SSE 불가(JSON) |

> **참고**: enum에 `TOKEN_EXPIRED`, `UNPROCESSABLE_ENTITY`가 있으나, 현재 HTTP 핸들러는 검증 실패를 **400** + body `code`로 내리고, JWT 만료는 **401 `UNAUTHORIZED`** 로 처리합니다.

---

## Auth

| HTTP | code | 상황 |
|------|------|------|
| 201 | SIGNUP_SUCCESS | 회원가입 |
| 200 | LOGIN_SUCCESS | 로그인 (Set-Cookie refresh) |
| 200 | LOGOUT_SUCCESS | 로그아웃 |
| 200 | AUTH_SUCCESS | `POST /auth/refresh` |
| 409 | EMAIL_ALREADY_EXISTS | 이메일 중복 |
| 409 | NICKNAME_ALREADY_EXISTS | 닉네임 중복 |
| 401 | INVALID_CREDENTIALS | 로그인 실패 |
| 400 | SIGNUP_IMAGE_TOKEN_INVALID | 가입용 업로드 토큰 무효 |

---

## Posts · Comments · Likes

| HTTP | code | 상황 |
|------|------|------|
| 404 | POST_NOT_FOUND | 게시글 없음/비가시 |
| 400 | POST_FILE_LIMIT_EXCEEDED | 첨부 이미지 수 초과 |
| 400 | POST_HASHTAG_LIMIT_EXCEEDED | 해시태그 수 초과 |
| 404 | COMMENT_NOT_FOUND | 댓글 없음 |
| 400 | INVALID_POSTID_FORMAT | postId 형식 오류 |
| 200 | ALREADY_LIKED | 이미 좋아요(게시글/댓글) |
| 404 | POST_NOT_FOUND / COMMENT_NOT_FOUND | 좋아요 대상 없음 |
| 409 | CONFLICT | 동시 수정(`StaleDataError`) |

`LIKE_NOT_FOUND` — enum 정의만 있음, 현재 서비스에서 미사용.

---

## Media

| HTTP | code | 상황 |
|------|------|------|
| 404 | IMAGE_NOT_FOUND | 이미지 없음 |
| 409 | IMAGE_IN_USE | 삭제 불가(참조 중) |
| 400 | INVALID_IMAGE_FILE | 매직 바이트/포맷 불일치 |
| 400 | FILE_SIZE_EXCEEDED | 크기 초과 |
| 400 | INVALID_FILE_TYPE | MIME 불허 |

---

## Users · Dogs · Reports · Notifications

| HTTP | code | 상황 |
|------|------|------|
| 404 | USER_NOT_FOUND | |
| 403 | USER_WITHDRAWN | 탈퇴·비활성 |
| 200 | DOG_UPDATED | 대표 강아지 설정 |
| 200 | OK | 신고 접수 (`ReportSubmitData`) |
| 409 | ALREADY_REPORTED | enum 정의만(현재 신고 API는 중복도 Insert) |
| 200 | OK | 알림 목록·읽음 |
| 202 | OK | `POST /notifications/{id}/dispatch` (Celery) |
| 503 | NOTIFICATION_SSE_UNAVAILABLE | `/notifications/stream` |

---

## Dependencies · Admin

| HTTP | code | 상황 |
|------|------|------|
| 404 | POST_NOT_FOUND | `require_post_author` |
| 403 | FORBIDDEN | 작성자 아님 · `require_admin` 실패 |
| 404 | COMMENT_NOT_FOUND | `require_comment_author` |
| 200 | OK | `/v1/admin/*` 성공(블라인드·정지·스윕 202 등) |

---

## 검색 · 멱등

| HTTP | code | 상황 |
|------|------|------|
| 400 | INVALID_REQUEST | `validate_search_query` 실패(짧은 검색어 등) |
| 409 | CONFLICT | 동일 `X-Idempotency-Key`로 POST 진행 중(게시글·미디어) |

---

## enum 전체 (`ApiCode`)

`app/common/codes.py`와 동기화. 위 표에 없는 코드는 예약·레거시이거나 HTTP 매핑 fallback(`HTTP_ERROR`)용입니다.

`HTTP_ERROR` · `METHOD_NOT_ALLOWED` · `SIGNUP_IMAGE_TOKEN_ALREADY_USED` 등은 특정 경로에서만 쓰이거나 Swagger용으로 enum에만 존재할 수 있습니다. **추가·변경 시 codes.py를 먼저 수정하고 이 문서를 맞춥니다.**
