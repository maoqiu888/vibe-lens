from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class UserVibeRelation(Base):
    __tablename__ = "user_vibe_relations"
    __table_args__ = (UniqueConstraint("user_id", "vibe_tag_id", name="uq_user_tag"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    vibe_tag_id: Mapped[int] = mapped_column(ForeignKey("vibe_tags.id"))
    curiosity_weight: Mapped[float] = mapped_column(Float, default=0.0)
    core_weight: Mapped[float] = mapped_column(Float, default=0.0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
