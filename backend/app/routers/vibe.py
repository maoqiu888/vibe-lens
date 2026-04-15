from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import get_current_user_id, get_db
from app.models.user import User
from app.models.vibe_tag import VibeTag
from app.schemas.action import ActionRequest, ActionResponse
from app.schemas.analyze import AnalyzeRequest, AnalyzeResponse, MatchedTag
from app.schemas.recommend import RecommendRequest, RecommendResponse
from app.services import llm_recommender, llm_roaster, llm_tagger, profile_calc

router = APIRouter(prefix="/api/v1/vibe", tags=["vibe"])

FIRST_IMPRESSION_DELTA = 10.0


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(
    payload: AnalyzeRequest,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    # 1. Tagger (cache-aware)
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

    # 2. Detect first-interaction BEFORE incrementing the counter
    user = db.scalar(select(User).where(User.id == user_id))
    is_first = (user is None) or (user.interaction_count == 0)

    # 3. Match score (may be 0 for first-time on empty vector — frontend hides it)
    score = profile_calc.compute_match_score(user_id=user_id, item_tags=item_tags)

    # 4. Roast (unchanged from V1.1)
    user_top_tag_names = profile_calc.get_top_core_tag_names(user_id=user_id, n=3)
    roast = await llm_roaster.generate_roast(
        text=payload.text,
        domain=payload.domain,
        item_tag_names=matched_tag_names,
        user_top_tag_names=user_top_tag_names,
    )

    # 5. Apply profile update — first-interaction gets strong core signal,
    #    subsequent calls get dynamic curiosity scaled by hesitation_ms.
    if is_first:
        profile_calc.apply_core_delta(
            user_id=user_id,
            tag_ids=matched_tag_ids,
            delta=FIRST_IMPRESSION_DELTA,
            action="first_impression",
        )
    else:
        curiosity_delta = profile_calc.dynamic_curiosity_delta(payload.hesitation_ms)
        profile_calc.apply_curiosity_delta(
            user_id=user_id,
            tag_ids=matched_tag_ids,
            delta=curiosity_delta,
            action="analyze",
        )

    # 6. Increment interaction counter AFTER profile update
    new_count, new_level, level_up = profile_calc.increment_interaction(user_id)
    info = profile_calc.level_info(new_count)
    ui_stage = profile_calc.compute_ui_stage(new_level)

    return AnalyzeResponse(
        match_score=score,
        summary=result["summary"],
        roast=roast,
        matched_tags=[MatchedTag(**t) for t in result["matched_tags"]],
        text_hash=result["text_hash"],
        cache_hit=result["cache_hit"],
        interaction_count=new_count,
        level=new_level,
        level_title=info["title"],
        level_emoji=info["emoji"],
        next_level_at=info["next_level_at"],
        level_up=level_up,
        ui_stage=ui_stage,
    )


@router.post("/action", response_model=ActionResponse)
def action(
    payload: ActionRequest,
    user_id: int = Depends(get_current_user_id),
):
    delta = profile_calc.dynamic_core_delta(payload.action, payload.read_ms)
    profile_calc.apply_core_delta(
        user_id=user_id,
        tag_ids=payload.matched_tag_ids,
        delta=delta,
        action=payload.action,
    )
    new_count, new_level, level_up = profile_calc.increment_interaction(user_id)
    info = profile_calc.level_info(new_count)
    return ActionResponse(
        status="ok",
        updated_tags=len(payload.matched_tag_ids),
        interaction_count=new_count,
        level=new_level,
        level_title=info["title"],
        level_emoji=info["emoji"],
        next_level_at=info["next_level_at"],
        level_up=level_up,
    )


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
