# PuppyTalk API - 배포 가이드

배포 시 환경 변수 설정, DB, S3, 실행 방법을 정리한 문서입니다.

---

## 1. 사전 요구사항

| 항목 | 요구사항 |
|------|----------|
| Python | 3.8 이상 |
| MySQL | 8.0 권장 (RDS, Cloud SQL 등) |
| AWS | S3 버킷, IAM 키 (이미지 저장 시) |

---

## 2. 배포 체크리스트

- [ ] MySQL DB 생성 및 테이블 적용 (`docs/puppyytalkdb.sql`)
- [ ] `.env` 또는 플랫폼 환경 변수 설정 (`.env.example` 복사 후 값 채우기)
- [ ] S3 버킷 생성 (이미지 저장 시)
- [ ] CORS에 배포된 프론트 URL 포함
- [ ] `DEBUG=False` 설정
- [ ] `STORAGE_BACKEND=s3` 설정 (권장)

---

## 3. 환경 변수 설정

앱은 **루트의 `.env`** 또는 **플랫폼 환경 변수**만 읽습니다. `.env.example`을 복사해 `.env`로 저장한 뒤 값을 채우면 됩니다.

### 필수

| 변수 | 설명 | 예시 |
|------|------|------|
| `DB_HOST` | MySQL 호스트 | `your-db.rds.amazonaws.com` |
| `DB_PORT` | MySQL 포트 | `3306` |
| `DB_USER` | DB 사용자 | `puppytalk_user` |
| `DB_PASSWORD` | DB 비밀번호 | (실제 비밀번호) |
| `DB_NAME` | DB 이름 | `puppytalk` |
| `CORS_ORIGINS` | 허용할 프론트 URL (쉼표 구분) | `https://app.example.com` |
| `BE_API_URL` | 배포된 API 주소 | `https://api.example.com` |

### 서버

| 변수 | 설명 | 권장값 |
|------|------|--------|
| `HOST` | 바인딩 주소 | `0.0.0.0` |
| `PORT` | 포트 | `8000` |
| `DEBUG` | 디버그 모드 | `False` |

### 이미지 저장 (S3)

| 변수 | 설명 |
|------|------|
| `STORAGE_BACKEND` | `s3` (배포 시 권장) |
| `S3_BUCKET_NAME` | S3 버킷 이름 |
| `AWS_REGION` | 리전 (예: `ap-northeast-2`) |
| `AWS_ACCESS_KEY_ID` | IAM Access Key |
| `AWS_SECRET_ACCESS_KEY` | IAM Secret Key |
| `S3_PUBLIC_BASE_URL` | CloudFront URL (선택) |

---

## 4. DB 설정

```bash
# DB 생성
mysql -h YOUR_DB_HOST -u YOUR_USER -p -e "CREATE DATABASE IF NOT EXISTS puppytalk;"

# 테이블 생성
mysql -h YOUR_DB_HOST -u YOUR_USER -p puppytalk < docs/puppyytalkdb.sql
```

---

## 5. S3 설정

1. S3 버킷 생성
2. IAM 사용자 생성 후 Access Key 발급
3. 버킷 정책 또는 객체 ACL로 공개 읽기 허용  
   - 또는 CloudFront 사용 시 `S3_PUBLIC_BASE_URL`에 CloudFront URL 설정
4. `.env`에 `STORAGE_BACKEND=s3` 및 S3 관련 변수 입력

---

## 6. 서버 실행

```bash
# 가상환경 활성화 후
pip install .
uvicorn main:app --host 0.0.0.0 --port 8000
```

프로덕션에서는 `--reload` 제거하고, gunicorn + uvicorn worker 또는 플랫폼 기본 설정 사용.

---

## 7. Docker로 실행 (추후 배포용)

```bash
# 이미지 빌드
docker build -t puppytalk-api .

# 실행 (환경 변수는 -e 또는 --env-file로 전달)
docker run -p 8000:8000 --env-file .env puppytalk-api
```

- `.env`는 이미지에 포함되지 않습니다. 반드시 `--env-file .env` 또는 `-e DB_HOST=...` 등으로 런타임에 전달하세요.
- MySQL은 같은 호스트/다른 컨테이너에 두었다면 `DB_HOST`를 `host.docker.internal`(Mac/Windows) 또는 실제 DB 호스트로 설정하세요.

---

## 8. 플랫폼별 참고

### Railway / Render / Fly.io

- 환경 변수를 플랫폼 대시보드에서 설정
- DB는 내장 MySQL 또는 외부 RDS/Cloud SQL 사용
- 빌드 커맨드: `pip install .`  
- 실행 커맨드: `uvicorn main:app --host 0.0.0.0 --port $PORT`

### AWS (EC2, ECS 등)

- EC2: `.env` 파일 생성 후 `systemd` 또는 `supervisor`로 uvicorn 실행
- ECS: Task Definition의 환경 변수에 설정
- RDS로 MySQL, S3로 이미지 저장

---

## 9. 문제 해결

| 현상 | 확인 사항 |
|------|-----------|
| DB 연결 실패 | 1) 보안 그룹/방화벽에서 DB 포트 허용 2) 환경 변수 값 확인 3) DB 존재 여부 |
| CORS 에러 | `CORS_ORIGINS`에 프론트 URL(https 포함) 정확히 입력 |
| 이미지 404 | S3 버킷 공개 설정 또는 CloudFront `S3_PUBLIC_BASE_URL` 확인 |
| 401 (쿠키) | 배포 환경 HTTPS 여부, 프론트에서 `credentials: 'include'` 사용 여부, CORS 허용 origin 확인 |
