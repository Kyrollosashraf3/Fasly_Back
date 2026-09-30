"""
API schemas, one module per domain.

Import anything from ``app.schemas`` directly - the shared models are
re-exported here so consumers stay decoupled from the file layout.

The ORM classes live in ``app.models``; every ``*Response`` schema carries
``from_attributes`` so the services can return SQLAlchemy rows directly.
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
from app.schemas.group import GroupAssign, GroupUnassign
from app.schemas.teacher import TeacherCreate, TeacherResponse, TeacherUpdate
from app.schemas.teacher_check import (
    TeacherCheckBulkCreate,
    TeacherCheckCreate,
    TeacherCheckItem,
    TeacherCheckResponse,
    TeacherCheckUpdate,
)
from app.schemas.user import Token, UserCreate, UserInDB, UserResponse, UserUpdate

__all__ = [
    "ORMResponse",
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
    "UserCreate",
    "UserUpdate",
    "UserResponse",
    "UserInDB",
    "Token",
]
