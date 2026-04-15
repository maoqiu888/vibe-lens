from fastapi.testclient import TestClient
from sqlalchemy import select

from app import database
from app.main import app
from app.models.user import User
from app.models.user_vibe_relation import UserVibeRelation
from app.services.seed import seed_all

client = TestClient(app)


def _prime_profile():
    """Prime user_id=1 with 6 tags at core_weight=15, mimicking V1.0 cold-start.
    Pre-bumps interaction_count to 16 (level=4 → ui_stage 'early') so
    /profile/radar returns a non-welcome, non-learning stage."""
    seed_all()
    db = database.SessionLocal()
    user = db.scalar(select(User).where(User.id == 1))
    if user is None:
        db.add(User(id=1, username="default", interaction_count=16))
        db.commit()
    else:
        user.interaction_count = 16
        db.commit()
    for tid in [1, 5, 9, 13, 17, 21]:
        existing = db.scalar(
            select(UserVibeRelation).where(
                UserVibeRelation.user_id == 1,
                UserVibeRelation.vibe_tag_id == tid,
            )
        )
        if existing is None:
            db.add(UserVibeRelation(
                user_id=1, vibe_tag_id=tid,
                curiosity_weight=0.0, core_weight=15.0,
            ))
    db.commit()
    db.close()


def test_radar_returns_6_dimensions():
    _prime_profile()
    r = client.get("/api/v1/profile/radar")
    assert r.status_code == 200
    body = r.json()
    assert body["user_id"] == 1
    assert len(body["dimensions"]) == 6
    cats = {d["category"] for d in body["dimensions"]}
    assert cats == {"pace", "mood", "cognition", "narrative", "world", "intensity"}
    for d in body["dimensions"]:
        assert 0 <= d["score"] <= 100
        assert "dominant_tag" in d
    # V1.2 level fields
    assert body["interaction_count"] == 16
    assert body["level"] == 4
    assert body["ui_stage"] == "early"


def test_radar_returns_level_fields_for_welcome_stage():
    """New user with no interactions gets welcome stage + level 0."""
    seed_all()
    # No _prime_profile — pristine state
    r = client.get("/api/v1/profile/radar")
    assert r.status_code == 200
    body = r.json()
    assert body["interaction_count"] == 0
    assert body["level"] == 0
    assert body["ui_stage"] == "welcome"
    assert body["level_title"] == "陌生人"
    assert body["level_emoji"] == "👤"
    assert body["next_level_at"] == 1
    assert len(body["dimensions"]) == 6  # empty dimensions still returned
