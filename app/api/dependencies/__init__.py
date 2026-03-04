# API 의존성 단일 진입점. 라우터/핸들러에서는 여기서만 import.
# 예: from app.api.dependencies import get_master_db, get_slave_db, get_current_user, CurrentUser, require_post_author, ...
from .auth import CurrentUser, get_current_user
from .db import get_master_db, get_slave_db
from .permissions import CommentAuthorContext, require_comment_author, require_post_author
from .query import parse_availability_query

__all__ = [
    "CommentAuthorContext",
    "CurrentUser",
    "get_current_user",
    "get_master_db",
    "get_slave_db",
    "parse_availability_query",
    "require_comment_author",
    "require_post_author",
]
