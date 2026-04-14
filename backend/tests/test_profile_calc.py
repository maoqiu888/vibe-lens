import pytest

from app import database
from app.models.action_log import ActionLog
from app.models.user import User
from app.models.user_vibe_relation import UserVibeRelation
from app.services import profile_calc
from app.services.seed import seed_all


@pytest.fixture
def seeded_user():
    seed_all()
    db = database.SessionLocal()
    db.add(User(id=1, username="default"))
    for tag_id in range(1, 25):
        db.add(UserVibeRelation(user_id=1, vibe_tag_id=tag_id,
                                curiosity_weight=0.0, core_weight=0.0))
    db.commit()
    db.close()


def test_compute_match_score_zero_profile_returns_zero(seeded_user):
    score = profile_calc.compute_match_score(
        user_id=1, item_tags=[(1, 1.0)]
    )
    assert score == 0


def test_compute_match_score_perfect_match_is_100(seeded_user):
    db = database.SessionLocal()
    rel = db.query(UserVibeRelation).filter_by(user_id=1, vibe_tag_id=1).one()
    rel.core_weight = 15.0
    db.commit()
    db.close()

    score = profile_calc.compute_match_score(user_id=1, item_tags=[(1, 1.0)])
    assert score == 100


def test_core_weight_is_3x_curiosity_weight(seeded_user):
    """effective = core*1.0 + curiosity*0.3"""
    db = database.SessionLocal()
    r1 = db.query(UserVibeRelation).filter_by(user_id=1, vibe_tag_id=1).one()
    r2 = db.query(UserVibeRelation).filter_by(user_id=1, vibe_tag_id=2).one()
    r1.core_weight = 10.0
    r2.curiosity_weight = 10.0
    db.commit()
    db.close()

    # vs item pointing only at tag 1 vs only at tag 2
    s1 = profile_calc.compute_match_score(user_id=1, item_tags=[(1, 1.0)])
    s2 = profile_calc.compute_match_score(user_id=1, item_tags=[(2, 1.0)])
    assert s1 > s2


def test_apply_curiosity_delta_updates_weight_and_writes_log(seeded_user):
    profile_calc.apply_curiosity_delta(user_id=1, tag_ids=[1, 2], delta=0.5,
                                       action="analyze")
    db = database.SessionLocal()
    r1 = db.query(UserVibeRelation).filter_by(user_id=1, vibe_tag_id=1).one()
    assert r1.curiosity_weight == 0.5
    logs = db.query(ActionLog).filter_by(user_id=1).all()
    assert len(logs) == 2
    assert all(l.target_column == "curiosity" and l.action == "analyze" for l in logs)
    db.close()


def test_apply_core_delta_updates_weight_and_writes_log(seeded_user):
    profile_calc.apply_core_delta(user_id=1, tag_ids=[1], delta=10.0,
                                  action="star")
    db = database.SessionLocal()
    r1 = db.query(UserVibeRelation).filter_by(user_id=1, vibe_tag_id=1).one()
    assert r1.core_weight == 10.0
    log = db.query(ActionLog).filter_by(user_id=1).one()
    assert log.target_column == "core"
    assert log.delta == 10.0
    db.close()


def test_compute_radar_returns_6_dimensions(seeded_user):
    data = profile_calc.compute_radar(user_id=1)
    assert len(data["dimensions"]) == 6
    assert {d["category"] for d in data["dimensions"]} == {
        "pace", "mood", "cognition", "narrative", "world", "intensity"
    }
    for d in data["dimensions"]:
        assert 0 <= d["score"] <= 100
