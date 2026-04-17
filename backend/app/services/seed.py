from sqlalchemy import select

from app import database
from app.database import Base
from app.models.action_log import ActionLog  # noqa: F401
from app.models.analysis_cache import AnalysisCache  # noqa: F401
from app.models.user import User  # noqa: F401
from app.models.user_personality import UserPersonality  # noqa: F401
from app.models.user_vibe_relation import UserVibeRelation  # noqa: F401
from app.models.vibe_tag import VibeTag
from app.services.seed_data import TAGS, compute_opposite


def seed_all() -> None:
    """Idempotent: create schema and insert 24 tags if absent."""
    Base.metadata.create_all(database.engine)
    db = database.SessionLocal()
    try:
        existing = db.scalar(select(VibeTag).where(VibeTag.id == 1))
        if existing is not None:
            return
        for category, tier, tid, name, description in TAGS:
            db.add(VibeTag(
                id=tid,
                name=name,
                category=category,
                tier=tier,
                opposite_id=compute_opposite(tid),
                description=description,
            ))
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    seed_all()
    print("Seeded 24 vibe tags.")
