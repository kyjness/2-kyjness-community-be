# 공용 enum. API·스키마·설정에서 허용 값 제한 및 문서화.
from enum import Enum


class DogGender(str, Enum):
    MALE = "male"
    FEMALE = "female"


class UserStatus(str, Enum):
    ACTIVE = "ACTIVE"  # 정상 이용
    SUSPENDED = "SUSPENDED"  # 정지
    WITHDRAWN = "WITHDRAWN"  # 탈퇴(soft delete)

    # Backward-compatibility (legacy 값)
    BANNED = "BANNED"
    DELETED = "DELETED"

    @classmethod
    def is_active_value(cls, status: object) -> bool:
        value = getattr(status, "value", status)
        return value == cls.ACTIVE.value

    @classmethod
    def is_suspended_value(cls, status: object) -> bool:
        value = getattr(status, "value", status)
        return value in {cls.SUSPENDED.value, cls.BANNED.value}

    @classmethod
    def is_withdrawn_value(cls, status: object) -> bool:
        value = getattr(status, "value", status)
        return value in {cls.WITHDRAWN.value, cls.DELETED.value}

    @classmethod
    def inactive_message_ko(cls, status: object) -> str:
        if cls.is_suspended_value(status):
            return "계정이 정지되었습니다."
        if cls.is_withdrawn_value(status):
            return "탈퇴한 계정입니다."
        return "계정이 비활성 상태입니다."
