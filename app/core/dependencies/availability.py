from typing import Optional

from fastapi import Query
from pydantic import ValidationError

from app.common import ApiCode, raise_http_error
from app.users.schema import UserAvailabilityQuery


def parse_availability_query(email: Optional[str] = Query(None, description="이메일"), nickname: Optional[str] = Query(None, description="닉네임")) -> UserAvailabilityQuery:
    try:
        return UserAvailabilityQuery(email=email, nickname=nickname)
    except ValidationError:
        raise_http_error(400, ApiCode.INVALID_REQUEST)
