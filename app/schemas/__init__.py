"""Lazy exports for API schemas now housed in feature packages."""

from importlib import import_module

_SCHEMA_MODULES = {
    "ORMResponse": "app.schemas.base",
    "AttendBulkCreate": "app.features.attendance.schemas.attend",
    "AttendCreate": "app.features.attendance.schemas.attend",
    "AttendItem": "app.features.attendance.schemas.attend",
    "AttendResponse": "app.features.attendance.schemas.attend",
    "AttendUpdate": "app.features.attendance.schemas.attend",
    "BoyCreate": "app.features.boy.schemas.boy",
    "BoyResponse": "app.features.boy.schemas.boy",
    "BoyUpdate": "app.features.boy.schemas.boy",
    "ChurchCreate": "app.features.church.schemas.church",
    "ChurchResponse": "app.features.church.schemas.church",
    "ChurchUpdate": "app.features.church.schemas.church",
    "FollowUpCreate": "app.features.follow_up.schemas.follow_up",
    "FollowUpResponse": "app.features.follow_up.schemas.follow_up",
    "FollowUpUpdate": "app.features.follow_up.schemas.follow_up",
    "GroupAssign": "app.features.group.schemas.group",
    "GroupResponse": "app.features.group.schemas.group",
    "GroupUnassign": "app.features.group.schemas.group",
    "FOLLOW_UP_STATUS_OPTIONS": "app.features.location.schemas.location",
    "BoyLocationResponse": "app.features.location.schemas.location",
    "FollowUpPrefill": "app.features.location.schemas.location",
    "LocationRecord": "app.features.location.schemas.location",
    "MapHouse": "app.features.location.schemas.location",
    "MapLeg": "app.features.location.schemas.location",
    "MapOrigin": "app.features.location.schemas.location",
    "MapRouteResponse": "app.features.location.schemas.location",
    "MapScopeEnum": "app.features.location.schemas.location",
    "MapSummary": "app.features.location.schemas.location",
    "CLASS_NAMES": "app.features.school_class.schemas.school_class",
    "SchoolClassCreate": "app.features.school_class.schemas.school_class",
    "SchoolClassResponse": "app.features.school_class.schemas.school_class",
    "SchoolClassUpdate": "app.features.school_class.schemas.school_class",
    "BoyTripSummary": "app.features.subscription.schemas.subscription",
    "BoyTripTotal": "app.features.subscription.schemas.subscription",
    "SubscriptionCreate": "app.features.subscription.schemas.subscription",
    "SubscriptionResponse": "app.features.subscription.schemas.subscription",
    "SubscriptionUpdate": "app.features.subscription.schemas.subscription",
    "TeacherCreate": "app.features.teacher.schemas.teacher",
    "TeacherResponse": "app.features.teacher.schemas.teacher",
    "TeacherUpdate": "app.features.teacher.schemas.teacher",
    "TripAttendanceAssign": "app.features.trip_attendance.schemas.trip_attendance",
    "TripAttendanceBulkCreate": "app.features.trip_attendance.schemas.trip_attendance",
    "TripAttendanceItem": "app.features.trip_attendance.schemas.trip_attendance",
    "TripAttendanceResponse": "app.features.trip_attendance.schemas.trip_attendance",
    "TripAttendanceUnassign": "app.features.trip_attendance.schemas.trip_attendance",
    "TripAttendanceUpdate": "app.features.trip_attendance.schemas.trip_attendance",
    "TripSheetResponse": "app.features.trip_attendance.schemas.trip_attendance",
    "TripSheetRow": "app.features.trip_attendance.schemas.trip_attendance",
    "TeacherCheckBulkCreate": "app.features.teacher_check.schemas.teacher_check",
    "TeacherCheckCreate": "app.features.teacher_check.schemas.teacher_check",
    "TeacherCheckItem": "app.features.teacher_check.schemas.teacher_check",
    "TeacherCheckResponse": "app.features.teacher_check.schemas.teacher_check",
    "TeacherCheckUpdate": "app.features.teacher_check.schemas.teacher_check",
    "ManagedClassesUpdate": "app.features.user.schemas.user",
    "SignupCheckRequest": "app.features.user.schemas.user",
    "SignupCheckResponse": "app.features.user.schemas.user",
    "SignupRequest": "app.features.user.schemas.user",
    "Token": "app.features.user.schemas.user",
    "UserCreate": "app.features.user.schemas.user",
    "UserImportRow": "app.features.user.schemas.user",
    "UserInDB": "app.features.user.schemas.user",
    "UserResponse": "app.features.user.schemas.user",
    "UserUpdate": "app.features.user.schemas.user",
}


def __getattr__(name: str):
    module_name = _SCHEMA_MODULES.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(module_name), name)
    globals()[name] = value
    return value


__all__ = list(_SCHEMA_MODULES)
