from sqlalchemy import select

from app import database
from app.database import Base
from app.models.action_log import ActionLog
from app.models.analysis_cache import AnalysisCache
from app.models.user import User
from app.models.user_vibe_relation import UserVibeRelation
from app.models.vibe_tag import VibeTag


def test_tables_are_created_and_basic_crud_works():
    db = database.SessionLocal()

    # users
    u = User(id=1, username="default")
    db.add(u)

    # vibe_tags (2 rows, each as the other's opposite)
    t1 = VibeTag(id=1, name="慢炖沉浸", category="pace", tier=1,
                 opposite_id=4, description="像在咖啡馆读一下午")
    t4 = VibeTag(id=4, name="爆裂快切", category="pace", tier=4,
                 opposite_id=1, description="密集刺激快切")
    db.add_all([t1, t4])
    db.flush()

    # user_vibe_relations
    r = UserVibeRelation(user_id=1, vibe_tag_id=1,
                         curiosity_weight=0.5, core_weight=15.0)
    db.add(r)

    # analysis_cache
    c = AnalysisCache(text_hash="abc", domain="book",
                      tags_json='{"tags":[]}', summary="s", hit_count=0)
    db.add(c)

    # action_log
    log = ActionLog(user_id=1, vibe_tag_id=1, action="cold_start",
                    delta=15.0, target_column="core")
    db.add(log)

    db.commit()

    assert db.scalar(select(User).where(User.id == 1)).username == "default"
    assert db.scalar(select(User).where(User.id == 1)).interaction_count == 0
    assert db.scalar(select(VibeTag).where(VibeTag.id == 1)).opposite_id == 4
    assert db.scalar(select(UserVibeRelation)).core_weight == 15.0
    assert db.scalar(select(AnalysisCache)).text_hash == "abc"
    assert db.scalar(select(ActionLog)).action == "cold_start"
    db.close()
