# 인증 비즈니스 로직. 회원가입·로그인(JWT)·로그아웃·리프레시.
from typing import Optional

from redis.asyncio import Redis
from sqlalchemy.orm import Session

from app.auth.schema import SignUpRequest, LoginRequest, LoginResponse, SessionUserResponse
from app.common import ApiCode, raise_http_error, success_response
from app.api.dependencies import CurrentUser
from app.core.security import create_access_token, create_refresh_token, verify_password, verify_refresh_token
from app.media.model import MediaModel
from app.users.model import UsersModel

_REFRESH_KEY_PREFIX = "rt:"


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
        if MediaModel.verify_signup_token(data.profile_image_id, data.signup_token, db=db) is None:
            raise_http_error(400, ApiCode.SIGNUP_IMAGE_TOKEN_INVALID)
        profile_image_id = data.profile_image_id
    from app.core.security import hash_password
    hashed = hash_password(data.password)
    with db.begin():
        created = UsersModel.create_user(
            data.email,
            hashed,
            data.nickname,
            profile_image_id=profile_image_id,
            db=db,
        )
        if profile_image_id is not None:
            MediaModel.attach_signup_image(profile_image_id, created.id, db=db)
    return success_response(ApiCode.SIGNUP_SUCCESS)


def login_user(data: LoginRequest, db: Session) -> tuple[dict, str, str, int]:
    user = UsersModel.get_user_by_email(data.email, db=db)
    if not user:
        raise_http_error(401, ApiCode.INVALID_CREDENTIALS, "이메일 또는 비밀번호가 일치하지 않습니다")
    if not verify_password(data.password, user.password):
        raise_http_error(401, ApiCode.INVALID_CREDENTIALS, "이메일 또는 비밀번호가 일치하지 않습니다")
    access_token = create_access_token(sub=user.id)
    refresh_token = create_refresh_token(sub=user.id)
    payload = LoginResponse.model_validate(user).model_dump(by_alias=True)
    result = success_response(ApiCode.LOGIN_SUCCESS, payload)
    result["data"]["accessToken"] = access_token
    return result, access_token, refresh_token, user.id


async def logout_user(refresh_token: Optional[str], redis: Optional[Redis]) -> dict:
    if not refresh_token:
        return success_response(ApiCode.LOGOUT_SUCCESS)
    try:
        payload = verify_refresh_token(refresh_token)
        user_id = payload.get("sub")
        if user_id is not None and redis:
            await redis.delete(f"{_REFRESH_KEY_PREFIX}{user_id}")
    except Exception:
        pass
    return success_response(ApiCode.LOGOUT_SUCCESS)


async def revoke_refresh_for_user(user_id: int, redis: Optional[Redis]) -> None:
    """비밀번호 변경·회원 탈퇴 시 Refresh Token 무효화."""
    if redis:
        await redis.delete(f"{_REFRESH_KEY_PREFIX}{user_id}")


async def refresh_tokens(refresh_token: Optional[str], redis: Optional[Redis], db: Session) -> tuple[dict, str]:
    if not refresh_token:
        raise_http_error(401, ApiCode.UNAUTHORIZED)
    payload = verify_refresh_token(refresh_token)
    user_id = int(payload["sub"])
    if redis:
        stored = await redis.get(f"{_REFRESH_KEY_PREFIX}{user_id}")
        if stored is None or stored != refresh_token:
            raise_http_error(401, ApiCode.UNAUTHORIZED)
    user = UsersModel.get_user_by_id(user_id, db=db)
    if not user:
        raise_http_error(401, ApiCode.UNAUTHORIZED)
    new_access = create_access_token(sub=user_id)
    return success_response(ApiCode.AUTH_SUCCESS, {"accessToken": new_access}), new_access


def get_session_user(user: CurrentUser) -> dict:
    data = SessionUserResponse.model_validate(user).model_dump(by_alias=True)
    return success_response(ApiCode.AUTH_SUCCESS, data)
