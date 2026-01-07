from datetime import datetime
from typing import Optional

from beanie import Document, Indexed
from pydantic import Field


class User(Document):
    """User model for storing Telegram user information."""

    telegram_id: Indexed(int, unique=True)  # type: ignore
    username: Optional[str] = None
    first_name: str
    last_name: Optional[str] = None
    default_provider: str = "claude"  # "openai" or "claude"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_active: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "users"
        indexes = [
            "telegram_id",
        ]

    class Config:
        json_schema_extra = {
            "example": {
                "telegram_id": 123456789,
                "username": "johndoe",
                "first_name": "John",
                "last_name": "Doe",
                "default_provider": "claude",
            }
        }
