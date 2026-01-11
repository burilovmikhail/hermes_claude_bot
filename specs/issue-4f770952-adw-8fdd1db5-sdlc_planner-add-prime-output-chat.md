# Feature: Add Prime Output to Chat

## Feature Description
Currently, when users add a repository using `/git add`, the system runs Claude Code's `/prime` command in the worker service but only sends basic success/failure messages to the chat. The prime output contains valuable contextual information about the repository (file structure, key patterns, architecture insights) that would be useful for users to see directly in the Telegram chat. This feature will extract the prime output from Claude Code's `output-format` response and send it to the chat, similar to how the ADW scripts already handle this pattern.

## User Story
As a developer using the Hermes bot
I want to see the prime output in the chat after adding a repository
So that I can immediately understand the repository structure and context without having to check logs or run prime manually

## Problem Statement
When users run `/git add` to register a new repository, the worker service executes `claude prime` but only the stdout is captured and stored. Users don't see the detailed contextual information that Claude Code generates during the prime operation, such as:
- Repository structure overview
- Key architectural patterns identified
- Important files and directories
- Technology stack detected

This information is valuable for understanding what the bot "knows" about the repository and would help users confirm the priming was successful and comprehensive.

## Solution Statement
Modify the worker service to run Claude Code's `prime` command with the `--output-format stream-json` flag (similar to how ADW scripts use it). Parse the JSONL output to extract the result message containing the prime output, then send this formatted output to the user via Telegram. This follows the existing pattern used in `adws/adw_modules/agent.py` where Claude Code is invoked with structured output format for parsing.

The implementation will:
1. Update the git add handler in the worker to use the agent module's `prompt_claude_code` function
2. Parse the JSONL output to extract the prime result
3. Send the prime output to chat via Redis (already has infrastructure for this)
4. Update the git response handler to format and display the prime output nicely

## Relevant Files
Use these files to implement the feature:

- `worker/main.py:handle_git_add` (lines 586-713) - Currently runs `claude prime` with basic subprocess. Needs to use the agent module pattern to get structured output.
  - Why: This is where the prime command is executed. We need to modify this to use `--output-format stream-json` and parse the result.

- `adws/adw_modules/agent.py:prompt_claude_code` (lines 161-246) - Existing function that runs Claude Code with `--output-format stream-json` and parses JSONL output.
  - Why: This demonstrates the exact pattern we need to follow - running claude with output format and parsing the result.

- `adws/adw_modules/agent.py:parse_jsonl_output` (lines 39-62) - Parses JSONL output and extracts result message.
  - Why: This function can be reused or referenced to extract the prime output from the JSONL file.

- `worker/main.py:send_git_response` (lines 716-752) - Sends git operation results to bot via Redis, including optional prime_output field.
  - Why: This already has infrastructure to send prime_output, just needs to receive the parsed data.

- `bot/handlers/git_handlers.py:handle_git_response` (lines 272-337) - Handles git responses and displays to user, already shows prime_output if present.
  - Why: This already formats and displays prime_output in chat. The implementation is complete on this end.

- `bot/models/repository.py` (lines 31-34) - Repository model that stores prime_output field.
  - Why: Confirms the data model already supports storing prime output.

### New Files
No new files need to be created. All functionality can be added to existing files.

## Implementation Plan

### Phase 1: Foundation
Before implementing the main feature, we need to make the agent module accessible to the worker service and understand the data flow:
1. Verify that the worker service can import the agent module (it should be copied to the repo during ADW workflow setup)
2. Review the existing prime execution in `worker/main.py:handle_git_add`
3. Review the existing pattern in `adws/adw_modules/agent.py:prompt_claude_code` for running claude with output format

### Phase 2: Core Implementation
Modify the worker service to run Claude Code with structured output and parse the result:
1. Update `worker/main.py:handle_git_add` to run claude with `--output-format stream-json`
2. Save the output to a JSONL file in a temporary location
3. Parse the JSONL output using the pattern from `agent.py:parse_jsonl_output`
4. Extract the prime result text from the result message
5. Pass the prime output to `send_git_response` (already supports this parameter)

### Phase 3: Integration
Ensure the prime output flows correctly through the system:
1. Verify that the prime output is sent via Redis to the bot
2. Verify that the bot handler displays the prime output correctly (already implemented)
3. Test the full flow from `/git add` command to chat output display

## Step by Step Tasks
IMPORTANT: Execute every step in order, top to bottom.

### 1. Analyze Current Implementation
- Read `worker/main.py:handle_git_add` to understand the current prime execution
- Identify where `subprocess.run` is called for the prime command (around line 651)
- Note the current error handling and timeout configuration

### 2. Add Agent Module Support to Worker
- Import necessary functions from the agent module at the top of `worker/main.py`
- Import `prompt_claude_code`, `AgentPromptRequest` from `adw_modules.agent`
- Handle import gracefully in case agent module is not available (shouldn't happen but defensive)

### 3. Create JSONL Output Directory Structure
- In `handle_git_add`, create a directory structure for storing prime output
- Use pattern: `{workspace}/{telegram_id}/{short_name}/prime_output.jsonl`
- Create the directory if it doesn't exist before running prime

### 4. Update Prime Command Execution
- Replace the subprocess.run call for prime with the agent pattern
- Build the prompt string: `/prime`
- Create an `AgentPromptRequest` with:
  - prompt: `/prime`
  - adw_id: Use `task_id` as adw_id
  - agent_name: "git_prime"
  - model: "sonnet" (default)
  - dangerously_skip_permissions: True (automated context)
  - output_file: path to prime_output.jsonl
- Call `prompt_claude_code(request)` and capture the response

### 5. Handle Prime Response
- Check `response.success` to determine if prime succeeded
- If success: extract `response.output` (this contains the parsed prime result)
- If error: use the existing error handling path
- Pass the prime output text to `send_git_response` as before

### 6. Update Error Handling
- Ensure timeout errors are handled (agent module has 5-minute timeout)
- Ensure parse errors are handled gracefully
- Log errors appropriately using the existing logger

### 7. Test the Implementation
- Add logging to verify the prime output is being captured
- Add logging to verify the JSONL parsing is working
- Test with a small repository first
- Verify the output is sent to chat correctly

## Testing Strategy

### Unit Tests
This feature primarily involves integration with external systems (Claude Code CLI, Redis, Telegram), so unit tests are less critical than integration testing. However, key testable components include:
- Parsing JSONL output format
- Error handling for malformed output
- Directory creation logic

### Edge Cases
Test the following scenarios to ensure robust behavior:
1. **Prime command fails** - Claude Code returns non-zero exit code
   - Expected: Error message sent to chat, repository not marked as primed
2. **Prime output is empty** - Claude Code succeeds but returns no output
   - Expected: Success message but no prime output shown
3. **Prime output is very large** (>4KB) - Output exceeds Telegram message limit
   - Expected: Output is truncated with indication (already handled in git_handlers.py:314)
4. **JSONL parsing fails** - Output file is malformed or incomplete
   - Expected: Fallback to raw output or error message
5. **Agent module not available** - Import fails in worker
   - Expected: Graceful degradation to old behavior or clear error message
6. **Timeout during prime** - Repository is very large and prime takes >5 minutes
   - Expected: Timeout error message, repository not marked as primed
7. **Directory creation fails** - Insufficient permissions
   - Expected: Clear error message about filesystem issue

## Acceptance Criteria
The feature is considered complete when:

1. **Prime output is captured**: When `/git add` is executed, the worker service runs `claude prime` with `--output-format stream-json` and saves output to a JSONL file
2. **Output is parsed correctly**: The JSONL output is parsed to extract the result message containing the prime summary
3. **Output is sent to chat**: The prime output is sent via Redis to the bot and displayed in the Telegram chat
4. **Output is formatted nicely**: The prime output is displayed in a code block or formatted section, truncated if necessary (already implemented in git_handlers.py)
5. **Errors are handled gracefully**: If prime fails or parsing fails, appropriate error messages are shown to the user
6. **Repository is marked as primed**: The repository model's `primed` field is set to true and `prime_output` is stored in MongoDB
7. **Existing functionality is preserved**: The `/git add` command continues to work as before, just with additional output
8. **Logging is comprehensive**: All steps (command execution, parsing, sending) are logged for debugging

## Notes

### Implementation Pattern Reference
The ADW scripts already implement this exact pattern. See `adws/adw_modules/agent.py:prompt_claude_code` for the reference implementation:
```python
# Build command with stream-json format
cmd = [CLAUDE_PATH, "-p", request.prompt]
cmd.extend(["--model", request.model])
cmd.extend(["--output-format", "stream-json"])
cmd.append("--verbose")

# Execute and save to file
with open(request.output_file, "w") as f:
    result = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, text=True, env=env)

# Parse the JSONL output
messages, result_message = parse_jsonl_output(request.output_file)
result_text = result_message.get("result", "")
```

### Alternative Approaches Considered
1. **Parse stdout directly without file**: Could parse the streaming JSON output directly, but saving to file provides better debugging and is the established pattern
2. **Use separate prime command module**: Could create a dedicated module for prime operations, but the agent module already provides the needed functionality
3. **Send prime output in chunks**: For very large outputs, could send multiple messages, but the existing truncation logic is simpler and sufficient

### Dependencies
- No new Python packages required
- Relies on existing `claude` CLI being installed and available (already required)
- Uses existing Redis infrastructure for message passing
- Uses existing MongoDB models for storage

### Future Enhancements
- Add a `/git prime` command to allow users to re-prime repositories manually
- Store prime history to track changes over time
- Add filtering options to show only specific parts of prime output (e.g., "show me the API routes")
- Support prime on specific branches, not just main
