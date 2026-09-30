from enum import Enum


class RoleEnum(str, Enum):
    """What an account is allowed to see.

    USER        -> a boy in the service: his own data only.
    TEACHER     -> a servant: his own follow-ups and performance only.
    ADMIN       -> a class amin: the servants and boys of his class.
    SUPER_ADMIN -> church-wide amin: every class, servants and boys.
    """

    USER = "user"
    TEACHER = "teacher"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"

ROLE_ENUM_NAME = "role_enum"

###########################


class GenderEnum(str, Enum):
    """Gender of a boy."""

    MALE = "m"
    FEMALE = "f"

GENDER_ENUM_NAME = "gender_enum"

###########################


class FollowEnum(str, Enum):
    """Result of a servant's weekly follow-up contact with a boy."""

    CALL = "call"
    VISIT = "visit"
    WHATSAPP = "whatsapp"
    NO_ANSWER = "no_answer"
    OTHER = "other"

FOLLOW_ENUM_NAME = "follow_enum"
