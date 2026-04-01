# API 응답 code · HTTP status 매핑

API 응답 body의 `code` 값과 HTTP 상태 코드 매핑을 정리한 문서입니다.  
프론트엔드·백엔드 협의용이며, Swagger/ReDoc 에서도 동일한 코드가 사용됩니다.

---

## 성공 응답 규격 (표준)

- **대부분의 성공(200/201/202)** 은 본문 `code`가 **`OK`** 입니다. (CRUD·조회·삭제·관리자 조작·알림·신고 접수 등)
- **예외적으로** 아래만 구분 코드를 유지합니다.
  - **Auth 엔드포인트**: `SIGNUP_SUCCESS`, `LOGIN_SUCCESS`, `LOGOUT_SUCCESS`, `AUTH_SUCCESS` (엔트리·토큰 흐름 구분)
  - **좋아요 중복**: `ALREADY_LIKED` (HTTP 200, 비즈니스 분기)
  - **대표 강아지 설정**: `DOG_UPDATED` (`PATCH /users/me/dogs/representative`)
- **DELETE** 성공도 **HTTP 200** + `ApiResponse` (`code: OK`, `data: null` 가능). ~~204 No Content~~ 는 사용하지 않습니다.

---

## 공통 · 오류

| HTTP | code | 상황 |
|------|------|------|
| 200 | OK | 대부분의 성공 응답 |
| 400 | INVALID_REQUEST | 비즈니스 로직상 잘못된 요청/파라미터 (형식은 유효) |
| 400 | MISSING_REQUIRED_FIELD | 서비스 규칙상 필수 필드 누락 |
| 422 | UNPROCESSABLE_ENTITY | Pydantic 자동 검증 실패 |
| 401 | UNAUTHORIZED | 미인증 / Bearer 토큰 없음·무효 |
| 401 | TOKEN_EXPIRED | Access Token 만료 |
| 403 | FORBIDDEN | 권한 없음 |
| 404 | NOT_FOUND | 리소스 없음 (일부는 도메인별 `POST_NOT_FOUND` 등) |
| 413 | PAYLOAD_TOO_LARGE | 요청 본문 초과 |
| 429 | RATE_LIMIT_EXCEEDED / LOGIN_RATE_LIMIT_EXCEEDED | Rate limit |

---

## Auth

| HTTP | code | 상황 |
|------|------|------|
| 201 | SIGNUP_SUCCESS | 회원가입 성공 |
| 200 | LOGIN_SUCCESS | 로그인 성공 |
| 200 | LOGOUT_SUCCESS | 로그아웃 성공 |
| 200 | AUTH_SUCCESS | POST /auth/refresh |
| 409 | EMAIL_ALREADY_EXISTS | 이메일 중복 |
| 409 | NICKNAME_ALREADY_EXISTS | 닉네임 중복 |
| 401 | INVALID_CREDENTIALS | 로그인 실패 |

---

## 도메인별 오류 코드 (성공은 원칙적으로 OK)

| 영역 | HTTP | code (실패 시 예시) |
|------|------|---------------------|
| Users | 404 | USER_NOT_FOUND, USER_WITHDRAWN |
| Users | 200 | DOG_UPDATED (대표 강아지만 성공 코드 예외) |
| Posts | 404 | POST_NOT_FOUND |
| Posts | 400 | POST_FILE_LIMIT_EXCEEDED, POST_HASHTAG_LIMIT_EXCEEDED |
| Comments | 404 | COMMENT_NOT_FOUND |
| Comments | 400 | INVALID_POSTID_FORMAT |
| Likes | 200 | ALREADY_LIKED (성공이지만 중복 분기) |
| Likes | 404 | POST_NOT_FOUND, COMMENT_NOT_FOUND, LIKE_NOT_FOUND |
| Media | 404/409 | IMAGE_NOT_FOUND, IMAGE_IN_USE |
| Notifications | 503 | NOTIFICATION_SSE_UNAVAILABLE (SSE 불가 시 JSON) |
| Reports | 409 | ALREADY_REPORTED |

---

## Dependencies / 권한

| HTTP | code | 상황 |
|------|------|------|
| 404 | POST_NOT_FOUND | require_post_author 시 게시글 없음 |
| 403 | FORBIDDEN | require_post_author / require_comment_author 권한 없음 |
| 404 | COMMENT_NOT_FOUND | require_comment_author 시 댓글 없음 |
