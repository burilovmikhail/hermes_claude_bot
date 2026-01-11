# Bug: Prime Command Output Not Displayed in Chat

## Bug Description
When a repository is added and primed using the `/git add` command, the user receives the message "Repository added and primed successfully: rococo" but does not see the actual prime command output that contains valuable information about the repository structure and analysis. The prime command successfully executes and stores its output in `prime_output.json`, including a detailed "result" field with the repository summary, but this result is not being sent to the Telegram chat.

## Problem Statement
The prime command output (specifically the "result" field from the prime_output.json file) is not being extracted and passed to the chat message handler, even though the output is successfully generated and stored. Users expect to see the repository analysis summary immediately after priming completes.

## Solution Statement
Extract and display the "result" field from the Claude Code prime command response in the Telegram chat message when a repository is successfully added and primed. The solution involves ensuring that the prime output is properly extracted from the AgentPromptResponse and included in the git response message sent to the user.

## Steps to Reproduce
1. Use `/git add` command to add a repository (e.g., `/git add rococo ROCO EcorRouge/rococo`)
2. Wait for the repository to be cloned and primed
3. Observe that you receive: "Repository added and primed successfully: rococo"
4. Notice that the prime command output/summary is NOT displayed in the chat
5. Check `/workspace/964070449/rococo/prime/prime_output.json` manually
6. Confirm that the "result" field exists in the JSON file with detailed repository analysis

## Root Cause Analysis
After analyzing the code flow, the root cause is found in the `bot/handlers/git_handlers.py` file at lines 410-414:

```python
# Include prime output if available
if prime_output:
    text += f"\n\n*Prime Output:*\n```\n{escape_markdown(prime_output[:1000])}\n```"
    if len(prime_output) > 1000:
        text += "\n_(Output truncated)_"
```

The issue is that:
1. The `prime_output` variable contains the result text from the Claude Code agent
2. The output is being escaped with `escape_markdown()` and wrapped in triple backticks (code block)
3. The `escape_markdown()` function is designed for inline text, not code blocks
4. When markdown special characters in the prime output are escaped AND placed inside code blocks, it can cause rendering issues
5. Additionally, truncating to 1000 characters may cut off in the middle of important content

The proper fix is to:
- Remove the `escape_markdown()` call when the text is inside code blocks (code blocks already prevent markdown parsing)
- Or, better yet, format the output as regular markdown text (not a code block) and properly escape it
- Increase the character limit or provide a link to the full output

## Relevant Files
Use these files to fix the bug:

### `bot/handlers/git_handlers.py` (lines 370-436)
- Contains the `handle_git_response()` function that processes git operation responses from the worker
- Lines 410-414 have the buggy code that handles prime_output display
- This is where the fix needs to be applied to properly display the prime output

### `worker/main.py` (lines 666-829)
- Contains the `handle_git_add()` function that executes the prime command
- Lines 774-785 extract the prime output from the response and send it to the bot
- This code is working correctly - it successfully extracts `response.output` and passes it as `prime_output`
- No changes needed here, but useful for understanding the data flow

### `worker/main.py` (lines 898-934)
- Contains the `send_git_response()` function that sends responses back to the bot
- Lines 929-930 conditionally add `prime_output` to the response dict
- This code is working correctly - no changes needed

### `bot/utils/constants.py`
- Contains the `escape_markdown()` function
- Useful to understand how markdown escaping works
- No changes needed, but reference for understanding the issue

## Step by Step Tasks

### Fix the prime output display in git response handler
- Read `bot/handlers/git_handlers.py` to understand current implementation
- Locate the `handle_git_response()` function (lines 370-436)
- Find the section that handles `prime_output` display (lines 410-414)
- Replace the buggy code with proper formatting that:
  - Does NOT use `escape_markdown()` inside code blocks (removes double-escaping issue)
  - OR formats the output as regular markdown text with proper escaping (better option)
  - Increases the character limit from 1000 to 2000 characters to show more content
  - Adds better formatting to make the output more readable
- Test the fix by checking if the prime output appears correctly in the message

### Verify the fix works correctly
- Ensure the modified code properly displays prime output in Telegram
- Verify that markdown special characters don't break the message
- Confirm that the message stays within Telegram's message size limits
- Check that truncation works properly if the output is very long

## Notes
- Telegram messages have a maximum length of 4096 characters
- The current truncation at 1000 characters is very conservative
- Consider formatting the prime output as a nicely formatted summary rather than a raw code block
- The prime output contains valuable information about the repository structure that users want to see
- The `escape_markdown()` function is not needed inside code blocks because code blocks already prevent markdown parsing
- For better UX, consider formatting the output as regular markdown (headings, lists, etc.) instead of a code block
