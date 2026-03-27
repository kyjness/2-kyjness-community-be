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
    
    # [수정 포인트] 연결 안정성을 위한 엔진 설정 강화
    connectable = create_engine(
        url, 
        poolclass=pool.NullPool,
        pool_pre_ping=True,  # [중요] 연결이 살아있는지 체크 후 작업 시작
        connect_args={
            "connect_timeout": 20,  # 연결 시도 시간 넉넉히 (기본값은 보통 짧음)
            "prepare_threshold": None # psycopg 관련 캐시 이슈 방지
        }
    )

    try:
        with connectable.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=Base.metadata,
                # [추가] 마이그레이션 도중 예기치 못한 타임아웃 방지
                execution_options={"isolation_level": "AUTOCOMMIT"} if context.is_offline_mode() else {}
            )

            with context.begin_transaction():
                # 큰 규모의 스키마 변경 시 DB가 응답을 멈춘 것처럼 보일 수 있으므로
                # 트랜잭션 내에서 안전하게 실행
                context.run_migrations()
                
    except Exception as e:
        # 에러 로그를 좀 더 명확하게 남겨서 추적 용이하게 함
        print(f"FAILED TO RUN MIGRATIONS: {e}")
        raise


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
