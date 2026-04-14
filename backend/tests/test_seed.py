from sqlalchemy import select

from app import database
from app.models.vibe_tag import VibeTag
from app.services.seed import seed_all


def test_seed_inserts_24_tags_with_opposite_relations():
    seed_all()
    db = database.SessionLocal()
    tags = db.scalars(select(VibeTag).order_by(VibeTag.id)).all()
    assert len(tags) == 24

    # 6 categories, each exactly 4 tiers
    from collections import Counter
    cat_count = Counter(t.category for t in tags)
    assert set(cat_count.keys()) == {"pace", "mood", "cognition", "narrative", "world", "intensity"}
    for cat, n in cat_count.items():
        assert n == 4, f"category {cat} has {n} tags, expected 4"

    # opposite relations: tier 1 <-> tier 4, tier 2 <-> tier 3 within same category
    by_id = {t.id: t for t in tags}
    for t in tags:
        opp = by_id[t.opposite_id]
        assert opp.category == t.category
        assert {t.tier, opp.tier} in ({1, 4}, {2, 3})

    db.close()


def test_seed_is_idempotent():
    seed_all()
    seed_all()  # second call must not duplicate
    db = database.SessionLocal()
    assert db.scalar(select(VibeTag).where(VibeTag.id == 1)).name == "慢炖沉浸"
    assert len(db.scalars(select(VibeTag)).all()) == 24
    db.close()
