from fastapi.testclient import TestClient
from sqlalchemy import select

from app import database
from app.main import app
from app.models.action_log import ActionLog
from app.models.user import User
from app.models.user_vibe_relation import UserVibeRelation
from app.services.seed import seed_all

client = TestClient(app)


def _ensure_user():
    seed_all()
    db = database.SessionLocal()
    if db.scalar(select(User).where(User.id == 1)) is None:
        db.add(User(id=1, username="default"))
        db.commit()
    db.close()


def test_get_cards_returns_6_categories_each_with_3_options():
    _ensure_user()
    r = client.get("/api/v1/cold-start/cards")
    assert r.status_code == 200
    body = r.json()
    assert len(body["cards"]) == 6
    for card in body["cards"]:
        assert len(card["options"]) == 3
        tiers = [o["tier"] for o in card["options"]]
        assert 1 in tiers
        assert 4 in tiers


def test_submit_6_valid_tags_initializes_profile():
    _ensure_user()
    # One tag per category (ids 1,5,9,13,17,21 = tier 1 of each)
    r = client.post("/api/v1/cold-start/submit",
                    json={"selected_tag_ids": [1, 5, 9, 13, 17, 21]})
    assert r.status_code == 200
    assert r.json()["profile_initialized"] is True

    db = database.SessionLocal()
    rels = db.scalars(
        select(UserVibeRelation).where(UserVibeRelation.user_id == 1)
    ).all()
    assert len(rels) == 24
    by_tag = {r.vibe_tag_id: r for r in rels}
    for tid in [1, 5, 9, 13, 17, 21]:
        assert by_tag[tid].core_weight == 15.0
    logs = db.scalars(select(ActionLog).where(ActionLog.action == "cold_start")).all()
    assert len(logs) == 6
    db.close()


def test_submit_with_duplicate_category_is_rejected():
    _ensure_user()
    # tags 1 and 4 are both "pace" category
    r = client.post("/api/v1/cold-start/submit",
                    json={"selected_tag_ids": [1, 4, 9, 13, 17, 21]})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "COLD_START_INVALID_SELECTION"


def test_submit_with_wrong_count_is_rejected():
    _ensure_user()
    r = client.post("/api/v1/cold-start/submit",
                    json={"selected_tag_ids": [1, 5, 9]})
    assert r.status_code == 422  # pydantic validation


def test_resubmit_returns_already_initialized():
    _ensure_user()
    client.post("/api/v1/cold-start/submit",
                json={"selected_tag_ids": [1, 5, 9, 13, 17, 21]})
    r = client.post("/api/v1/cold-start/submit",
                    json={"selected_tag_ids": [2, 6, 10, 14, 18, 22]})
    assert r.status_code == 200
    assert r.json()["already_initialized"] is True

    # Weights from the first submit must be preserved
    db = database.SessionLocal()
    rel = db.scalar(
        select(UserVibeRelation).where(
            UserVibeRelation.user_id == 1,
            UserVibeRelation.vibe_tag_id == 1,
        )
    )
    assert rel.core_weight == 15.0
    db.close()
