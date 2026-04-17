from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import get_db
from app.models.llm_config import LlmConfig

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])

# Preset providers with their default base URLs and models
PROVIDERS = {
    "deepseek": {"base_url": "https://api.deepseek.com", "models": ["deepseek-chat", "deepseek-reasoner"]},
    "openai": {"base_url": "https://api.openai.com", "models": ["gpt-4o", "gpt-4o-mini", "gpt-4.1", "gpt-4.1-mini"]},
    "anthropic": {"base_url": "https://api.anthropic.com", "models": ["claude-sonnet-4-20250514", "claude-haiku-4-20250414"]},
    "moonshot": {"base_url": "https://api.moonshot.cn", "models": ["moonshot-v1-8k", "moonshot-v1-32k"]},
    "qwen": {"base_url": "https://dashscope.aliyuncs.com/compatible-mode", "models": ["qwen-plus", "qwen-turbo", "qwen-max"]},
    "zhipu": {"base_url": "https://open.bigmodel.cn/api/paas", "models": ["glm-4-flash", "glm-4-plus"]},
    "custom": {"base_url": "", "models": []},
}


class LlmConfigResponse(BaseModel):
    provider: str
    api_key_masked: str
    model: str
    base_url: str
    providers: dict


class LlmConfigUpdate(BaseModel):
    provider: str
    api_key: str
    model: str
    base_url: str


def _mask_key(key: str) -> str:
    if not key or len(key) < 8:
        return "未配置"
    return f"{key[:4]}****{key[-4:]}"


@router.get("/llm", response_model=LlmConfigResponse)
def get_llm_config(db: Session = Depends(get_db)):
    config = db.scalar(select(LlmConfig).where(LlmConfig.id == 1))
    if config is None:
        from app.config import settings
        return LlmConfigResponse(
            provider=settings.llm_provider,
            api_key_masked=_mask_key(settings.llm_api_key),
            model=settings.llm_model,
            base_url=settings.llm_base_url,
            providers=PROVIDERS,
        )
    return LlmConfigResponse(
        provider=config.provider,
        api_key_masked=_mask_key(config.api_key),
        model=config.model,
        base_url=config.base_url,
        providers=PROVIDERS,
    )


@router.put("/llm", response_model=LlmConfigResponse)
def update_llm_config(
    payload: LlmConfigUpdate,
    db: Session = Depends(get_db),
):
    config = db.scalar(select(LlmConfig).where(LlmConfig.id == 1))
    if config is None:
        config = LlmConfig(id=1)
        db.add(config)

    config.provider = payload.provider
    config.model = payload.model
    config.base_url = payload.base_url
    if payload.api_key and not payload.api_key.startswith("****"):
        config.api_key = payload.api_key
    db.commit()

    return LlmConfigResponse(
        provider=config.provider,
        api_key_masked=_mask_key(config.api_key),
        model=config.model,
        base_url=config.base_url,
        providers=PROVIDERS,
    )
