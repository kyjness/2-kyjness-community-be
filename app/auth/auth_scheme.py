# app/schemas/auth.py
from pydantic import BaseModel, EmailStr #Pydantic은 422에러를 자동해결해줌
from typing import Optional, Dict, Any

#회원가입 요청 바디
class SignUpRequest(BaseModel):
    email: EmailStr
    password: str
    nickname: str
    profile_image_url: Optional[str] = None  # 프로필 이미지 URL (선택)

#회원가입 응답 바디
class SignUpResponse(BaseModel):
    code: str
    data: Optional[Dict[str, Any]] = None