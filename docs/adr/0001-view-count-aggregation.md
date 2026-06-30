# ADR 0001 — 조회수 집계: Redis 버퍼링 + 비동기 Flush

- **상태**: 채택됨 (Accepted)
- **관련 코드**: `app/domain/posts/services/post_service.py`
  (`record_post_view`, `get_post_detail`, `flush_view_counts_to_db`), `app/worker/`

## 맥락 (Context)

게시글 조회수를 집계해야 한다. [운영 봉투](README.md)상 **인기글 1건에 초당 수백~수천 조회**가
멀티 인스턴스 3~10대로 분산 유입된다.

조회마다 `UPDATE posts SET view_count = view_count + 1`을 직접 실행하면:

1. **Hot-row 경합** — 인기글 한 row에 초당 수천 write가 몰려 row-level lock 경합이 발생,
   조회 API 전반의 지연으로 전파된다.
2. **DB write IOPS 잠식** — 의미가 낮은 단일 증가 write가 실제 비즈니스 write(게시·댓글)와 경쟁한다.
3. **수치 신뢰도 저하** — 같은 사용자의 새로고침·연타가 그대로 카운트된다.

한편 조회수는 **강한 정합성이 필요 없는 지표**다. 약간의 지연·근사가 허용된다.
이 비대칭(쓰기 폭주 vs 정합성 여유)이 설계의 출발점이다.

## 결정 (Decision)

조회수를 **Redis에서 흡수하고 DB에는 비동기로 합산 반영**한다.

1. **중복 제거**: `(post, viewer)` 키에 `SET NX EX`(TTL 1h). TTL 내 같은 뷰어의 재조회는 미집계.
2. **버퍼링**: `HINCRBY views:buffer <post_id> 1`. 증가를 Redis 해시에 누적하고 DB는 건드리지 않는다.
3. **비동기 Flush** (Celery 주기 작업):
   - **분산 락**(`SET NX EX` + 랜덤 토큰)으로 멀티 인스턴스 중 **한 워커만** flush.
   - Lua `RENAME`으로 버퍼를 drain 키로 **원자 스냅샷** — 그 사이 신규 증가는 새 버퍼로 쌓인다.
   - drain의 post별 누적치를 `view_count = view_count + delta` **단일 UPDATE**로 합산(N:1).
   - 실패 시 drain을 버퍼로 **merge-back** → 데이터 무손실. 락 해제는 Lua **CAS**(자기 토큰일 때만 DEL).
4. **표시 보정**: 상세 조회 시 `DB view_count + 버퍼 pending`을 더해 거의 실시간 수치를 노출.
5. **읽기/쓰기 DB 분리**: 상세 조회(읽기)와 증가(쓰기)를 분리된 엔진으로 처리.

## 트레이드오프 (Consequences)

**얻은 것**
- 인기글 hot-row write가 초당 수천 → flush 주기당 1회로 축소(N:1 합산).
- 뷰어 dedup으로 수치 신뢰도↑, DB write IOPS 절약.
- 멀티 인스턴스에서 안전: 분산 락 + 원자 RENAME + CAS 해제로 중복·오삭제 방지.

**치른 비용**
- **최종 일관성**: DB 반영이 flush 주기만큼 지연 — 단, 표시 보정으로 사용자 체감은 완화.
- **Redis 의존성**: 단, 전 구간 **fail-open**. Redis 장애 시 dedup/버퍼를 건너뛰고 DB 직접 증가로
  자동 폴백한다(정합성보다 가용성 우선 — 99.9% 목표에 부합).
- **복잡도 증가**: 본 문서로 동작과 정당성을 명시해 상쇄한다.

## 고려한 대안 (Alternatives)

| 대안 | 기각 사유 |
|------|-----------|
| 매 조회 직접 `UPDATE +1` | 가장 단순하나, 가정한 인기글 초당 수천 조회에서 hot-row 경합으로 운영 봉투를 못 버팀 |
| DB 원자 increment만(버퍼·dedup 없음) | 경합 그대로 + 새로고침 어뷰징 미방어 |
| Redis `INCR`만, Flush 없음 | DB 영속화 부재 → 재시작·eviction 시 유실, 정렬·통계 쿼리 불리 |
| 카운팅 전용 외부 서비스 | 운영 봉투 상한(멀티리전·초당 수만 신규 write 아님)을 넘는 과잉 |

## 일부러 하지 않은 것 (Non-goals)

- **정확히-한-번(exactly-once) 보장**: 조회수엔 불필요. 근사·최종 일관성으로 충분.
- **강한 트랜잭션 정합성**: 조회수는 비즈니스 임계 데이터가 아니므로 의도적으로 포기.
  (반대로 게시글 *수정*에는 낙관적 락(`version`)을 적용 — 거긴 동시수정 충돌이 실제 문제이기 때문.)
