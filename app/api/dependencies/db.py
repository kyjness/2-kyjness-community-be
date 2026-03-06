# DB 세션 의존성. get_master_db(CUD) / get_slave_db(Read). yield 후 commit/rollback/close.
# 주의: 세션은 이미 트랜잭션 중이므로 controller에서 db.begin() 사용 시 InvalidRequestError 발생.
from typing import Generator

from sqlalchemy.orm import Session

from app.db.engine import SessionLocal, SessionLocalReader


def get_master_db() -> Generator[Session, None, None]:
    """CUD용 Writer 세션. yield 후 commit/예외 시 rollback/finally close."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_slave_db() -> Generator[Session, None, None]:
    """조회용 Reader 세션(READ ONLY). yield 후 commit/예외 시 rollback/finally close."""
    db = SessionLocalReader()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
