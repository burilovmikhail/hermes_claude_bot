import structlog
import uuid
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ChatAction

from bot.models.repository import Repository
from bot.services.git_parser import GitCommandParser
from bot.services.redis_service import RedisService
from bot.config import settings
from bot.utils.auth import authorized_users_only

logger = structlog.get_logger()


# Global Redis service instance (shared with adw_handlers)
redis_service: RedisService = None


def set_redis_service(service: RedisService):
    """Set the global Redis service instance."""
    global redis_service
    redis_service = service


@authorized_users_only
async def git_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /git command.

    Supports:
    - /git clone <short_name> <jira_prefix> <repo_url>
    - /git pull <short_name>

    Usage examples:
      /git clone backend MS EcorRouge/mcguire-sponsel-backend
      /git clone api PROJ https://github.com/myorg/api-service
      /git pull backend
    """
    user = update.effective_user
    telegram_id = user.id

    # Extract command text
    message_text = update.message.text.replace("/git", "", 1).strip()

    if not message_text:
        await update.message.reply_text(
            "Please provide a git command.\n\n"
            "Usage:\n"
            "  /git clone <short_name> <jira_prefix> <repo_url>\n"
            "  /git pull <short_name>\n\n"
            "Examples:\n"
            "  /git clone backend MS EcorRouge/backend-api\n"
            "  /git clone api PROJ github.com/myorg/api-service\n"
            "  /git pull backend"
        )
        return

    logger.info(
        "Processing git command",
        telegram_id=telegram_id,
        message_text=message_text
    )

    # Show typing indicator
    await update.message.chat.send_action(ChatAction.TYPING)

    try:
        # Parse command using OpenAI
        parser = GitCommandParser(api_key=settings.openai_api_key)
        parsed = await parser.parse(message_text)

        operation = parsed.get("operation")

        if operation == "clone":
            await handle_clone(update, telegram_id, parsed)
        elif operation == "pull":
            await handle_pull(update, telegram_id, parsed)
        else:
            error_msg = parsed.get("error", "Could not determine git operation")
            await update.message.reply_text(
                f"❌ Invalid command: {error_msg}\n\n"
                "Please use:\n"
                "  /git clone <short_name> <jira_prefix> <repo_url>\n"
                "  /git pull <short_name>"
            )

    except Exception as e:
        logger.error(
            "Error processing git command",
            telegram_id=telegram_id,
            error=str(e)
        )
        await update.message.reply_text(
            f"Sorry, I encountered an error:\n{str(e)}"
        )


async def handle_clone(update: Update, telegram_id: int, parsed: dict):
    """
    Handle git clone operation.

    Args:
        update: Telegram update
        telegram_id: User's Telegram ID
        parsed: Parsed command data
    """
    # Validate parsed data
    is_valid, error_msg = GitCommandParser.validate_clone_data(parsed)
    if not is_valid:
        await update.message.reply_text(
            f"❌ Invalid clone command: {error_msg}\n\n"
            "Required: /git clone <short_name> <jira_prefix> <repo_url>\n"
            "Example: /git clone backend MS EcorRouge/backend-api"
        )
        return

    short_name = parsed["short_name"]
    jira_prefix = parsed["jira_prefix"].upper()
    repo_url = parsed["repo_url"]

    # Check if repository with same short_name already exists for this user
    existing = await Repository.find_one(
        Repository.telegram_id == telegram_id,
        Repository.short_name == short_name
    )

    if existing:
        await update.message.reply_text(
            f"❌ Repository with short name '{short_name}' already exists.\n\n"
            f"Existing: {existing.repo_url}\n"
            f"Jira Prefix: {existing.jira_prefix}\n\n"
            "Please choose a different short name or delete the existing one first."
        )
        return

    # Normalize repo URL
    short_form, full_url = GitCommandParser.normalize_repo_url(repo_url)

    # Create repository record
    repo = Repository(
        telegram_id=telegram_id,
        short_name=short_name,
        jira_prefix=jira_prefix,
        repo_url=short_form,
        full_url=full_url,
        cloned=False
    )

    # Save to database
    await repo.insert()

    logger.info(
        "Repository saved to database",
        telegram_id=telegram_id,
        short_name=short_name,
        repo_url=short_form
    )

    # Send clone task to worker
    if redis_service:
        task_id = str(uuid.uuid4())
        task_data = {
            "task_id": task_id,
            "telegram_id": telegram_id,
            "operation": "git_clone",
            "repo_id": str(repo.id),
            "short_name": short_name,
            "repo_url": short_form,
            "full_url": full_url,
            "timestamp": datetime.utcnow().isoformat()
        }

        success = await redis_service.publish_task(task_data)

        if success:
            await update.message.reply_text(
                f"🔄 *Cloning Repository*\n\n"
                f"*Short Name:* {short_name}\n"
                f"*Jira Prefix:* {jira_prefix}\n"
                f"*Repository:* {short_form}\n\n"
                f"I'll notify you when the clone completes.",
                parse_mode="Markdown"
            )

            logger.info(
                "Clone task queued",
                task_id=task_id,
                telegram_id=telegram_id,
                short_name=short_name
            )
        else:
            await update.message.reply_text(
                "Failed to queue clone task. Repository saved but not cloned yet."
            )
    else:
        await update.message.reply_text(
            "Worker service is not available. Repository saved but not cloned yet."
        )


async def handle_pull(update: Update, telegram_id: int, parsed: dict):
    """
    Handle git pull operation.

    Args:
        update: Telegram update
        telegram_id: User's Telegram ID
        parsed: Parsed command data
    """
    # Validate parsed data
    is_valid, error_msg = GitCommandParser.validate_pull_data(parsed)
    if not is_valid:
        await update.message.reply_text(
            f"❌ Invalid pull command: {error_msg}\n\n"
            "Required: /git pull <short_name>\n"
            "Example: /git pull backend"
        )
        return

    short_name = parsed["short_name"]

    # Find repository
    repo = await Repository.find_one(
        Repository.telegram_id == telegram_id,
        Repository.short_name == short_name
    )

    if not repo:
        await update.message.reply_text(
            f"❌ Repository '{short_name}' not found.\n\n"
            "Use /git clone to add a repository first."
        )
        return

    # Send pull task to worker
    if redis_service:
        task_id = str(uuid.uuid4())
        task_data = {
            "task_id": task_id,
            "telegram_id": telegram_id,
            "operation": "git_pull",
            "repo_id": str(repo.id),
            "short_name": short_name,
            "repo_url": repo.repo_url,
            "full_url": repo.full_url,
            "timestamp": datetime.utcnow().isoformat()
        }

        success = await redis_service.publish_task(task_data)

        if success:
            await update.message.reply_text(
                f"🔄 *Pulling Repository*\n\n"
                f"*Short Name:* {short_name}\n"
                f"*Repository:* {repo.repo_url}\n\n"
                f"I'll notify you when the pull completes.",
                parse_mode="Markdown"
            )

            logger.info(
                "Pull task queued",
                task_id=task_id,
                telegram_id=telegram_id,
                short_name=short_name
            )
        else:
            await update.message.reply_text(
                "Failed to queue pull task. Please try again later."
            )
    else:
        await update.message.reply_text(
            "Worker service is not available. Please contact the administrator."
        )


async def handle_git_response(response_data: dict, application):
    """
    Handle responses from worker service for git operations.

    Args:
        response_data: Response data from worker
        application: Telegram application instance
    """
    try:
        task_id = response_data.get("task_id")
        telegram_id = response_data.get("telegram_id")
        status = response_data.get("status")
        message = response_data.get("message", "")
        operation = response_data.get("operation")
        repo_id = response_data.get("repo_id")

        if not all([task_id, telegram_id, status]):
            logger.warning("Incomplete git response", data=response_data)
            return

        # Update repository status if clone succeeded
        if operation == "git_clone" and status == "success" and repo_id:
            try:
                repo = await Repository.get(repo_id)
                if repo:
                    repo.cloned = True
                    repo.update_timestamp()
                    await repo.save()
                    logger.info("Updated repository clone status", repo_id=repo_id)
            except Exception as e:
                logger.error("Failed to update repository status", error=str(e))

        # Update last_pulled timestamp if pull succeeded
        if operation == "git_pull" and status == "success" and repo_id:
            try:
                repo = await Repository.get(repo_id)
                if repo:
                    repo.last_pulled = datetime.utcnow()
                    repo.update_timestamp()
                    await repo.save()
                    logger.info("Updated repository pull timestamp", repo_id=repo_id)
            except Exception as e:
                logger.error("Failed to update pull timestamp", error=str(e))

        # Format message based on status
        if status == "success":
            text = f"✅ {message}"
        elif status == "failed":
            text = f"❌ {message}"
        else:
            text = f"ℹ️ {message}"

        # Send message to user
        await application.bot.send_message(
            chat_id=telegram_id,
            text=text
        )

        logger.info(
            "Sent git response to user",
            task_id=task_id,
            telegram_id=telegram_id,
            status=status
        )

    except Exception as e:
        logger.error("Error handling git response", error=str(e), data=response_data)
