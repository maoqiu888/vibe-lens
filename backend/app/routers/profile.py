from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.deps import get_current_user_id, get_db
from app.models.action_log import ActionLog
from app.models.user import User
from app.schemas.profile import RadarResponse
from app.services import profile_calc

router = APIRouter(prefix="/api/v1/profile", tags=["profile"])


_EMPTY_DIMENSIONS = [
    {"category": c, "category_label": label, "score": 0.0,
     "dominant_tag": {"tag_id": 0, "name": "—"}}
    for c, label in [
        ("pace", "节奏"), ("mood", "情绪色调"), ("cognition", "智力负载"),
        ("narrative", "叙事质感"), ("world", "世界感"), ("intensity", "情感浓度"),
    ]
]


@router.get("/radar", response_model=RadarResponse)
def radar(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    user = db.scalar(select(User).where(User.id == user_id))
    interaction_count = user.interaction_count if user else 0

    info = profile_calc.level_info(interaction_count)
    ui_stage = profile_calc.compute_ui_stage(info["level"])

    # For zero-interaction users (welcome state), we return an empty radar
    # structure instead of calling compute_radar (which would KeyError on
    # the missing tag categories for a brand-new user). The frontend shows
    # the welcome page when interaction_count == 0 and never reads dimensions.
    if interaction_count == 0:
        dimensions = _EMPTY_DIMENSIONS
    else:
        data = profile_calc.compute_radar(user_id=user_id)
        dimensions = data["dimensions"]

    # Count distinct call events (not per-tag rows). ActionLog has one row
    # per matched tag, so each analyze/star call produces multiple rows all
    # sharing near-identical created_at timestamps. Group by second-truncated
    # timestamp to recover the true call count.
    total_analyze = db.scalar(
        select(func.count(func.distinct(func.strftime("%Y-%m-%d %H:%M:%S", ActionLog.created_at)))).where(
            ActionLog.user_id == user_id,
            ActionLog.action == "analyze",
        )
    ) or 0
    total_action = db.scalar(
        select(func.count(func.distinct(func.strftime("%Y-%m-%d %H:%M:%S", ActionLog.created_at)))).where(
            ActionLog.user_id == user_id,
            ActionLog.action.in_(["star", "bomb"]),
        )
    ) or 0

    return RadarResponse(
        user_id=user_id,
        interaction_count=interaction_count,
        level=info["level"],
        level_title=info["title"],
        level_emoji=info["emoji"],
        next_level_at=info["next_level_at"],
        ui_stage=ui_stage,
        dimensions=dimensions,
        total_analyze_count=total_analyze,
        total_action_count=total_action,
    )
