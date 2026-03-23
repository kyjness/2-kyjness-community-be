# 공용 enum. API·스키마·설정에서 허용 값 제한 및 문서화.
from enum import StrEnum


class TargetType(StrEnum):
    POST = "POST"
    COMMENT = "COMMENT"


class ReportReason(StrEnum):
    SPAM = "스팸"
    PROFANITY = "욕설"
    INAPPROPRIATE_CONTENT = "부적절한 콘텐츠"
    OTHER = "기타"


class DogGender(StrEnum):
    MALE = "male"
    FEMALE = "female"


class UserStatus(StrEnum):
    ACTIVE = "ACTIVE"  # 정상 이용
    SUSPENDED = "SUSPENDED"  # 정지
    WITHDRAWN = "WITHDRAWN"  # 탈퇴(soft delete)

    @classmethod
    def is_active_value(cls, status: object) -> bool:
        value = getattr(status, "value", status)
        return value == cls.ACTIVE.value

    @classmethod
    def is_suspended_value(cls, status: object) -> bool:
        value = getattr(status, "value", status)
        return value == cls.SUSPENDED.value

    @classmethod
    def is_withdrawn_value(cls, status: object) -> bool:
        value = getattr(status, "value", status)
        return value == cls.WITHDRAWN.value

    @classmethod
    def inactive_message_ko(cls, status: object) -> str:
        if cls.is_suspended_value(status):
            return "계정이 정지되었습니다."
        if cls.is_withdrawn_value(status):
            return "탈퇴한 계정입니다."
        return "계정이 비활성 상태입니다."
