# 요청별 세션 주입. get_db(Generator), get_connection(contextmanager). commit/rollback 스코프.
from contextlib import contextmanager
from typing import Generator

from sqlalchemy.orm import Session

from app.db.engine import SessionLocal


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@contextmanager
def get_connection():
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
