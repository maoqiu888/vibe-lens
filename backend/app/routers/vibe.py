import json
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import get_current_user_id, get_db
from app.models.user import User
from app.models.user_personality import UserPersonality
from app.models.vibe_tag import VibeTag
from app.schemas.action import ActionRequest, ActionResponse
from app.schemas.analyze import AnalyzeRequest, AnalyzeResponse, MatchedTag
from app.schemas.recommend import RecommendRequest, RecommendResponse
from app.models.match_feedback import MatchFeedback
from app.services import llm_recommender, llm_identifier, llm_judge, profile_calc

router = APIRouter(prefix="/api/v1/vibe", tags=["vibe"])

FIRST_IMPRESSION_DELTA = 10.0


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(
    payload: AnalyzeRequest,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    # Step 1: Agent 1 — Identify (cached)
    page_title = payload.context.page_title if payload.context else None
    try:
        identification = await llm_identifier.identify(
            payload.text, payload.domain, page_title=page_title,
            exclude_items=payload.exclude_items or None,
        )
    except llm_identifier.LlmParseError as e:
        raise HTTPException(
            status_code=503,
            detail={"error": {"code": "LLM_PARSE_FAIL", "message": str(e)}},
        )
    except llm_identifier.LlmTimeoutError as e:
        raise HTTPException(
            status_code=503,
            detail={"error": {"code": "LLM_TIMEOUT", "message": str(e)}},
        )

    item_profile = identification["item_profile"]
    matched_tags = identification["matched_tags"]
    matched_tag_ids = [t["tag_id"] for t in matched_tags]
    item_tags = [(t["tag_id"], t["weight"]) for t in matched_tags]

    # Step 2: Detect first-interaction BEFORE incrementing counter
    user = db.scalar(select(User).where(User.id == user_id))
    is_first = (user is None) or (user.interaction_count == 0)

    # Step 3: Cosine base_score (unchanged math backbone)
    base_score = profile_calc.compute_match_score(user_id=user_id, item_tags=item_tags)

    # Step 4: Build user context
    user_personality = db.scalar(
        select(UserPersonality).where(UserPersonality.user_id == user_id)
    )
    if user_personality and user_personality.summary:
        user_taste_hint = user_personality.summary
    else:
        user_taste_descriptions = profile_calc.get_top_core_tag_descriptions(
            user_id=user_id, n=2
        )
        user_taste_hint = "；".join(user_taste_descriptions)

    user_top_descriptions = profile_calc.get_top_core_tag_descriptions(
        user_id=user_id, n=2
    )

    # Step 5: Judge — Match + Advise in one LLM call (graceful degradation)
    judge_result = await llm_judge.judge(
        text=payload.text,
        domain=payload.domain,
        item_profile=item_profile,
        base_score=base_score,
        user_personality_summary=user_taste_hint,
        user_top_tag_descriptions=user_top_descriptions,
    )
    final_score = judge_result["final_score"]
    reasons = judge_result["reasons"]
    verdict = judge_result["verdict"]
    roast = judge_result["roast"]

    # Step 7: Apply profile update (unchanged from V1.2/V1.3)
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

    # Step 8: Increment interaction counter
    new_count, new_level, level_up = profile_calc.increment_interaction(user_id)
    info = profile_calc.level_info(new_count)
    ui_stage = profile_calc.compute_ui_stage(new_level)

    return AnalyzeResponse(
        match_score=final_score,
        item_name=item_profile.get("item_name", ""),
        summary=identification["summary"],
        roast=roast,
        verdict=verdict,
        reasons=reasons,
        matched_tags=[MatchedTag(**t) for t in matched_tags],
        text_hash=identification["text_hash"],
        cache_hit=identification["cache_hit"],
        interaction_count=new_count,
        level=new_level,
        level_title=info["title"],
        level_emoji=info["emoji"],
        next_level_at=info["next_level_at"],
        level_up=level_up,
        ui_stage=ui_stage,
    )


def _sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/analyze-stream")
async def analyze_stream(
    payload: AnalyzeRequest,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    async def event_generator() -> AsyncGenerator[str, None]:
        # Phase 1: Identify
        yield _sse_event("step", {"step": "searching", "progress": 10})
        page_title = payload.context.page_title if payload.context else None
        try:
            identification = await llm_identifier.identify(
                payload.text, payload.domain, page_title=page_title,
                exclude_items=payload.exclude_items or None,
            )
        except (llm_identifier.LlmParseError, llm_identifier.LlmTimeoutError) as e:
            yield _sse_event("error", {"code": "LLM_FAIL", "message": str(e)})
            return

        item_profile = identification["item_profile"]
        matched_tags = identification["matched_tags"]
        matched_tag_ids = [t["tag_id"] for t in matched_tags]
        item_tags = [(t["tag_id"], t["weight"]) for t in matched_tags]

        yield _sse_event("step", {"step": "identified", "progress": 50})

        # Phase 2: Cosine score (instant)
        user = db.scalar(select(User).where(User.id == user_id))
        is_first = (user is None) or (user.interaction_count == 0)
        base_score = profile_calc.compute_match_score(user_id=user_id, item_tags=item_tags)

        # Send early result: item_name + base_score + tags
        yield _sse_event("identified", {
            "item_name": item_profile.get("item_name", ""),
            "summary": identification["summary"],
            "matched_tags": matched_tags,
            "text_hash": identification["text_hash"],
            "cache_hit": identification["cache_hit"],
            "base_score": base_score,
        })

        # Phase 3: Judge (the slow part)
        yield _sse_event("step", {"step": "judging", "progress": 70})

        user_personality = db.scalar(
            select(UserPersonality).where(UserPersonality.user_id == user_id)
        )
        if user_personality and user_personality.summary:
            user_taste_hint = user_personality.summary
        else:
            user_taste_descriptions = profile_calc.get_top_core_tag_descriptions(
                user_id=user_id, n=2
            )
            user_taste_hint = "；".join(user_taste_descriptions)

        user_top_descriptions = profile_calc.get_top_core_tag_descriptions(
            user_id=user_id, n=2
        )

        judge_result = await llm_judge.judge(
            text=payload.text,
            domain=payload.domain,
            item_profile=item_profile,
            base_score=base_score,
            user_personality_summary=user_taste_hint,
            user_top_tag_descriptions=user_top_descriptions,
        )

        # Profile update + level
        if is_first:
            profile_calc.apply_core_delta(
                user_id=user_id, tag_ids=matched_tag_ids,
                delta=FIRST_IMPRESSION_DELTA, action="first_impression",
            )
        else:
            curiosity_delta = profile_calc.dynamic_curiosity_delta(payload.hesitation_ms)
            profile_calc.apply_curiosity_delta(
                user_id=user_id, tag_ids=matched_tag_ids,
                delta=curiosity_delta, action="analyze",
            )

        new_count, new_level, level_up = profile_calc.increment_interaction(user_id)
        info = profile_calc.level_info(new_count)
        ui_stage = profile_calc.compute_ui_stage(new_level)

        # Send complete result
        yield _sse_event("done", {
            "match_score": judge_result["final_score"],
            "item_name": item_profile.get("item_name", ""),
            "summary": identification["summary"],
            "roast": judge_result["roast"],
            "verdict": judge_result["verdict"],
            "reasons": judge_result["reasons"],
            "matched_tags": matched_tags,
            "text_hash": identification["text_hash"],
            "cache_hit": identification["cache_hit"],
            "interaction_count": new_count,
            "level": new_level,
            "level_title": info["title"],
            "level_emoji": info["emoji"],
            "next_level_at": info["next_level_at"],
            "level_up": level_up,
            "ui_stage": ui_stage,
        })

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/action", response_model=ActionResponse)
def action(
    payload: ActionRequest,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    delta = profile_calc.dynamic_core_delta(payload.action, payload.read_ms)
    profile_calc.apply_core_delta(
        user_id=user_id,
        tag_ids=payload.matched_tag_ids,
        delta=delta,
        action=payload.action,
    )

    # Save match feedback for background analysis
    if payload.text_hash and payload.item_name:
        db.add(MatchFeedback(
            user_id=user_id,
            text_hash=payload.text_hash or "",
            item_name=payload.item_name or "",
            domain=payload.domain or "",
            match_score=payload.match_score or 0,
            verdict=payload.verdict or "",
            feedback="accurate" if payload.action == "star" else "inaccurate",
            matched_tag_ids=",".join(str(t) for t in payload.matched_tag_ids),
        ))
        db.commit()

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
