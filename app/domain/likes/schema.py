# Likes 도메인 응답 스키마.
from app.common import BaseSchema


class LikeResponseData(BaseSchema):
    is_liked: bool = False
    like_count: int = 0
