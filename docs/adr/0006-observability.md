# ADR 0006 — 관측성: 구조화 로그 + 얇은 메트릭 & 트레이싱 백엔드 미채택

- **상태**: 채택됨 (Accepted)
- **관련 코드**: `app/common/logging_config.py`, `app/core/middleware/request_id.py`,
  `app/core/middleware/access_log.py`, `/metrics`(신규)

## 맥락 (Context)

[운영 봉투](../00-operating-envelope-and-scope.md)상 인스턴스가 3~10대라, 장애·성능 문제를
**어느 인스턴스에서든 상관 추적**할 수 있어야 한다. ECS→CloudWatch 환경에서 로그를 필드로 쿼리하고
(`request_id`·`path`·`status`·`duration_ms`), 무중단 배포 시 준비된 인스턴스에만 트래픽을 보내야 한다.
현재 `request_id` 전파는 이미 훌륭하나, 로그가 plain text라 필드 쿼리가 어렵고 메트릭은 전무하다.

## 결정 (Decision)

**구조화 로그 + 얇은 메트릭**을 두고, **분산 트레이싱 백엔드는 채택하지 않는다.**

1. **JSON 구조화 로그(프로덕션)** — `request_id·method·path·status·duration_ms·client_ip`를 필드로.
   개발 환경은 사람이 읽는 콘솔 포맷으로 분기. `request_id` 전파(state·contextvars·헤더)는 유지.
2. **얇은 메트릭** — `prometheus-client`로 `/metrics` 노출. 핵심만: 요청 수·지연 히스토그램·에러율
   + 도메인 지표(조회수 flush 건수·rate limit 429·캐시 hit/miss). ECS에서 스크레이프.
3. **헬스 분리** — `/health`를 liveness(shallow) + readiness(deep: DB·Redis ping)로 나눠 롤링/블루-그린
   배포에서 준비된 인스턴스에만 트래픽.
4. **트레이싱 백엔드 미채택** — 아래 Non-goals 참조.

## 트레이드오프 (Consequences)

**얻은 것**
- 로그를 필드로 쿼리 → 장애 원인 추적 시간 단축.
- 요청률·지연·에러율 + 도메인 지표로 봉투 가정(조회 폭주 등)을 실측으로 검증 가능.
- 헬스 분리로 무중단 배포 안전성 확보.

**치른 비용**
- JSON 로그는 사람이 눈으로 읽기엔 덜 편함(개발 콘솔 포맷 분기로 완화).
- 메트릭 카디널리티(라벨 남용 시 폭증) 관리 필요 — 라벨을 저카디널리티로 제한.

## 고려한 대안 (Alternatives)

| 대안 | 기각 사유 |
|------|-----------|
| plain text 로그 유지 | 필드 쿼리 불가(grep만) → 멀티 인스턴스 상관 추적 곤란 |
| OpenTelemetry 풀 스택(Collector·트레이싱 백엔드) | 3~10 인스턴스 + request_id 로그 상관으로 충분 → 운영 부담 대비 과잉 |
| APM SaaS(Datadog 등) | 비용·범위 밖. 포트폴리오 목적엔 self-hosted 얇은 메트릭으로 충분 |

## 일부러 하지 않은 것 (Non-goals)

- **분산 트레이싱 백엔드(OTel Collector·Jaeger)**: `request_id` 기반 로그 상관으로 이 규모의 추적은
  충분하다. 트레이싱 인프라는 봉투 상한 밖 복잡도 — **의식적으로 배제.**
- **커스텀 대시보드 코드**: 메트릭 노출까지만. 시각화는 운영 도구(Grafana 등) 몫으로 남긴다.
