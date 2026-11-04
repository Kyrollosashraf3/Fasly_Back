"""
API schemas, one module per domain.

Import anything from ``app.schemas`` directly - the shared models are
re-exported here so consumers stay decoupled from the file layout.

The ORM classes live in ``app.models``; every ``*Response`` schema carries
``from_attributes`` so the services can return SQLAlchemy rows directly.

Conventions
-----------
``*Create``  -> POST body; ids, timestamps and historical ``class_id``
                snapshots are stamped by the service, never by the client.
``*Update``  -> PATCH body; every field optional (``exclude_unset``).
``*Response``-> the row that leaves the server; never carries a credential.
                Fields named after an ORM property (``age``,
                ``display_name``) are filled in automatically.
"""

from app.schemas.attend import (
    AttendBulkCreate,
    AttendCreate,
    AttendItem,
    AttendResponse,
    AttendUpdate,
)
from app.schemas.base import ORMResponse
from app.schemas.boy import BoyCreate, BoyResponse, BoyUpdate
from app.schemas.follow_up import FollowUpCreate, FollowUpResponse, FollowUpUpdate
from app.schemas.group import GroupAssign, GroupResponse, GroupUnassign
from app.schemas.school_class import (
    CLASS_NAMES,
    SchoolClassCreate,
    SchoolClassResponse,
    SchoolClassUpdate,
)
from app.schemas.subscription import (
    BoyTripSummary,
    BoyTripTotal,
    SubscriptionCreate,
    SubscriptionResponse,
    SubscriptionUpdate,
)
from app.schemas.teacher import TeacherCreate, TeacherResponse, TeacherUpdate
from app.schemas.teacher_check import (
    TeacherCheckBulkCreate,
    TeacherCheckCreate,
    TeacherCheckItem,
    TeacherCheckResponse,
    TeacherCheckUpdate,
)
from app.schemas.user import (
    ManagedClassesUpdate,
    SignupCheckRequest,
    SignupCheckResponse,
    SignupRequest,
    Token,
    UserCreate,
    UserImportRow,
    UserInDB,
    UserResponse,
    UserUpdate,
)

__all__ = [
    "ORMResponse",
    "CLASS_NAMES",
    "SchoolClassCreate",
    "SchoolClassUpdate",
    "SchoolClassResponse",
    "BoyCreate",
    "BoyUpdate",
    "BoyResponse",
    "AttendCreate",
    "AttendUpdate",
    "AttendResponse",
    "AttendItem",
    "AttendBulkCreate",
    "TeacherCreate",
    "TeacherUpdate",
    "TeacherResponse",
    "TeacherCheckCreate",
    "TeacherCheckUpdate",
    "TeacherCheckResponse",
    "TeacherCheckItem",
    "TeacherCheckBulkCreate",
    "FollowUpCreate",
    "FollowUpUpdate",
    "FollowUpResponse",
    "GroupAssign",
    "GroupUnassign",
    "GroupResponse",
    "SubscriptionCreate",
    "SubscriptionUpdate",
    "SubscriptionResponse",
    "BoyTripSummary",
    "BoyTripTotal",
    "UserCreate",
    "ManagedClassesUpdate",
    "UserImportRow",
    "UserUpdate",
    "UserResponse",
    "UserInDB",
    "Token",
    "SignupCheckRequest",
    "SignupCheckResponse",
    "SignupRequest",
]
