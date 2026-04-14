from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.deps import get_current_user_id, get_db
from app.models.action_log import ActionLog
from app.schemas.profile import RadarResponse
from app.services import profile_calc

router = APIRouter(prefix="/api/v1/profile", tags=["profile"])


@router.get("/radar", response_model=RadarResponse)
def radar(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    data = profile_calc.compute_radar(user_id=user_id)
    total_analyze = db.scalar(
        select(func.count(ActionLog.id)).where(
            ActionLog.user_id == user_id,
            ActionLog.action == "analyze",
        )
    ) or 0
    total_action = db.scalar(
        select(func.count(ActionLog.id)).where(
            ActionLog.user_id == user_id,
            ActionLog.action.in_(["star", "bomb"]),
        )
    ) or 0
    return RadarResponse(
        user_id=user_id,
        dimensions=data["dimensions"],
        total_analyze_count=total_analyze,
        total_action_count=total_action,
    )
