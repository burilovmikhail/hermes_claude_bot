import asyncio
import signal
import structlog
from telegram.ext import Application, CommandHandler

from bot.config import settings
from bot.database.mongodb import MongoDB
from bot.utils.logger import setup_logging
from bot.handlers.common_handlers import start_handler, help_handler, new_handler
from bot.handlers.chat_handlers import chat_handler, chat_gpt_handler, chat_claude_handler
from bot.handlers.error_handlers import error_handler

# Setup logging
setup_logging()
logger = structlog.get_logger()


async def startup():
    """Initialize connections and services."""
    logger.info("Starting Hermes Bot...")

    # Extract database name from MongoDB URI
    # Format: mongodb://user:pass@host:port/database?options
    try:
        db_name = settings.mongodb_uri.split("/")[-1].split("?")[0]
        if not db_name:
            db_name = settings.mongo_initdb_database
    except Exception:
        db_name = settings.mongo_initdb_database

    # Connect to MongoDB
    await MongoDB.connect(settings.mongodb_uri, db_name)
    logger.info("Startup complete")


async def shutdown():
    """Cleanup connections and services."""
    logger.info("Shutting down Hermes Bot...")
    await MongoDB.close()
    logger.info("Shutdown complete")


def main():
    """Main entry point for the bot."""
    logger.info("Initializing Hermes Bot", log_level=settings.log_level)

    # Create the Application
    application = Application.builder().token(settings.telegram_api_key).build()

    # Register command handlers (order matters - more specific first)
    application.add_handler(CommandHandler("start", start_handler))
    application.add_handler(CommandHandler("help", help_handler))
    application.add_handler(CommandHandler("new", new_handler))
    application.add_handler(CommandHandler("chat_gpt", chat_gpt_handler))
    application.add_handler(CommandHandler("chat_claude", chat_claude_handler))
    application.add_handler(CommandHandler("chat", chat_handler))

    # Register error handler
    application.add_error_handler(error_handler)

    # Register startup and shutdown callbacks
    application.post_init = startup
    application.post_shutdown = shutdown

    logger.info("Starting polling...")

    # Run the bot with polling
    application.run_polling(
        allowed_updates=["message", "callback_query"],
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error("Fatal error", error=str(e))
        raise
