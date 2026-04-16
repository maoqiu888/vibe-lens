import pytest
from sqlalchemy import select

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


def test_get_top_core_tag_names_returns_top_3_by_core_weight(seeded_user):
    db = database.SessionLocal()
    db.query(UserVibeRelation).filter_by(user_id=1, vibe_tag_id=1).one().core_weight = 30.0
    db.query(UserVibeRelation).filter_by(user_id=1, vibe_tag_id=5).one().core_weight = 20.0
    db.query(UserVibeRelation).filter_by(user_id=1, vibe_tag_id=9).one().core_weight = 10.0
    db.query(UserVibeRelation).filter_by(user_id=1, vibe_tag_id=13).one().core_weight = 5.0
    db.commit()
    db.close()

    names = profile_calc.get_top_core_tag_names(user_id=1, n=3)
    assert len(names) == 3
    assert names[0] == "慢炖沉浸"
    assert names[1] == "治愈温暖"
    assert names[2] == "放空友好"


def test_get_top_core_tag_names_excludes_zero_and_negative_weights(seeded_user):
    db = database.SessionLocal()
    db.query(UserVibeRelation).filter_by(user_id=1, vibe_tag_id=1).one().core_weight = 10.0
    db.query(UserVibeRelation).filter_by(user_id=1, vibe_tag_id=2).one().core_weight = -5.0
    db.commit()
    db.close()

    names = profile_calc.get_top_core_tag_names(user_id=1, n=3)
    assert names == ["慢炖沉浸"]


def test_get_top_core_tag_names_cold_start_user_returns_empty(seeded_user):
    names = profile_calc.get_top_core_tag_names(user_id=1, n=3)
    assert names == []


# ------------------- V1.2 level system -------------------

def test_compute_level_zero_interactions():
    assert profile_calc.compute_level(0) == 0


def test_compute_level_sqrt_boundaries():
    assert profile_calc.compute_level(1) == 1
    assert profile_calc.compute_level(3) == 1
    assert profile_calc.compute_level(4) == 2
    assert profile_calc.compute_level(8) == 2
    assert profile_calc.compute_level(9) == 3
    assert profile_calc.compute_level(15) == 3
    assert profile_calc.compute_level(16) == 4
    assert profile_calc.compute_level(24) == 4
    assert profile_calc.compute_level(25) == 5
    assert profile_calc.compute_level(100) == 10
    # L10+ returns raw sqrt — caller caps for metadata lookup
    assert profile_calc.compute_level(144) == 12


def test_level_info_returns_title_emoji_next_at():
    info = profile_calc.level_info(0)
    assert info == {"level": 0, "title": "陌生人", "emoji": "👤", "next_level_at": 1}

    info = profile_calc.level_info(1)
    assert info["level"] == 1
    assert info["title"] == "初遇"
    assert info["emoji"] == "🌱"
    assert info["next_level_at"] == 4

    info = profile_calc.level_info(15)
    assert info["level"] == 3
    assert info["title"] == "识味"
    assert info["next_level_at"] == 16

    info = profile_calc.level_info(100)
    assert info["level"] == 10
    assert info["title"] == "知己"
    assert info["next_level_at"] == 121

    # L10+ caps metadata but keeps next_level_at advancing
    info = profile_calc.level_info(144)
    assert info["level"] == 12
    assert info["title"] == "知己"  # capped metadata
    assert info["emoji"] == "💎"
    assert info["next_level_at"] == 169


def test_compute_ui_stage_boundaries():
    assert profile_calc.compute_ui_stage(0) == "welcome"
    assert profile_calc.compute_ui_stage(1) == "early"
    assert profile_calc.compute_ui_stage(3) == "early"
    assert profile_calc.compute_ui_stage(4) == "early"
    assert profile_calc.compute_ui_stage(5) == "early"
    assert profile_calc.compute_ui_stage(6) == "stable"
    assert profile_calc.compute_ui_stage(10) == "stable"


def test_dynamic_curiosity_delta_all_brackets():
    assert profile_calc.dynamic_curiosity_delta(None) == 0.5
    assert profile_calc.dynamic_curiosity_delta(-1) == 0.5
    assert profile_calc.dynamic_curiosity_delta(70000) == 0.5
    assert profile_calc.dynamic_curiosity_delta(100) == pytest.approx(0.15)
    assert profile_calc.dynamic_curiosity_delta(499) == pytest.approx(0.15)
    assert profile_calc.dynamic_curiosity_delta(500) == 0.5
    assert profile_calc.dynamic_curiosity_delta(1999) == 0.5
    assert profile_calc.dynamic_curiosity_delta(2000) == 0.75
    assert profile_calc.dynamic_curiosity_delta(9999) == 0.75
    assert profile_calc.dynamic_curiosity_delta(10000) == 0.5


def test_dynamic_core_delta_star_brackets():
    assert profile_calc.dynamic_core_delta("star", None) == 10.0
    assert profile_calc.dynamic_core_delta("star", 500) == 5.0
    assert profile_calc.dynamic_core_delta("star", 999) == 5.0
    assert profile_calc.dynamic_core_delta("star", 1000) == 10.0
    assert profile_calc.dynamic_core_delta("star", 4999) == 10.0
    assert profile_calc.dynamic_core_delta("star", 5000) == 15.0
    assert profile_calc.dynamic_core_delta("star", 29999) == 15.0
    assert profile_calc.dynamic_core_delta("star", 30000) == 10.0
    assert profile_calc.dynamic_core_delta("star", 500000) == 10.0


def test_dynamic_core_delta_bomb_brackets():
    assert profile_calc.dynamic_core_delta("bomb", None) == -10.0
    assert profile_calc.dynamic_core_delta("bomb", 500) == -5.0
    assert profile_calc.dynamic_core_delta("bomb", 3000) == -10.0
    assert profile_calc.dynamic_core_delta("bomb", 10000) == -15.0


def test_increment_interaction_creates_user_lazily():
    seed_all()
    # No pre-existing user row
    count, level, level_up = profile_calc.increment_interaction(user_id=1)
    assert count == 1
    assert level == 1
    assert level_up is True

    db = database.SessionLocal()
    user = db.scalar(select(User).where(User.id == 1))
    assert user is not None
    assert user.interaction_count == 1
    db.close()


def test_increment_interaction_crosses_sqrt_boundary():
    seed_all()
    db = database.SessionLocal()
    db.add(User(id=1, username="default", interaction_count=3))
    db.commit()
    db.close()

    count, level, level_up = profile_calc.increment_interaction(user_id=1)
    assert count == 4
    assert level == 2
    assert level_up is True


def test_increment_interaction_no_level_up_within_bracket():
    seed_all()
    db = database.SessionLocal()
    db.add(User(id=1, username="default", interaction_count=5))
    db.commit()
    db.close()

    count, level, level_up = profile_calc.increment_interaction(user_id=1)
    assert count == 6
    assert level == 2
    assert level_up is False


def test_apply_delta_lazy_creates_user_and_relation():
    """V1.2 core fix — _apply_delta must lazy-create missing rows.

    Before V1.2, cold-start pre-created 24 UserVibeRelation rows. V1.2
    deletes cold-start, so on a brand-new user the first _apply_delta
    call encounters zero rows. It must create them on the fly.
    """
    seed_all()
    # No user row, no relations — pristine state
    profile_calc.apply_core_delta(
        user_id=1,
        tag_ids=[1, 5],
        delta=10.0,
        action="first_impression",
    )

    db = database.SessionLocal()
    # User row was lazy-created
    user = db.scalar(select(User).where(User.id == 1))
    assert user is not None
    assert user.interaction_count == 0  # apply_delta does NOT touch counter

    # Both relations were lazy-created with the delta applied
    rels = db.scalars(
        select(UserVibeRelation).where(UserVibeRelation.user_id == 1)
    ).all()
    by_tag = {r.vibe_tag_id: r for r in rels}
    assert len(rels) == 2
    assert by_tag[1].core_weight == 10.0
    assert by_tag[1].curiosity_weight == 0.0
    assert by_tag[5].core_weight == 10.0

    # ActionLog was written for each tag
    logs = db.scalars(select(ActionLog).where(ActionLog.action == "first_impression")).all()
    assert len(logs) == 2
    db.close()


def test_apply_delta_does_not_duplicate_on_second_call():
    """Second _apply_delta for the same tag must UPDATE, not INSERT."""
    seed_all()
    profile_calc.apply_core_delta(user_id=1, tag_ids=[1], delta=10.0, action="first_impression")
    profile_calc.apply_core_delta(user_id=1, tag_ids=[1], delta=10.0, action="star")

    db = database.SessionLocal()
    rels = db.scalars(
        select(UserVibeRelation).where(
            UserVibeRelation.user_id == 1,
            UserVibeRelation.vibe_tag_id == 1,
        )
    ).all()
    assert len(rels) == 1
    assert rels[0].core_weight == 20.0
    db.close()
