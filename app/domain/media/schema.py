# 이미지 업로드 응답 DTO. Image ORM → Controller에서 Schema로 직렬화.
from pydantic import BaseModel, ConfigDict, Field


class ImageUploadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(serialization_alias="imageId")
    file_url: str = Field(serialization_alias="url")
