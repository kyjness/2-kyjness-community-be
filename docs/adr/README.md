# 아키텍처 의사결정 기록 (ADR)

이 디렉터리는 PuppyTalk 백엔드의 주요 설계 결정을 기록한다.
각 ADR은 *"어떤 문제를 어떤 전제 위에서, 왜 이렇게 풀었고, 무엇을 포기했는가"*를 남긴다.

## 전제 — 가정 운영 시나리오 (Operating Envelope)
모든 ADR은 아래 전제를 공유한다. 복잡도는 이 봉투 안에서만 정당화된다.

| 축 | 전제 |
|----|------|
| 규모 | 평상시 수천~수만 DAU |
| 핫스팟 | 인기글 1건에 초당 수백~수천 **조회** |
| 서버 | 멀티 인스턴스 3~10대 (수평 확장) |
| 배포 | 무중단 롤링 / 블루-그린 |
| 가용성 | 99.9% (월 ~43분 다운 허용) |

**상한(이걸 넘는 복잡도는 과잉으로 본다)**: 멀티리전·금융권 강정합성·99.99%+·초당 수만 건 *신규 write*.

## 목록
| # | 제목 | 상태 |
|---|------|------|
| [0001](0001-view-count-aggregation.md) | 조회수 집계 — Redis 버퍼링 + 비동기 Flush | 채택됨 |
| [0002](0002-distributed-rate-limit.md) | 분산 Rate Limit — Redis Lua + 메모리 폴백 | 채택됨 |
| [0003](0003-idempotency-keys.md) | POST 멱등성 — Idempotency-Key + 결과 캐시 | 채택됨 |
| [0004](0004-realtime-fanout-pubsub.md) | 실시간 전달 — WebSocket·SSE × Redis Pub/Sub | 채택됨 |
| [0005](0005-identifier-strategy.md) | 식별자 전략 — UUID v7 · Base62 · ULID | 채택됨 |

## 형식
각 ADR: **맥락(문제) → 결정 → 트레이드오프 → 고려한 대안 → 일부러 하지 않은 것**.
