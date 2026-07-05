"""chat 통합: 인박스 미읽음 집계(#16)·방 접근 멤버십 가드(#19). 라이브 PG 필요(없으면 collect)."""

import pytest
from app.core.ids import uuid_to_base62
from app.db.base_class import utc_now
from app.domain.chat.model import ChatMessage, ChatRoom, normalize_dm_user_ids
from app.domain.users.model import User
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.asyncio


def _token(res_json: dict) -> str:
    d = res_json.get("data", res_json)
    t = d.get("accessToken") or d.get("access_token")
    if not t:
        raise AssertionError("로그인 응답에 accessToken이 없습니다.")
    return t


async def _auth(client: AsyncClient, email: str, nickname: str) -> dict[str, str]:
    pw = "TestPassword123!"
    await client.post(
        "/v1/auth/signup", json={"email": email, "password": pw, "nickname": nickname}
    )
    res = await client.post("/v1/auth/login", json={"email": email, "password": pw})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {_token(res.json())}"}


async def _uid(db: AsyncSession, email: str):
    return (await db.execute(select(User.id).where(User.email == email))).scalar_one()


async def _make_room(db: AsyncSession, a, b) -> ChatRoom:
    u1, u2 = normalize_dm_user_ids(a, b)
    now = utc_now()
    room = ChatRoom(user1_id=u1, user2_id=u2, created_at=now, updated_at=now)
    db.add(room)
    await db.flush()
    return room


async def test_inbox_unread_counts_peer_messages_only(
    client: AsyncClient, db_session: AsyncSession
):
    a = await _auth(client, "chat_a@example.com", "채팅A")
    await _auth(client, "chat_b@example.com", "채팅B")
    aid = await _uid(db_session, "chat_a@example.com")
    bid = await _uid(db_session, "chat_b@example.com")

    room = await _make_room(db_session, aid, bid)
    now = utc_now()
    # 상대(B)가 보낸 미읽음 2건 + 내(A)가 보낸 1건. 미읽음은 상대 발신분만 세어야 한다.
    db_session.add_all(
        [
            ChatMessage(
                room_id=room.id, sender_id=bid, content="hi1", is_read=False, created_at=now
            ),
            ChatMessage(
                room_id=room.id, sender_id=bid, content="hi2", is_read=False, created_at=now
            ),
            ChatMessage(
                room_id=room.id, sender_id=aid, content="yo", is_read=False, created_at=now
            ),
        ]
    )
    await db_session.commit()

    res = await client.get("/v1/chat/rooms", headers=a)
    assert res.status_code == 200, res.text
    items = res.json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["unreadCount"] == 2

    read = await client.post(f"/v1/chat/rooms/{items[0]['roomId']}/read", headers=a)
    assert read.status_code == 200, read.text
    after = await client.get("/v1/chat/rooms", headers=a)
    assert after.json()["data"]["items"][0]["unreadCount"] == 0


async def test_room_access_guarded_by_membership(client: AsyncClient, db_session: AsyncSession):
    a = await _auth(client, "peer_a@example.com", "피어A")
    await _auth(client, "peer_b@example.com", "피어B")
    c = await _auth(client, "peer_c@example.com", "피어C")
    aid = await _uid(db_session, "peer_a@example.com")
    bid = await _uid(db_session, "peer_b@example.com")

    room = await _make_room(db_session, aid, bid)
    rid = room.id
    await db_session.commit()
    pub = uuid_to_base62(rid)

    # 멤버(A)는 200이고 상대 정보 = B, 비멤버(C)는 방 정보·메시지 모두 403.
    ok = await client.get(f"/v1/chat/rooms/{pub}", headers=a)
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["peerNickname"] == "피어B"

    assert (await client.get(f"/v1/chat/rooms/{pub}", headers=c)).status_code == 403
    assert (await client.get(f"/v1/chat/rooms/{pub}/messages", headers=c)).status_code == 403
