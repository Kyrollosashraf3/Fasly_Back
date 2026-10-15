"""Dashboard analytics - one summary, one boy drill-down. Read-only."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.auth.deps import get_current_user
from app.core.DA.dashboard import DashboardService
from app.core.DA.follow_up_performance import FollowUpPerformanceService
from app.db.database import get_db
from app.models.user import User

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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Attendance, streaks, absences, servant scores, follow-up coverage and
    late confessions - all already scoped to the classes this login may see."""
    return DashboardService(db, current_user).summary(
        class_id=class_id,
        streak_n=streak_n,
        absent_n=absent_n,
        top_n=top_n,
        trend_n=trend_n,
        teacher_trend_n=teacher_trend_n,
        period_days=period_days,
        date_mode=date_mode,
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
    class_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upcoming birthdays for boys and/or servants (a servant only sees boys)."""
    return DashboardService(db, current_user).birthdays(
        kind=kind, window=window, class_id=class_id
    )


@router.get("/boys/{boy_id}")
def dashboard_boy(
    boy_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """One boy: master data, every Friday, season table and follow-up log."""
    return DashboardService(db, current_user).boy_profile(boy_id)