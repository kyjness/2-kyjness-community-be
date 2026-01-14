# app/models/auth_model.py (임시 Mock 버전)
from typing import Optional, Dict


class AuthModel:
    """임시 Mock - 나중에 제대로 구현"""

    _users: Dict[int, dict] = {
        1: {
            "userId": 1,
            "email": "test@test.com",
            "nickname": "테스트유저",
            "profileImage": "http://example.com/profile.jpg"
        }
    }

    @classmethod
    def find_user_by_id(cls, user_id: int) -> Optional[dict]:
        """ID로 사용자 찾기 (임시)"""
        return cls._users.get(user_id, cls._users[1])  # 없으면 기본 유저 반환