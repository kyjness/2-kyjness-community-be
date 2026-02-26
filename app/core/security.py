import hashlib

import bcrypt


def hash_token(token: str) -> str:
    """토큰 원문을 DB 저장용 해시로 변환 (예: signup 이미지 소유권 검증)."""
    return hashlib.sha256(token.encode()).hexdigest()


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(
            password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except (ValueError, TypeError):
        return False
