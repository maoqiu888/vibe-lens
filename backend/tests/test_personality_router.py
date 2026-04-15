import json

from fastapi.testclient import TestClient
from sqlalchemy import select

from app import database
from app.main import app
from app.models.action_log import ActionLog
from app.models.user import User
from app.models.user_personality import UserPersonality
from app.models.user_vibe_relation import UserVibeRelation
from app.services.seed import seed_all

client = TestClient(app)


def _install_fake_agent(monkeypatch, tag_seeds, summary):
    async def fake(system_prompt, user_prompt):
        return json.dumps({
            "tag_seeds": tag_seeds,
            "personality_summary": summary,
        })
    from app.services import llm_personality_agent
    monkeypatch.setattr(llm_personality_agent, "_default_llm_call", fake)


def test_skip_both_fields_returns_skipped_and_writes_null_row():
    seed_all()
    r = client.post("/api/v1/personality/submit", json={
        "mbti": None,
        "constellation": None,
    })
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "skipped"
    assert body["seeded_tag_count"] == 0
    assert body["summary"] == ""

    db = database.SessionLocal()
    row = db.scalar(select(UserPersonality).where(UserPersonality.user_id == 1))
    assert row is not None
    assert row.mbti is None
    assert row.constellation is None
    assert row.summary is None
    db.close()


def test_submit_mbti_only_writes_row_and_seeds_tags(monkeypatch):
    seed_all()
    _install_fake_agent(
        monkeypatch,
        tag_seeds=[
            {"tag_id": 11, "weight": 15},
            {"tag_id": 12, "weight": 10},
        ],
        summary="这个朋友是典型的深度思考者。" * 3,
    )
    r = client.post("/api/v1/personality/submit", json={
        "mbti": "INTP",
        "constellation": None,
    })
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["seeded_tag_count"] == 2
    assert body["summary"].startswith("这个朋友")

    db = database.SessionLocal()
    row = db.scalar(select(UserPersonality).where(UserPersonality.user_id == 1))
    assert row.mbti == "INTP"
    assert row.constellation is None
    assert row.summary.startswith("这个朋友")

    rel11 = db.scalar(
        select(UserVibeRelation).where(
            UserVibeRelation.user_id == 1,
            UserVibeRelation.vibe_tag_id == 11,
        )
    )
    assert rel11.core_weight == 15.0

    rel12 = db.scalar(
        select(UserVibeRelation).where(
            UserVibeRelation.user_id == 1,
            UserVibeRelation.vibe_tag_id == 12,
        )
    )
    assert rel12.core_weight == 10.0

    logs = db.scalars(
        select(ActionLog).where(ActionLog.action == "personality_seed")
    ).all()
    assert len(logs) == 2

    # interaction_count NOT bumped by personality_seed
    user = db.scalar(select(User).where(User.id == 1))
    assert user.interaction_count == 0
    db.close()


def test_submit_constellation_only_also_works(monkeypatch):
    seed_all()
    _install_fake_agent(
        monkeypatch,
        tag_seeds=[{"tag_id": 5, "weight": 8}],
        summary="一个比较感性的人喜欢温暖柔和的东西。" * 2,
    )
    r = client.post("/api/v1/personality/submit", json={
        "mbti": None,
        "constellation": "双鱼座",
    })
    assert r.status_code == 200
    assert r.json()["seeded_tag_count"] == 1


def test_already_submitted_returns_400(monkeypatch):
    seed_all()
    # First submission — skip path
    client.post("/api/v1/personality/submit", json={
        "mbti": None, "constellation": None,
    })
    # Second submission attempt — must be blocked
    r = client.post("/api/v1/personality/submit", json={
        "mbti": "INTP", "constellation": None,
    })
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "ALREADY_SUBMITTED"


def test_invalid_mbti_format_returns_422():
    seed_all()
    r = client.post("/api/v1/personality/submit", json={
        "mbti": "XXXX",
        "constellation": None,
    })
    assert r.status_code == 422


def test_invalid_constellation_returns_422():
    seed_all()
    r = client.post("/api/v1/personality/submit", json={
        "mbti": None,
        "constellation": "未知座",
    })
    assert r.status_code == 422


def test_llm_failure_still_persists_empty_row(monkeypatch):
    seed_all()

    async def broken(system_prompt, user_prompt):
        raise RuntimeError("timeout")

    from app.services import llm_personality_agent
    monkeypatch.setattr(llm_personality_agent, "_default_llm_call", broken)

    r = client.post("/api/v1/personality/submit", json={
        "mbti": "INTP",
        "constellation": None,
    })
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["seeded_tag_count"] == 0
    assert body["summary"] == ""

    db = database.SessionLocal()
    row = db.scalar(select(UserPersonality).where(UserPersonality.user_id == 1))
    assert row is not None
    assert row.mbti == "INTP"
    # summary is None or "" — LLM failed so no content
    assert row.summary is None or row.summary == ""
    db.close()

    # Retry attempt should be blocked
    r2 = client.post("/api/v1/personality/submit", json={
        "mbti": "ENFP", "constellation": None,
    })
    assert r2.status_code == 400
