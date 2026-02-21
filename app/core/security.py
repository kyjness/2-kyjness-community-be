# app/core/security.py
"""비밀번호 해시·검증 (bcrypt)"""

import bcrypt


def hash_password(password: str) -> str:
    """비밀번호 해시화"""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(password: str, hashed_password: str) -> bool:
    """비밀번호 검증"""
    try:
        return bcrypt.checkpw(
            password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except (ValueError, TypeError):
        return False
