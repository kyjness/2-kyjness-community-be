# app/users/users_model.py
from typing import Optional
from app.auth.auth_model import AuthModel

class UsersModel:
    """사용자 정보 수정 관련 데이터 모델"""
    
    @classmethod
    def update_nickname(cls, user_id: int, new_nickname: str) -> bool:
        """닉네임 수정"""
        # AuthModel의 public 메서드 사용 (캡슐화 개선)
        user = AuthModel.get_user_by_id(user_id)
        if not user:
            return False
        
        old_nickname = user["nickname"]
        return AuthModel.update_user_nickname(user_id, old_nickname, new_nickname)
    
    @classmethod
    def update_password(cls, user_id: int, new_password: str) -> bool:
        """비밀번호 수정"""
        # AuthModel의 public 메서드 사용 (캡슐화 개선)
        return AuthModel.update_user_password(user_id, new_password)
    
    @classmethod
    def delete_user(cls, user_id: int) -> bool:
        """회원 탈퇴 (사용자 삭제)"""
        # AuthModel의 public 메서드 사용 (캡슐화 개선)
        if not AuthModel.delete_user_data(user_id):
            return False
        
        # 해당 사용자의 모든 세션 삭제
        AuthModel.revoke_all_sessions_for_user(user_id)
        
        return True
    
    @classmethod
    def get_user_by_id(cls, user_id: int) -> Optional[dict]:
        """사용자 정보 조회 (비밀번호 제외, createdAt 포함)"""
        # AuthModel의 public 메서드 사용 (캡슐화 개선)
        return AuthModel.get_user_by_id(user_id)
    
    @classmethod
    def update_profile_image_url(cls, user_id: int, profile_image_url: str) -> bool:
        """프로필 이미지 URL 수정"""
        # AuthModel의 public 메서드 사용 (캡슐화 개선)
        return AuthModel.update_user_profile_image_url(user_id, profile_image_url)
