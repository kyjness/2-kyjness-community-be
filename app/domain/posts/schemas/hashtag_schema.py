from app.common import BaseSchema


class TrendingHashtagResponse(BaseSchema):
    name: str
    count: int
