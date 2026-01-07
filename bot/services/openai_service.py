from typing import List, Dict
import structlog
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from bot.services.ai_service import AIService, AIResponse

logger = structlog.get_logger()


class OpenAIService(AIService):
    """OpenAI GPT service implementation."""

    def __init__(self, api_key: str, model: str = "gpt-4-turbo-preview"):
        """
        Initialize OpenAI service.

        Args:
            api_key: OpenAI API key
            model: Model to use (default: gpt-4-turbo-preview)
        """
        super().__init__(api_key)
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model
        self.system_prompt = "You are a helpful assistant."

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    async def send_message(
        self,
        message: str,
        conversation_history: List[Dict[str, str]],
    ) -> AIResponse:
        """
        Send a message to OpenAI.

        Args:
            message: User message to send
            conversation_history: List of previous messages

        Returns:
            AIResponse with content and metadata
        """
        try:
            # Build messages list with system prompt
            messages = [{"role": "system", "content": self.system_prompt}]
            messages.extend(conversation_history)
            messages.append({"role": "user", "content": message})

            logger.info(
                "Sending message to OpenAI",
                model=self.model,
                message_count=len(messages),
            )

            # Call OpenAI API
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
            )

            content = response.choices[0].message.content
            tokens_used = response.usage.total_tokens if response.usage else None

            logger.info(
                "Received response from OpenAI",
                tokens_used=tokens_used,
                model=self.model,
            )

            return AIResponse(
                content=content,
                tokens_used=tokens_used,
                model=self.model,
                metadata={
                    "finish_reason": response.choices[0].finish_reason,
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else None,
                    "completion_tokens": response.usage.completion_tokens if response.usage else None,
                },
            )

        except Exception as e:
            logger.error("Error calling OpenAI API", error=str(e), model=self.model)
            raise

    def get_provider_name(self) -> str:
        """Get the name of the AI provider."""
        return "openai"
