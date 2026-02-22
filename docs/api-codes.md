# API 응답 code · HTTP status 매핑 (내부용)

> 이 문서는 GitHub에 올리지 않습니다 (.gitignore: docs/internal/).

## 공통

| HTTP | code | 상황 |
|------|------|------|
| 200 | OK | 이미지 업로드 성공, 가용성 조회 등 |
| 400 | INVALID_REQUEST | 잘못된 요청/파라미터 |
| 400 | MISSING_REQUIRED_FIELD | 필수 필드 누락 |
| 401 | UNAUTHORIZED | 미인증 / 세션 만료 / 비밀번호 불일치 |
| 403 | FORBIDDEN | 권한 없음 (타인 리소스 수정·삭제 등) |
| 404 | NOT_FOUND | 리소스 없음 (도메인별 아래 참고) |
| 429 | LOGIN_RATE_LIMIT_EXCEEDED | 로그인 시도 횟수 제한 초과 |

---

## Auth

| HTTP | code | 상황 |
|------|------|------|
| 201 | SIGNUP_SUCCESS | 회원가입 성공 |
| 200 | LOGIN_SUCCESS | 로그인 성공 |
| 200 | LOGOUT_SUCCESS | 로그아웃 성공 |
| 200 | AUTH_SUCCESS | GET /auth/me 세션 유효 + 사용자 정보 |
| 409 | EMAIL_ALREADY_EXISTS | 가입 시 이메일 중복 |
| 409 | NICKNAME_ALREADY_EXISTS | 가입 시 닉네임 중복 |
| 401 | EMAIL_NOT_FOUND | 로그인 시 존재하지 않는 이메일 |
| 401 | INVALID_CREDENTIALS | 로그인 시 비밀번호 오류 |

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
| 201 | POSTLIKE_UPLOADED | 좋아요 새로 추가 |
| 200 | ALREADY_LIKED | 좋아요 이미 있음 (중복 요청) |
| 200 | LIKE_DELETED | 좋아요 취소 |
| 404 | LIKE_NOT_FOUND | 좋아요 취소 시 해당 like 없음 |
| 409 | CONFLICT | 좋아요 중복 등 제약 위반 |
| 400 | INVALID_REQUEST | imageIds 검증 실패 등 |

---

## Comments

| HTTP | code | 상황 |
|------|------|------|
| 201 | COMMENT_UPLOADED | 댓글 작성 성공 |
| 200 | COMMENTS_RETRIEVED | 댓글 목록 조회 |
| 200 | COMMENT_UPDATED | 댓글 수정 성공 |
| 404 | POST_NOT_FOUND | 댓글 작성/목록 시 게시글 없음 |
| 404 | COMMENT_NOT_FOUND | 댓글 수정/삭제 시 댓글 없음 |
| 400 | INVALID_POSTID_FORMAT | post_id 형식 오류 |
| 403 | FORBIDDEN | 타인 댓글 수정/삭제 시도 |

---

## Media

| HTTP | code | 상황 |
|------|------|------|
| 200 | OK | 이미지 업로드 성공 (imageId, url) |
| 404 | IMAGE_NOT_FOUND | 이미지 없음 / 이미 철회됨 |
| 403 | FORBIDDEN | 타인 업로드 이미지 철회 시도 |
| 400 | MISSING_REQUIRED_FIELD | 파일 없음 |
| 400 | INVALID_FILE_TYPE, INVALID_IMAGE_FILE, FILE_SIZE_EXCEEDED | 파일 검증 실패 |

---

## Dependencies / 기타

| HTTP | code | 상황 |
|------|------|------|
| 401 | UNAUTHORIZED | get_current_user 세션 없음/만료 |
| 404 | POST_NOT_FOUND | require_post_author 시 게시글 없음 |
| 403 | FORBIDDEN | require_post_author / require_comment_author 권한 없음 |
| 404 | COMMENT_NOT_FOUND | require_comment_author 시 댓글 없음 |
| 400 | INVALID_POSTID_FORMAT | Path post_id 형식 오류 |
