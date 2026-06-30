# ADR 0004 — 실시간 전달: WebSocket·SSE × Redis Pub/Sub 크로스-인스턴스 Fanout

- **상태**: 채택됨 (Accepted)
- **관련 코드**: `app/domain/chat/pubsub.py`, `app/domain/chat/manager.py`,
  `app/domain/notifications/service.py`

## 맥락 (Context)

채팅 DM과 알림을 실시간 전달해야 한다. [운영 봉투](README.md)상 서버는 멀티 인스턴스 3~10대다.

- WebSocket·SSE 연결은 **특정 인스턴스 하나에 고정**된다.
- 그런데 메시지 송신자(또는 이벤트 발생)는 **다른 인스턴스**일 수 있다.
- 따라서 로컬 연결 매니저로만 fanout하면 **다른 인스턴스에 붙은 수신자에게 전달이 누락**된다.

## 결정 (Decision)

도메인 이벤트를 **Redis Pub/Sub로 크로스-인스턴스 fanout**한다.

1. **커밋 이후 publish**: DB 트랜잭션 커밋 *후*에 publish — 미커밋 데이터가 새어나가지 않게.
2. **구독 루프**: 각 인스턴스는 풀과 분리된 **전용 Redis 연결**로 채널을 구독 → 수신 시 로컬 연결 매니저로 push.
3. **채널 설계**:
   - 채팅 DM: **단일 채널 + envelope**(수신자 UUID 포함)로 라우팅.
   - 알림: **사용자별 채널**(`notif:user:{id}`). 알림은 추가로 **DB에 영속화**(목록·미읽음 조회).
4. **WAS는 Stateless에 가깝게** — fanout 책임을 Redis가 지고, 인스턴스는 자유롭게 증설/교체.

## 트레이드오프 (Consequences)

**얻은 것**: 무중단 배포·수평 확장과 양립(연결이 어느 인스턴스에 붙든 전달), 짧은 DB 세션 점유 유지.
**치른 비용**:
- **At-most-once** — 구독 중이 아닌(오프라인) 수신자는 실시간 메시지를 놓침.
  → **알림은 DB 영속화로 보완**(재접속 시 조회), 채팅은 메시지 자체를 DB 저장.
- **Redis 의존** — publish는 fail-open(실패해도 요청 흐름은 유지). Pub/Sub은 영속 큐가 아니다.

## 고려한 대안 (Alternatives)

| 대안 | 기각 사유 |
|------|-----------|
| Sticky session(연결 고정) | 인스턴스 증설·무중단 배포·장애 시 연결 재분배에 취약 |
| DB 폴링 | 지연·DB 부하↑, 실시간성 부족 |
| 단일 인스턴스 운영 | 수평 확장·무중단 배포 포기 — 봉투 위반 |
| Kafka 등 메시지 브로커 | 영속·순서 보장이 필요 없는 실시간 fanout엔 과잉(봉투 상한 초과) |

## 일부러 하지 않은 것 (Non-goals)

- 메시지 **영속·재전송 보장** — 그 책임은 DB가 진다(Pub/Sub은 실시간 전달만).
- exactly-once / 글로벌 순서 보장 — 채팅·알림 UX엔 불필요.
