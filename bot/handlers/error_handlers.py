import structlog
from telegram import Update
from telegram.ext import ContextTypes

logger = structlog.get_logger()


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """
    Global error handler for the bot.

    Args:
        update: Telegram update (may be None)
        context: Telegram context with error information
    """
    logger.error(
        "Exception while handling an update",
        error=str(context.error),
        error_type=type(context.error).__name__,
        update=update,
    )

    # Try to send error message to user if update is available
    if isinstance(update, Update) and update.effective_message:
        error_message = (
            "An unexpected error occurred while processing your request.\n"
            "Please try again later or use /start to reinitialize the bot."
        )

        try:
            await update.effective_message.reply_text(error_message)
        except Exception as e:
            logger.error("Failed to send error message to user", error=str(e))
