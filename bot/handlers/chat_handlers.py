import structlog
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ChatAction

from bot.services.openai_service import OpenAIService
from bot.services.claude_service import ClaudeService
from bot.services.conversation_service import ConversationService
from bot.models.message import MessageRole
from bot.config import settings
from bot.utils.auth import authorized_users_only

logger = structlog.get_logger()


async def _process_chat_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    message_text: str,
    provider: str,
):
    """
    Process chat message with specified AI provider.

    Args:
        update: Telegram update
        context: Telegram context
        message_text: User's message text
        provider: AI provider ("openai" or "claude")
    """
    user = update.effective_user
    telegram_id = user.id

    if not message_text.strip():
        await update.message.reply_text(
            "Please provide a message after the command.\n"
            f"Example: /{update.message.text.split()[0][1:]} Hello, how are you?"
        )
        return

    logger.info(
        "Processing chat message",
        telegram_id=telegram_id,
        provider=provider,
        message_length=len(message_text),
    )

    # Show typing indicator
    await update.message.chat.send_action(ChatAction.TYPING)

    try:
        # Get or create conversation
        conversation = await ConversationService.get_or_create_conversation(
            telegram_id, provider
        )

        # Get conversation history
        history = await ConversationService.get_conversation_history(
            conversation.session_id
        )

        # Initialize AI service
        if provider == "openai":
            ai_service = OpenAIService(api_key=settings.openai_api_key)
        elif provider == "claude":
            ai_service = ClaudeService(api_key=settings.anthropic_api_key)
        else:
            await update.message.reply_text(f"Unknown provider: {provider}")
            return

        # Send message to AI
        response = await ai_service.send_message(message_text, history)

        # Save user message
        await ConversationService.save_message(
            session_id=conversation.session_id,
            telegram_id=telegram_id,
            role=MessageRole.USER,
            content=message_text,
            provider=provider,
        )

        # Save assistant response
        await ConversationService.save_message(
            session_id=conversation.session_id,
            telegram_id=telegram_id,
            role=MessageRole.ASSISTANT,
            content=response.content,
            provider=provider,
            tokens_used=response.tokens_used,
        )

        # Split response if it's too long (Telegram limit: 4096 characters)
        max_length = 4096
        if len(response.content) <= max_length:
            await update.message.reply_text(response.content)
        else:
            # Split into chunks
            for i in range(0, len(response.content), max_length):
                chunk = response.content[i : i + max_length]
                await update.message.reply_text(chunk)

        logger.info(
            "Chat message processed successfully",
            telegram_id=telegram_id,
            provider=provider,
            tokens_used=response.tokens_used,
        )

    except Exception as e:
        logger.error(
            "Error processing chat message",
            telegram_id=telegram_id,
            provider=provider,
            error=str(e),
        )
        await update.message.reply_text(
            f"Sorry, I encountered an error: {str(e)}\n"
            "Please try again later or use /new to start a fresh conversation."
        )


@authorized_users_only
async def chat_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /chat command (default provider).
    """
    # Extract message text after command
    message_text = update.message.text.replace("/chat", "", 1).strip()
    await _process_chat_message(
        update, context, message_text, settings.default_ai_provider
    )


@authorized_users_only
async def chat_gpt_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /chat_gpt command (OpenAI).
    """
    message_text = update.message.text.replace("/chat_gpt", "", 1).strip()
    await _process_chat_message(update, context, message_text, "openai")


@authorized_users_only
async def chat_claude_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /chat_claude command (Anthropic Claude).
    """
    message_text = update.message.text.replace("/chat_claude", "", 1).strip()
    await _process_chat_message(update, context, message_text, "claude")
