# API 의존성 단일 진입점. 라우터/핸들러에서는 여기서만 import.
from .auth import (
    CurrentUser,
    get_current_admin,
    get_current_user,
    get_current_user_optional,
)
from .client import (
    MEDIA_SIGNUP_IDEMPOTENT_RESPONSE_ATTR,
    MEDIA_UPLOAD_IDEMPOTENT_RESPONSE_ATTR,
    get_client_identifier,
    media_image_upload_idempotency_prepare,
    media_signup_upload_idempotency_after_failure,
    media_signup_upload_idempotency_after_success,
    media_signup_upload_idempotency_prepare,
    media_upload_idempotency_after_failure,
    media_upload_idempotency_after_success,
    post_create_idempotency_after_failure,
    post_create_idempotency_after_success,
    post_create_idempotency_before,
)
from .db import get_master_db, get_slave_db
from .permissions import (
    CommentAuthorContext,
    require_comment_author,
    require_comment_author_for_delete,
    require_post_author,
)
from .query import parse_availability_query
from .redis_client import get_optional_redis
from .upload import check_upload_content_length

__all__ = [
    "check_upload_content_length",
    "CommentAuthorContext",
    "CurrentUser",
    "get_client_identifier",
    "MEDIA_SIGNUP_IDEMPOTENT_RESPONSE_ATTR",
    "MEDIA_UPLOAD_IDEMPOTENT_RESPONSE_ATTR",
    "media_image_upload_idempotency_prepare",
    "media_signup_upload_idempotency_after_failure",
    "media_signup_upload_idempotency_after_success",
    "media_signup_upload_idempotency_prepare",
    "media_upload_idempotency_after_failure",
    "media_upload_idempotency_after_success",
    "post_create_idempotency_after_failure",
    "post_create_idempotency_after_success",
    "post_create_idempotency_before",
    "get_current_admin",
    "get_current_user",
    "get_current_user_optional",
    "get_master_db",
    "get_slave_db",
    "get_optional_redis",
    "parse_availability_query",
    "require_comment_author",
    "require_comment_author_for_delete",
    "require_post_author",
]
