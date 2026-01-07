from typing import List, Dict, Optional
from datetime import datetime
import structlog

from bot.models.conversation import Conversation
from bot.models.message import Message, MessageRole
from bot.config import settings

logger = structlog.get_logger()


class ConversationService:
    """Service for managing conversation history and sessions."""

    @staticmethod
    async def get_or_create_conversation(
        telegram_id: int, provider: str
    ) -> Conversation:
        """
        Get active conversation or create a new one.

        Args:
            telegram_id: Telegram user ID
            provider: AI provider name ("openai" or "claude")

        Returns:
            Active Conversation object
        """
        # Try to find active conversation for this user and provider
        conversation = await Conversation.find_one(
            Conversation.telegram_id == telegram_id,
            Conversation.provider == provider,
            Conversation.is_active == True,
        )

        if conversation:
            logger.info(
                "Found existing conversation",
                telegram_id=telegram_id,
                session_id=conversation.session_id,
                provider=provider,
            )
            return conversation

        # Create new conversation
        conversation = Conversation(
            telegram_id=telegram_id,
            provider=provider,
            is_active=True,
        )
        await conversation.insert()

        logger.info(
            "Created new conversation",
            telegram_id=telegram_id,
            session_id=conversation.session_id,
            provider=provider,
        )
        return conversation

    @staticmethod
    async def get_conversation_history(
        session_id: str, max_messages: Optional[int] = None
    ) -> List[Dict[str, str]]:
        """
        Get conversation history for a session.

        Args:
            session_id: Conversation session ID
            max_messages: Maximum number of messages to retrieve (defaults to settings)

        Returns:
            List of messages in format [{"role": "user", "content": "..."}, ...]
        """
        if max_messages is None:
            max_messages = settings.max_context_messages

        # Fetch messages sorted by timestamp
        messages = (
            await Message.find(Message.session_id == session_id)
            .sort(+Message.timestamp)
            .to_list()
        )

        # Take only the last N messages
        messages = messages[-max_messages:]

        # Convert to format expected by AI services
        history = [
            {"role": msg.role.value, "content": msg.content} for msg in messages
        ]

        logger.info(
            "Retrieved conversation history",
            session_id=session_id,
            message_count=len(history),
        )

        return history

    @staticmethod
    async def save_message(
        session_id: str,
        telegram_id: int,
        role: MessageRole,
        content: str,
        provider: str,
        tokens_used: Optional[int] = None,
    ) -> Message:
        """
        Save a message to the database.

        Args:
            session_id: Conversation session ID
            telegram_id: Telegram user ID
            role: Message role (user or assistant)
            content: Message content
            provider: AI provider name
            tokens_used: Number of tokens used (optional)

        Returns:
            Saved Message object
        """
        message = Message(
            session_id=session_id,
            telegram_id=telegram_id,
            role=role,
            content=content,
            provider=provider,
            tokens_used=tokens_used,
        )
        await message.insert()

        # Update conversation metadata
        conversation = await Conversation.find_one(
            Conversation.session_id == session_id
        )
        if conversation:
            conversation.last_message_at = datetime.utcnow()
            conversation.message_count += 1
            await conversation.save()

        logger.info(
            "Saved message",
            session_id=session_id,
            role=role.value,
            tokens_used=tokens_used,
        )

        return message

    @staticmethod
    async def start_new_conversation(telegram_id: int, provider: str) -> Conversation:
        """
        Start a new conversation by deactivating old ones and creating a new one.

        Args:
            telegram_id: Telegram user ID
            provider: AI provider name

        Returns:
            New Conversation object
        """
        # Deactivate all active conversations for this user and provider
        active_conversations = await Conversation.find(
            Conversation.telegram_id == telegram_id,
            Conversation.provider == provider,
            Conversation.is_active == True,
        ).to_list()

        for conv in active_conversations:
            conv.is_active = False
            await conv.save()

        logger.info(
            "Deactivated conversations",
            telegram_id=telegram_id,
            provider=provider,
            count=len(active_conversations),
        )

        # Create new conversation
        return await ConversationService.get_or_create_conversation(
            telegram_id, provider
        )
