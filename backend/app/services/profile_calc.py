from datetime import datetime

import numpy as np
from sqlalchemy import select

from app import database
from app.models.action_log import ActionLog
from app.models.user_vibe_relation import UserVibeRelation
from app.models.vibe_tag import VibeTag
from app.services.seed_data import CATEGORY_LABELS

CORE_COEFF = 1.0
CURIOSITY_COEFF = 0.3
NUM_TAGS = 24


def _effective_vector(db, user_id: int) -> np.ndarray:
    rels = db.scalars(
        select(UserVibeRelation).where(UserVibeRelation.user_id == user_id)
    ).all()
    vec = np.zeros(NUM_TAGS + 1)  # index 0 unused; 1..24
    for r in rels:
        vec[r.vibe_tag_id] = r.core_weight * CORE_COEFF + r.curiosity_weight * CURIOSITY_COEFF
    return vec


def compute_match_score(user_id: int, item_tags: list[tuple[int, float]]) -> int:
    """Cosine similarity x 100, clamped to 0..100. Negative cosine -> 0."""
    db = database.SessionLocal()
    try:
        user_vec = _effective_vector(db, user_id)
    finally:
        db.close()

    item_vec = np.zeros(NUM_TAGS + 1)
    for tag_id, weight in item_tags:
        if 1 <= tag_id <= NUM_TAGS:
            item_vec[tag_id] = weight

    un = np.linalg.norm(user_vec)
    inorm = np.linalg.norm(item_vec)
    if un == 0 or inorm == 0:
        return 0
    cos = float(np.dot(user_vec, item_vec) / (un * inorm))
    score = max(0, min(100, round(cos * 100)))
    return int(score)


def _apply_delta(user_id: int, tag_ids: list[int], delta: float,
                 target_column: str, action: str) -> None:
    db = database.SessionLocal()
    try:
        for tid in tag_ids:
            rel = db.scalar(
                select(UserVibeRelation).where(
                    UserVibeRelation.user_id == user_id,
                    UserVibeRelation.vibe_tag_id == tid,
                )
            )
            if rel is None:
                continue
            if target_column == "curiosity":
                rel.curiosity_weight += delta
            elif target_column == "core":
                rel.core_weight += delta
            else:
                raise ValueError(f"unknown target_column: {target_column}")
            rel.updated_at = datetime.utcnow()
            db.add(ActionLog(
                user_id=user_id, vibe_tag_id=tid, action=action,
                delta=delta, target_column=target_column,
            ))
        db.commit()
    finally:
        db.close()


def apply_curiosity_delta(user_id: int, tag_ids: list[int], delta: float,
                          action: str) -> None:
    _apply_delta(user_id, tag_ids, delta, "curiosity", action)


def apply_core_delta(user_id: int, tag_ids: list[int], delta: float,
                     action: str) -> None:
    _apply_delta(user_id, tag_ids, delta, "core", action)


def compute_radar(user_id: int) -> dict:
    db = database.SessionLocal()
    try:
        tags = db.scalars(select(VibeTag)).all()
        rels = db.scalars(
            select(UserVibeRelation).where(UserVibeRelation.user_id == user_id)
        ).all()
    finally:
        db.close()

    eff_by_tag: dict[int, float] = {}
    for r in rels:
        eff_by_tag[r.vibe_tag_id] = (
            r.core_weight * CORE_COEFF + r.curiosity_weight * CURIOSITY_COEFF
        )

    by_cat: dict[str, list[VibeTag]] = {}
    for t in tags:
        by_cat.setdefault(t.category, []).append(t)

    dimensions = []
    for cat in ["pace", "mood", "cognition", "narrative", "world", "intensity"]:
        cat_tags = sorted(by_cat[cat], key=lambda t: t.tier)
        numerator = sum(t.tier * max(0.0, eff_by_tag.get(t.id, 0.0)) for t in cat_tags)
        # max_possible = max tier (4) * max expected effective weight (~45: 15*1 + 100*0.3)
        max_possible = 4 * 45.0
        raw = min(1.0, numerator / max_possible) if max_possible else 0.0
        score = round(raw * 100, 1)
        dominant = max(cat_tags, key=lambda t: eff_by_tag.get(t.id, 0.0))
        dimensions.append({
            "category": cat,
            "category_label": CATEGORY_LABELS[cat],
            "score": score,
            "dominant_tag": {"tag_id": dominant.id, "name": dominant.name},
        })
    return {"dimensions": dimensions}


def get_top_core_tag_names(user_id: int, n: int = 3) -> list[str]:
    """Return the names of the N tags with highest core_weight for this user.

    Used by the analyze router to pass 'user_top_tag_names' into the roaster
    and recommender prompts. Ties are broken by tag_id ascending. Returns an
    empty list if the user has no relations yet (cold-start state) or all
    weights are zero/negative.
    """
    db = database.SessionLocal()
    try:
        rels = db.scalars(
            select(UserVibeRelation).where(UserVibeRelation.user_id == user_id)
        ).all()
        if not rels:
            return []
        sorted_rels = sorted(rels, key=lambda r: (-r.core_weight, r.vibe_tag_id))
        top_ids = [r.vibe_tag_id for r in sorted_rels[:n] if r.core_weight > 0]
        if not top_ids:
            return []
        tags = db.scalars(select(VibeTag).where(VibeTag.id.in_(top_ids))).all()
        tag_by_id = {t.id: t.name for t in tags}
        return [tag_by_id[tid] for tid in top_ids if tid in tag_by_id]
    finally:
        db.close()
