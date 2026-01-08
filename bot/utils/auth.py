from functools import wraps
import structlog
from telegram import Update
from telegram.ext import ContextTypes

from bot.config import settings

logger = structlog.get_logger()


def authorized_users_only(func):
    """
    Decorator to restrict bot access to allowed users only.
    Checks if the user's Telegram ID matches the ALLOWED_USER_ID from settings.
    """

    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        telegram_id = user.id

        if telegram_id != settings.allowed_user_id:
            logger.warning(
                "Unauthorized access attempt",
                telegram_id=telegram_id,
                username=user.username,
                allowed_user_id=settings.allowed_user_id,
            )
            await update.message.reply_text(
                "Sorry, you are not authorized to use this bot."
            )
            return

        return await func(update, context, *args, **kwargs)

    return wrapper
