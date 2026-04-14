from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import get_current_user_id, get_db
from app.models.vibe_tag import VibeTag
from app.schemas.action import ActionRequest, ActionResponse
from app.schemas.analyze import AnalyzeRequest, AnalyzeResponse, MatchedTag
from app.schemas.recommend import RecommendRequest, RecommendResponse
from app.services import llm_recommender, llm_roaster, llm_tagger, profile_calc

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
    matched_tag_names = [t["name"] for t in result["matched_tags"]]
    item_tags = [(t["tag_id"], t["weight"]) for t in result["matched_tags"]]

    score = profile_calc.compute_match_score(user_id=user_id, item_tags=item_tags)

    user_top_tag_names = profile_calc.get_top_core_tag_names(user_id=user_id, n=3)
    roast = await llm_roaster.generate_roast(
        text=payload.text,
        domain=payload.domain,
        item_tag_names=matched_tag_names,
        user_top_tag_names=user_top_tag_names,
    )

    profile_calc.apply_curiosity_delta(
        user_id=user_id,
        tag_ids=matched_tag_ids,
        delta=CURIOSITY_DELTA,
        action="analyze",
    )

    return AnalyzeResponse(
        match_score=score,
        summary=result["summary"],
        roast=roast,
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


@router.post("/recommend", response_model=RecommendResponse)
async def recommend(
    payload: RecommendRequest,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    # 1. Resolve tag_ids → tag names, fail if any id is out of range
    tags = db.scalars(
        select(VibeTag).where(VibeTag.id.in_(payload.matched_tag_ids))
    ).all()
    if len(tags) != len(set(payload.matched_tag_ids)):
        raise HTTPException(
            status_code=400,
            detail={"error": {
                "code": "INVALID_TAG_IDS",
                "message": "one or more tag_ids are not in the 1-24 pool",
            }},
        )
    item_tag_names = [t.name for t in tags]

    # 2. User's top-3 core_weight tags for prompt context
    user_top_tag_names = profile_calc.get_top_core_tag_names(user_id=user_id, n=3)

    # 3. LLM call with cross-domain filtering
    try:
        items = await llm_recommender.recommend(
            text=payload.text,
            source_domain=payload.source_domain,
            item_tag_names=item_tag_names,
            user_top_tag_names=user_top_tag_names,
        )
    except llm_recommender.LlmParseError as e:
        raise HTTPException(
            status_code=503,
            detail={"error": {"code": "LLM_PARSE_FAIL", "message": str(e)}},
        )
    except llm_recommender.LlmTimeoutError as e:
        raise HTTPException(
            status_code=503,
            detail={"error": {"code": "LLM_TIMEOUT", "message": str(e)}},
        )
    except llm_recommender.RecommendEmptyError as e:
        raise HTTPException(
            status_code=503,
            detail={"error": {"code": "NO_CROSS_DOMAIN", "message": str(e)}},
        )

    return RecommendResponse(items=items)
