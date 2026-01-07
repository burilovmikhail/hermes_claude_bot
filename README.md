# Hermes Telegram Bot

An intelligent Telegram bot that connects users with both OpenAI GPT and Anthropic Claude AI models. Built with Python, using polling mode for simplicity, and MongoDB for conversation persistence.

## Features

- **Multi-Provider Support**: Chat with both OpenAI GPT-4 and Anthropic Claude
- **Conversation Context**: Maintains conversation history for natural multi-turn conversations
- **Session Management**: Start new conversations while preserving old ones
- **Docker Orchestration**: Easy deployment with Docker Compose
- **Structured Logging**: JSON-formatted logs for production monitoring
- **Retry Logic**: Automatic retry with exponential backoff for API calls
- **Error Handling**: Graceful error handling with user-friendly messages

## Architecture

### Technology Stack

- **Language**: Python 3.11
- **Telegram Library**: python-telegram-bot (v20+)
- **AI SDKs**: OpenAI, Anthropic official SDKs
- **Database**: MongoDB with Beanie ODM
- **Configuration**: Pydantic Settings
- **Deployment**: Docker Compose

### Project Structure

```
Hermes/
├── bot/
│   ├── handlers/          # Telegram command handlers
│   ├── services/          # AI services and conversation logic
│   ├── models/            # MongoDB/Beanie models
│   ├── database/          # Database connection
│   ├── utils/             # Logging and constants
│   ├── config.py          # Configuration management
│   └── main.py            # Application entry point
├── docker-compose.yml     # Docker orchestration
├── Dockerfile             # Bot container definition
├── requirements.txt       # Python dependencies
├── .env.example          # Environment variables template
└── README.md             # This file
```

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Telegram Bot Token (from [@BotFather](https://t.me/botfather))
- OpenAI API Key
- Anthropic API Key

### Setup

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd Hermes
   ```

2. **Configure environment variables**:
   ```bash
   cp .env.example .env
   ```

   Edit `.env` and add your API keys:
   ```ini
   TELEGRAM_API_KEY=your-telegram-bot-token
   OPENAI_API_KEY=sk-your-openai-key
   ANTHROPIC_API_KEY=sk-ant-your-anthropic-key
   ```

3. **Start the bot**:
   ```bash
   docker-compose up -d
   ```

4. **View logs**:
   ```bash
   docker-compose logs -f bot
   ```

5. **Stop the bot**:
   ```bash
   docker-compose down
   ```

## Usage

### Bot Commands

- `/start` - Initialize the bot and create/update user profile
- `/help` - Show available commands and usage examples
- `/chat <message>` - Chat with default AI provider (Claude)
- `/chat_gpt <message>` - Chat with OpenAI GPT-4
- `/chat_claude <message>` - Chat with Anthropic Claude
- `/new` - Start a new conversation session

### Examples

```
/start
/chat Hello, how are you?
/chat_gpt What is the capital of France?
/chat_claude Explain quantum computing in simple terms
/new
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `TELEGRAM_API_KEY` | Telegram bot token from @BotFather | Required |
| `OPENAI_API_KEY` | OpenAI API key | Required |
| `ANTHROPIC_API_KEY` | Anthropic API key | Required |
| `MONGODB_URI` | MongoDB connection string | `mongodb://hermes_user:hermes_pass@mongodb:27017/hermes_bot?authSource=admin` |
| `DEFAULT_AI_PROVIDER` | Default AI provider (openai or claude) | `claude` |
| `MAX_CONTEXT_MESSAGES` | Maximum messages to include in context | `20` |
| `MAX_CONTEXT_TOKENS` | Maximum tokens to include in context | `4000` |
| `LOG_LEVEL` | Logging level (DEBUG, INFO, WARNING, ERROR) | `INFO` |

### MongoDB Configuration

The bot uses MongoDB to store:
- **Users**: Telegram user profiles and preferences
- **Conversations**: Chat sessions with metadata
- **Messages**: Individual messages with role and content

## Development

### Local Development (without Docker)

1. **Install Python 3.11+**

2. **Create virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Start MongoDB locally** (or update `MONGODB_URI` in `.env`)

5. **Run the bot**:
   ```bash
   python -m bot.main
   ```

### Testing

Manual testing checklist:
- [ ] `/start` creates user in MongoDB
- [ ] `/chat_gpt` sends to OpenAI and stores message
- [ ] `/chat_claude` sends to Anthropic and stores message
- [ ] Conversation context maintained across messages
- [ ] `/new` starts fresh session
- [ ] Error handling for invalid API keys
- [ ] Bot restarts preserve conversation history
- [ ] Long responses split correctly (>4096 chars)

## Troubleshooting

### Bot not responding

1. Check if bot is running:
   ```bash
   docker-compose ps
   ```

2. Check logs for errors:
   ```bash
   docker-compose logs bot
   ```

3. Verify environment variables:
   ```bash
   docker-compose exec bot env | grep -E "(TELEGRAM|OPENAI|ANTHROPIC)"
   ```

### Database connection issues

1. Check MongoDB status:
   ```bash
   docker-compose ps mongodb
   ```

2. Verify MongoDB logs:
   ```bash
   docker-compose logs mongodb
   ```

3. Test MongoDB connection:
   ```bash
   docker-compose exec mongodb mongosh -u hermes_user -p hermes_pass
   ```

### API errors

- **OpenAI**: Verify API key has sufficient credits
- **Anthropic**: Ensure API key has correct permissions
- Check rate limits in respective provider dashboards

## Architecture Details

### Conversation Flow

1. User sends command (e.g., `/chat_gpt Hello`)
2. Handler extracts message and provider
3. ConversationService retrieves or creates active session
4. Service loads last N messages from MongoDB
5. AI provider receives message with context
6. Response saved to MongoDB and sent to user

### Session Management

- Each user can have multiple conversations per provider
- Only one conversation per provider is "active" at a time
- `/new` command deactivates current session and creates new one
- Old conversations remain in database for history

### Error Handling

- **API Level**: 3 retries with exponential backoff
- **Handler Level**: User-friendly error messages
- **Global Level**: Catch-all error handler with logging

## License

This project is licensed under the MIT License.

## Support

For issues, questions, or contributions, please open an issue on GitHub.

## Acknowledgments

- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot)
- [OpenAI Python SDK](https://github.com/openai/openai-python)
- [Anthropic Python SDK](https://github.com/anthropics/anthropic-sdk-python)
- [Beanie ODM](https://github.com/roman-right/beanie)
