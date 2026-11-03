"""Dashboard analytics - one summary, one boy drill-down. Read-only."""

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.auth.deps import get_current_user
from app.core.DA.dashboard import DashboardService
from app.core.DA.follow_up_performance import FollowUpPerformanceService
from app.db.database import get_db
from app.models.enums import GenderEnum
from app.models.user import User
from app.routes.sheets import xlsx_response

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/summary")
def dashboard_summary(
    class_id: int | None = None,
    streak_n: int = Query(default=4, ge=1, le=52),
    absent_n: int = Query(default=4, ge=0, le=52),
    top_n: int = Query(default=5, ge=1, le=50),
    trend_n: int = Query(default=8, ge=1, le=52),
    teacher_trend_n: int = Query(default=8, ge=1, le=52),
    period_days: int = Query(default=30, ge=1, le=365),
    date_mode: str = Query(default="all", pattern="^(all|last_friday|season)$"),
    streak_from: date | None = Query(default=None),
    streak_to: date | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Attendance, streaks, absences, servant scores, follow-up coverage and
    late confessions - all already scoped to the classes this login may see.

    ``streak_from`` / ``streak_to`` measure the "المواظبون على الحضور" list over
    that Friday range instead of the trailing streak, independent of
    ``date_mode``."""
    return DashboardService(db, current_user).summary(
        class_id=class_id,
        streak_n=streak_n,
        absent_n=absent_n,
        top_n=top_n,
        trend_n=trend_n,
        teacher_trend_n=teacher_trend_n,
        period_days=period_days,
        date_mode=date_mode,
        streak_from=streak_from,
        streak_to=streak_to,
    )


@router.get("/my-performance")
def dashboard_my_performance(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """The home screen's own numbers.

    A servant is measured on his group and his reviews, a class amin on his
    whole class, the general amin on every class. Both windows come back at
    once: the last 7 days and the church year so far.
    """
    return DashboardService(db, current_user).my_performance()


@router.get("/today-check/tasks")
def dashboard_today_check_tasks(
    class_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return DashboardService(db, current_user).today_check_tasks(class_id=class_id)


@router.get("/today-check")
def dashboard_today_check(
    class_id: int,
    task_id: int,
    status: str = Query(default="all", pattern="^(all|complete|incomplete)$"),
    gender: GenderEnum = Query(default=GenderEnum.MALE),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return DashboardService(db, current_user).today_check(
        class_id=class_id, task_id=task_id, status=status, gender=gender
    )


@router.get("/today-check/export")
def dashboard_today_check_export(
    class_id: int,
    task_id: int,
    status: str = Query(default="all", pattern="^(all|complete|incomplete)$"),
    gender: GenderEnum = Query(default=GenderEnum.MALE),
    search: str = "",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.core.EDA.write_today_check import build_today_check_workbook

    sheet = DashboardService(db, current_user).today_check(
        class_id=class_id, task_id=task_id, status=status, gender=gender, search=search
    )
    return xlsx_response(build_today_check_workbook(sheet), "today-check.xlsx")


@router.get("/teachers/export")
def dashboard_teachers_export(
    class_id: int | None = None,
    date_mode: str = Query(default="all", pattern="^(all|last_friday|season)$"),
    metric: str = Query(
        default="all",
        pattern="^(attend|liturgy|follow|prepare|teachers_meeting|all)$",
    ),
    order: str = Query(default="desc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """The "تفاصيل الخدام" table as a simple sheet - same rows, same order."""
    # lazy: openpyxl only loads when someone asks for a file
    from app.core.EDA.write_servants import build_servants_workbook

    summary = DashboardService(db, current_user).summary(
        class_id=class_id, date_mode=date_mode
    )
    return xlsx_response(
        build_servants_workbook(
            summary["servants"], summary["scope"], metric=metric, order=order
        ),
        "servants-details.xlsx",
    )


@router.get("/follow-up")
def dashboard_follow_up(
    class_id: int | None = None,
    period: str = Query(default="month", pattern="^(week|month|season|all)$"),
    teacher_id: int | None = None,
    boy_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Follow-up performance: coverage %, reached vs pending boys, a servant
    breakdown (who logged and who did not) and a ranked boy list - all scoped
    to the login and the chosen period."""
    return FollowUpPerformanceService(db, current_user).performance(
        class_id=class_id, period=period, teacher_id=teacher_id, boy_id=boy_id
    )


@router.get("/birthdays")
def dashboard_birthdays(
    kind: str = Query(default="boys", pattern="^(boys|teachers|all)$"),
    window: str = Query(default="twoweeks", pattern="^(twoweeks|month)$"),
    month: int | None = Query(default=None, ge=1, le=12),
    class_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upcoming birthdays for boys and/or servants (a servant only sees boys).

    `month` overrides the quick `window` when set."""
    return DashboardService(db, current_user).birthdays(
        kind=kind, window=window, class_id=class_id, month=month
    )


@router.get("/boys/{boy_id}")
def dashboard_boy(
    boy_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """One boy: master data, every Friday, season table and follow-up log."""
    return DashboardService(db, current_user).boy_profile(boy_id)