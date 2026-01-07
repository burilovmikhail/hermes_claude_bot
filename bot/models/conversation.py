from datetime import datetime
from typing import Optional, Dict, Any
import uuid

from beanie import Document, Indexed
from pydantic import Field


class Conversation(Document):
    """Conversation model for tracking chat sessions."""

    telegram_id: Indexed(int)  # type: ignore
    provider: str  # "openai" or "claude"
    session_id: Indexed(str, unique=True) = Field(default_factory=lambda: str(uuid.uuid4()))  # type: ignore
    started_at: datetime = Field(default_factory=datetime.utcnow)
    last_message_at: datetime = Field(default_factory=datetime.utcnow)
    message_count: int = 0
    is_active: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Settings:
        name = "conversations"
        indexes = [
            "telegram_id",
            "session_id",
            [("telegram_id", 1), ("is_active", 1)],
            [("telegram_id", 1), ("provider", 1), ("is_active", 1)],
        ]

    class Config:
        json_schema_extra = {
            "example": {
                "telegram_id": 123456789,
                "provider": "claude",
                "session_id": "550e8400-e29b-41d4-a716-446655440000",
                "is_active": True,
                "message_count": 5,
            }
        }
