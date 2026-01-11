from enum import Enum
from telegram.helpers import escape_markdown as telegram_escape_markdown


class AIProvider(str, Enum):
    """AI provider enum."""

    OPENAI = "openai"
    CLAUDE = "claude"


def escape_markdown(text: str | None) -> str:
    """
    Escape special markdown characters for Telegram messages.

    This function wraps telegram.helpers.escape_markdown() to properly escape
    all Telegram markdown special characters, preventing unintended formatting
    when sending dynamic content (like variable names, file paths, repository URLs,
    task IDs, error messages, etc.).

    When using parse_mode="Markdown" in Telegram messages, special characters
    like underscores (_), asterisks (*), and backticks (`) are interpreted as
    markdown formatting. This function escapes those characters so they display
    literally instead of being parsed as formatting.

    Args:
        text: The text to escape. Can be None or empty string.

    Returns:
        Escaped text safe for Telegram markdown, or empty string if input is None/empty.

    Example:
        >>> task_id = "abc_123_def"  # Has underscores
        >>> repo_url = "org/my_repo"  # Has underscores
        >>> # Wrong - underscores will be interpreted as markdown:
        >>> message = f"*Task ID:* {task_id}"
        >>> # Correct - escape dynamic values:
        >>> message = f"*Task ID:* {escape_markdown(task_id)}"

    Note:
        - Use this for ALL dynamic/user-generated content
        - Do NOT use this for static markdown formatting (like *Header*)
        - Build messages by combining static markdown with escaped dynamic values
    """
    if not text:
        return ""
    return telegram_escape_markdown(str(text), version=1)


# Telegram message limits
TELEGRAM_MAX_MESSAGE_LENGTH = 4096

# Error messages
ERROR_MESSAGE_EMPTY = "Please provide a message after the command."
ERROR_MESSAGE_GENERAL = (
    "Sorry, I encountered an error. Please try again later or use /new to start a fresh conversation."
)
ERROR_MESSAGE_UNKNOWN_PROVIDER = "Unknown AI provider: {provider}"

# Success messages
MESSAGE_NEW_CONVERSATION = "Started a new conversation session.\nProvider: {provider}\nSession ID: {session_id}"
MESSAGE_WELCOME = """Hello {first_name}!

I'm Hermes, your AI assistant bot. I can connect you with both OpenAI and Anthropic Claude.

Available commands:
/chat <message> - Chat with default AI (Claude)
/chat_gpt <message> - Chat with OpenAI GPT
/chat_claude <message> - Chat with Anthropic Claude
/new - Start a new conversation
/help - Show this help message

Just send me a message using any of the chat commands!"""

MESSAGE_HELP = """Hermes Bot - AI Assistant

Available commands:

/start - Initialize the bot
/help - Show this help message
/new - Start a new conversation session

Chat commands:
/chat <message> - Chat with default AI (Claude)
/chat_gpt <message> - Chat with OpenAI GPT-4
/chat_claude <message> - Chat with Anthropic Claude

Examples:
/chat Hello, how are you?
/chat_gpt What is the capital of France?
/chat_claude Explain quantum computing

The bot maintains conversation context, so follow-up messages will remember previous messages in the same session."""
