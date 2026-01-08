from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    """Worker service settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Redis Configuration
    redis_url: str = "redis://redis:6379/0"

    # GitHub Configuration
    github_token: str

    # Anthropic API Key (for Claude Code)
    anthropic_api_key: str

    # Claude Model
    claude_model: str = "claude-3-5-sonnet-20250122"

    # Workspace Configuration
    workspace_dir: str = "/workspace"

    # Logging
    log_level: str = "INFO"


# Global settings instance
settings = WorkerSettings()
