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
