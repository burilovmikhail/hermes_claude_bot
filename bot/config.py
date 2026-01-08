from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Telegram Bot Configuration
    telegram_api_key: str
    allowed_user_id: int

    # AI Provider API Keys
    openai_api_key: str
    anthropic_api_key: str
    claude_model: str = "claude-3-5-sonnet-20250122"

    # Jira Configuration
    jira_url: str
    jira_email: str
    jira_api_token: str

    # GitHub Configuration
    github_token: str

    # Redis Configuration
    redis_url: str = "redis://redis:6379/0"

    # MongoDB Configuration
    mongodb_uri: str

    # Default AI Provider
    default_ai_provider: Literal["openai", "claude"] = "claude"

    # Conversation Settings
    max_context_messages: int = 20
    max_context_tokens: int = 4000

    # Logging
    log_level: str = "INFO"

    # MongoDB Authentication (for docker-compose)
    mongo_initdb_root_username: str = "hermes_user"
    mongo_initdb_root_password: str = "hermes_pass"
    mongo_initdb_database: str = "hermes_bot"


# Global settings instance
settings = Settings()
