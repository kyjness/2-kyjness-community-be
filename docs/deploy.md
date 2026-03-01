# 배포 가이드

이 문서는 **로컬 실행**, **Docker 이미지·Compose**, **환경 변수**, **Alembic 마이그레이션** 방법을 정리합니다.  
처음 설정할 때는 README의 "빠른 실행"을 먼저 진행한 뒤, Docker·Alembic 상세는 여기서 참고하면 됩니다.

- **확장 전략**(기능·인프라)은 README에만 있으며, 이 문서에는 적지 않습니다.

---

## 마이그레이션 위치

- **마이그레이션 스크립트**: 프로젝트 **루트** 의 `alembic/` 폴더에 둡니다. (Alembic 관례)
- **app/db**: DB **엔진·세션·연결·Base** 만 담당. `alembic/env.py` 에서 `app.db` 와 ORM 모델을 import하여 `Base.metadata` 로 autogenerate에 사용합니다.
- **docs/** 에는 마이그레이션 스크립트를 두지 않습니다. `docs/puppytalkdb.sql` 은 참고용 DDL일 뿐입니다.

---

## 환경 변수

`ENV` 값에 따라 `.env.development` 또는 `.env.production` 을 로드합니다. `ENV` 가 없으면 development.

| 변수 | 설명 | 기본값(예) |
|------|------|------------|
| **ENV** | development / production | development |
| **HOST**, **PORT** | 서버 바인드 | 0.0.0.0, 8000 |
| **DEBUG** | 디버그 모드 | True |
| **CORS_ORIGINS** | 허용 Origin (쉼표 구분) | http://127.0.0.1:5500 |
| **SESSION_EXPIRY_TIME** | 세션 만료 시간(초) | 86400 |
| **SESSION_CLEANUP_INTERVAL** | 세션 cleanup 주기(초), 0이면 비활성화 | 3600 |
| **COOKIE_SECURE** | 쿠키 Secure 플래그 | false |
| **TRUST_X_FORWARDED_FOR** | 프록시 뒤에서 X-Forwarded-For 신뢰 (rate limit용) | false |
| **RATE_LIMIT_WINDOW** | 전역 rate limit 창(초) | 60 |
| **RATE_LIMIT_MAX_REQUESTS** | 창 내 최대 요청 수 | 100 |
| **LOGIN_RATE_LIMIT_WINDOW** | 로그인 rate limit 창(초) | 60 |
| **LOGIN_RATE_LIMIT_MAX_ATTEMPTS** | 창 내 최대 로그인 시도 | 5 |
| **SIGNUP_IMAGE_TOKEN_TTL_SECONDS** | 회원가입용 이미지 토큰 TTL(초) | 3600 |
| **SIGNUP_UPLOAD_RATE_LIMIT_*** | 회원가입 업로드 rate limit (창·최대) | 3600, 10 |
| **MAX_FILE_SIZE** | 업로드 최대 바이트 | 10485760 |
| **ALLOWED_IMAGE_TYPES** | 허용 이미지 MIME (쉼표 구분) | image/jpeg,image/png |
| **BE_API_URL** | 백엔드 기준 URL (예: 공개 URL 생성 시) | http://127.0.0.1:8000 |
| **STORAGE_BACKEND** | local / S3 | local |
| **S3_BUCKET_NAME**, **AWS_REGION** | S3 버킷·리전 | (빈 문자열 등) |
| **AWS_ACCESS_KEY_ID**, **AWS_SECRET_ACCESS_KEY** | S3 인증 | (빈 문자열) |
| **S3_PUBLIC_BASE_URL** | S3 공개 URL 베이스 | (빈 문자열) |
| **LOG_LEVEL**, **LOG_FILE_PATH** | 로깅 레벨·파일 경로 | INFO, (빈 문자열) |
| **SLOW_REQUEST_MS** | 슬로우 요청 임계치(ms) | 1000 |
| **HSTS_ENABLED**, **HSTS_MAX_AGE** | HSTS | false, 31536000 |
| **REFERRER_POLICY**, **PERMISSIONS_POLICY** | 보안 헤더 | strict-origin-when-cross-origin 등 |
| **DB_HOST**, **DB_PORT**, **DB_USER**, **DB_PASSWORD**, **DB_NAME** | MySQL 연결 정보 | localhost, 3306, root, (비밀번호), puppytalk |
| **DB_PING_TIMEOUT** | /health DB ping 타임아웃(초) | 1 |

상세는 `.env.example` 주석을 참고하세요.

---

## 로컬 실행 (요약)

**이 프로젝트 폴더(`2-kyjness-community-be`)를 연 터미널에서** 아래 순서로 진행합니다.

1. **Python 3.8+**, **MySQL** 설치·실행. (MySQL이 먼저 떠 있어야 DB 연결 가능.)
2. MySQL에서 `puppytalk` DB 생성 후, **Alembic** 또는 **수동** 중 하나로 테이블 생성.
   - Alembic: 3번 `poetry install` 후 프로젝트 루트에서 `alembic revision --autogenerate -m "initial"` → `alembic upgrade head`
   - 수동: `mysql -u root -p puppytalk < docs/puppytalkdb.sql`
3. **`poetry install`** — 의존성·가상환경 준비. (Alembic 사용 시 여기서 설치됨.)
4. **환경 변수**: `.env.example`을 복사해 `.env.development`로 저장. `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME` 등 필수 값 입력. `ENV`를 주지 않으면 development 설정이 로드됨.
5. **서버 실행**: `poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`  
   - `--reload`: 코드 변경 시 자동 재시작.  
   - 종료: Ctrl+C.

**테스트**: `poetry run pytest test/ -v` (MySQL 접속·환경 변수 필요.)

---

## Docker 이미지 빌드 및 실행

이미지는 **멀티스테이지 빌드**, **비루트 사용자(USER appuser)**, **.dockerignore** 로 최소 복사, **시크릿/환경변수는 런타임 주입**을 원칙으로 합니다.

**빌드** — 프로젝트 루트(`2-kyjness-community-be`)에서 실행.

```bash
docker build -t puppytalk-be .
```

**실행** — 환경 변수는 `-e` 또는 `--env-file` 로 주입합니다. 이미지 안에 시크릿을 넣지 않습니다.

```bash
docker run -d -p 8000:8000 \
  -e ENV=production \
  -e DB_HOST=호스트 \
  -e DB_PORT=3306 \
  -e DB_USER=사용자 \
  -e DB_PASSWORD=비밀번호 \
  -e DB_NAME=puppytalk \
  --name puppytalk-be puppytalk-be
```

- 포트 `8000` 노출. 호스트에서 `-p 8000:8000` 사용.
- 필요한 나머지 변수(CORS, S3, LOG_LEVEL 등)도 `-e` 또는 `--env-file .env.production` 로 전달.

**프로덕션 시 확인**: `ENV=production`, `COOKIE_SECURE=true`(HTTPS 사용 시), `CORS_ORIGINS`에 실제 프론트 도메인 지정, DB·S3 등 시크릿은 환경 변수로만 주입.

---

## Docker Compose

Compose 파일을 프로젝트 **한 단계 위 폴더**에 두고 실행하는 구성을 가정합니다. 백엔드 서비스는 이 프로젝트의 `.env.production`(또는 동일한 환경 변수)을 참조하도록 설정합니다.

```bash
docker compose up -d
docker compose up --build -d   # 이미지 다시 빌드 시
docker compose stop
```

파일이 여러 개일 때: `docker compose -f docker-compose.ec2.yml up -d` 처럼 `-f` 로 지정.

---

## Alembic (DB 마이그레이션)

스키마 변경은 **Alembic**으로 관리합니다.  
**프로젝트 루트**에서 실행할 때, DB URL은 `app.core.config` 에서 읽으며, 로드되는 `.env.*` 파일은 `ENV` 값에 따릅니다.

| 명령 | 설명 |
|------|------|
| `alembic revision --autogenerate -m "메시지"` | ORM 모델과 현재 DB 비교 후 마이그레이션 파일 생성 |
| `alembic upgrade head` | 최신 리비전까지 적용 |
| `alembic downgrade -1` | 직전 리비전으로 되돌리기 |
| `alembic history` | 마이그레이션 이력 확인 |

**최초 1회 (테이블이 없을 때)**

```bash
poetry install
alembic revision --autogenerate -m "initial"
alembic upgrade head
```

**이미 `docs/puppytalkdb.sql` 로 테이블을 만든 경우**

현재 DB를 "최신 적용됨"으로만 표시하려면: **`alembic stamp head`** 한 번 실행. 이후 스키마 변경분만 `alembic revision --autogenerate -m "메시지"` → `alembic upgrade head` 로 적용.

- 스키마의 **기준**은 Alembic 마이그레이션입니다. `puppytalkdb.sql` 은 참고용 DDL입니다.
- 명령은 **프로젝트 루트**에서 실행. `poetry run` 또는 해당 가상환경이 활성화된 상태에서 `alembic` 사용.
