"""Lazy exports for ORM models now housed in feature packages."""

from importlib import import_module

_MODEL_MODULES = {
    "Attend": "app.features.attendance.models.attend",
    "Boy": "app.features.boy.models.boy",
    "Church": "app.features.church.models.church",
    "FollowUp": "app.features.follow_up.models.follow_up",
    "GeneralAdminClass": "app.features.school_class.models.general_admin_class",
    "Group": "app.features.group.models.group",
    "NotificationInbox": "app.features.notification.models.notification_inbox",
    "NotificationLog": "app.features.notification.models.notification_log",
    "PushDevice": "app.features.notification.models.push_device",
    "SchoolClass": "app.features.school_class.models.school_class",
    "Subscription": "app.features.subscription.models.subscription",
    "Team": "app.features.team.models.team",
    "TeamMember": "app.features.team.models.team_member",
    "TeamTeacher": "app.features.team.models.team_teacher",
    "Task": "app.features.task.models.task",
    "TaskValue": "app.features.task_value.models.task_value",
    "Teacher": "app.features.teacher.models.teacher",
    "TeacherCheck": "app.features.teacher_check.models.teacher_check",
    "TeacherFollowUp": "app.features.teacher_follow_up.models.teacher_follow_up",
    "Trip": "app.features.trip.models.trip",
    "TripAttendance": "app.features.trip_attendance.models.trip_attendance",
    "User": "app.features.user.models.user",
}


def __getattr__(name: str):
    module_name = _MODEL_MODULES.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(module_name), name)
    globals()[name] = value
    return value


__all__ = list(_MODEL_MODULES)
