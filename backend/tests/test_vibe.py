import json

from fastapi.testclient import TestClient
from sqlalchemy import select

from app import database
from app.main import app
from app.models.action_log import ActionLog
from app.models.user import User
from app.models.user_vibe_relation import UserVibeRelation
from app.services.seed import seed_all

client = TestClient(app)


def _init_profile():
    seed_all()
    db = database.SessionLocal()
    if db.scalar(select(User).where(User.id == 1)) is None:
        db.add(User(id=1, username="default"))
        db.commit()
    db.close()
    client.post(
        "/api/v1/cold-start/submit",
        json={"selected_tag_ids": [1, 5, 9, 13, 17, 21]},
    )


def _install_fake_llm(monkeypatch, response):
    async def fake(text, domain, tag_pool):
        return response
    from app.services import llm_tagger
    monkeypatch.setattr(llm_tagger, "_default_llm_call", fake)


def _install_fake_roaster(monkeypatch, roast_text):
    async def fake(system_prompt, user_prompt):
        return json.dumps({"roast": roast_text})
    from app.services import llm_roaster
    monkeypatch.setattr(llm_roaster, "_default_llm_call", fake)


def test_analyze_returns_match_score_and_updates_curiosity(monkeypatch):
    _init_profile()
    _install_fake_llm(monkeypatch, json.dumps({
        "tags": [{"tag_id": 1, "weight": 0.9}], "summary": "slow"
    }))
    _install_fake_roaster(monkeypatch, "慢炖神作，你会睡着但心满意足")
    r = client.post("/api/v1/vibe/analyze",
                    json={"text": "A gentle slow piece", "domain": "book"})
    assert r.status_code == 200
    body = r.json()
    assert body["match_score"] > 0
    assert body["matched_tags"][0]["tag_id"] == 1
    assert body["cache_hit"] is False
    assert body["roast"] == "慢炖神作，你会睡着但心满意足"

    db = database.SessionLocal()
    rel = db.scalar(
        select(UserVibeRelation).where(
            UserVibeRelation.user_id == 1,
            UserVibeRelation.vibe_tag_id == 1,
        )
    )
    assert rel.curiosity_weight == 0.5
    db.close()


def test_analyze_second_call_hits_cache(monkeypatch):
    _init_profile()
    _install_fake_llm(monkeypatch, json.dumps({
        "tags": [{"tag_id": 1, "weight": 0.9}], "summary": "slow"
    }))
    _install_fake_roaster(monkeypatch, "roast text")
    client.post("/api/v1/vibe/analyze",
                json={"text": "same text", "domain": "book"})
    r = client.post("/api/v1/vibe/analyze",
                    json={"text": "same text", "domain": "book"})
    assert r.json()["cache_hit"] is True


def test_analyze_llm_parse_failure_returns_503(monkeypatch):
    _init_profile()
    _install_fake_llm(monkeypatch, "garbage")
    _install_fake_roaster(monkeypatch, "unused")
    r = client.post("/api/v1/vibe/analyze",
                    json={"text": "x is too short anyway", "domain": "book"})
    assert r.status_code == 503
    assert r.json()["error"]["code"] == "LLM_PARSE_FAIL"


def test_analyze_roaster_failure_returns_empty_roast(monkeypatch):
    """If the roaster fails, analyze still returns 200 with roast=''."""
    _init_profile()
    _install_fake_llm(monkeypatch, json.dumps({
        "tags": [{"tag_id": 1, "weight": 0.9}], "summary": "slow"
    }))

    async def broken_roaster(system_prompt, user_prompt):
        raise RuntimeError("boom")
    from app.services import llm_roaster
    monkeypatch.setattr(llm_roaster, "_default_llm_call", broken_roaster)

    r = client.post("/api/v1/vibe/analyze",
                    json={"text": "A gentle slow piece", "domain": "book"})
    assert r.status_code == 200
    body = r.json()
    assert body["roast"] == ""
    assert body["match_score"] >= 0


def test_action_star_increments_core_weight(monkeypatch):
    _init_profile()
    r = client.post("/api/v1/vibe/action",
                    json={"action": "star", "matched_tag_ids": [2, 3]})
    assert r.status_code == 200
    assert r.json()["updated_tags"] == 2

    db = database.SessionLocal()
    r2 = db.scalar(
        select(UserVibeRelation).where(
            UserVibeRelation.user_id == 1,
            UserVibeRelation.vibe_tag_id == 2,
        )
    )
    assert r2.core_weight == 10.0
    logs = db.scalars(select(ActionLog).where(ActionLog.action == "star")).all()
    assert len(logs) == 2
    db.close()


def test_action_bomb_decrements_core_weight(monkeypatch):
    _init_profile()
    r = client.post("/api/v1/vibe/action",
                    json={"action": "bomb", "matched_tag_ids": [1]})
    assert r.status_code == 200
    db = database.SessionLocal()
    rel = db.scalar(
        select(UserVibeRelation).where(
            UserVibeRelation.user_id == 1,
            UserVibeRelation.vibe_tag_id == 1,
        )
    )
    # Started at 15 (cold start), bomb = -10 → 5
    assert rel.core_weight == 5.0
    db.close()
