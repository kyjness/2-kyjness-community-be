# 도메인 기반 커스텀 예외. Service에서 raise → 전역 handler가 { code, data, message } 규격으로 변환.
# core 계층이 특정 Model에 의존하지 않도록 예외 객체만으로 응답 구성.
from typing import Any

from app.common.codes import ApiCode


class BaseProjectException(Exception):
    """프로젝트 공통 예외. status_code, code, message, data로 전역 handler가 JSON 응답 생성."""

    def __init__(
        self,
        status_code: int = 500,
        code: ApiCode | str = ApiCode.INTERNAL_SERVER_ERROR,
        message: str | None = None,
        data: Any | None = None,
    ):
        self.status_code = status_code
        self.code = code
        self.message = message
        self.data = data
        super().__init__(message or str(code))


# --- Posts ---
class PostNotFoundException(BaseProjectException):
    def __init__(self, message: str | None = None):
        super().__init__(status_code=404, code=ApiCode.POST_NOT_FOUND, message=message)


class ConcurrentUpdateException(BaseProjectException):
    """낙관적 락 충돌(예: SQLAlchemy StaleDataError) 시 반환하는 409 예외."""

    def __init__(self, message: str | None = None):
        super().__init__(
            status_code=409,
            code=ApiCode.CONFLICT,
            message=message or "데이터가 다른 요청에 의해 변경되어 완료할 수 없습니다.",
        )


# --- Users / Auth ---
class UserNotFoundException(BaseProjectException):
    def __init__(self, message: str | None = None):
        super().__init__(status_code=404, code=ApiCode.USER_NOT_FOUND, message=message)


class UserWithdrawnException(BaseProjectException):
    def __init__(self, message: str | None = None):
        super().__init__(
            status_code=400,
            code=ApiCode.USER_WITHDRAWN,
            message=message or "탈퇴한 유저입니다.",
        )


class EmailAlreadyExistsException(BaseProjectException):
    def __init__(self, message: str | None = None):
        super().__init__(status_code=409, code=ApiCode.EMAIL_ALREADY_EXISTS, message=message)


class NicknameAlreadyExistsException(BaseProjectException):
    def __init__(self, message: str | None = None):
        super().__init__(status_code=409, code=ApiCode.NICKNAME_ALREADY_EXISTS, message=message)


class MissingRequiredFieldException(BaseProjectException):
    def __init__(self, message: str | None = None):
        super().__init__(status_code=400, code=ApiCode.MISSING_REQUIRED_FIELD, message=message)


class SignupImageTokenInvalidException(BaseProjectException):
    def __init__(self, message: str | None = None):
        super().__init__(status_code=400, code=ApiCode.SIGNUP_IMAGE_TOKEN_INVALID, message=message)


class InvalidCredentialsException(BaseProjectException):
    """이메일/비밀번호 불일치 등 로그인 실패(401)."""

    def __init__(self, message: str | None = None):
        super().__init__(
            status_code=401,
            code=ApiCode.INVALID_CREDENTIALS,
            message=message or "이메일 또는 비밀번호가 일치하지 않습니다",
        )


class InvalidUserInfoException(BaseProjectException):
    """요청 데이터 검증 실패(400). 메시지로 상세 사유 전달."""

    def __init__(self, message: str | None = None):
        super().__init__(status_code=400, code=ApiCode.INVALID_REQUEST, message=message)


class UnauthorizedException(BaseProjectException):
    def __init__(self, message: str | None = None):
        super().__init__(status_code=401, code=ApiCode.UNAUTHORIZED, message=message)


class ForbiddenException(BaseProjectException):
    def __init__(self, message: str | None = None):
        super().__init__(status_code=403, code=ApiCode.FORBIDDEN, message=message)


# --- Comments ---
class CommentNotFoundException(BaseProjectException):
    def __init__(self, message: str | None = None):
        super().__init__(status_code=404, code=ApiCode.COMMENT_NOT_FOUND, message=message)


class InvalidPostIdFormatException(BaseProjectException):
    def __init__(self, message: str | None = None):
        super().__init__(status_code=400, code=ApiCode.INVALID_POSTID_FORMAT, message=message)


# --- Likes: 응답에 likeCount, isLiked 등 데이터 전달 ---
class AlreadyLikedException(BaseProjectException):
    """이미 좋아요한 상태(UniqueViolation 등). data에 likeCount, isLiked 등 담아 전달."""

    def __init__(self, data: dict | None = None, message: str | None = None):
        super().__init__(
            status_code=200,
            code=ApiCode.ALREADY_LIKED,
            message=message,
            data=data,
        )


# --- Media / Image ---
class ImageNotFoundException(BaseProjectException):
    def __init__(self, message: str | None = None):
        super().__init__(status_code=404, code=ApiCode.IMAGE_NOT_FOUND, message=message)


class InvalidImageException(BaseProjectException):
    """업로드되지 않았거나 잘못된 이미지 ID 참조(400)."""

    def __init__(self, message: str | None = None):
        super().__init__(
            status_code=400,
            code=ApiCode.INVALID_REQUEST,
            message=message or "업로드되지 않은 이미지 ID를 참조할 수 없습니다.",
        )


class InvalidImageFileException(BaseProjectException):
    """이미지 파일 형식/포맷 오류(400)."""

    def __init__(self, message: str | None = None):
        super().__init__(status_code=400, code=ApiCode.INVALID_IMAGE_FILE, message=message)


class FileSizeExceededException(BaseProjectException):
    def __init__(self, message: str | None = None):
        super().__init__(status_code=400, code=ApiCode.FILE_SIZE_EXCEEDED, message=message)


class InvalidFileTypeException(BaseProjectException):
    def __init__(self, message: str | None = None):
        super().__init__(status_code=400, code=ApiCode.INVALID_FILE_TYPE, message=message)


class ImageInUseException(BaseProjectException):
    def __init__(self, message: str | None = None):
        super().__init__(status_code=409, code=ApiCode.IMAGE_IN_USE, message=message)


# --- 공통 ---
class InternalServerErrorException(BaseProjectException):
    def __init__(self, message: str | None = None):
        super().__init__(status_code=500, code=ApiCode.INTERNAL_SERVER_ERROR, message=message)


class DBErrorException(BaseProjectException):
    """DB 연결 오류·교착 등. 전역 handler에서 500 처리."""

    def __init__(self, message: str | None = None):
        super().__init__(status_code=500, code=ApiCode.DB_ERROR, message=message)


class InvalidRequestException(BaseProjectException):
    def __init__(self, message: str | None = None):
        super().__init__(status_code=400, code=ApiCode.INVALID_REQUEST, message=message)


class PayloadTooLargeException(BaseProjectException):
    def __init__(self, message: str | None = None):
        super().__init__(
            status_code=413,
            code=ApiCode.PAYLOAD_TOO_LARGE,
            message=message or "요청 본문이 허용 크기를 초과합니다.",
        )


class NotFoundException(BaseProjectException):
    def __init__(
        self,
        code: ApiCode | str = ApiCode.NOT_FOUND,
        message: str | None = None,
    ):
        super().__init__(status_code=404, code=code, message=message)
