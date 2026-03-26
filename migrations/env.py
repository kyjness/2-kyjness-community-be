import sys
from pathlib import Path

from alembic import context
from sqlalchemy import create_engine, pool

# 프로젝트 루트 (migrations/env.py → 상위 1단계)
_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

# app 패키지 로드 시 app/__init__.py에서 app.users → app.domain.users 등 별칭이 등록됨.
from app.comments.model import Comment, CommentLike  # noqa: E402, F401
from app.db.base import Base  # noqa: E402
from app.likes.model import PostLike  # noqa: E402, F401
from app.media.model import Image  # noqa: E402, F401
from app.posts.model import Category, Hashtag, Post, PostImage  # noqa: E402, F401
from app.users.model import DogProfile, Report, User, UserBlock  # noqa: E402, F401

config = context.config


def _set_database_url_if_needed() -> None:
    """순환 import 방지: settings는 마이그레이션 실행 시점에만 로드."""
    url = config.get_main_option("sqlalchemy.url", "")
    if not url or url.startswith("driver://"):
        from urllib.parse import quote_plus

        from app.core.config import settings

        if settings.WRITER_DB_URL:
            url = settings.WRITER_DB_URL
        else:
            url = (
                f"postgresql+psycopg://{settings.DB_USER}:{quote_plus(settings.DB_PASSWORD)}"
                f"@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
            )
        config.set_main_option("sqlalchemy.url", url)


def run_migrations_offline() -> None:
    _set_database_url_if_needed()
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=Base.metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    _set_database_url_if_needed()
    url = config.get_main_option("sqlalchemy.url", "")
    connectable = create_engine(url, poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=Base.metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
