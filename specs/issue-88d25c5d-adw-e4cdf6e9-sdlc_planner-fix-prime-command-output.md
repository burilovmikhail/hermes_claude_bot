# Bug: Prime Command Output Not Sent to Chat

## Bug Description
When users add a repository using `/git add`, the worker service successfully runs Claude Code's `/prime` command and generates output files (`prime_output.json` and `prime_output.jsonl`), but the prime output is not being sent to the Telegram chat. The user only receives the message "Repository added and primed successfully: rococo" without the actual prime analysis that describes the repository structure, patterns, and architecture.

The logs show that:
1. The repository is cloned successfully
2. Claude commands are copied to the repository
3. The `/prime` command is executed with the agent module
4. Output files are created successfully at `/workspace/964070449/rococo/prime/prime_output.json`
5. A success response is sent with message "Repository added and primed successfully: rococo"
6. However, the prime output content is not included in the chat message

## Problem Statement
The `handle_git_add` function in `worker/main.py` successfully executes the `/prime` command and generates structured output, but it fails to extract and send the actual prime analysis text to the user. The `response.output` from `prompt_claude_code` contains the parsed result message, but this output is not being passed to the `send_git_response` function, so users don't see the valuable context that Claude Code generated about their repository.

## Solution Statement
Extract the prime output text from the `AgentPromptResponse.output` field and pass it to the `send_git_response` function as the `prime_output` parameter. This will ensure that the bot handler receives the prime analysis text and displays it in the Telegram chat with proper formatting.

## Steps to Reproduce
1. Send `/git add rococo PROJ EcorRouge/rococo` command in Telegram
2. Wait for the worker to clone the repository and run prime
3. Observe the chat message received
4. Expected: Should see prime output with repository analysis
5. Actual: Only see "Repository added and primed successfully: rococo"
6. Verify: Check logs showing the prime command ran successfully
7. Verify: Check that `prime_output.json` file exists and contains data

## Root Cause Analysis
Looking at `worker/main.py:handle_git_add` around lines 774-784:

```python
# Handle response
if response.success:
    prime_output = response.output
    await self.send_git_response(
        task_id,
        telegram_id,
        "success",
        f"Repository added and primed successfully: {short_name}",
        "git_add",
        repo_id,
        prime_output  # <-- This is being passed
    )
```

The code correctly extracts `prime_output = response.output` and passes it to `send_git_response`. Let me check the `send_git_response` function at lines 898-934:

```python
async def send_git_response(
    self,
    task_id: str,
    telegram_id: int,
    status: str,
    message: str,
    operation: str,
    repo_id: str,
    prime_output: str = None  # <-- Parameter exists
):
    try:
        response = {
            "task_id": task_id,
            "telegram_id": telegram_id,
            "status": status,
            "message": message,
            "operation": operation,
            "repo_id": repo_id
        }
        if prime_output is not None:
            response["prime_output"] = prime_output  # <-- Should be added
```

The function accepts `prime_output` and should add it to the response dict. However, looking at the issue more carefully, the problem is that `response.output` from the agent module contains the full result message text from Claude Code, not just a summary.

Actually, examining the `agent.py:prompt_claude_code` function at lines 206-224, I can see it extracts the "result" field from the result message:

```python
if result_message:
    # Extract session_id from result message
    session_id = result_message.get("session_id")

    # Check if there was an error in the result
    is_error = result_message.get("is_error", False)
    subtype = result_message.get("subtype", "")

    # Handle error_during_execution case where there's no result field
    if subtype == "error_during_execution":
        error_msg = "Error during execution: Agent encountered an error and did not return a result"
        return AgentPromptResponse(
            output=error_msg, success=False, session_id=session_id
        )

    result_text = result_message.get("result", "")

    return AgentPromptResponse(
        output=result_text, success=not is_error, session_id=session_id
    )
```

**THE ROOT CAUSE**: Looking at the JSON output provided in the bug report, the messages array shows that the last message is an assistant message, not a "result" type message. The JSONL stream was cut off in the log output, so we can't see if there's a result message at the end.

However, the real issue is that when `/prime` runs, it doesn't produce a "result" type message by default. The `/prime` command in Claude Code produces assistant messages with text output, but the `parse_jsonl_output` function specifically looks for a message with `type == "result"`.

If no result message is found (which is the case for `/prime`), the code at lines 226-232 handles this:

```python
else:
    # No result message found, return raw output
    with open(request.output_file, "r") as f:
        raw_output = f.read()
    return AgentPromptResponse(
        output=raw_output, success=True, session_id=None
    )
```

This returns the entire raw JSONL as a string, which is not what we want to send to chat. We need to extract the assistant's text messages instead.

The actual root cause is: **The `/prime` command produces assistant messages with text content, but the agent module's `prompt_claude_code` function only extracts result-type messages. When no result message is found, it returns the raw JSONL content, which is not user-friendly.**

## Relevant Files
Use these files to fix the bug:

- `adws/adw_modules/agent.py:parse_jsonl_output` (lines 39-62) - Parses JSONL output but only looks for result-type messages. Needs to extract assistant text messages when no result message exists.
  - Why: This is where the parsing logic needs to be enhanced to handle `/prime` output which produces assistant messages, not result messages.

- `adws/adw_modules/agent.py:prompt_claude_code` (lines 161-246) - Uses parse_jsonl_output and handles the response. Currently returns raw JSONL when no result message found.
  - Why: The fallback logic needs to extract text from assistant messages instead of returning raw JSONL.

- `worker/main.py:handle_git_add` (lines 745-807) - Calls prompt_claude_code and handles the response.
  - Why: Already correctly passing prime_output to send_git_response, no changes needed here.

- `worker/main.py:send_git_response` (lines 898-934) - Sends response with prime_output.
  - Why: Already correctly adds prime_output to response dict, no changes needed here.

- `bot/handlers/git_handlers.py:handle_git_response` (lines 370-436) - Displays prime_output in chat.
  - Why: Already correctly formats and displays prime_output, no changes needed here.

## Step by Step Tasks
IMPORTANT: Execute every step in order, top to bottom.

### 1. Enhance parse_jsonl_output to Extract Assistant Messages
- Read `adws/adw_modules/agent.py:parse_jsonl_output` function (lines 39-62)
- Add logic to extract text content from assistant messages when no result message is found
- Create a new helper function to concatenate all assistant message text content
- Return both the result message (if exists) and the concatenated assistant text

### 2. Update prompt_claude_code Fallback Logic
- Read `adws/adw_modules/agent.py:prompt_claude_code` function (lines 161-246)
- Update the fallback logic at lines 226-232 to use the extracted assistant text instead of raw JSONL
- When no result message exists, extract assistant text from parsed messages
- Format the assistant text for readability (concatenate with newlines)
- Return the formatted assistant text in the AgentPromptResponse

### 3. Add Helper Function for Text Extraction
- Create a new function `extract_assistant_text_from_messages` in `agent.py`
- Function should take the messages list from parse_jsonl_output
- Iterate through messages and find all assistant-type messages
- Extract text content from each assistant message
- Concatenate the text with proper spacing and return as a single string

### 4. Handle Edge Cases
- Handle case where messages list is empty
- Handle case where assistant messages have no text content
- Handle case where text is in different formats (string vs dict)
- Ensure the function doesn't crash on unexpected message structures

### 5. Test the Fix
- Test with a repository that has `/prime` command to verify output extraction
- Verify the prime output appears in Telegram chat with proper formatting
- Verify the output is readable and not raw JSONL
- Test error cases to ensure graceful degradation

## Notes

### Example JSONL Structure for /prime
Based on the bug report logs, the `/prime` command produces output like:

```json
{
  "type": "assistant",
  "message": {
    "model": "claude-sonnet-4-5-20250929",
    "id": "msg_0112hFUdomLWK7NYvwiVRP5C",
    "type": "message",
    "role": "assistant",
    "content": [
      {
        "type": "text",
        "text": "I'll help you understand the codebase by first listing all files and then reading the README."
      }
    ],
    "stop_reason": null,
    ...
  },
  ...
}
```

The assistant messages contain a `message.content` array with text objects. We need to extract this text.

### Text Extraction Pattern
To extract text from assistant messages:

1. Filter messages where `type == "assistant"`
2. For each assistant message, access `message.content`
3. For each content item, if `type == "text"`, extract the `text` field
4. Concatenate all extracted text with newlines

### Why This Approach
- Minimal code changes - only affects the agent module parsing
- Reuses existing infrastructure - no changes to worker or bot handlers
- Handles both result-type and assistant-type messages
- Maintains backward compatibility with ADW scripts that use result messages
- Provides clean, readable output to users

### Alternative Approaches Considered

1. **Change /prime to produce result message** - Modify Claude Code behavior
   - Rejected: Can't control Claude Code's internal behavior

2. **Parse JSONL in worker service** - Add parsing logic to worker
   - Rejected: Violates DRY, agent module should handle all Claude Code output parsing

3. **Return raw JSONL and parse in bot** - Move parsing to bot handler
   - Rejected: Wrong layer, bot should only format for display, not parse

4. **Add specific /prime handling in worker** - Special case for prime command
   - Rejected: Agent module should handle all Claude Code output uniformly
