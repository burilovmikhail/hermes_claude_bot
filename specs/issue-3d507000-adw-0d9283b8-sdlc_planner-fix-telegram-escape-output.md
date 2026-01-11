# Bug: Telegram Markdown Escaping - Underscores Causing Italic Formatting

## Bug Description
When sending messages to Telegram users, the bot uses `parse_mode="Markdown"` in several places. This causes Telegram to interpret certain special characters (especially underscores `_`) as markdown formatting, resulting in unintended text styling. For example, text with underscores like `task_id` or `repo_url` gets converted to italic text, making the output hard to read and potentially obscuring important information.

**Symptoms:**
- Underscores in variable names, file paths, and technical terms are being eaten by Telegram
- Text between underscores is rendered as italic instead of showing the underscore characters
- Code snippets, IDs, and technical content appear improperly formatted

**Expected Behavior:**
- All special markdown characters should be properly escaped before sending to Telegram
- Technical content like variable names, file paths, and IDs should be displayed literally
- Users should see underscores and other special characters as-is

**Actual Behavior:**
- Unescaped underscores cause Telegram to apply italic formatting
- Special characters are being consumed by Telegram's markdown parser
- Technical information becomes difficult to read

## Problem Statement
The bot sends messages to Telegram users with `parse_mode="Markdown"` but does not properly escape special markdown characters in the message content. Telegram's markdown parser treats certain characters as formatting directives:

**Markdown special characters:**
- `_` (underscore) - italic text
- `*` (asterisk) - bold text
- `` ` `` (backtick) - inline code
- `[` and `]` - links
- And others

When these characters appear in dynamic content (like file paths, variable names, repository URLs, task IDs, error messages), they need to be escaped to prevent unintended formatting.

**Affected Areas:**
1. Chat handler responses (AI responses from OpenAI/Claude)
2. ADW workflow responses (status updates with task IDs, repository URLs)
3. Git operation responses (repository names, error messages)
4. Ticket handler responses (Jira ticket details)
5. Error messages throughout the application

## Solution Statement
Create a centralized text escaping utility function that properly escapes all Telegram markdown special characters. This function will be used whenever sending messages that contain dynamic user content or technical information. The solution will:

1. **Create a utility function** `escape_markdown()` in `bot/utils/` to handle escaping of all markdown special characters
2. **Strategically apply escaping** to dynamic content while preserving intentional markdown formatting (like bold/italic in static messages)
3. **Use mixed approach**: Keep `parse_mode="Markdown"` for structured messages that need formatting, but escape all dynamic/user-generated content
4. **Apply escaping in all handlers** where dynamic content is displayed

The approach will preserve intentional formatting (like bold headers using `*Header*`) while escaping dynamic content that should be displayed literally.

## Steps to Reproduce
1. Start the bot and authenticate
2. Send a command that generates output with underscores, such as:
   - `/adw repo:myorg/my_repo Fix the login_handler bug`
   - The bot will respond with task details containing `task_id`, `repo_url`, etc.
3. Observe that underscores in the response are missing and text appears italicized
4. Similarly, any error messages or AI responses containing underscores will have formatting issues

## Root Cause Analysis
The root cause is that the bot uses `parse_mode="Markdown"` when sending messages via Telegram's `reply_text()` and `send_message()` methods, but does not escape special markdown characters in dynamic content.

**Key Issues:**
1. **No escaping function exists**: There is no utility to escape markdown characters
2. **Mixed content problem**: Messages contain both intentional markdown (for headers, structure) and dynamic content (that should be literal)
3. **Multiple locations**: The issue exists across multiple handler files:
   - `bot/handlers/chat_handlers.py` - AI responses may contain underscores
   - `bot/handlers/adw_handlers.py` - Task IDs, repository URLs contain underscores
   - `bot/handlers/git_handlers.py` - Repository names and paths with underscores
   - `bot/handlers/ticket_handlers.py` - Jira content may have underscores
   - `bot/handlers/error_handlers.py` - Error messages with technical content

**Why this happens:**
- When you use `parse_mode="Markdown"`, Telegram parses the entire message as markdown
- Characters like `_text_` are interpreted as `<em>text</em>` (italic)
- Without escaping, all underscores trigger markdown formatting
- This is by design in Telegram's API, not a bug - we need to escape properly

## Relevant Files
Use these files to fix the bug:

- **`bot/utils/constants.py`** - Add the escaping utility function here alongside other utility constants, or create a new utils module
  - Contains utility constants and would be a good place for text formatting utilities

- **`bot/handlers/chat_handlers.py`** - Escape AI response content before sending to user
  - Line 99, 104: `reply_text()` calls that send AI responses
  - AI-generated content may contain underscores in code examples, technical terms

- **`bot/handlers/adw_handlers.py`** - Escape dynamic content in ADW workflow messages
  - Line 229-232: Sending ADW task started message with task_id, repo_url
  - Line 317-320: Sending status updates to users via `send_message()`
  - These contain dynamic values that need escaping

- **`bot/handlers/git_handlers.py`** - Escape repository names and error messages
  - Line 178-185: Clone status messages with repository names
  - Line 254-260: Pull status messages
  - Line 331-334: Git operation responses

- **`bot/handlers/ticket_handlers.py`** - Escape Jira ticket content
  - Line 97-101: Ticket details with AI summary
  - The summary and ticket description may contain markdown special characters

- **`bot/handlers/error_handlers.py`** - Escape error messages
  - Line 31: Error message replies
  - Error messages often contain technical content with underscores

- **`bot/handlers/common_handlers.py`** - Review static messages (likely OK as-is)
  - Static help/welcome messages are controlled and unlikely to have issues

### New Files
- **`bot/utils/text_utils.py`** (if we want to separate text utilities from constants)
  - Would contain `escape_markdown()` and potentially other text formatting utilities

## Step by Step Tasks

### Create Markdown Escaping Utility
- Create a utility function `escape_markdown()` that escapes all Telegram markdown special characters
- The function should escape: `_`, `*`, `` ` ``, `[`, `]`, `(`, `)`, `~`, `>`, `#`, `+`, `-`, `=`, `|`, `{`, `}`, `.`, `!`
- Add this function to `bot/utils/constants.py` or create a new `bot/utils/text_utils.py` module
- Include comprehensive docstring explaining when and how to use the function
- The function should handle None/empty strings gracefully

### Fix Chat Handler (AI Response Escaping)
- In `bot/handlers/chat_handlers.py`, import the escape function
- Escape `response.content` before sending via `reply_text()` at line 99
- Escape each chunk before sending at line 104 (in the split message loop)
- Escape error message content at line 120-123 (the `str(e)` part)
- Test that AI responses with underscores, asterisks, and other special chars display correctly

### Fix ADW Handler (Task and Status Messages)
- In `bot/handlers/adw_handlers.py`, import the escape function
- At lines 211-227 (ADW task started message):
  - Escape `task_id` value
  - Escape `task_data['workflow_name']` value
  - Escape `task_data['repo_url']` value
  - Escape `task_data['jira_ticket']` value
  - Escape `task_data['task_description']` value
- At lines 306-314 (ADW status messages in `handle_adw_response`):
  - Escape `task_id` value
  - Escape `message` value (contains dynamic status content)
- Keep the markdown formatting symbols (`*`, `\n`) but escape the dynamic values

### Fix Git Handler (Repository Messages)
- In `bot/handlers/git_handlers.py`, import the escape function
- At lines 178-185 (clone status message):
  - Escape `short_name` value
  - Escape `jira_prefix` value
  - Escape `short_form` value
- At lines 254-260 (pull status message):
  - Escape `short_name` value
  - Escape `repo.repo_url` value
- At lines 323-328 (git response handler):
  - Escape the `message` value from response_data
- Escape error messages that contain repository information

### Fix Ticket Handler (Jira Content)
- In `bot/handlers/ticket_handlers.py`, import the escape function
- At lines 88-95 (ticket response formatting):
  - Escape `issue['key']` value
  - Escape `issue['summary']` value
  - Escape `issue['status']` value
  - Escape `issue['priority']` value
  - Escape `issue['assignee']` value
  - Escape `response.content` (AI summary content)
  - Keep the URL as-is (it's in markdown link format)
- Escape error messages at lines 117-121

### Fix Error Handler
- In `bot/handlers/error_handlers.py`, import the escape function
- At line 31, the static error message is fine (no dynamic content)
- Consider if `context.error` should be logged but not sent to users (security consideration)

### Add Tests or Manual Testing Checklist
- Test chat responses containing underscores, asterisks, backticks
- Test ADW workflow with repository names containing underscores
- Test git operations with repository names containing special characters
- Test Jira tickets with markdown-like content in descriptions
- Test error scenarios to ensure error messages display correctly
- Verify that intentional markdown formatting (bold headers, etc.) still works
- Verify that URLs in markdown link format `[text](url)` still work

## Notes

### Telegram Markdown Special Characters
According to Telegram Bot API documentation, when using `parse_mode="Markdown"`, these characters need escaping with a backslash (`\`):
- `_` (underscore)
- `*` (asterisk)
- `` ` `` (backtick)
- `[` (left square bracket)

### Alternative: Consider MarkdownV2
Telegram supports both "Markdown" and "MarkdownV2" parse modes. MarkdownV2 is more strict and requires escaping more characters:
- `_`, `*`, `[`, `]`, `(`, `)`, `~`, `` ` ``, `>`, `#`, `+`, `-`, `=`, `|`, `{`, `}`, `.`, `!`

For now, we'll fix the current "Markdown" implementation, but consider migrating to MarkdownV2 or HTML parse mode in the future for better control.

### Implementation Strategy
Use a **selective escaping approach**:
1. For static formatted text (like headers with `*Header*`), don't escape
2. For all dynamic values (variables, user input, API responses), always escape
3. Build messages by combining static markdown strings with escaped dynamic values

Example:
```python
from bot.utils.text_utils import escape_markdown

task_id = "abc_123_def"  # Has underscores
repo_url = "org/my_repo"  # Has underscores

# Wrong - underscores will be interpreted as markdown:
message = f"*Task ID:* {task_id}\n*Repository:* {repo_url}"

# Correct - escape dynamic values:
message = f"*Task ID:* {escape_markdown(task_id)}\n*Repository:* {escape_markdown(repo_url)}"
```

### Security Consideration
- Escaping prevents unintended formatting
- Also helps prevent potential markdown injection attacks
- Users can't inject markdown to spoof bot messages

### Python-telegram-bot Utilities
The `python-telegram-bot` library (v20.7) provides `telegram.helpers.escape_markdown()` utility functions:
- `escape_markdown(text, version=1)` for Markdown
- `escape_markdown(text, version=2)` for MarkdownV2

We can use these built-in utilities instead of writing our own, which would be more maintainable.
