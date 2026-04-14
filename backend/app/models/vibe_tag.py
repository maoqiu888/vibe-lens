from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class VibeTag(Base):
    __tablename__ = "vibe_tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(64))
    category: Mapped[str] = mapped_column(String(32))
    tier: Mapped[int] = mapped_column(Integer)
    opposite_id: Mapped[int | None] = mapped_column(ForeignKey("vibe_tags.id"), nullable=True)
    description: Mapped[str] = mapped_column(Text)
