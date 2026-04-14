import random

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import get_current_user_id, get_db
from app.models.action_log import ActionLog
from app.models.user_vibe_relation import UserVibeRelation
from app.models.vibe_tag import VibeTag
from app.schemas.cold_start import (
    CardOption,
    CategoryCard,
    ColdStartCardsResponse,
    ColdStartSubmitRequest,
    ColdStartSubmitResponse,
)
from app.services.seed_data import CARD_META, CATEGORY_LABELS

router = APIRouter(prefix="/api/v1/cold-start", tags=["cold-start"])

CATEGORY_ORDER = ["pace", "mood", "cognition", "narrative", "world", "intensity"]
COLD_START_DELTA = 15.0


@router.get("/cards", response_model=ColdStartCardsResponse)
def get_cards(db: Session = Depends(get_db)):
    cards: list[CategoryCard] = []
    for cat in CATEGORY_ORDER:
        tags = db.scalars(
            select(VibeTag).where(VibeTag.category == cat).order_by(VibeTag.tier)
        ).all()
        middle_choice = random.choice([t for t in tags if t.tier in (2, 3)])
        chosen = [t for t in tags if t.tier in (1, 4)] + [middle_choice]
        chosen.sort(key=lambda t: t.tier)
        options = [
            CardOption(
                tag_id=t.id,
                name=t.name,
                tier=t.tier,
                tagline=CARD_META[t.id]["tagline"],
                examples=CARD_META[t.id]["examples"],
            )
            for t in chosen
        ]
        cards.append(CategoryCard(
            category=cat,
            category_label=CATEGORY_LABELS[cat],
            options=options,
        ))
    return ColdStartCardsResponse(cards=cards)


@router.post("/submit", response_model=ColdStartSubmitResponse)
def submit(
    payload: ColdStartSubmitRequest,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    # Already initialized? short-circuit
    existing = db.scalar(
        select(UserVibeRelation).where(UserVibeRelation.user_id == user_id)
    )
    if existing is not None:
        return ColdStartSubmitResponse(
            status="ok",
            profile_initialized=True,
            already_initialized=True,
        )

    selected = db.scalars(
        select(VibeTag).where(VibeTag.id.in_(payload.selected_tag_ids))
    ).all()
    if len(selected) != 6 or {t.category for t in selected} != set(CATEGORY_ORDER):
        raise HTTPException(
            status_code=400,
            detail={"error": {
                "code": "COLD_START_INVALID_SELECTION",
                "message": "must select exactly one tag from each of the 6 categories",
            }},
        )

    # Initialize 24 rows, 6 of them with core_weight = +15
    all_tags = db.scalars(select(VibeTag)).all()
    selected_ids = set(payload.selected_tag_ids)
    for t in all_tags:
        db.add(UserVibeRelation(
            user_id=user_id,
            vibe_tag_id=t.id,
            curiosity_weight=0.0,
            core_weight=COLD_START_DELTA if t.id in selected_ids else 0.0,
        ))
    for tid in selected_ids:
        db.add(ActionLog(
            user_id=user_id,
            vibe_tag_id=tid,
            action="cold_start",
            delta=COLD_START_DELTA,
            target_column="core",
        ))
    db.commit()

    return ColdStartSubmitResponse(status="ok", profile_initialized=True)
