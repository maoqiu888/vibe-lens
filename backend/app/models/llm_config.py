from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class LlmConfig(Base):
    __tablename__ = "llm_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    provider: Mapped[str] = mapped_column(String(32), default="deepseek")
    api_key: Mapped[str] = mapped_column(String(256), default="")
    model: Mapped[str] = mapped_column(String(64), default="deepseek-chat")
    base_url: Mapped[str] = mapped_column(String(256), default="https://api.deepseek.com")
