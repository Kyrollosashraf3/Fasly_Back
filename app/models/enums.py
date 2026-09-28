from enum import Enum


class RoleEnum(str, Enum):
    """Account role: admin sees all classes, user (amin) sees his class only."""

    ADMIN = "admin"
    USER = "user"

ROLE_ENUM_NAME = "role_enum"

###########################

class AttendEnum(str, Enum):
    """Attendance / check-in flag: y = present, n = absent."""

    YES = "y"
    NO = "n"

ATTEND_ENUM_NAME = "attend_enum"

###########################


class GenderEnum(str, Enum):
    """Gender of a boy."""

    MALE = "m"
    FEMALE = "f"

GENDER_ENUM_NAME = "gender_enum"

###########################


class ClassEnum(str, Enum):
    """Sunday school class (grade) 1..6."""

    FIRST = "1"
    SECOND = "2"
    THIRD = "3"
    FOURTH = "4"
    FIFTH = "5"
    SIXTH = "6"

CLASS_ENUM_NAME = "class_enum"


###########################

class FollowEnum(str, Enum):
    """Result of a teacher's weekly phone follow-up call to a boy."""

    CALL = "call"
    VISIT = "visit"
    WHATSAPP = "whatsapp"
    NO_ANSWER = "no answer"
    OTHER = "other"

FOLLOW_ENUM_NAME = "follow_enum"
