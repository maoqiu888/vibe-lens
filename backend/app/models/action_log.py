from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ActionLog(Base):
    __tablename__ = "action_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    vibe_tag_id: Mapped[int] = mapped_column(ForeignKey("vibe_tags.id"))
    action: Mapped[str] = mapped_column(String(32))
    delta: Mapped[float] = mapped_column(Float)
    target_column: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
