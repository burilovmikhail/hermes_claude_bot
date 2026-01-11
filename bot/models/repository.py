from datetime import datetime
from typing import Optional
from beanie import Document
from pydantic import Field


class Repository(Document):
    """Repository model for storing GitHub repository information."""

    # User who added this repository
    telegram_id: int = Field(description="Telegram user ID who owns this repository")

    # Repository identifiers
    short_name: str = Field(description="Short name for easy reference (e.g., 'backend')")
    jira_prefix: str = Field(description="Jira project prefix (e.g., 'MS', 'PROJ')")
    repo_url: str = Field(description="Full or short GitHub repo URL (e.g., 'owner/repo')")

    # Full URL constructed from short form if needed
    full_url: Optional[str] = Field(
        default=None,
        description="Full GitHub URL (e.g., 'https://github.com/owner/repo.git')"
    )

    # Status tracking
    registered: bool = Field(default=False, description="Whether repo was successfully registered")
    primed: bool = Field(default=False, description="Whether repo was successfully primed with Claude Code")
    last_primed: Optional[datetime] = Field(
        default=None,
        description="Last time repo was primed"
    )
    prime_output: Optional[str] = Field(
        default=None,
        description="Output from Claude Code /prime command"
    )

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "repositories"
        indexes = [
            [("telegram_id", 1), ("short_name", 1)],  # Unique per user
            [("telegram_id", 1), ("jira_prefix", 1)],
        ]

    def update_timestamp(self):
        """Update the updated_at timestamp."""
        self.updated_at = datetime.utcnow()
