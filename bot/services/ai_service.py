from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class AIResponse:
    """Response from AI provider."""

    content: str
    tokens_used: Optional[int] = None
    model: Optional[str] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class AIService(ABC):
    """Abstract base class for AI providers."""

    def __init__(self, api_key: str):
        """
        Initialize AI service.

        Args:
            api_key: API key for the AI provider
        """
        self.api_key = api_key

    @abstractmethod
    async def send_message(
        self,
        message: str,
        conversation_history: List[Dict[str, str]],
    ) -> AIResponse:
        """
        Send a message to the AI provider.

        Args:
            message: User message to send
            conversation_history: List of previous messages in format:
                [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]

        Returns:
            AIResponse with content and metadata
        """
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        """Get the name of the AI provider."""
        pass
