from enum import Enum


class RoleEnum(str, Enum):
    """What an account is allowed to see.

    USER        -> a boy in the service: his own data only.
    TEACHER     -> a servant: his own follow-ups and performance only - and he can add new boy or edit boys of his class - take attend for class.
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


class FatherEnum(str, Enum):
    """ابونا الاعتراف الخاص بالولد (optional)."""
    KIERLOS = "ابونا كيرلس روماني"
    ARSANIOUS = "ابونا ارسانيوس عزت"
    FAMES = "ابونا فام عبدالمسيح"

FATHER_ENUM_NAME = "father_enum"


class SkillEnum(str, Enum):
    """مهارات الولد - predefined skills + 'أخرى'."""
    ACTING = "تمثيل"
    DRAWING = "رسم"
    COLORING = "تلوين"
    PLAYING = "عزف"
    DECOR = "ديكور"
    PROGRAMMING = "برمجة"
    GRAPHIC_DESIGN = "تصميم جرافيك"
    EXCEL = "اكسيل"
    COMPUTER = "كمبيوتر"
    COMPOSITION = "تأليف"
    OTHER = "أخرى"

SKILL_ENUM_NAME = "skill_enum"
