from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    llm_provider: str = "deepseek"
    llm_api_key: str = "sk-replace-me"
    llm_model: str = "deepseek-chat"
    llm_base_url: str = "https://api.deepseek.com"
    db_path: str = "./data/vibe_radar.db"


settings = Settings()
