# PuppyTalk Backend

**PuppyTalk**는 반려견을 키우는 사람들을 위한 커뮤니티 서비스의 백엔드로, **FastAPI** 기반의의 **RESTful API**로 설계·구현된 서버입니다.
회원가입·로그인, 게시글 작성·댓글·좋아요, 이미지 업로드 등 커뮤니티 운영에 필요한 핵심 기능을 제공합니다.

- **인증** — 회원가입·로그인·로그아웃 (쿠키 세션)
- **사용자** — 프로필 조회·수정, 비밀번호 변경
- **게시글** — CRUD, 무한 스크롤 피드, 조회수·좋아요
- **댓글** — 페이지네이션, 작성자 검증
- **미디어** — 이미지 업로드 (로컬/S3), 회원가입 전 프로필 첨부

프론트엔드는 별도 프로젝트에서 이 API를 사용합니다. → [**PuppyTalk Frontend**](https://github.com/kyjness/2-kyjness-community-fe)  

---

## 기술 스택

| 구분 | 기술 |
|------|------|
| **언어** | Python 3.8+ |
| **패키지 관리** | Poetry 2.x |
| **서버** | Uvicorn (개발), Gunicorn + Uvicorn worker (프로덕션) |
| **DB** | MySQL (pymysql) |
| **ORM** | SQLAlchemy 2.x |
| **마이그레이션** | Alembic |
| **스토리지** | 로컬 파일 / S3 (boto3) |
| **검증** | Pydantic v2 |
| **암호화** | bcrypt (비밀번호) |

---

## 폴더 구조

- **루트** — 실행·배포 설정, 테스트·문서. 애플리케이션 코드는 **app/** 패키지에 둡니다.
- **app/** — 공통·인프라와 기능 단위 **domain**으로 구분합니다.
- **도메인** — **router**(엔드포인트) → **controller**(비즈니스 로직) → **model**(DB 접근) → **schema**(요청·응답 DTO) 흐름으로 처리합니다.

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
│   │   ├── config.py        # 환경 변수 설정
│   │   ├── dependencies/   # 로그인 유저·작성자 검증 등 의존성
│   │   ├── middleware/     # 요청 ID·접근 로그·속도 제한·보안 헤더
│   │   ├── security.py     # 비밀번호 해시·세션 ID 생성
│   │   ├── storage.py      # 로컬/S3 파일 업로드
│   │   ├── exception_handlers.py  # 전역 예외 → 공통 응답 형식
│   │   └── cleanup.py      # 만료 세션·미사용 이미지 정리
│   ├── db/                  # 엔진·세션·연결·Base
│   └── domain/
│       ├── auth/            # 로그인·로그아웃·회원가입
│       ├── users/           # 프로필 조회·수정
│       ├── media/           # 이미지 업로드
│       ├── posts/           # 게시글 CRUD·피드·좋아요
│       └── comments/        # 댓글 CRUD
│   └── main.py              # 앱 진입점·미들웨어·라우터 등록
├── alembic/                 # DB 스키마 마이그레이션 스크립트
├── docs/                    # 상세 문서·참고용 SQL
├── test/                    # pytest
├── alembic.ini              # Alembic 설정 (DB URL 등)
├── pyproject.toml           # Poetry 의존성·스크립트 정의
├── poetry.lock              # 의존성 잠금 (poetry install 시 참조)
├── Dockerfile               # 프로덕션 이미지 빌드
├── docker-compose.yml       # 로컬·배포용 Compose
├── docker-compose.ec2.yml   # EC2 배포용 Compose
└── .env.example             # 환경 변수 예시 (복사 후 .env.development,.env.production 으로 사용)
```

---

## API 문서

서버를 실행한 뒤, 브라우저에서 **아래 주소**로 접속하면 API 명세를 볼 수 있습니다.  
(Swagger UI는 요청 테스트, ReDoc은 읽기용 정리 문서입니다.)

| 문서 | 주소 |
|------|------|
| **Swagger UI** | http://localhost:8000/docs |
| **ReDoc** | http://localhost:8000/redoc |

---

## 설계 배경

| 선택 | 이유 |
|------|------|
| **무한 스크롤 vs 페이지네이션** | 게시글은 피드형(hasMore). 댓글은 페이지 번호(totalCount, totalPages). |
| **쿠키-세션** | JWT 대신 쿠키(HttpOnly, SameSite)로 세션 ID만 전달. |
| **조회수 전용 엔드포인트** | GET 상세는 멱등, 조회수 증가는 POST /view 별도 호출. |
| **이미지 미리 업로드** | `/media/images/signup`(비로그인) 또는 `/media/images?purpose=profile|post`(로그인) 업로드 후 imageId만 본문에 넣음. |
| **스토리지: 로컬/S3** | `STORAGE_BACKEND`(local \| S3)로 전환 가능. |

---

## 빠른 실행 (Quick Start)

아래는 **이 프로젝트 폴더(`2-kyjness-community-be`)를 연 터미널에서** 순서대로 진행하면 됩니다.

1. **사전 준비**  
   Python 3.8 이상, MySQL이 설치되어 있고 실행 중이어야 합니다.

2. **DB·테이블 준비**  
   - MySQL에서 `puppytalk` 데이터베이스를 만듭니다.  
   - 테이블은 다음 중 하나로 만듭니다.  
     - **Alembic (권장)**: 3번에서 패키지 설치한 뒤, 프로젝트 루트에서  
       `alembic revision --autogenerate -m "initial"` → `alembic upgrade head`  
     - **수동**: `mysql -u root -p puppytalk < docs/puppytalkdb.sql`

3. **패키지 설치**  
   프로젝트 루트에서 `poetry install`을 실행합니다.

4. **환경 변수**  
   `.env.example`을 복사해 `.env.development`로 저장한 뒤, DB 주소·비밀번호 등 필요한 값을 채웁니다.  
   (`ENV`를 주지 않으면 development 설정을 사용합니다.)

5. **서버 실행**  
   같은 폴더에서 아래를 실행하면 서버가 뜹니다.  
   ```bash
   poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

- **테스트**: `poetry run pytest test/ -v` (MySQL·환경 변수 필요)
- Docker·Compose·Alembic 자세한 절차: [docs/deploy.md](docs/deploy.md)

---

## 확장 전략

### 기능

- **검색/필터**: 견종·지역·태그로 게시글 검색
- **신고/차단**: 게시글 신고, 사용자 차단 (차단한 사람 글 숨김)
- **알림**: 내 글에 댓글 달리면 알림 리스트
- **관리자**: 신고 누적 글 숨김, 유저 제재 (ROLE 기반)

### 인프라 (규모 확대 시)

- **세션 저장소**: 현재 MySQL. 확장 시 Redis 등으로 이전 가능.
- 기타: 로드밸런서·캐시·메시지 큐 등 필요 시 도입.

---

## 상세 문서 (docs/)

| 문서 | 설명 |
|------|------|
| [deploy.md](docs/deploy.md) | Docker 이미지·Compose 실행, 환경 변수 목록, Alembic 마이그레이션 방법 |
| [architecture.md](docs/architecture.md) | 폴더 역할·요청 흐름·인증 흐름 등 구조 설명 |
| [api-codes.md](docs/api-codes.md) | API 응답 코드(성공·에러)와 HTTP 상태 코드 매핑 |
