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
from bot.utils.constants import escape_markdown

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
    - /git add <short_name> <jira_prefix> <repo_url>
    - /git list

    Usage examples:
      /git add backend MS EcorRouge/mcguire-sponsel-backend
      /git add api PROJ https://github.com/myorg/api-service
      /git list
    """
    user = update.effective_user
    telegram_id = user.id

    # Extract command text
    message_text = update.message.text.replace("/git", "", 1).strip()

    if not message_text:
        await update.message.reply_text(
            "Please provide a git command.\n\n"
            "Usage:\n"
            "  /git add <short_name> <jira_prefix> <repo_url>\n"
            "  /git list\n\n"
            "Examples:\n"
            "  /git add backend MS EcorRouge/backend-api\n"
            "  /git add api PROJ github.com/myorg/api-service\n"
            "  /git list"
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

        if operation == "add":
            await handle_add(update, telegram_id, parsed)
        elif operation == "list":
            await handle_list(update, telegram_id, parsed)
        else:
            error_msg = parsed.get("error", "Could not determine git operation")
            await update.message.reply_text(
                f"❌ Invalid command: {escape_markdown(error_msg)}\n\n"
                "Please use:\n"
                "  /git add <short_name> <jira_prefix> <repo_url>\n"
                "  /git list"
            )

    except Exception as e:
        logger.error(
            "Error processing git command",
            telegram_id=telegram_id,
            error=str(e)
        )
        await update.message.reply_text(
            f"Sorry, I encountered an error:\n{escape_markdown(str(e))}"
        )


async def handle_add(update: Update, telegram_id: int, parsed: dict):
    """
    Handle git add operation.

    Args:
        update: Telegram update
        telegram_id: User's Telegram ID
        parsed: Parsed command data
    """
    # Validate parsed data
    is_valid, error_msg = GitCommandParser.validate_add_data(parsed)
    if not is_valid:
        await update.message.reply_text(
            f"❌ Invalid add command: {escape_markdown(error_msg)}\n\n"
            "Required: /git add <short_name> <jira_prefix> <repo_url>\n"
            "Example: /git add backend MS EcorRouge/backend-api"
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
            f"❌ Repository with short name '{escape_markdown(short_name)}' already exists.\n\n"
            f"Existing: {escape_markdown(existing.repo_url)}\n"
            f"Jira Prefix: {escape_markdown(existing.jira_prefix)}\n\n"
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
        registered=False,
        primed=False
    )

    # Save to database
    await repo.insert()

    logger.info(
        "Repository saved to database",
        telegram_id=telegram_id,
        short_name=short_name,
        repo_url=short_form
    )

    # Send add task to worker (clone + prime)
    if redis_service:
        task_id = str(uuid.uuid4())
        task_data = {
            "task_id": task_id,
            "telegram_id": telegram_id,
            "operation": "git_add",
            "repo_id": str(repo.id),
            "short_name": short_name,
            "repo_url": short_form,
            "full_url": full_url,
            "timestamp": datetime.utcnow().isoformat()
        }

        success = await redis_service.publish_task(task_data)

        if success:
            await update.message.reply_text(
                f"🔄 *Adding Repository*\n\n"
                f"*Short Name:* {escape_markdown(short_name)}\n"
                f"*Jira Prefix:* {escape_markdown(jira_prefix)}\n"
                f"*Repository:* {escape_markdown(short_form)}\n\n"
                f"I'll clone the repository and prime it with Claude Code. You'll be notified when complete.",
                parse_mode="Markdown"
            )

            logger.info(
                "Add task queued",
                task_id=task_id,
                telegram_id=telegram_id,
                short_name=short_name
            )
        else:
            await update.message.reply_text(
                "Failed to queue add task. Repository saved but not processed yet."
            )
    else:
        await update.message.reply_text(
            "Worker service is not available. Repository saved but not processed yet."
        )


async def handle_list(update: Update, telegram_id: int, parsed: dict):
    """
    Handle git list operation.

    Args:
        update: Telegram update
        telegram_id: User's Telegram ID
        parsed: Parsed command data
    """
    # Validate parsed data
    is_valid, error_msg = GitCommandParser.validate_list_data(parsed)
    if not is_valid:
        await update.message.reply_text(
            f"❌ Invalid list command: {escape_markdown(error_msg)}\n\n"
            "Usage: /git list"
        )
        return

    # Find all repositories for this user
    repos = await Repository.find(Repository.telegram_id == telegram_id).to_list()

    if not repos:
        await update.message.reply_text(
            "📋 You have no registered repositories.\n\n"
            "Use `/git add` to register a repository.\n"
            "Example: `/git add backend MS EcorRouge/backend-api`",
            parse_mode="Markdown"
        )
        return

    # Format repository list
    response_lines = ["📋 *Your Registered Repositories*\n"]

    for repo in repos:
        response_lines.append(f"━━━━━━━━━━━━━━━━━━")
        response_lines.append(f"*{escape_markdown(repo.short_name)}*")
        response_lines.append(f"Repository: {escape_markdown(repo.repo_url)}")
        response_lines.append(f"Jira Prefix: {escape_markdown(repo.jira_prefix)}")

        # Status
        if repo.registered:
            reg_status = "✅ Registered"
        else:
            reg_status = "⏳ Pending"
        response_lines.append(f"Status: {reg_status}")

        if repo.primed:
            prime_status = "✅ Primed"
            if repo.last_primed:
                prime_status += f" ({repo.last_primed.strftime('%Y-%m-%d %H:%M')} UTC)"
        else:
            prime_status = "❌ Not Primed"
        response_lines.append(f"Prime: {prime_status}")
        response_lines.append("")

    await update.message.reply_text(
        "\n".join(response_lines),
        parse_mode="Markdown"
    )

    logger.info(
        "Listed repositories",
        telegram_id=telegram_id,
        count=len(repos)
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
        prime_output = response_data.get("prime_output")

        if not all([task_id, telegram_id, status]):
            logger.warning("Incomplete git response", data=response_data)
            return

        # Update repository status if add (clone + prime) succeeded
        if operation == "git_add" and status == "success" and repo_id:
            try:
                repo = await Repository.get(repo_id)
                if repo:
                    repo.registered = True
                    repo.primed = True
                    repo.last_primed = datetime.utcnow()
                    if prime_output:
                        repo.prime_output = prime_output
                    repo.update_timestamp()
                    await repo.save()
                    logger.info("Updated repository add status", repo_id=repo_id)
            except Exception as e:
                logger.error("Failed to update repository status", error=str(e))

        # Format message based on status with escaped dynamic values
        if status == "success":
            text = f"✅ {escape_markdown(message)}"
            # Include prime output if available
            if prime_output:
                text += f"\n\n*Prime Output:*\n```\n{escape_markdown(prime_output[:1000])}\n```"
                if len(prime_output) > 1000:
                    text += "\n_(Output truncated)_"
        elif status == "failed":
            text = f"❌ {escape_markdown(message)}"
        else:
            text = f"ℹ️ {escape_markdown(message)}"

        # Send message to user
        await application.bot.send_message(
            chat_id=telegram_id,
            text=text,
            parse_mode="Markdown"
        )

        logger.info(
            "Sent git response to user",
            task_id=task_id,
            telegram_id=telegram_id,
            status=status
        )

    except Exception as e:
        logger.error("Error handling git response", error=str(e), data=response_data)
