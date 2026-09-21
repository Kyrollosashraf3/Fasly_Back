"""models package - Pydantic schemas for Firestore documents."""

from .attend import AttendBulkCreate, AttendCreate, AttendItem, AttendResponse, AttendUpdate
from .boy import BoyCreate, BoyResponse, BoyUpdate
from .enums import AttendEnum, ClassEnum, FollowEnum, GenderEnum, RoleEnum
from .follow_up import FollowUpCreate, FollowUpResponse, FollowUpUpdate
from .group import GroupAssign, GroupUnassign
from .teacher import TeacherCreate, TeacherResponse, TeacherUpdate
from .teacher_check import (
    TeacherCheckBulkCreate,
    TeacherCheckCreate,
    TeacherCheckItem,
    TeacherCheckResponse,
    TeacherCheckUpdate,
)
from .user import Token, UserCreate, UserInDB, UserResponse, UserUpdate

__all__ = [
    "AttendEnum",
    "FollowEnum",
    "ClassEnum",
    "GenderEnum",
    "RoleEnum",
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
