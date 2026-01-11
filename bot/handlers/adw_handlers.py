import structlog
import uuid
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ChatAction

from bot.services.adw_parser import ADWParser
from bot.services.jira_service import JiraService
from bot.services.redis_service import RedisService
from bot.config import settings
from bot.utils.auth import authorized_users_only
from bot.models.repository import Repository
from bot.utils.constants import escape_markdown

logger = structlog.get_logger()


# Global Redis service instance (will be initialized in main.py)
redis_service: RedisService = None


def set_redis_service(service: RedisService):
    """Set the global Redis service instance."""
    global redis_service
    redis_service = service


async def resolve_repository(
    telegram_id: int,
    parsed: dict
) -> tuple[str | None, str | None]:
    """
    Resolve repository URL from parsed command data.

    Priority:
    1. Explicit github_repo (owner/repo format)
    2. Repository alias lookup
    3. Jira prefix lookup

    Args:
        telegram_id: User's Telegram ID
        parsed: Parsed ADW command data

    Returns:
        Tuple of (repo_url, error_message). repo_url is None if not found.
    """
    # 1. If explicit GitHub repo provided, use it
    if parsed.get("github_repo"):
        return parsed["github_repo"], None

    # 2. Try repo alias
    if parsed.get("repo_alias"):
        repo = await Repository.find_one(
            Repository.telegram_id == telegram_id,
            Repository.short_name == parsed["repo_alias"]
        )
        if repo:
            logger.info(
                "Resolved repository by alias",
                alias=parsed["repo_alias"],
                repo_url=repo.repo_url
            )
            return repo.repo_url, None
        else:
            return None, (
                f"Repository alias '{parsed['repo_alias']}' not found. "
                "Use /git list to see your repositories."
            )

    # 3. Try Jira prefix
    if parsed.get("jira_prefix"):
        repo = await Repository.find_one(
            Repository.telegram_id == telegram_id,
            Repository.jira_prefix == parsed["jira_prefix"]
        )
        if repo:
            logger.info(
                "Resolved repository by Jira prefix",
                jira_prefix=parsed["jira_prefix"],
                repo_url=repo.repo_url
            )
            return repo.repo_url, None
        else:
            return None, (
                f"No repository found for Jira prefix '{parsed['jira_prefix']}'. "
                f"Please specify the repository using 'in the <alias> repo' or register it with /git add."
            )

    return None, "Could not resolve repository"


@authorized_users_only
async def adw_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /adw command (AI-Driven Workflow).

    Parses the command, resolves repository, fetches Jira details if needed,
    and sends task to worker.

    Usage: /adw [workflow:name] in the <alias> repo <task description> [JIRA-123]

    Examples:
      /adw in the bot repo implement git list command
      /adw in the ms-backend repo fix the MS-113 issue
      /adw workflow:plan_build in backend repo add authentication
      /adw repo:myorg/myrepo Fix the login bug MS-1234

    Repository resolution:
      1. Explicit: repo:owner/repo format
      2. Alias: "in the <alias> repo" (must be registered with /git add)
      3. Jira prefix: If JIRA-123 is provided, finds repo by prefix "JIRA"
    """
    user = update.effective_user
    telegram_id = user.id

    # Extract command text
    message_text = update.message.text.replace("/adw", "", 1).strip()

    if not message_text:
        await update.message.reply_text(
            "Please provide task details.\n\n"
            "Usage: /adw [workflow:name] [repo:owner/repo] <task description> [JIRA-123]\n\n"
            "Examples:\n"
            "  /adw repo:myorg/myrepo Fix the login bug MS-1234\n"
            "  /adw workflow:build_test repo:myorg/myrepo Implement new feature\n\n"
            "Default workflow: plan_build_test"
        )
        return

    logger.info(
        "Processing ADW request",
        telegram_id=telegram_id,
        message_text=message_text
    )

    # Show typing indicator
    await update.message.chat.send_action(ChatAction.TYPING)

    try:
        # Parse the command
        parsed = ADWParser.parse(message_text)

        # Validate parsed data
        is_valid, error_msg = ADWParser.validate(parsed)
        if not is_valid:
            await update.message.reply_text(f"Invalid command: {error_msg}")
            return

        # Resolve repository
        repo_url, repo_error = await resolve_repository(telegram_id, parsed)
        if not repo_url:
            await update.message.reply_text(f"❌ {escape_markdown(repo_error)}")
            return

        # Generate task ID
        task_id = str(uuid.uuid4())

        # Prepare task data
        task_data = {
            "task_id": task_id,
            "telegram_id": telegram_id,
            "workflow_name": parsed["workflow_name"],
            "repo_url": repo_url,  # Use resolved repo_url instead of github_repo
            "task_description": parsed["task_description"],
            "jira_ticket": parsed["jira_ticket"],
            "jira_details": None,
            "reporting_level": parsed["reporting_level"],
            "timestamp": datetime.utcnow().isoformat()
        }

        # If Jira ticket is specified, fetch details and comments
        if parsed["jira_ticket"]:
            try:
                jira_service = JiraService(
                    jira_url=settings.jira_url,
                    email=settings.jira_email,
                    api_token=settings.jira_api_token,
                )

                issue = await jira_service.get_issue_with_comments(parsed["jira_ticket"])

                if issue:
                    task_data["jira_details"] = issue
                    logger.info(
                        "Fetched Jira details for ADW task",
                        task_id=task_id,
                        jira_ticket=parsed["jira_ticket"]
                    )
                else:
                    await update.message.reply_text(
                        f"Warning: Jira ticket {escape_markdown(parsed['jira_ticket'])} not found. "
                        "Proceeding without Jira details."
                    )
            except Exception as e:
                logger.error(
                    "Failed to fetch Jira details for ADW task",
                    task_id=task_id,
                    jira_ticket=parsed["jira_ticket"],
                    error=str(e)
                )
                await update.message.reply_text(
                    f"Warning: Could not fetch Jira ticket {escape_markdown(parsed['jira_ticket'])}: {escape_markdown(str(e))}\n"
                    "Proceeding without Jira details."
                )

        # Send task to worker via Redis
        if redis_service:
            success = await redis_service.publish_task(task_data)

            if success:
                # Format response message with escaped dynamic values
                response_parts = [
                    f"🚀 *AI-Driven Workflow Started*",
                    f"",
                    f"*Task ID:* `{escape_markdown(task_id)}`",
                    f"*Workflow:* {escape_markdown(task_data['workflow_name'])}",
                    f"*Repository:* {escape_markdown(task_data['repo_url'])}",
                ]

                if task_data.get("jira_ticket"):
                    response_parts.append(f"*Jira Ticket:* {escape_markdown(task_data['jira_ticket'])}")

                response_parts.extend([
                    f"",
                    f"*Task:* {escape_markdown(task_data['task_description'])}",
                    f"",
                    f"I'll notify you when the workflow completes."
                ])

                await update.message.reply_text(
                    "\n".join(response_parts),
                    parse_mode="Markdown"
                )

                logger.info(
                    "ADW task queued successfully",
                    task_id=task_id,
                    telegram_id=telegram_id
                )
            else:
                await update.message.reply_text(
                    "Failed to queue the task. Please try again later."
                )
        else:
            await update.message.reply_text(
                "Worker service is not available. Please contact the administrator."
            )
            logger.error("Redis service not initialized")

    except Exception as e:
        logger.error(
            "Error processing ADW request",
            telegram_id=telegram_id,
            error=str(e)
        )
        await update.message.reply_text(
            f"Sorry, I encountered an error processing your request:\n{escape_markdown(str(e))}"
        )


async def handle_worker_response(response_data: dict, application):
    """
    Handle responses from worker service.

    Routes to appropriate handler based on operation type.

    Args:
        response_data: Response data from worker
        application: Telegram application instance
    """
    try:
        operation = response_data.get("operation", "adw")

        # Route to appropriate handler
        if operation in ["git_clone", "git_pull"]:
            # Import here to avoid circular dependency
            from bot.handlers.git_handlers import handle_git_response
            await handle_git_response(response_data, application)
        else:
            # Handle ADW responses
            await handle_adw_response(response_data, application)

    except Exception as e:
        logger.error("Error routing worker response", error=str(e), data=response_data)


async def handle_adw_response(response_data: dict, application):
    """
    Handle ADW workflow responses from worker service.

    Args:
        response_data: Response data from worker
        application: Telegram application instance
    """
    try:
        task_id = response_data.get("task_id")
        telegram_id = response_data.get("telegram_id")
        status = response_data.get("status")
        message = response_data.get("message", "")

        if not all([task_id, telegram_id, status]):
            logger.warning("Incomplete ADW response", data=response_data)
            return

        # Format message based on status with escaped dynamic values
        if status == "started":
            text = f"⚙️ *Workflow Started*\n\nTask ID: `{escape_markdown(task_id)}`\n{escape_markdown(message)}"
        elif status == "finished":
            text = f"✅ *Workflow Completed*\n\nTask ID: `{escape_markdown(task_id)}`\n{escape_markdown(message)}"
        elif status == "failed":
            text = f"❌ *Workflow Failed*\n\nTask ID: `{escape_markdown(task_id)}`\n{escape_markdown(message)}"
        elif status == "progress":
            # Simplified progress format - no "Progress Update" title or task_id
            text = f"🔄 {escape_markdown(message)}"
        else:
            text = f"📝 *Update*\n\nTask ID: `{escape_markdown(task_id)}`\n{escape_markdown(message)}"

        # Send message to user
        await application.bot.send_message(
            chat_id=telegram_id,
            text=text,
            parse_mode="Markdown"
        )

        logger.info(
            "Sent ADW response to user",
            task_id=task_id,
            telegram_id=telegram_id,
            status=status
        )

    except Exception as e:
        logger.error("Error handling ADW response", error=str(e), data=response_data)
