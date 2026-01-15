# app/schemas/users.py
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

# 내 정보 수정 요청 바디
class UpdateUserRequest(BaseModel):
    nickname: Optional[str] = Field(default=None, min_length=1, max_length=10, description="닉네임 (1-10자, 선택)")
    profileImageUrl: Optional[str] = Field(default=None, description="프로필 이미지 URL (선택)")

# 비밀번호 변경 요청 바디
class UpdatePasswordRequest(BaseModel):
    currentPassword: str = Field(..., description="현재 비밀번호")
    newPassword: str = Field(..., min_length=8, max_length=20, description="새 비밀번호 (8-20자)")

# 공통 응답 바디
class UsersResponse(BaseModel):
    code: str
    data: Optional[Dict[str, Any]] = None

# 내 정보 조회 응답 데이터
class UserRetrievedData(BaseModel):
    userId: int
    email: str
    nickname: str
    profileImageUrl: str
    createdAt: str

# 프로필 이미지 업로드
# 요청: 파일 업로드 (FastAPI의 UploadFile 사용, 스키마 없음)
# - profileImage: .jpg 파일 (multipart/form-data)
# 응답 데이터
class ProfileImageUploadData(BaseModel):
    profileImageUrl: str

# 이메일 중복 체크 응답 데이터
class EmailAvailableData(BaseModel):
    available: bool

# 닉네임 중복 체크 응답 데이터
class NicknameAvailableData(BaseModel):
    available: bool
