from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.auth.deps import get_current_user
from app.core.DA.dashboard import DashboardService
from app.db.database import get_db
from app.schemas.user import UserResponse

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/summary")
def dashboard_summary(
    class_id: int | None = None,
    streak_n: int = Query(default=4, ge=1, le=52),
    absent_n: int = Query(default=4, ge=0, le=52),
    top_n: int = Query(default=5, ge=1, le=50),
    trend_n: int = Query(default=8, ge=1, le=52),
    teacher_trend_n: int = Query(default=8, ge=1, le=52),
    db: Session = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    return DashboardService(db, current_user).summary(
        class_id=class_id,
        streak_n=streak_n,
        absent_n=absent_n,
        top_n=top_n,
        trend_n=trend_n,
        teacher_trend_n=teacher_trend_n,
    )


@router.get("/boys/{boy_id}")
def dashboard_boy(
    boy_id: int,
    db: Session = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    return DashboardService(db, current_user).boy_profile(boy_id)
