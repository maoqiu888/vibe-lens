"""Dynamic LLM config reader: DB first, fallback to .env."""
from sqlalchemy import select

from app import database
from app.config import settings


def get_llm_settings() -> dict:
    """Returns {api_key, model, base_url} from DB or .env fallback."""
    try:
        from app.models.llm_config import LlmConfig
        db = database.SessionLocal()
        try:
            config = db.scalar(select(LlmConfig).where(LlmConfig.id == 1))
            if config and config.api_key:
                return {
                    "api_key": config.api_key,
                    "model": config.model,
                    "base_url": config.base_url,
                    "provider": config.provider,
                }
        finally:
            db.close()
    except Exception:
        pass
    return {
        "api_key": settings.llm_api_key,
        "model": settings.llm_model,
        "base_url": settings.llm_base_url,
        "provider": settings.llm_provider,
    }
