# ADR 0001 — 식별자 전략: UUIDv7(PK) · Base62(공개) · ULID(추적)

- **상태**: 채택됨 (Accepted)
- **관련 코드**: `app/core/ids.py`(`new_uuid7`, `uuid_to_base62`, `base62_to_uuid`, `parse_public_id_value`),
  `app/common/schemas.py`(`PublicId`), `app/core/middleware/request_id.py`(ULID request_id)

## 맥락 (Context)

식별자에는 성격이 다른 세 요구가 섞여 있다.

1. **내부 PK** — 조인·인덱스의 축. [운영 봉투](../00-operating-envelope-and-scope.md)상 멀티 인스턴스
   3~10대가 동시에 write하고 인기글에 조회가 폭주한다.
2. **공개 ID** — URL·API에 노출되는 값.
3. **추적 ID** — request_id·JWT jti 등 엔티티가 아닌 토큰.

auto-increment 정수 PK를 쓰면: (a) 시퀀스가 단일 경합점이 되고, (b) 순차 값이 그대로 노출돼
전체 규모·증가율이 추정 가능하며(enumeration), (c) 멀티 인스턴스 분산 생성이 어렵다.
한편 값 하나로 세 요구를 다 덮으려 하면 어딘가는 과하거나 부족해진다.

## 결정 (Decision)

역할별로 형식을 나눈다.

1. **내부 PK = UUID v7** (`new_uuid7`). 시간 정렬성이 있어 B-Tree 삽입 지역성이 좋고
   (UUIDv4의 랜덤 단편화 회피), 분산 생성이 가능하다. `posts` 목록의 **keyset 페이지네이션이
   `id` 정렬만으로 성립**하는 근거이기도 하다([ADR 0002](0002-cursor-pagination.md)).
2. **공개 ID = Base62(UUID)** (`uuid_to_base62`/`base62_to_uuid`). 내부 UUID를 그대로 노출하지 않고
   짧은 URL-safe 문자열로 인코딩 — 순차 비노출 + 길이 절감. Pydantic `PublicId` 타입이 경계에서
   자동 인코딩/디코딩한다.
3. **추적 ID = ULID 문자열** (request_id, jti). 엔티티가 아니므로 PK 형식과 분리. 시간 정렬 문자열이라
   로그 정렬에 유리.
4. **레거시 ULID 수용 폴백 제거.** 재건 이전 `parse_public_id_value`/`jwt_sub_to_uuid`가 공개 ID로
   레거시 ULID까지 받아주던 마이그레이션 잔재를 걷어낸다 → 공개 ID는 **Base62/UUID만** 수용.

## 트레이드오프 (Consequences)

**얻은 것**
- 분산 생성(중앙 발급기 불필요) + 시간정렬 PK로 인덱스 지역성·keyset 페이지네이션 확보.
- 공개 ID 순차 비노출로 enumeration 방어, URL 길이 절감.
- 형식이 역할에 1:1 대응 → "왜 이 값이 여기 있나"가 자명.

**치른 비용**
- UUID 16바이트 > int 8바이트: 저장·인덱스 폭 증가(봉투 규모에선 수용 가능).
- Base62 인코딩/디코딩 CPU 비용(무시 가능 수준).
- 형식이 셋이라 인지 부담 — 본 ADR로 "역할이 다르다"를 명시해 상쇄.

## 고려한 대안 (Alternatives)

| 대안 | 기각 사유 |
|------|-----------|
| auto-increment 정수 PK | 시퀀스 경합 + 순차 노출(enumeration) + 분산 생성 곤란 |
| UUID v4 | 랜덤이라 B-Tree 삽입 단편화 → 조회 폭주 봉투에서 인덱스 성능 불리 |
| 공개 ID도 내부 UUID 그대로 | 순차는 아니나 길고, 내부 PK 노출 → 경계 분리 원칙 약화 |
| Snowflake 등 중앙 발급 ID | 발급기가 새 단일 의존점 → 봉투(멀티 인스턴스·단순 운영)에 과잉 |

## 일부러 하지 않은 것 (Non-goals)

- **공개 ID 서명/암호화(HMAC 등)**: enumeration은 Base62 비순차로 충분히 완화. 서명은 봉투 상한을
  넘는 복잡도라 배제.
- **멀티리전 충돌 회피 조율**: 단일 리전 전제(봉투 상한). UUIDv7 자체 충돌 확률로 충분.
