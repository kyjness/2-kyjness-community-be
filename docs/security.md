# 보안 (위협별 대응)

백엔드가 직접 막는 범위와, **프론트·브라우저·인프라**에 맡기는 범위를 구분해 적는다.

[← 아키텍처 개요](architecture.md)

---

## 목차

1. [XSS](#1-xss-cross-site-scripting)
2. [SQL Injection](#2-sql-injection)
3. [CSRF](#3-csrf)
4. [인증·세션·토큰](#4-인증세션토큰)
5. [IDOR·권한 상승](#5-idor권한-상승)
6. [파일 업로드 악용](#6-파일-업로드-악용)
7. [Brute Force·DoS](#7-brute-forcedos남용)
8. [IP 스푸핑](#8-ip-스푸핑)
9. [정보 노출](#9-정보-노출)
10. [CORS·클릭재킹·HTTPS](#10-cors클릭재킹https)
11. [비밀·설정 유출](#11-비밀설정-유출)
12. [비정상 페이로드·캐시](#12-비정상-페이로드캐시)

---

## 1. XSS (Cross-Site Scripting)

**위험**: 게시글·댓글·닉네임 등 사용자 입력이 다른 사용자 브라우저에서 스크립트로 실행되는 것(저장형 XSS). API가 HTML을 렌더하지 않더라도, JSON을 `innerHTML`에 넣으면 프론트에서 터질 수 있다.

**백엔드 대응**

- API는 **JSON만** 반환. HTML 이스케이프·sanitize는 **프론트 책임**. 백엔드는 Pydantic으로 길이·형식·필수값을 제한 (`app/domain/*/schema.py`).
- `app/core/middleware/security_headers.py`:
  - `Content-Security-Policy` (`config.CONTENT_SECURITY_POLICY`)
  - `X-Content-Type-Options: nosniff`
  - `/v1/docs`, `/v1/redoc` 등 문서 경로는 CSP 미적용(개발·문서용).
- 저장형 XSS 완화의 핵심은 **클라이언트 이스케이프**. CSP는 같은 오리진 SPA의 정책 보조.

---

## 2. SQL Injection

**위험**: 검색어·ID가 SQL 문자열에 이어 붙어 DB가 조작되는 것.

**대응**

- SQLAlchemy 2.0 — 사용자 입력은 **바인딩 파라미터**만 사용. Raw f-string SQL 금지.
- `validate_search_query` → 토큰 규칙 검증 후 `ILIKE` (`app/domain/posts/repository.py`).
- 마이그레이션 `007_pg_trgm_hashtag_gin_search` — GIN 인덱스.

---

## 3. CSRF

**위험**: 로그인된 브라우저가 의도하지 않은 요청을 보내는 것.

**대응**

- 대부분 API: `Authorization: Bearer` — 타 사이트에서 임의 삽입 어려움.
- Refresh: **HttpOnly 쿠키** + `CORS_ORIGINS` 화이트리스트 + 배포 시 SameSite 정책.
- `CORSMiddleware` — `allow_credentials=True`이므로 오리진 목록을 좁게 유지 (`app/main.py`).

---

## 4. 인증·세션·토큰

**위험**: 토큰 탈취·재사용, 로그아웃 후 Access 사용, Refresh 동시 갱신 레이스.

| 항목 | 구현 |
|------|------|
| Access JWT | 짧은 TTL, `app/core/security.py`, `get_current_user` |
| 로그아웃 | Redis `blacklist:jti:{jti}` — HTTP·WS 공통 |
| Refresh | HttpOnly 쿠키 + Redis, **Lua** 회전 (`app/domain/auth/service.py`) |
| WebSocket | `app/domain/chat/ws_auth.py` |
| 비밀번호 | bcrypt + `PASSWORD_PEPPER`, `asyncio.to_thread` |
| 비활성 유저 | `ForbiddenException` |

회원가입 시 bcrypt 해시는 **DB 트랜잭션 밖**에서 수행한 뒤 `db.begin()`으로 유저 행만 커밋 (블로킹·트랜잭션 시간 분리).

---

## 5. IDOR·권한 상승

**위험**: 남의 리소스 수정·삭제, 일반 유저의 관리자 API 호출.

**대응**

- `require_post_author`, `require_comment_author` — 작성자 ID 비교 (`app/api/dependencies/permissions.py`).
- `require_admin` — `role == ADMIN` (`app/api/dependencies/auth.py`).
- 조회: `post_is_visible`, `UserBlock`, `is_blinded`, `deleted_at` 필터.
- API PK: Base62 `PublicId` → UUID ([#데이터·식별자](architecture.md#33-식별자-uuid-v7--base62)).

---

## 6. 파일 업로드 악용

**위험**: 악성 파일·거대 파일·MIME 위조·경로 traversal.

**대응**

- `ALLOWED_IMAGE_TYPES`, `MAX_FILE_SIZE`, multipart 상한 (`upload.py`).
- 매직 바이트 `sniff_image_type` — JPEG/PNG/WebP.
- `sanitize_presign_filename`.
- 가입 전: Redis 단회성 업로드 토큰.
- S3: `run_in_threadpool` ([도메인 플로우](domain-flows.md#1-이미지-media)).

---

## 7. Brute Force·DoS·남용

**위험**: 로그인 대입, API 폭주.

**대응**

- `rate_limit.py` — Redis + Lua. `LOGIN_RATE_LIMIT_*`, `SIGNUP_UPLOAD_RATE_LIMIT_*`.
- Redis 장애 시 대부분 Fail-open, 로그인 등은 인메모리 보조.
- 검색 최소 토큰 길이 — pg_trgm 남용 완화.
- GZip 1KB 이상만 압축.

---

## 8. IP 스푸핑

**위험**: `X-Forwarded-For` 위조.

**대응**

- `ProxyHeadersMiddleware` — `TRUSTED_PROXY_IPS` 내에서만 Forwarded 신뢰.
- Rate limit·로그: `scope["client"]`만 사용.

---

## 9. 정보 노출

**위험**: 500에 스택·SQL, 403/404로 존재 여부 유추.

**대응**

- `exception_handlers.py` — 클라이언트는 `code`, `message`, `requestId`만.
- `DEBUG` 기본 False.

---

## 10. CORS·클릭재킹·HTTPS

- CORS: `CORS_ORIGINS` 화이트리스트.
- `X-Frame-Options: DENY`.
- `HSTS_ENABLED`, `COOKIE_SECURE` (프로덕션).
- `TrustedHostMiddleware` (`TRUSTED_HOSTS`).

---

## 11. 비밀·설정 유출

- `validate_settings_for_environment()` — 프로덕션에서 JWT placeholder·32자 미만 시 **기동 실패**.
- 비밀번호·토큰은 응답·로그에 미포함.

---

## 12. 비정상 페이로드·캐시

- `TypeAdapter.validate_json` — 멱등 캐시, 해시태그 캐시, WS 수신.
- HTTP: Pydantic `RequestValidationError` → 400.

관련: [요청·API 계약](request-and-api-contract.md), [실시간·알림](realtime-notifications.md).
