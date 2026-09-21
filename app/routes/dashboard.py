from fastapi import APIRouter, Depends, Query

from app.core.auth.deps import get_current_user
from app.core.DA.dashboard import DashboardService
from app.db.firebase import get_db
from app.models.enums import ClassEnum
from app.models.user import UserResponse

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/summary")
def dashboard_summary(
    class_name: ClassEnum | None = None,
    streak_n: int = Query(default=4, ge=1, le=52),
    absent_n: int = Query(default=4, ge=0, le=52),
    db=Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    """Whole-dashboard analytics in one response.

    Admin: all classes or one via class_name. Amin: own class only.
    streak_n: consecutive presences threshold (default 4).
    absent_n: frequent-absence threshold, absent count > absent_n (default 4).
    """
    return DashboardService(db, current_user).summary(class_name, streak_n, absent_n)


@router.get("/boys/{boy_id}")
def dashboard_boy(
    boy_id: str,
    db=Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    """Boy drill-down: details + full attendance history + rate + notes.

    Admin: any. Amin: own class only."""
    return DashboardService(db, current_user).boy_profile(boy_id)
