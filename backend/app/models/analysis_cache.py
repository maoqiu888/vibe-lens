from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AnalysisCache(Base):
    __tablename__ = "analysis_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    text_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    domain: Mapped[str] = mapped_column(String(16))
    tags_json: Mapped[str] = mapped_column(Text)
    summary: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    hit_count: Mapped[int] = mapped_column(Integer, default=0)
