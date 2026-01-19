# app/core/dependencies.py
import logging
from fastapi import HTTPException, Cookie
from typing import Optional
from app.auth.auth_model import AuthModel

logger = logging.getLogger(__name__)

def get_current_user(session_id: Optional[str] = Cookie(None)) -> int:
    """인증된 사용자 ID를 반환하는 Dependency 함수"""
    # status code 401번
    # 인증 정보 없음
    if not session_id:
        logger.warning("Authentication failed: No session ID provided")
        raise HTTPException(status_code=401, detail={"code": "UNAUTHORIZED", "data": None})
    
    # 세션 ID 검증
    user_id = AuthModel.verify_token(session_id)
    if not user_id:
        logger.warning(f"Authentication failed: Invalid session ID (session_id exists but verification failed)")
        raise HTTPException(status_code=401, detail={"code": "UNAUTHORIZED", "data": None})
    
    return user_id
