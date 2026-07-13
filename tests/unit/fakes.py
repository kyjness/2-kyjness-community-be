"""단위 테스트 공용 인메모리 가짜.

파일마다 FakeRedis·FakeDB류를 각자 구현해 드리프트하던 것을 한 곳으로 모은다.
FakeRedis는 get_app_redis의 isinstance(Redis) 가드를 통과하도록 실제 Redis를
상속하되, __init__을 덮어써 실연결(커넥션 풀)은 만들지 않는다. eval 의미론이
다른 테스트(rate limit 고정 창 등)는 FakeRedis를 상속해 eval만 교체한다.
"""

from typing import Any, cast

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession


class FakeRedis(Redis):
    """kv(get/set NX·EX/delete)·hash(hincrby/hget/hgetall)·publish 기록과
    조회수 버퍼 Lua 2종(RENAME 스왑·CAS 해제)을 흉내내는 수퍼셋 가짜."""

    def __init__(
        self,
        *,
        preloaded: dict[str, str] | None = None,
        fail_publish: bool = False,
        fail_delete_substr: str | None = None,
    ) -> None:
        self.kv: dict[str, str] = dict(preloaded or {})
        self.hashes: dict[str, dict[str, int]] = {}
        self.published: list[tuple[str, str]] = []
        self.set_calls: list[str] = []
        self.fail_publish = fail_publish
        self._fail_delete_substr = fail_delete_substr

    async def get(self, key):
        v = self.kv.get(key)
        return v.encode() if v is not None else None

    async def set(self, key, val, nx=False, ex=None):
        if nx and key in self.kv:
            return None
        self.kv[key] = val
        self.set_calls.append(key)
        return True

    async def delete(self, key):  # pyright: ignore[reportIncompatibleMethodOverride]
        if self._fail_delete_substr is not None and self._fail_delete_substr in key:
            raise ConnectionError("redis del failed")
        existed = key in self.kv or key in self.hashes
        self.kv.pop(key, None)
        self.hashes.pop(key, None)
        return 1 if existed else 0

    @staticmethod
    def _field(field):
        # 실 Redis처럼 bytes 필드와 str 필드를 동일 키로 취급.
        return field.decode() if isinstance(field, (bytes, bytearray)) else field

    async def hincrby(self, key, field, n):
        h = self.hashes.setdefault(key, {})
        f = self._field(field)
        h[f] = h.get(f, 0) + n
        return h[f]

    async def hget(self, key, field):
        v = self.hashes.get(key, {}).get(self._field(field))
        return str(v).encode() if v is not None else None

    async def hgetall(self, key):
        h = self.hashes.get(key, {})
        return {k.encode(): str(v).encode() for k, v in h.items()}

    async def publish(self, channel, message):
        if self.fail_publish:
            raise ConnectionError("redis down")
        self.published.append((channel, message))
        return 1

    async def eval(self, script, numkeys, *args):  # pyright: ignore[reportIncompatibleMethodOverride]
        keys = args[:numkeys]
        argv = args[numkeys:]
        if "RENAME" in script:  # view buffer -> drain (원자 스왑)
            src, dst = keys[0], keys[1]
            if not self.hashes.get(src):
                return 0
            self.hashes[dst] = self.hashes.pop(src)
            return 1
        # CAS 해제: GET==ARGV[0] 일 때만 DEL
        k, expected = keys[0], argv[0]
        if self.kv.get(k) == expected:
            self.kv.pop(k, None)
            return 1
        return 0


class FakeBegin:
    async def __aenter__(self):
        return None

    async def __aexit__(self, *a):
        return False


class FakeDB:
    """`async with db.begin()` 만 흉내내는 가짜 세션."""

    def begin(self):
        return FakeBegin()


class RecordingDB(FakeDB):
    """begin() 호출 수를 세는 가짜 세션 — writer 트랜잭션이 열렸는지 판별용."""

    def __init__(self) -> None:
        self.begin_count = 0

    def begin(self):
        self.begin_count += 1
        return FakeBegin()


def as_session(db: Any) -> AsyncSession:
    """가짜 세션을 시그니처 타입에 맞춰 전달(런타임은 begin()만 쓴다)."""
    return cast(AsyncSession, db)
