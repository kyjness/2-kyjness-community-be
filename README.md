# PuppyTalk API - 커뮤니티 백엔드

FastAPI 기반의 커뮤니티 백엔드 API 서버입니다.

## 프로젝트 구조

```
.
├── app/                    # 애플리케이션 코드
│   ├── auth/              # 인증 모듈
│   ├── users/             # 사용자 모듈
│   ├── posts/             # 게시글 모듈
│   ├── comments/          # 댓글 모듈
│   └── likes/             # 좋아요 모듈
├── main.py                # FastAPI 애플리케이션 진입점
├── config.py              # 설정 관리
├── pyproject.toml         # Python 프로젝트 설정 및 의존성
├── .env.example          # 환경 변수 예시 파일
└── README.md             # 프로젝트 문서
```

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
pip install -e .

# 또는 Poetry를 사용하는 경우 (선택사항)
poetry install
```

### 3. 환경 변수 설정

`.env.example` 파일을 참고하여 `.env` 파일을 생성하세요.

```bash
# .env.example을 복사하여 .env 파일 생성
cp .env.example .env

# 또는 직접 .env 파일 생성
```

### 4. 서버 실행

```bash
# 개발 모드 (자동 리로드)
python main.py

# 또는 uvicorn 직접 실행
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 5. API 문서 확인

서버 실행 후 다음 URL에서 API 문서를 확인할 수 있습니다:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 주요 기능

- **인증 (Auth)**: 회원가입, 로그인, 로그아웃, 세션 관리
- **사용자 (Users)**: 프로필 조회/수정, 비밀번호 변경, 프로필 이미지 업로드
- **게시글 (Posts)**: 게시글 작성/조회/수정/삭제, 이미지 업로드
- **댓글 (Comments)**: 댓글 작성/조회/수정/삭제
- **좋아요 (Likes)**: 좋아요 추가/취소

## 기술 스택

- **FastAPI**: 웹 프레임워크
- **Pydantic**: 데이터 검증 및 설정 관리
- **Uvicorn**: ASGI 서버
- **Python-dotenv**: 환경 변수 관리

## 환경 변수

`.env` 파일에서 다음 설정을 관리할 수 있습니다:

- `HOST`: 서버 호스트 (기본값: 0.0.0.0)
- `PORT`: 서버 포트 (기본값: 8000)
- `DEBUG`: 디버그 모드 (기본값: True)
- `CORS_ORIGINS`: CORS 허용 오리진 (기본값: *)
- `SESSION_EXPIRY_TIME`: 세션 만료 시간 (초, 기본값: 86400)
- `RATE_LIMIT_WINDOW`: Rate limiting 윈도우 (초, 기본값: 60)
- `RATE_LIMIT_MAX_REQUESTS`: 최대 요청 수 (기본값: 10)
- `MAX_FILE_SIZE`: 최대 파일 크기 (바이트, 기본값: 10485760)
- `ALLOWED_IMAGE_TYPES`: 허용된 이미지 타입 (쉼표로 구분)
- `BE_API_URL`: API 기본 URL

## 데이터 저장

현재는 인메모리 저장소를 사용합니다. 서버 재시작 시 모든 데이터가 초기화됩니다.

## 라이선스

이 프로젝트는 학습 목적으로 제작되었습니다.
