# API 응답 code · HTTP status 매핑

API 응답 body의 `code` 값과 HTTP 상태 코드 매핑을 정리한 문서입니다.  
프론트엔드·백엔드 협의용이며, Swagger/ReDoc 에서도 동일한 코드가 사용됩니다.

---

## 공통

| HTTP | code | 상황 |
|------|------|------|
| 200 | OK | 가용성 조회 등 (이미지 업로드는 201 IMAGE_UPLOADED) |
| 400 | INVALID_REQUEST | 비즈니스 로직상 잘못된 요청/파라미터 (형식은 유효) |
| 400 | MISSING_REQUIRED_FIELD | 서비스 규칙상 필수 필드 누락 (예: signup 시 이미지·토큰 쌍) |
| 422 | UNPROCESSABLE_ENTITY | Pydantic 자동 검증 실패 (타입·스키마·필수필드·enum 등, FastAPI 기본 응답) |
| 401 | UNAUTHORIZED | 미인증 / Bearer 토큰 없음·무효 |
| 401 | TOKEN_EXPIRED | Access Token 만료 (프론트에서 Refresh 호출 유도) |
| 403 | FORBIDDEN | 권한 없음 (타인 리소스 수정·삭제 등) |
| 404 | NOT_FOUND | 리소스 없음 (기본값, 도메인별로 POST_NOT_FOUND 등 구체 코드 사용) |
| 413 | PAYLOAD_TOO_LARGE | 요청 본문 초과 (업로드 Content-Length 선검증) |
| 429 | LOGIN_RATE_LIMIT_EXCEEDED | 로그인 시도 횟수 제한 초과 |

---

## Auth

| HTTP | code | 상황 |
|------|------|------|
| 201 | SIGNUP_SUCCESS | 회원가입 성공 |
| 200 | LOGIN_SUCCESS | 로그인 성공 |
| 200 | LOGOUT_SUCCESS | 로그아웃 성공 |
| 200 | AUTH_SUCCESS | POST /auth/refresh 새 Access Token |
| 409 | EMAIL_ALREADY_EXISTS | 가입 시 이메일 중복 |
| 409 | NICKNAME_ALREADY_EXISTS | 가입 시 닉네임 중복 |
| 401 | INVALID_CREDENTIALS | 로그인 실패 (이메일/비밀번호 불일치, 구분하지 않음) |

---

## Users

| HTTP | code | 상황 |
|------|------|------|
| 200 | USER_RETRIEVED | GET /users/me 프로필 조회 성공 |
| 200 | USER_UPDATED | PATCH /users/me 수정 성공 |
| 200 | PASSWORD_UPDATED | PATCH /users/me/password 성공 |
| 404 | USER_NOT_FOUND | 사용자 없음 |
| 409 | NICKNAME_ALREADY_EXISTS | 프로필 수정 시 닉네임 중복 |
| 500 | INTERNAL_SERVER_ERROR | DB/내부 오류 |

---

## Posts

| HTTP | code | 상황 |
|------|------|------|
| 201 | POST_UPLOADED | 게시글 작성 성공 |
| 200 | POST_RETRIEVED | 게시글 상세 조회 |
| 200 | POSTS_RETRIEVED | 게시글 목록 조회 |
| 200 | POST_UPDATED | 게시글 수정 성공 |
| 404 | POST_NOT_FOUND | 게시글 없음 |
| 400 | INVALID_REQUEST | imageIds 검증 실패 등 |

---

## Likes

| HTTP | code | 상황 |
|------|------|------|
| 200 | LIKE_SUCCESS | 좋아요 추가 성공 (POST /likes/posts\|comments/{id}) |
| 200 | ALREADY_LIKED | 이미 좋아요 함 (중복 POST 시 200으로 동일 응답) |
| 200 | LIKE_DELETED | 좋아요 취소 성공 (DELETE) |
| 404 | POST_NOT_FOUND | 게시글 좋아요 시 해당 게시글 없음 |
| 404 | COMMENT_NOT_FOUND | 댓글 좋아요 시 해당 댓글 없음 |

---

## Comments

| HTTP | code | 상황 |
|------|------|------|
| 201 | COMMENT_UPLOADED | 댓글 작성 성공 |
| 200 | COMMENTS_RETRIEVED | 댓글 목록 조회 |
| 200 | COMMENT_UPDATED | 댓글 수정 성공 |
| 404 | POST_NOT_FOUND | 댓글 작성/목록 시 게시글 없음 |
| 404 | COMMENT_NOT_FOUND | 댓글 수정/삭제 시 댓글 없음 |
| 400 | INVALID_POSTID_FORMAT | Path post_id 형식 오류 (권한 의존성) |
| 403 | FORBIDDEN | 타인 댓글 수정/삭제 시도 (require_comment_author) |

---

## Media

| HTTP | code | 상황 |
|------|------|------|
| 201 | IMAGE_UPLOADED | 이미지 업로드 성공 (회원가입용·일반 업로드) |
| 404 | IMAGE_NOT_FOUND | 이미지 없음 또는 본인 소유 아님 (삭제 시) |
| 409 | CONFLICT | 이미지 사용 중 삭제 불가 (ref_count > 0, IMAGE_IN_USE) |
| 413 | PAYLOAD_TOO_LARGE | 업로드 요청 본문 초과 (라우터 Content-Length 선검증) |
| 400 | INVALID_REQUEST | purpose 등 요청 검증 실패 |
| 400 | MISSING_REQUIRED_FIELD | 파일 없음 |
| 400 | INVALID_IMAGE_FILE, INVALID_FILE_TYPE, FILE_SIZE_EXCEEDED | 파일 형식·크기 검증 실패 (image_policy) |

---

## Dependencies / 기타

| HTTP | code | 상황 |
|------|------|------|
| 401 | UNAUTHORIZED | get_current_user Bearer 없음/무효 |
| 401 | TOKEN_EXPIRED | get_current_user Access Token 만료 |
| 404 | POST_NOT_FOUND | require_post_author 시 게시글 없음 |
| 403 | FORBIDDEN | require_post_author / require_comment_author 권한 없음 |
| 404 | COMMENT_NOT_FOUND | require_comment_author 시 댓글 없음 |
| 400 | INVALID_POSTID_FORMAT | Path post_id 형식 오류 |
