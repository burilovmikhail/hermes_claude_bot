import structlog
import re
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ChatAction

from bot.services.jira_service import JiraService
from bot.services.openai_service import OpenAIService
from bot.config import settings
from bot.utils.auth import authorized_users_only

logger = structlog.get_logger()


@authorized_users_only
async def ticket_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /ticket command.
    Fetch Jira ticket details and provide AI-generated summary.

    Usage: /ticket MS-1234
    """
    user = update.effective_user
    telegram_id = user.id

    # Extract ticket ID from command
    message_text = update.message.text.replace("/ticket", "", 1).strip()

    if not message_text:
        await update.message.reply_text(
            "Please provide a ticket ID.\n"
            "Example: /ticket MS-1234"
        )
        return

    # Validate ticket ID format (PROJECT-NUMBER)
    ticket_id = message_text.strip().upper()
    if not re.match(r"^[A-Z]+-\d+$", ticket_id):
        await update.message.reply_text(
            f"Invalid ticket ID format: {ticket_id}\n"
            "Expected format: PROJECT-NUMBER (e.g., MS-1234)"
        )
        return

    logger.info(
        "Processing ticket request",
        telegram_id=telegram_id,
        ticket_id=ticket_id,
    )

    # Show typing indicator
    await update.message.chat.send_action(ChatAction.TYPING)

    try:
        # Initialize Jira service
        jira_service = JiraService(
            jira_url=settings.jira_url,
            email=settings.jira_email,
            api_token=settings.jira_api_token,
        )

        # Fetch ticket details
        issue = await jira_service.get_issue(ticket_id)

        if not issue:
            await update.message.reply_text(
                f"Ticket {ticket_id} not found.\n"
                "Please check the ticket ID and try again."
            )
            return

        # Format ticket details for AI summarization
        ticket_details = _format_ticket_for_summary(issue)

        # Use OpenAI to generate summary
        ai_service = OpenAIService(api_key=settings.openai_api_key)

        prompt = (
            "Please provide a brief, clear summary of this Jira ticket. "
            "Include the key points, current status, and any important details. "
            "Keep it concise (3-5 sentences).\n\n"
            f"{ticket_details}"
        )

        response = await ai_service.send_message(prompt, [])

        # Format final response
        response_text = (
            f"🎫 *{issue['key']}*: {issue['summary']}\n\n"
            f"📊 *Status:* {issue['status']}\n"
            f"⚡ *Priority:* {issue['priority']}\n"
            f"👤 *Assignee:* {issue['assignee']}\n"
            f"🔗 [View in Jira]({issue['url']})\n\n"
            f"*AI Summary:*\n{response.content}"
        )

        await update.message.reply_text(
            response_text,
            parse_mode="Markdown",
            disable_web_page_preview=True,
        )

        logger.info(
            "Ticket request processed successfully",
            telegram_id=telegram_id,
            ticket_id=ticket_id,
            tokens_used=response.tokens_used,
        )

    except Exception as e:
        logger.error(
            "Error processing ticket request",
            telegram_id=telegram_id,
            ticket_id=ticket_id,
            error=str(e),
        )
        await update.message.reply_text(
            f"Sorry, I encountered an error while fetching ticket {ticket_id}:\n"
            f"{str(e)}\n\n"
            "Please check your Jira configuration and try again."
        )


def _format_ticket_for_summary(issue: dict) -> str:
    """
    Format Jira issue details for AI summarization.

    Args:
        issue: Issue data from Jira service

    Returns:
        Formatted string for AI processing
    """
    components_str = ", ".join(issue["components"]) if issue["components"] else "None"
    labels_str = ", ".join(issue["labels"]) if issue["labels"] else "None"

    return (
        f"Ticket: {issue['key']}\n"
        f"Type: {issue['issue_type']}\n"
        f"Summary: {issue['summary']}\n"
        f"Status: {issue['status']}\n"
        f"Priority: {issue['priority']}\n"
        f"Assignee: {issue['assignee']}\n"
        f"Reporter: {issue['reporter']}\n"
        f"Components: {components_str}\n"
        f"Labels: {labels_str}\n"
        f"Created: {issue['created']}\n"
        f"Updated: {issue['updated']}\n\n"
        f"Description:\n{issue['description']}"
    )
