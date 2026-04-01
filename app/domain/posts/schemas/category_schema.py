from app.common import BaseSchema


class CategoryResponse(BaseSchema):
    id: int
    name: str

