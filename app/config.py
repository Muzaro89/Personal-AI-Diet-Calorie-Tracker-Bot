from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    telegram_bot_token: str
    gemini_api_key: str
    database_url: str = "sqlite:///./calorie_tracker.db"
    webhook_secret: str = ""
    gemini_model: str = "gemini-2.0-flash"


settings = Settings()
