# ADR 0010 — 스토리지 백엔드 전략: S3 API 단일 경로 + dev MinIO 패리티

- **상태**: 채택됨 (Accepted) · 코드 반영은 Ops 단계
- **관련 코드**: `app/infra/storage.py`(`STORAGE_BACKEND` 분기 · presigned 계열
  `issue_presigned_post`/`promote_pending_object`/`require_s3_direct_upload`),
  `app/domain/media/service.py`, `app/domain/media/router.py`

## 맥락 (Context)

현재 스토리지는 `STORAGE_BACKEND=local|s3`로 분기하고, 미디어 업로드 **경로가 둘**이다.

1. **Presigned 직접 업로드** (`/media/images/presign` → 클라이언트가 스토리지로 직접 PUT →
   `/confirm`) — `require_s3_direct_upload()`가 `local`이면 `raise`. **S3에서만 동작한다.**
2. **직접 multipart** (`/media/images`·`/media/images/signup` → 앱 서버가 수신·저장) — local·s3 모두.

[운영 봉투](../00-operating-envelope-and-scope.md)의 멀티 인스턴스(3~10대)·업로드 부하에서
**경로 ①이 운영 등급 선택**이다: 업로드 대역폭을 앱 서버에서 떼어 스토리지로 직접 보낸다. 그런데
`local` 개발 환경에서는 **경로 ①을 실행조차 못 한다** — 즉 prod의 주 업로드 경로가 dev/CI에서
검증되지 않는다. 게다가 `local` 디스크 백엔드는 prod에 존재하지 않는 **두 번째 구현**이라, S3에서만
드러나는 버그(키 프리픽스·presign·copy 승격)를 가릴 수 있다.

## 결정 (Decision)

**"S3 API를 단일 스토리지 계약으로, dev/CI는 S3 호환 MinIO로 패리티"** 를 채택한다.

1. **S3 API 단일 경로** — presigned 직접 업로드(①)를 기본 업로드 경로로 삼는다. prod·dev·CI 모두
   동일한 boto3/S3 코드 경로를 탄다.
2. **dev/CI = MinIO** — S3 호환 오브젝트 스토리지 MinIO를 개발·테스트 백엔드로 쓴다(무료·self-host,
   presigned POST·`copy_object` 승격 지원). prod = 실제 S3. 코드 분기 없이 엔드포인트·자격만 다르다.
3. **local 디스크 백엔드 폐기** — `_local_save`/`_local_delete`와 `STORAGE_BACKEND=local` 분기를
   제거한다. 단, **MinIO가 dev/CI에 배선되기 전까지는 남겨 둔다**(그 사이 개발·테스트가 깨지지
   않도록). 제거 시점 = Ops 단계에서 docker-compose에 MinIO를 올린 직후.
4. **배선은 Transition(Ops)** — docker-compose·CI에 MinIO 컨테이너 추가, 통합 테스트를 MinIO 대상
   실행으로 전환, 그 후 local 백엔드 코드 삭제. 이 ADR은 **방향 확정**이고, 코드 반영은 Ops 묶음에서.

> 비용: 포트폴리오는 유료 S3 버킷을 상시 켤 필요가 없다. dev·데모는 MinIO(무료, 앱과 같은
> compose/ECS에 동거 가능), 실제 S3는 설정·문서로만 두고 진짜 AWS 배포 시에만 과금한다.

## 트레이드오프 (Consequences)

**얻은 것**
- **dev/prod parity** — dev/CI가 prod와 같은 S3 코드 경로를 실행. presigned 업로드(①)가 비로소
  자동 검증된다.
- **단일 구현** — prod에 없는 divergent local 경로 제거로 유지보수·버그 은폐 표면 축소.
- 비용 0으로 운영 경로 시연 가능(MinIO).

**치른 비용**
- 로컬 실행·CI에 **MinIO 컨테이너 의존** — 도커 없이 즉석 실행하던 편의를 잃는다.
- 통합 테스트 인프라가 Redis·Postgres에 이어 **MinIO까지** 필요(compose로 일괄 기동해 완화).

## 고려한 대안 (Alternatives)

| 대안 | 기각 사유 |
|------|-----------|
| local-only dev 유지 | presigned 주 경로를 dev/CI에서 영영 검증 못 함 — 가장 약한 선택 |
| local 백엔드 영구 병행 | prod에 없는 이중 구현 유지 — divergence로 S3 전용 버그 은폐 |
| dev도 실제 S3 | AWS 계정·비용을 개발 루프에 결합. 무료 MinIO로 동일 API 검증 가능 |
| 멀티 클라우드 스토리지 추상화 | 봉투에 GCS·Azure 요구 없음 — 과한 추상화 |

## 일부러 하지 않은 것 (Non-goals)

- **prod에서 MinIO 자체 운영**: prod는 관리형 S3. MinIO는 dev/CI/데모 한정(자체 스토리지 서버
  운영은 가용성·백업 부채).
- **멀티 클라우드/스토리지 플러그인 프레임워크**: 대상이 S3 하나 → 얇은 분기로 충분.
- **CDN·이미지 리사이즈/트랜스코딩 파이프라인**: 봉투 밖(전송 최적화·미디어 가공은 이번 범위 아님).
- **경로 ②(직접 multipart) 즉시 제거**: 서버 수신 업로드의 단순 경로로 당분간 병행. 엔드포인트
  일원화 여부는 별도 판단(이 ADR 범위 밖).
