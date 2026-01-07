from typing import List, Dict
import structlog
from anthropic import AsyncAnthropic
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from bot.services.ai_service import AIService, AIResponse

logger = structlog.get_logger()


class ClaudeService(AIService):
    """Anthropic Claude service implementation."""

    def __init__(self, api_key: str, model: str = "claude-3-5-sonnet-20241022"):
        """
        Initialize Claude service.

        Args:
            api_key: Anthropic API key
            model: Model to use (default: claude-3-5-sonnet-20241022)
        """
        super().__init__(api_key)
        self.client = AsyncAnthropic(api_key=api_key)
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
        Send a message to Claude.

        Args:
            message: User message to send
            conversation_history: List of previous messages

        Returns:
            AIResponse with content and metadata
        """
        try:
            # Build messages list (Claude uses separate system parameter)
            messages = conversation_history.copy()
            messages.append({"role": "user", "content": message})

            logger.info(
                "Sending message to Claude",
                model=self.model,
                message_count=len(messages),
            )

            # Call Claude API
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=self.system_prompt,
                messages=messages,
            )

            content = response.content[0].text
            tokens_used = response.usage.input_tokens + response.usage.output_tokens

            logger.info(
                "Received response from Claude",
                tokens_used=tokens_used,
                model=self.model,
            )

            return AIResponse(
                content=content,
                tokens_used=tokens_used,
                model=self.model,
                metadata={
                    "stop_reason": response.stop_reason,
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                },
            )

        except Exception as e:
            logger.error("Error calling Claude API", error=str(e), model=self.model)
            raise

    def get_provider_name(self) -> str:
        """Get the name of the AI provider."""
        return "claude"
