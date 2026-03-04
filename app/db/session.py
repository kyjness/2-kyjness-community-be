# 비요청 스코프용 세션. get_connection(cleanup/exception 등). 요청 스코프용 get_master_db/get_slave_db는 app.api.dependencies.db.
from contextlib import contextmanager

from app.db.engine import SessionLocal


@contextmanager
def get_connection():
    """cleanup·exception_handlers 등 비요청 스코프용. commit/rollback/close 보장."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
