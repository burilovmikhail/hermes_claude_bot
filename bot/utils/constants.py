from enum import Enum


class AIProvider(str, Enum):
    """AI provider enum."""

    OPENAI = "openai"
    CLAUDE = "claude"


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
