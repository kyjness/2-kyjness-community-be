# 쿼리 파싱. parse_availability_query (가용성 등).

from fastapi import Query
from pydantic import ValidationError

from app.common.exceptions import InvalidRequestException
from app.users.schema import UserAvailabilityQuery


def parse_availability_query(
    email: str | None = Query(None, description="이메일"),
    nickname: str | None = Query(None, description="닉네임"),
) -> UserAvailabilityQuery:
    try:
        return UserAvailabilityQuery(email=email, nickname=nickname)
    except ValidationError:
        raise InvalidRequestException(message="이메일 또는 닉네임 중 하나는 필수입니다.")
