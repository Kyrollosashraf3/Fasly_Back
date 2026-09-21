from enum import Enum


class RoleEnum(str, Enum):
    ADMIN = "admin"
    USER = "user"


class AttendEnum(str, Enum):
    YES = "y"
    NO = "n"


class GenderEnum(str, Enum):
    MALE = "m"
    FEMALE = "f"


class ClassEnum(str, Enum):
    FIRST = "1"
    SECOND = "2"
    THIRD = "3"
    FOURTH = "4"
    FIFTH = "5"
    SIXTH = "6"


class FollowEnum(str, Enum):
    """Result of a teacher's weekly phone follow-up call to a boy."""

    CALL = "call"
    VISIT = "visit"
    WHATSAPP = "whatsapp"
    NO_ANSWER = "no answer"
    OTHER = "other"
