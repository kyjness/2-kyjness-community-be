from app.common import BaseSchema, PublicId


class TrendingPostResponse(BaseSchema):
    id: PublicId
    title: str
    category_id: int | None = None
    comment_count: int = 0
    like_count: int = 0
    view_count: int = 0
