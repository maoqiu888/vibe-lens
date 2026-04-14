from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.deps import get_current_user_id, get_db
from app.schemas.action import ActionRequest, ActionResponse
from app.schemas.analyze import AnalyzeRequest, AnalyzeResponse, MatchedTag
from app.services import llm_tagger, profile_calc

router = APIRouter(prefix="/api/v1/vibe", tags=["vibe"])

CURIOSITY_DELTA = 0.5
STAR_DELTA = 10.0
BOMB_DELTA = -10.0


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(
    payload: AnalyzeRequest,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    try:
        result = await llm_tagger.analyze(payload.text, payload.domain)
    except llm_tagger.LlmParseError as e:
        raise HTTPException(
            status_code=503,
            detail={"error": {"code": "LLM_PARSE_FAIL", "message": str(e)}},
        )
    except llm_tagger.LlmTimeoutError as e:
        raise HTTPException(
            status_code=503,
            detail={"error": {"code": "LLM_TIMEOUT", "message": str(e)}},
        )

    matched_tag_ids = [t["tag_id"] for t in result["matched_tags"]]
    item_tags = [(t["tag_id"], t["weight"]) for t in result["matched_tags"]]

    score = profile_calc.compute_match_score(user_id=user_id, item_tags=item_tags)
    profile_calc.apply_curiosity_delta(
        user_id=user_id,
        tag_ids=matched_tag_ids,
        delta=CURIOSITY_DELTA,
        action="analyze",
    )

    return AnalyzeResponse(
        match_score=score,
        summary=result["summary"],
        matched_tags=[MatchedTag(**t) for t in result["matched_tags"]],
        text_hash=result["text_hash"],
        cache_hit=result["cache_hit"],
    )


@router.post("/action", response_model=ActionResponse)
def action(
    payload: ActionRequest,
    user_id: int = Depends(get_current_user_id),
):
    delta = STAR_DELTA if payload.action == "star" else BOMB_DELTA
    profile_calc.apply_core_delta(
        user_id=user_id,
        tag_ids=payload.matched_tag_ids,
        delta=delta,
        action=payload.action,
    )
    return ActionResponse(status="ok", updated_tags=len(payload.matched_tag_ids))
