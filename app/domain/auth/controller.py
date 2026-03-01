# 인증 비즈니스 로직. 회원가입·로그인·로그아웃·세션 생성.
import logging
import hmac
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.auth.model import AuthModel
from app.auth.schema import SignUpRequest, LoginRequest, LoginResponse, SessionUserResponse
from app.common import ApiCode
from app.core.dependencies import CurrentUser
from app.core.security import hash_password, hash_token, verify_password
from app.common import raise_http_error, success_response
from app.media.model import MediaModel
from app.users.model import UsersModel


def signup_user(data: SignUpRequest, db: Session) -> dict:
    if UsersModel.email_exists(data.email, db=db):
        raise_http_error(409, ApiCode.EMAIL_ALREADY_EXISTS)
    if UsersModel.nickname_exists(data.nickname, db=db):
        raise_http_error(409, ApiCode.NICKNAME_ALREADY_EXISTS)
    has_image = data.profile_image_id is not None
    has_token = bool(data.signup_token)
    if has_image != has_token:
        raise_http_error(400, ApiCode.MISSING_REQUIRED_FIELD)
    profile_image_id = None
    if has_image and has_token:
        image = MediaModel.get_signup_image_for_update(data.profile_image_id, db=db)
        if image is None:
            raise_http_error(400, ApiCode.SIGNUP_IMAGE_TOKEN_INVALID)
        if image.uploader_id is not None:
            raise_http_error(400, ApiCode.SIGNUP_IMAGE_TOKEN_INVALID)
        expected_hash = hash_token(data.signup_token)
        if not hmac.compare_digest(image.signup_token_hash or "", expected_hash):
            raise_http_error(400, ApiCode.SIGNUP_IMAGE_TOKEN_INVALID)
        now = datetime.now(timezone.utc)
        expires_at = image.signup_expires_at
        if expires_at is None:
            raise_http_error(400, ApiCode.SIGNUP_IMAGE_TOKEN_INVALID)
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at <= now:
            raise_http_error(400, ApiCode.SIGNUP_IMAGE_TOKEN_INVALID)
        profile_image_id = data.profile_image_id
    hashed = hash_password(data.password)
    created = UsersModel.create_user(
        data.email,
        hashed,
        data.nickname,
        profile_image_id=profile_image_id,
        db=db,
    )
    if profile_image_id is not None:
        try:
            MediaModel.finalize_signup_image(profile_image_id, created.id, db=db)
        except Exception as exc:
            logger.warning("finalize_signup_image failed (user already created): %s", exc)
    return success_response(ApiCode.SIGNUP_SUCCESS)


def login_user(data: LoginRequest, db: Session) -> tuple[dict, str]:
    user = UsersModel.find_user_by_email(data.email, db=db)
    if not user:
        raise_http_error(401, ApiCode.EMAIL_NOT_FOUND, "존재하지 않는 이메일입니다")
    if not verify_password(data.password, user.password):
        raise_http_error(401, ApiCode.INVALID_CREDENTIALS)
    session_id = AuthModel.create_session(user.id, db=db)
    payload = LoginResponse.model_validate(user).model_dump(by_alias=True)
    return success_response(ApiCode.LOGIN_SUCCESS, payload), session_id


def logout_user(session_id: Optional[str], db: Session) -> dict:
    AuthModel.revoke_session(session_id, db=db)
    return success_response(ApiCode.LOGOUT_SUCCESS)


def get_session_user(user: CurrentUser) -> dict:
    data = SessionUserResponse.model_validate(user).model_dump(by_alias=True)
    return success_response(ApiCode.AUTH_SUCCESS, data)
