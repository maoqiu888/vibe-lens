from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from app import database
from app.deps import get_current_user_id
from app.models.user import User
from app.models.user_personality import UserPersonality
from app.schemas.personality import PersonalityRequest, PersonalityResponse
from app.services import llm_personality_agent, profile_calc

router = APIRouter(prefix="/api/v1/personality", tags=["personality"])

PERSONALITY_SEED_ACTION = "personality_seed"


def _ensure_user_and_check_existing(user_id: int) -> bool:
    """Lazy-create the user row and report whether a personality row exists."""
    db = database.SessionLocal()
    try:
        user = db.scalar(select(User).where(User.id == user_id))
        if user is None:
            db.add(User(id=user_id, username="default", interaction_count=0))
            db.flush()
        existing = db.scalar(
            select(UserPersonality).where(UserPersonality.user_id == user_id)
        )
        db.commit()
        return existing is not None
    finally:
        db.close()


def _persist_personality_row(
    user_id: int,
    mbti: str | None,
    constellation: str | None,
    summary: str | None,
) -> None:
    db = database.SessionLocal()
    try:
        db.add(UserPersonality(
            user_id=user_id,
            mbti=mbti,
            constellation=constellation,
            summary=summary,
        ))
        db.commit()
    finally:
        db.close()


@router.post("/submit", response_model=PersonalityResponse)
async def submit(
    payload: PersonalityRequest,
    user_id: int = Depends(get_current_user_id),
):
    # Lazy-create user, check existing personality
    already_submitted = _ensure_user_and_check_existing(user_id)
    if already_submitted:
        raise HTTPException(
            status_code=400,
            detail={"error": {
                "code": "ALREADY_SUBMITTED",
                "message": "personality profile already submitted; cannot resubmit in V1.3",
            }},
        )

    # Short-circuit: both fields empty → write null row, return "skipped"
    if payload.mbti is None and payload.constellation is None:
        _persist_personality_row(user_id, None, None, None)
        return PersonalityResponse(
            status="skipped",
            seeded_tag_count=0,
            summary="",
        )

    # Call the agent — on PersonalityAgentEmptyError (shouldn't happen here
    # since we've already checked both-empty) fall through to skipped
    try:
        result = await llm_personality_agent.analyze_personality(
            mbti=payload.mbti,
            constellation=payload.constellation,
        )
    except llm_personality_agent.PersonalityAgentEmptyError:
        _persist_personality_row(user_id, payload.mbti, payload.constellation, None)
        return PersonalityResponse(
            status="skipped",
            seeded_tag_count=0,
            summary="",
        )

    tag_seeds = result["tag_seeds"]
    summary = result["personality_summary"]

    # Apply tag seeds (lazy-creates UserVibeRelation via existing _apply_delta)
    for seed in tag_seeds:
        profile_calc.apply_core_delta(
            user_id=user_id,
            tag_ids=[seed["tag_id"]],
            delta=seed["weight"],
            action=PERSONALITY_SEED_ACTION,
        )

    # Persist personality row AFTER seeds are written
    _persist_personality_row(
        user_id,
        payload.mbti,
        payload.constellation,
        summary if summary else None,
    )

    return PersonalityResponse(
        status="ok",
        seeded_tag_count=len(tag_seeds),
        summary=summary,
    )
