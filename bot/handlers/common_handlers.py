from datetime import datetime
import structlog
from telegram import Update
from telegram.ext import ContextTypes

from bot.models.user import User
from bot.services.conversation_service import ConversationService
from bot.config import settings
from bot.utils.auth import authorized_users_only

logger = structlog.get_logger()


@authorized_users_only
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /start command.
    Initialize user in database and send welcome message.
    """
    user = update.effective_user
    telegram_id = user.id

    logger.info("Start command received", telegram_id=telegram_id, username=user.username)

    # Get or create user in database
    db_user = await User.find_one(User.telegram_id == telegram_id)

    if db_user:
        # Update last active time
        db_user.last_active = datetime.utcnow()
        await db_user.save()
        logger.info("Updated existing user", telegram_id=telegram_id)
    else:
        # Create new user
        db_user = User(
            telegram_id=telegram_id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            default_provider=settings.default_ai_provider,
        )
        await db_user.insert()
        logger.info("Created new user", telegram_id=telegram_id)

    # Send welcome message
    welcome_message = (
        f"Hello {user.first_name}!\n\n"
        "I'm Hermes, your AI assistant bot. I can connect you with both OpenAI and Anthropic Claude.\n\n"
        "Available commands:\n"
        "/chat <message> - Chat with default AI (Claude)\n"
        "/chat_gpt <message> - Chat with OpenAI GPT\n"
        "/chat_claude <message> - Chat with Anthropic Claude\n"
        "/new - Start a new conversation\n"
        "/help - Show this help message\n\n"
        "Just send me a message using any of the chat commands!"
    )

    await update.message.reply_text(welcome_message)


@authorized_users_only
async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    user = update.effective_user
    logger.info("Help command received", telegram_id=user.id)

    help_message = (
        "Hermes Bot - AI Assistant\n\n"
        "Available commands:\n\n"
        "/start - Initialize the bot\n"
        "/help - Show this help message\n"
        "/new - Start a new conversation session\n\n"
        "Chat commands:\n"
        "/chat <message> - Chat with default AI (Claude)\n"
        "/chat_gpt <message> - Chat with OpenAI GPT-4\n"
        "/chat_claude <message> - Chat with Anthropic Claude\n\n"
        "Examples:\n"
        "/chat Hello, how are you?\n"
        "/chat_gpt What is the capital of France?\n"
        "/chat_claude Explain quantum computing\n\n"
        "The bot maintains conversation context, so follow-up messages "
        "will remember previous messages in the same session."
    )

    await update.message.reply_text(help_message)


@authorized_users_only
async def new_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /new command.
    Start a new conversation session.
    """
    user = update.effective_user
    telegram_id = user.id

    logger.info("New conversation command received", telegram_id=telegram_id)

    # Get user's default provider or use system default
    db_user = await User.find_one(User.telegram_id == telegram_id)
    provider = db_user.default_provider if db_user else settings.default_ai_provider

    # Start new conversation
    conversation = await ConversationService.start_new_conversation(
        telegram_id, provider
    )

    await update.message.reply_text(
        f"Started a new conversation session.\n"
        f"Provider: {provider.upper()}\n"
        f"Session ID: {conversation.session_id[:8]}..."
    )
