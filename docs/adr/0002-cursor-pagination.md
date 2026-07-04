# ADR 0002 — Cursor 페이지네이션: keyset · `total` 제거

- **상태**: 채택됨 (Accepted)
- **관련 코드**: `app/domain/posts/repository.py`(`get_all_posts`),
  `app/domain/posts/services/post_service.py`, `app/common/schemas.py`(`PaginatedResponse`)

## 맥락 (Context)

목록 조회가 [운영 봉투](../00-operating-envelope-and-scope.md)상 가장 뜨거운 경로다.
`OFFSET/LIMIT` 방식은 두 가지로 봉투를 못 버틴다.

1. **깊은 페이지 비용** — `OFFSET N`은 앞 N행을 스캔 후 버린다. 페이지가 깊을수록 선형 증가.
2. **drift(중복·누락)** — 조회 중 새 글이 삽입되면 offset 기준이 밀려 같은 글이 다음 페이지에 다시
   나오거나 건너뛰어진다.

여기에 매 요청 `COUNT(*)`까지 겹친다 — 검색 시 `pg_trgm` 필터가 COUNT에도 걸려 비용이 크고
([analysis #10](../../analysis.md)), 커서 방식에선 `total` 자체의 의미도 약하다.
게다가 admin 신고 목록(#5)·댓글 트리(#6)는 **메모리에서 잘라내** total·items가 어긋나는 버그가 있다.

## 결정 (Decision)

**keyset(cursor) 페이지네이션을 목록 표준으로 통일**한다.

1. **keyset 스캔** — `WHERE id < :cursor ORDER BY id DESC LIMIT size+1`. UUIDv7 PK가 시간정렬이라
   ([ADR 0001](0001-identifier-strategy.md)) **PK B-Tree 범위 스캔만으로 성립** — 추가 인덱스 불필요.
2. **`has_more`** — `size+1`건을 가져와 초과분 존재로 판정, 초과분은 잘라 `next_cursor` 산출.
3. **응답 계약** — `{items, has_more, next_cursor}`. **`total` 제거.** total이 실제 필요한 화면
   (관리자 통계 등)만 별도 count 옵션/엔드포인트로 분리.
4. **인메모리 페이지네이션 제거** — admin·댓글을 DB keyset로. 댓글 트리는 "루트는 keyset,
   대댓글은 부모별 로드"로 하드리밋(#6) 제거.

## 트레이드오프 (Consequences)

**얻은 것**
- 깊은 페이지에서도 `O(log n)` 범위 스캔 — 페이지 깊이와 무관하게 일정.
- 삽입 중에도 커서 기준이 안정적(drift 없음).
- 매 요청 `COUNT(*)` 제거로 조회 비용 절감.

**치른 비용**
- **임의 페이지 번호 점프 불가**(1→5페이지 직행 X) — 무한 스크롤/다음 버튼엔 무해.
- `total` 부재 → "전체 N개" UI는 별도 처리 필요.

## 고려한 대안 (Alternatives)

| 대안 | 기각 사유 |
|------|-----------|
| `OFFSET/LIMIT` | 깊은 페이지 선형 스캔 + 삽입 시 drift → 조회 폭주 봉투에서 불리 |
| `OFFSET/LIMIT` + `COUNT(*)` | 위 문제 + 매 요청 COUNT(검색 시 pg_trgm) 이중 비용(#10) |
| 인메모리 슬라이스 | 하드리밋 초과분 무음 소실 + total 불일치(#5·#6) |

## 일부러 하지 않은 것 (Non-goals)

- **전체 `total` 실시간 정확 카운트**: 커서 방식에 불필요·고비용. 필요한 화면만 근사/별도 카운트.
- **임의 페이지 번호 점프**: 커뮤니티 피드 UX(무한 스크롤)엔 불필요.
