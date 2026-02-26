from typing import Optional

from sqlalchemy.orm import Session

from app.auth.model import AuthModel
from app.auth.schema import SignUpRequest, LoginRequest, LoginResponse, SessionUserResponse
from app.common import ApiCode
from app.core.dependencies import CurrentUser
from app.core.security import hash_password, verify_password
from app.common import raise_http_error, success_response
from app.media.model import MediaModel
from app.users.model import UsersModel


def signup_user(data: SignUpRequest, db: Session) -> dict:
    if UsersModel.email_exists(data.email, db=db):
        raise_http_error(409, ApiCode.EMAIL_ALREADY_EXISTS)
    if UsersModel.nickname_exists(data.nickname, db=db):
        raise_http_error(409, ApiCode.NICKNAME_ALREADY_EXISTS)
    hashed = hash_password(data.password)
    created = UsersModel.create_user(data.email, hashed, data.nickname, None, db=db)
    if data.profile_image_id is not None and data.signup_token:
        file_url, err = MediaModel.attach_signup_image_to_user(
            data.signup_token, data.profile_image_id, created["id"], db=db
        )
        if err:
            raise_http_error(400, ApiCode[err])
        if file_url:
            UsersModel.update_profile_image_url(created["id"], file_url, db=db)
    return success_response(ApiCode.SIGNUP_SUCCESS)


def login_user(data: LoginRequest, db: Session) -> tuple[dict, str]:
    row = UsersModel.find_user_by_email(data.email, db=db)
    if not row:
        raise_http_error(401, ApiCode.EMAIL_NOT_FOUND, "존재하지 않는 이메일입니다")
    if not verify_password(data.password, row["password"]):
        raise_http_error(401, ApiCode.INVALID_CREDENTIALS)
    session_id = AuthModel.create_session(row["id"], db=db)
    payload = LoginResponse.model_validate(row).model_dump(by_alias=True)
    return success_response(ApiCode.LOGIN_SUCCESS, payload), session_id


def logout_user(session_id: Optional[str], db: Session) -> dict:
    AuthModel.revoke_session(session_id, db=db)
    return success_response(ApiCode.LOGOUT_SUCCESS)


def get_session_user(user: CurrentUser) -> dict:
    data = SessionUserResponse.model_validate(user).model_dump(by_alias=True)
    return success_response(ApiCode.AUTH_SUCCESS, data)
