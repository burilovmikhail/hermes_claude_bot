from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum

from beanie import Document, Indexed
from pydantic import Field


class MessageRole(str, Enum):
    """Message role enum."""

    USER = "user"
    ASSISTANT = "assistant"


class Message(Document):
    """Message model for storing chat messages."""

    session_id: Indexed(str)  # type: ignore
    telegram_id: int
    role: MessageRole
    content: str
    provider: str  # "openai" or "claude"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    tokens_used: Optional[int] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Settings:
        name = "messages"
        indexes = [
            "session_id",
            "telegram_id",
            [("session_id", 1), ("timestamp", 1)],
            [("telegram_id", 1), ("timestamp", 1)],
        ]

    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "550e8400-e29b-41d4-a716-446655440000",
                "telegram_id": 123456789,
                "role": "user",
                "content": "Hello, how are you?",
                "provider": "claude",
                "tokens_used": 15,
            }
        }
