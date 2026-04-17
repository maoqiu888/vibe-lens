from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class MatchFeedback(Base):
    __tablename__ = "match_feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    text_hash: Mapped[str] = mapped_column(String(64))
    item_name: Mapped[str] = mapped_column(String(200), default="")
    domain: Mapped[str] = mapped_column(String(16), default="")
    match_score: Mapped[int] = mapped_column(Integer, default=0)
    verdict: Mapped[str] = mapped_column(String(16), default="")
    feedback: Mapped[str] = mapped_column(String(16))  # "accurate" or "inaccurate"
    matched_tag_ids: Mapped[str] = mapped_column(Text, default="")  # comma-separated
    analyzed: Mapped[bool] = mapped_column(Integer, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
