# app/auth/auth_schema.py
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Dict, Any

# 회원가입 요청 바디
class SignUpRequest(BaseModel):
    email: EmailStr = Field(..., description="사용자 이메일")
    password: str = Field(..., min_length=8, max_length=20, description="비밀번호 (8-20자)")
    passwordConfirm: str = Field(..., description="비밀번호 확인")
    nickname: str = Field(..., min_length=1, max_length=10, description="닉네임 (1-10자, 공백 불가)")
    profileImageUrl: Optional[str] = Field(default=None, description="프로필 이미지 URL (선택)")

# 로그인 요청 바디
class LoginRequest(BaseModel):
    email: EmailStr = Field(..., description="사용자 이메일")
    password: str = Field(..., min_length=8, max_length=20, description="비밀번호 (8-20자)")

# 공통 응답 바디
class AuthResponse(BaseModel):
    code: str
    data: Optional[Dict[str, Any]] = None

# 로그인 성공 응답 데이터
class LoginData(BaseModel):
    userId: int
    email: str
    nickname: str
    profileImage: str

# 로그인 상태 체크 응답 데이터
class MeData(BaseModel):
    userId: int
    email: str
    nickname: str
    profileImageUrl: str
