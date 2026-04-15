import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app import database
from app.main import app
from app.models.action_log import ActionLog
from app.models.user import User
from app.models.user_vibe_relation import UserVibeRelation
from app.services.seed import seed_all

client = TestClient(app)


def _prime_profile():
    """Prime user_id=1 with 6 tags at core_weight=15, mimicking V1.0 cold-start.

    Used by tests that want a pre-seeded profile to check star/bomb math.
    Does NOT touch interaction_count — it stays at 0 so tests can still
    verify first-interaction behavior if needed.
    """
    seed_all()
    db = database.SessionLocal()
    user = db.scalar(select(User).where(User.id == 1))
    if user is None:
        db.add(User(id=1, username="default", interaction_count=0))
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


def _install_fake_recommender(monkeypatch, items):
    async def fake(system_prompt, user_prompt):
        return json.dumps({"items": items})
    from app.services import llm_recommender
    monkeypatch.setattr(llm_recommender, "_default_llm_call", fake)


def test_analyze_returns_match_score_and_updates_curiosity(monkeypatch):
    _prime_profile()
    # Bump interaction_count past 0 so analyze takes the curiosity path
    # (first-impression branch only fires for brand-new users).
    db = database.SessionLocal()
    user = db.scalar(select(User).where(User.id == 1))
    user.interaction_count = 1
    db.commit()
    db.close()
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
    _prime_profile()
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
    _prime_profile()
    _install_fake_llm(monkeypatch, "garbage")
    _install_fake_roaster(monkeypatch, "unused")
    r = client.post("/api/v1/vibe/analyze",
                    json={"text": "x is too short anyway", "domain": "book"})
    assert r.status_code == 503
    assert r.json()["error"]["code"] == "LLM_PARSE_FAIL"


def test_analyze_roaster_failure_returns_empty_roast(monkeypatch):
    """If the roaster fails, analyze still returns 200 with roast=''."""
    _prime_profile()
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
    _prime_profile()
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
    _prime_profile()
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


def test_recommend_happy_path_returns_3_cross_domain_items(monkeypatch):
    _prime_profile()
    _install_fake_recommender(monkeypatch, [
        {"domain": "game", "name": "《逃生》",     "reason": "幽闭窒息"},
        {"domain": "book", "name": "《幽灵之家》", "reason": "心理压抑"},
        {"domain": "music", "name": "Ben Frost",  "reason": "黑暗环境音"},
    ])
    r = client.post("/api/v1/vibe/recommend", json={
        "text": "《闪灵》",
        "source_domain": "movie",
        "matched_tag_ids": [8, 11],
    })
    assert r.status_code == 200
    body = r.json()
    assert len(body["items"]) == 3
    assert {i["domain"] for i in body["items"]} == {"game", "book", "music"}
    assert all(i["domain"] != "movie" for i in body["items"])


def test_recommend_empty_tag_ids_rejected_by_pydantic(monkeypatch):
    _prime_profile()
    r = client.post("/api/v1/vibe/recommend", json={
        "text": "x",
        "source_domain": "movie",
        "matched_tag_ids": [],
    })
    assert r.status_code == 422


def test_recommend_invalid_tag_ids_returns_400(monkeypatch):
    _prime_profile()
    r = client.post("/api/v1/vibe/recommend", json={
        "text": "x",
        "source_domain": "movie",
        "matched_tag_ids": [999],
    })
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "INVALID_TAG_IDS"


def test_recommend_all_same_domain_returns_503(monkeypatch):
    _prime_profile()
    _install_fake_recommender(monkeypatch, [
        {"domain": "movie", "name": "a", "reason": "x"},
        {"domain": "movie", "name": "b", "reason": "y"},
    ])
    r = client.post("/api/v1/vibe/recommend", json={
        "text": "x",
        "source_domain": "movie",
        "matched_tag_ids": [1],
    })
    assert r.status_code == 503
    assert r.json()["error"]["code"] == "NO_CROSS_DOMAIN"


def test_recommend_llm_parse_failure_returns_503(monkeypatch):
    _prime_profile()
    async def broken(system_prompt, user_prompt):
        return "garbage"
    from app.services import llm_recommender
    monkeypatch.setattr(llm_recommender, "_default_llm_call", broken)
    r = client.post("/api/v1/vibe/recommend", json={
        "text": "x",
        "source_domain": "movie",
        "matched_tag_ids": [1],
    })
    assert r.status_code == 503
    assert r.json()["error"]["code"] == "LLM_PARSE_FAIL"


def test_analyze_first_interaction_applies_first_impression_delta(monkeypatch):
    """First-ever analyze gives core_weight += 10 instead of curiosity += 0.5."""
    seed_all()
    # Do NOT call _prime_profile — start pristine
    _install_fake_llm(monkeypatch, json.dumps({
        "tags": [{"tag_id": 1, "weight": 0.9}], "summary": "slow"
    }))
    _install_fake_roaster(monkeypatch, "first impression")
    r = client.post("/api/v1/vibe/analyze",
                    json={"text": "my first highlight", "domain": "book"})
    assert r.status_code == 200
    body = r.json()
    assert body["level"] == 1
    assert body["level_up"] is True
    assert body["ui_stage"] == "learning"
    assert body["interaction_count"] == 1
    assert body["level_title"] == "初遇"
    assert body["level_emoji"] == "🌱"

    db = database.SessionLocal()
    rel = db.scalar(
        select(UserVibeRelation).where(
            UserVibeRelation.user_id == 1,
            UserVibeRelation.vibe_tag_id == 1,
        )
    )
    assert rel.core_weight == 10.0
    assert rel.curiosity_weight == 0.0
    db.close()


def test_analyze_second_interaction_uses_curiosity(monkeypatch):
    seed_all()
    _install_fake_llm(monkeypatch, json.dumps({
        "tags": [{"tag_id": 1, "weight": 0.9}], "summary": "slow"
    }))
    _install_fake_roaster(monkeypatch, "r")
    # First call (first-impression)
    client.post("/api/v1/vibe/analyze", json={"text": "first", "domain": "book"})
    # Second call — baseline curiosity (no hesitation_ms sent)
    r = client.post("/api/v1/vibe/analyze",
                    json={"text": "second", "domain": "book"})
    body = r.json()
    assert body["interaction_count"] == 2
    assert body["level"] == 1
    assert body["level_up"] is False

    db = database.SessionLocal()
    rel = db.scalar(
        select(UserVibeRelation).where(
            UserVibeRelation.user_id == 1,
            UserVibeRelation.vibe_tag_id == 1,
        )
    )
    assert rel.core_weight == 10.0  # unchanged from first
    assert rel.curiosity_weight == 0.5  # baseline applied on second
    db.close()


def test_analyze_impulsive_hesitation_gives_small_curiosity(monkeypatch):
    seed_all()
    _install_fake_llm(monkeypatch, json.dumps({
        "tags": [{"tag_id": 2, "weight": 0.9}], "summary": "x"
    }))
    _install_fake_roaster(monkeypatch, "r")
    client.post("/api/v1/vibe/analyze", json={"text": "first", "domain": "book"})
    client.post("/api/v1/vibe/analyze",
                json={"text": "quick", "domain": "book", "hesitation_ms": 100})

    db = database.SessionLocal()
    rel = db.scalar(
        select(UserVibeRelation).where(
            UserVibeRelation.user_id == 1,
            UserVibeRelation.vibe_tag_id == 2,
        )
    )
    assert rel.curiosity_weight == pytest.approx(0.15)
    db.close()


def test_analyze_deliberate_hesitation_gives_bigger_curiosity(monkeypatch):
    seed_all()
    _install_fake_llm(monkeypatch, json.dumps({
        "tags": [{"tag_id": 3, "weight": 0.9}], "summary": "x"
    }))
    _install_fake_roaster(monkeypatch, "r")
    client.post("/api/v1/vibe/analyze", json={"text": "first", "domain": "book"})
    client.post("/api/v1/vibe/analyze",
                json={"text": "careful", "domain": "book", "hesitation_ms": 5000})

    db = database.SessionLocal()
    rel = db.scalar(
        select(UserVibeRelation).where(
            UserVibeRelation.user_id == 1,
            UserVibeRelation.vibe_tag_id == 3,
        )
    )
    assert rel.curiosity_weight == pytest.approx(0.75)
    db.close()


def test_analyze_crosses_level_up_at_count_4(monkeypatch):
    seed_all()
    _install_fake_llm(monkeypatch, json.dumps({
        "tags": [{"tag_id": 1, "weight": 0.9}], "summary": "x"
    }))
    _install_fake_roaster(monkeypatch, "r")
    for i in range(3):
        client.post("/api/v1/vibe/analyze", json={"text": f"text-{i}", "domain": "book"})
    r = client.post("/api/v1/vibe/analyze", json={"text": "fourth", "domain": "book"})
    body = r.json()
    assert body["interaction_count"] == 4
    assert body["level"] == 2
    assert body["level_up"] is True
    assert body["level_title"] == "浅尝"
    assert body["ui_stage"] == "learning"


def test_action_star_read_ms_scales_core_delta(monkeypatch):
    seed_all()
    _install_fake_llm(monkeypatch, json.dumps({
        "tags": [{"tag_id": 1, "weight": 0.9}], "summary": "x"
    }))
    _install_fake_roaster(monkeypatch, "r")
    # First analyze → core_weight=10
    client.post("/api/v1/vibe/analyze", json={"text": "first", "domain": "book"})
    # Careful star (10 second read) → delta=+15
    r = client.post("/api/v1/vibe/action", json={
        "action": "star",
        "matched_tag_ids": [1],
        "read_ms": 10000,
    })
    assert r.status_code == 200
    body = r.json()
    assert body["interaction_count"] == 2
    assert "level" in body
    assert "level_title" in body

    db = database.SessionLocal()
    rel = db.scalar(
        select(UserVibeRelation).where(
            UserVibeRelation.user_id == 1,
            UserVibeRelation.vibe_tag_id == 1,
        )
    )
    assert rel.core_weight == 25.0  # 10 (first-impression) + 15 (careful star)
    db.close()


def test_action_response_carries_level_fields(monkeypatch):
    seed_all()
    _install_fake_llm(monkeypatch, json.dumps({"tags": [{"tag_id": 1, "weight": 0.9}], "summary": "x"}))
    _install_fake_roaster(monkeypatch, "r")
    client.post("/api/v1/vibe/analyze", json={"text": "first", "domain": "book"})
    r = client.post("/api/v1/vibe/action", json={
        "action": "star",
        "matched_tag_ids": [1],
    })
    body = r.json()
    assert body["interaction_count"] == 2
    assert body["level"] == 1
    assert body["level_up"] is False
    assert body["level_title"] == "初遇"
    assert "next_level_at" in body
