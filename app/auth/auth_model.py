# app/auth/auth_model.py
from typing import Optional, Dict
import secrets  # 암호학적으로 안전한 랜덤 세션 ID 생성용
import time
import hashlib
import threading
from datetime import datetime

class AuthModel:
    """인증 관련 데이터 모델 (JSON 기반, DB 사용하지 않음)"""
    
    # 사용자 저장소 (메모리 기반)
    _users: Dict[int, dict] = {}
    _next_user_id: int = 1
    _user_id_lock = threading.Lock()  # 동시성 제어용 락
    
    # 이메일 인덱스 (중복 체크용)
    _email_index: Dict[str, int] = {}
    
    # 닉네임 인덱스 (중복 체크용)
    _nickname_index: Dict[str, int] = {}
    
    # 세션 저장소 (세션 ID -> 사용자 ID/생성시간 매핑)
    _tokens: Dict[str, dict] = {}
    
    # Rate limiting 저장소 (IP -> 요청 정보)
    _rate_limits: Dict[str, dict] = {}
    
    RATE_LIMIT_WINDOW = 60  # 60초 윈도우
    RATE_LIMIT_MAX_REQUESTS = 10  # 최대 10회 요청
    SESSION_EXPIRY_TIME = 86400  # 세션 만료 시간 (24시간, 초 단위)
    
    @staticmethod
    def _hash_password(password: str) -> str:
        """비밀번호 해시화 (SHA-256 사용)"""
        return hashlib.sha256(password.encode('utf-8')).hexdigest()
    
    @staticmethod
    def _verify_password(password: str, hashed_password: str) -> bool:
        """비밀번호 검증"""
        return AuthModel._hash_password(password) == hashed_password
    
    #데이터 CRUD 메서드
    @classmethod
    def create_user(cls, email: str, password: str, nickname: str, profile_image_url: Optional[str] = None) -> dict:
        """새 사용자 생성"""
        # 동시성 제어: user_id 할당 시 락 사용
        with cls._user_id_lock:
            user_id = cls._next_user_id
            cls._next_user_id += 1
        
        default_profile = profile_image_url or "{BE-API-URL}/public/image/profile/default.png"
        
        # 비밀번호 해시화
        hashed_password = cls._hash_password(password)
        
        user = {
            "userId": user_id,
            "email": email,
            "password": hashed_password,  # 해시화된 비밀번호 저장
            "nickname": nickname,
            "profileImageUrl": default_profile,
            "createdAt": datetime.now().isoformat()
        }
        
        cls._users[user_id] = user
        cls._email_index[email.lower()] = user_id
        cls._nickname_index[nickname] = user_id
        
        return user
    
    @classmethod
    def find_user_by_email(cls, email: str) -> Optional[dict]:
        """이메일로 사용자 찾기"""
        user_id = cls._email_index.get(email.lower())
        if user_id:
            return cls._users.get(user_id)
        return None
    
    @classmethod
    def find_user_by_nickname(cls, nickname: str) -> Optional[dict]:
        """닉네임으로 사용자 찾기"""
        user_id = cls._nickname_index.get(nickname)
        if user_id:
            return cls._users.get(user_id)
        return None
    
    @classmethod
    def find_user_by_id(cls, user_id: int) -> Optional[dict]:
        """ID로 사용자 찾기"""
        user = cls._users.get(user_id)
        if user:
            # 비밀번호 제외하고 반환
            return {
                "userId": user["userId"],
                "email": user["email"],
                "nickname": user["nickname"],
                "profileImageUrl": user["profileImageUrl"]
            }
        return None
    
    @classmethod
    def get_user_by_id(cls, user_id: int) -> Optional[dict]:
        """사용자 정보 조회 (비밀번호 제외, createdAt 포함) - UsersModel용 public 메서드"""
        user = cls._users.get(user_id)
        if not user:
            return None
        
        return {
            "userId": user["userId"],
            "email": user["email"],
            "nickname": user["nickname"],
            "profileImageUrl": user["profileImageUrl"],
            "createdAt": user.get("createdAt", "")
        }
    
    @classmethod
    def update_user_nickname(cls, user_id: int, old_nickname: str, new_nickname: str) -> bool:
        """닉네임 수정 - UsersModel용 public 메서드"""
        user = cls._users.get(user_id)
        if not user:
            return False
        
        # 기존 닉네임 인덱스에서 제거
        if old_nickname in cls._nickname_index:
            del cls._nickname_index[old_nickname]
        
        # 새 닉네임으로 업데이트
        user["nickname"] = new_nickname
        cls._nickname_index[new_nickname] = user_id
        
        return True
    
    @classmethod
    def update_user_password(cls, user_id: int, new_password: str) -> bool:
        """비밀번호 수정 - UsersModel용 public 메서드"""
        user = cls._users.get(user_id)
        if not user:
            return False
        
        # 비밀번호 해시화하여 저장
        user["password"] = cls._hash_password(new_password)
        return True
    
    @classmethod
    def update_user_profile_image_url(cls, user_id: int, profile_image_url: str) -> bool:
        """프로필 이미지 URL 수정 - UsersModel용 public 메서드"""
        user = cls._users.get(user_id)
        if not user:
            return False
        
        user["profileImageUrl"] = profile_image_url
        return True
    
    @classmethod
    def delete_user_data(cls, user_id: int) -> bool:
        """사용자 데이터 삭제 - UsersModel용 public 메서드"""
        user = cls._users.get(user_id)
        if not user:
            return False
        
        email = user["email"]
        nickname = user["nickname"]
        
        # 인덱스에서 제거
        if email.lower() in cls._email_index:
            del cls._email_index[email.lower()]
        if nickname in cls._nickname_index:
            del cls._nickname_index[nickname]
        
        # 사용자 데이터 삭제
        del cls._users[user_id]
        
        return True
    
    @classmethod
    def revoke_all_user_tokens(cls, user_id: int) -> int:
        """사용자의 모든 세션 삭제 - UsersModel용 public 메서드"""
        sessions_to_remove = []
        for session_id, session_info in cls._tokens.items():
            if session_info["userId"] == user_id:
                sessions_to_remove.append(session_id)
        
        for session_id in sessions_to_remove:
            del cls._tokens[session_id]
        
        return len(sessions_to_remove)
    
    @classmethod
    def email_exists(cls, email: str) -> bool:
        """이메일 중복 확인"""
        return email.lower() in cls._email_index
    
    @classmethod
    def nickname_exists(cls, nickname: str) -> bool:
        """닉네임 중복 확인"""
        return nickname in cls._nickname_index
    
    @classmethod
    def verify_password(cls, user_id: int, password: str) -> bool:
        """비밀번호 검증"""
        user = cls._users.get(user_id)
        if not user:
            return False
        return cls._verify_password(password, user["password"])
    
    # 세션 저장소 관리 (쿠키-세션 방식)
    @classmethod
    def create_token(cls, user_id: int) -> str:
        """세션 ID 생성 (쿠키-세션 방식)"""
        session_id = secrets.token_urlsafe(32)
        cls._tokens[session_id] = {
            "userId": user_id,
            "createdAt": time.time()
        }
        return session_id
    
    @classmethod
    def verify_token(cls, session_id: Optional[str]) -> Optional[int]:
        """세션 ID 검증 및 사용자 ID 반환 (만료 시간 체크 포함)"""
        if not session_id:
            return None
        
        session_info = cls._tokens.get(session_id)
        if not session_info:
            return None
        
        # 세션 만료 시간 체크
        current_time = time.time()
        if current_time - session_info["createdAt"] > cls.SESSION_EXPIRY_TIME:
            # 만료된 세션 삭제
            del cls._tokens[session_id]
            return None
        
        return session_info["userId"]
    
    @classmethod
    def revoke_token(cls, session_id: Optional[str]) -> bool:
        """세션 ID 삭제 (로그아웃)"""
        if not session_id:
            return False
        
        if session_id in cls._tokens:
            del cls._tokens[session_id]
            return True
        return False
    
    @classmethod
    def cleanup_expired_sessions(cls) -> int:
        """만료된 세션 정리"""
        current_time = time.time()
        expired_sessions = []
        
        for session_id, session_info in cls._tokens.items():
            if current_time - session_info["createdAt"] > cls.SESSION_EXPIRY_TIME:
                expired_sessions.append(session_id)
        
        for session_id in expired_sessions:
            del cls._tokens[session_id]
        
        return len(expired_sessions)
    
    @classmethod
    def check_rate_limit(cls, identifier: str) -> bool:
        """Rate limiting 확인 (True: 허용, False: 거부)"""
        current_time = time.time()
        
        if identifier not in cls._rate_limits:
            cls._rate_limits[identifier] = {
                "requests": [],
                "window_start": current_time
            }
        
        rate_info = cls._rate_limits[identifier]
        
        # 윈도우 밖의 요청 제거
        rate_info["requests"] = [
            req_time for req_time in rate_info["requests"]
            if current_time - req_time < cls.RATE_LIMIT_WINDOW
        ]
        
        # 요청 수 확인
        if len(rate_info["requests"]) >= cls.RATE_LIMIT_MAX_REQUESTS:
            return False
        
        # 요청 기록
        rate_info["requests"].append(current_time)
        return True
