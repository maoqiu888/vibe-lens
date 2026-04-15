import math
from datetime import datetime

import numpy as np
from sqlalchemy import select

from app import database
from app.models.action_log import ActionLog
from app.models.user import User
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
        # Lazy-create user row if missing (V1.2: no cold-start pre-creates it)
        user = db.scalar(select(User).where(User.id == user_id))
        if user is None:
            db.add(User(id=user_id, username="default", interaction_count=0))
            db.flush()

        for tid in tag_ids:
            rel = db.scalar(
                select(UserVibeRelation).where(
                    UserVibeRelation.user_id == user_id,
                    UserVibeRelation.vibe_tag_id == tid,
                )
            )
            if rel is None:
                # Lazy-create with default weights, then apply delta on top
                rel = UserVibeRelation(
                    user_id=user_id,
                    vibe_tag_id=tid,
                    curiosity_weight=0.0,
                    core_weight=0.0,
                )
                db.add(rel)
                db.flush()

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


# ----------------------------------------------------------------------
# V1.2 — Level system and dynamic weights
# ----------------------------------------------------------------------

LEVEL_DATA = {
    0:  {"title": "陌生人", "emoji": "👤"},
    1:  {"title": "初遇",   "emoji": "🌱"},
    2:  {"title": "浅尝",   "emoji": "🌿"},
    3:  {"title": "识味",   "emoji": "🌳"},
    4:  {"title": "入门",   "emoji": "🔍"},
    5:  {"title": "辨识",   "emoji": "🎯"},
    6:  {"title": "洞察",   "emoji": "🧠"},
    7:  {"title": "共鸣",   "emoji": "💞"},
    8:  {"title": "通透",   "emoji": "🔮"},
    9:  {"title": "灵魂",   "emoji": "👻"},
    10: {"title": "知己",   "emoji": "💎"},
}


def compute_level(interaction_count: int) -> int:
    """sqrt-based level curve. L0 is pre-interaction, L10+ keeps climbing."""
    if interaction_count <= 0:
        return 0
    return int(math.sqrt(interaction_count))


def level_info(interaction_count: int) -> dict:
    """Return a dict with level, title, emoji, next_level_at.

    For levels above 10, metadata (title/emoji) is capped at L10's data
    ("知己" / "💎") but the raw level and next_level_at keep advancing.
    """
    level = compute_level(interaction_count)
    capped = min(level, 10)
    info = LEVEL_DATA[capped]
    next_at = (level + 1) ** 2
    return {
        "level": level,
        "title": info["title"],
        "emoji": info["emoji"],
        "next_level_at": next_at,
    }


def compute_ui_stage(level: int) -> str:
    """Map a level to the frontend rendering stage.

    welcome  — L0 (popup pre-interaction)
    learning — L1-L3 (rate card hides percentage)
    early    — L4-L5 (percentage visible with level hint)
    stable   — L6+ (percentage visible, no level hint)
    """
    if level <= 0:
        return "welcome"
    if level <= 3:
        return "learning"
    if level <= 5:
        return "early"
    return "stable"


CURIOSITY_BASE = 0.5


def dynamic_curiosity_delta(hesitation_ms: int | None) -> float:
    """Scale curiosity delta by hesitation duration.

    <500ms:       0.3× baseline (impulsive)
    500-2000ms:   1.0× baseline (normal)
    2000-10000ms: 1.5× baseline (deliberate)
    >10000ms or invalid: 1.0× baseline (fallback)
    """
    if hesitation_ms is None or hesitation_ms < 0 or hesitation_ms > 60000:
        return CURIOSITY_BASE
    if hesitation_ms < 500:
        return CURIOSITY_BASE * 0.3
    if hesitation_ms < 2000:
        return CURIOSITY_BASE
    if hesitation_ms < 10000:
        return CURIOSITY_BASE * 1.5
    return CURIOSITY_BASE


STAR_BASE = 10.0
BOMB_BASE = -10.0


def dynamic_core_delta(action: str, read_ms: int | None) -> float:
    """Scale ±10 by read duration on the vibe card.

    <1000ms: 0.5× (reflex)
    1000-5000ms: 1.0× (normal)
    5000-30000ms: 1.5× (careful)
    >30000ms or invalid: 1.0× fallback
    """
    base = STAR_BASE if action == "star" else BOMB_BASE
    if read_ms is None or read_ms < 0 or read_ms > 300000:
        return base
    if read_ms < 1000:
        return base * 0.5
    if read_ms < 5000:
        return base
    if read_ms < 30000:
        return base * 1.5
    return base


def increment_interaction(user_id: int) -> tuple[int, int, bool]:
    """Atomically increment user.interaction_count by 1.

    Lazy-creates the user row if missing. Returns (new_count, new_level,
    level_up) where level_up is True iff the increment crossed a sqrt boundary.
    """
    db = database.SessionLocal()
    try:
        user = db.scalar(select(User).where(User.id == user_id))
        if user is None:
            user = User(id=user_id, username="default", interaction_count=0)
            db.add(user)
            db.flush()
        old_level = compute_level(user.interaction_count)
        user.interaction_count += 1
        new_count = user.interaction_count
        new_level = compute_level(new_count)
        db.commit()
        return new_count, new_level, new_level > old_level
    finally:
        db.close()
