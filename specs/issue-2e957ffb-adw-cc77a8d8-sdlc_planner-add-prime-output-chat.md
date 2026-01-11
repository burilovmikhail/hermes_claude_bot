# Feature: Add Prime Output to Chat

## Feature Description
Currently, when users add a repository using `/git add`, the system runs Claude Code's `/prime` command in the worker service but only captures basic stdout output. The prime command, when run with the `--output-format stream-json` flag, returns structured JSONL output containing rich contextual information about the repository including file structure, key patterns, architecture insights, and technology stack details. This feature will use the same approach as the ADW scripts (specifically `adws/adw_modules/agent.py`) to run Claude with structured output format, extract the parsed result, and send it to chat so users can immediately see what the bot learned about their repository.

## User Story
As a developer using the Hermes bot
I want to see the detailed prime output in the chat after adding a repository
So that I can immediately understand what context the bot has about the repository structure, patterns, and architecture without checking logs or running commands manually

## Problem Statement
When users run `/git add` to register a new repository, the worker service executes `claude prime` with basic subprocess.run, capturing only stdout. This approach has several limitations:
- Only raw stdout is captured, missing the rich structured output Claude Code can provide
- No parsing of the result message, which contains the actual prime summary
- Users don't see the detailed analysis that Claude generates during priming
- The output quality is inconsistent and not formatted for readability

The ADW scripts already demonstrate a better pattern: using `--output-format stream-json` to get structured JSONL output, parsing it with `parse_jsonl_output()`, and extracting the result message. This provides much richer, more readable output.

## Solution Statement
Refactor the worker service's `handle_git_add` function to use the agent module pattern for running Claude Code's prime command. Specifically:
1. Use the existing `prompt_claude_code` function from `adws/adw_modules/agent.py` with `/prime` as the prompt
2. This will automatically run claude with `--output-format stream-json` and parse the JSONL output
3. Extract the result text from the AgentPromptResponse
4. Send this formatted prime output to chat via the existing Redis infrastructure

This approach reuses proven code from the ADW scripts, ensures consistent output format handling, and provides users with rich, readable context about their repositories.

## Relevant Files
Use these files to implement the feature:

- `worker/main.py:handle_git_add` (lines 586-714) - Currently runs `claude prime` with basic subprocess.run capturing stdout. Needs to be updated to use the agent module pattern.
  - Why: This is where prime execution happens. We need to replace the subprocess.run call (lines 651-657) with the agent module approach.

- `adws/adw_modules/agent.py:prompt_claude_code` (lines 161-246) - Reference implementation that runs Claude Code with `--output-format stream-json`, parses JSONL output, and returns structured AgentPromptResponse.
  - Why: This is the proven pattern we need to follow. We'll import and use this function directly.

- `adws/adw_modules/agent.py:parse_jsonl_output` (lines 39-62) - Parses JSONL output and extracts result message.
  - Why: Already used by prompt_claude_code, demonstrates the parsing pattern we're leveraging.

- `adws/adw_modules/data_types.py` - Contains AgentPromptRequest and AgentPromptResponse type definitions.
  - Why: Need to import these types to construct the request and handle the response.

- `worker/main.py:send_git_response` (lines 716-752) - Sends git operation results to bot via Redis, already accepts optional prime_output parameter.
  - Why: Already has infrastructure to pass prime output, just needs to receive the parsed data from the new implementation.

- `bot/handlers/git_handlers.py:handle_git_response` (lines 272-338) - Handles git responses and displays to user, already formats and displays prime_output if present (lines 313-316).
  - Why: Already complete - formats prime output in code block and truncates if needed. No changes required here.

- `bot/models/repository.py` (lines 31-34) - Repository model stores prime_output field in MongoDB.
  - Why: Confirms the data model supports storing prime output. No changes needed.

### New Files
No new files need to be created. All functionality can be added by modifying existing code in `worker/main.py`.

## Implementation Plan

### Phase 1: Foundation
Before implementing the main feature, understand the existing code and prepare imports:
1. Review the current prime execution in `worker/main.py:handle_git_add` (lines 651-657)
2. Review the reference implementation in `adws/adw_modules/agent.py:prompt_claude_code`
3. Understand the data types in `adws/adw_modules/data_types.py` (AgentPromptRequest, AgentPromptResponse)
4. Verify the agent module is accessible to the worker service

### Phase 2: Core Implementation
Modify the worker service to use the agent module pattern for prime execution:
1. Import necessary components from the agent module at the top of `worker/main.py`
2. Create output directory structure for storing JSONL files from prime operations
3. Replace the basic subprocess.run call with prompt_claude_code function
4. Construct AgentPromptRequest with appropriate parameters
5. Handle the AgentPromptResponse to extract prime output text
6. Pass the extracted prime output to send_git_response

### Phase 3: Integration
Ensure the prime output flows correctly through the system:
1. Test that prime output is captured and parsed correctly
2. Verify prime output is sent via Redis to the bot
3. Confirm the bot handler displays the formatted output in chat
4. Test error handling for cases where prime fails or output parsing fails
5. Verify logging captures all steps for debugging

## Step by Step Tasks
IMPORTANT: Execute every step in order, top to bottom.

### 1. Review Current Implementation
- Read `worker/main.py:handle_git_add` focusing on lines 651-657 where prime is executed
- Read `adws/adw_modules/agent.py:prompt_claude_code` to understand the pattern we'll follow
- Note the key differences: output format flag, JSONL parsing, structured response

### 2. Add Agent Module Imports
- At the top of `worker/main.py`, add imports for the agent module
- Import `prompt_claude_code` function from `adws.adw_modules.agent`
- Import `AgentPromptRequest` and `AgentPromptResponse` from `adws.adw_modules.data_types`
- Add error handling for import in case module is not available (should not happen but defensive)

### 3. Create Output Directory Structure
- In `handle_git_add`, before running prime, create directory for storing JSONL output
- Use pattern: `{workspace}/{telegram_id}/{short_name}/prime/prime_output.jsonl`
- The directory `{workspace}/{telegram_id}/{short_name}` already exists after clone
- Create the `prime` subdirectory with `repo_dir / "prime"` and `.mkdir(exist_ok=True)`

### 4. Build AgentPromptRequest
- After successful clone and before running prime (around line 649)
- Create the output file path: `output_file = str(repo_dir / "prime" / "prime_output.jsonl")`
- Create output directory: `(repo_dir / "prime").mkdir(exist_ok=True)`
- Build AgentPromptRequest with:
  - `prompt="/prime"`
  - `adw_id=task_id` (use task_id as unique identifier)
  - `agent_name="git_prime"` (descriptive name for this operation)
  - `model="sonnet"` (use default Sonnet model)
  - `dangerously_skip_permissions=True` (automated operation, no user interaction)
  - `output_file=output_file`

### 5. Replace subprocess.run with prompt_claude_code
- Remove the existing try-except block that contains `subprocess.run(["claude", "prime"], ...)`
- Replace with call to `prompt_claude_code(request)` where request is the AgentPromptRequest
- Store the response: `response = prompt_claude_code(request)`
- The function returns AgentPromptResponse with `output`, `success`, and `session_id` fields

### 6. Handle AgentPromptResponse
- Check `response.success` to determine if prime succeeded
- If `response.success == True`:
  - Extract prime output: `prime_output = response.output`
  - Call `send_git_response` with success status and prime_output
  - Log success with appropriate details
- If `response.success == False`:
  - Use `response.output` as error message (contains error details)
  - Call `send_git_response` with failed status
  - Log error with details

### 7. Update Error Handling
- Add try-except around the prompt_claude_code call for unexpected errors
- Handle the case where agent module import fails (though should not happen)
- Ensure all error paths call `send_git_response` with appropriate status
- Maintain existing timeout handling (prompt_claude_code has internal 5-minute timeout)

### 8. Update Logging
- Add log statement before calling prompt_claude_code
- Add log statement after receiving response showing success/failure
- Log the output file path for debugging
- Ensure all error cases are logged with context

### 9. Test Implementation
- Test with a small repository to verify output is captured
- Verify JSONL file is created in correct location
- Verify prime output appears in Telegram chat formatted correctly
- Test error cases: prime failure, timeout, parsing errors
- Verify repository model is updated with prime_output

## Testing Strategy

### Unit Tests
While this feature primarily involves integration with external systems (Claude Code CLI, Redis, Telegram), the following components can be unit tested:
- JSONL parsing logic (already tested in agent.py)
- Error handling paths in the modified code
- Directory creation logic
- Request construction logic

Create tests in a new file `worker/tests/test_git_operations.py`:
- Test AgentPromptRequest is constructed correctly with proper parameters
- Test response handling for success and failure cases
- Test error message formatting

### Edge Cases
Test the following scenarios to ensure robust behavior:

1. **Prime command fails** - Claude Code returns non-zero exit code
   - Expected: Error message sent to chat, repository not marked as primed

2. **Prime output is empty** - Claude Code succeeds but result is empty string
   - Expected: Success message but no prime output section shown

3. **Prime output is very large** (>4KB) - Output exceeds typical message size
   - Expected: Output truncated to 1000 chars with "Output truncated" note (already handled in git_handlers.py:314-316)

4. **JSONL parsing fails** - Output file is malformed or incomplete
   - Expected: Agent module returns success=False with error in output field

5. **Agent module not available** - Import fails in worker
   - Expected: Import error caught and clear error message logged/sent

6. **Output directory creation fails** - Insufficient permissions
   - Expected: Exception caught, error message sent via send_git_response

7. **Claude Code not installed** - claude binary not found in PATH
   - Expected: Agent module's check_claude_installed catches this, returns error

8. **Timeout during prime** - Repository very large, prime takes >5 minutes
   - Expected: Agent module handles timeout, returns error message

9. **Concurrent prime operations** - Multiple users adding repos simultaneously
   - Expected: Each operation uses unique directory/file, no conflicts

## Acceptance Criteria
The feature is considered complete when:

1. **Agent module is integrated**: Worker imports and uses prompt_claude_code function successfully
2. **Prime runs with structured output**: Claude Code executed with `--output-format stream-json` flag
3. **JSONL output is saved**: Prime output saved to `{workspace}/{telegram_id}/{short_name}/prime/prime_output.jsonl`
4. **Output is parsed correctly**: Result message extracted from JSONL with prime summary text
5. **Output is sent to chat**: Prime output transmitted via Redis and displayed in Telegram with code block formatting
6. **Output is stored in database**: Repository model's `prime_output` field populated with the prime text
7. **Repository marked as primed**: Repository model's `primed` field set to true after successful prime
8. **Errors handled gracefully**: All error conditions (prime failure, parsing error, timeout, etc.) produce clear error messages
9. **Logging is comprehensive**: All steps logged with context for debugging (request creation, execution, parsing, response)
10. **Existing functionality preserved**: `/git add` command continues to work, just with enhanced output quality

## Notes

### Implementation Pattern Reference
The agent module already implements the exact pattern we need. Key code from `adws/adw_modules/agent.py:prompt_claude_code`:

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
if result_message:
    result_text = result_message.get("result", "")
    return AgentPromptResponse(output=result_text, success=not is_error, session_id=session_id)
```

By using this function directly, we get all this functionality without reimplementing it.

### Why This Approach is Better
Compared to the current `subprocess.run(["claude", "prime"], capture_output=True)` approach:

1. **Structured output**: JSONL format is machine-parseable and consistent
2. **Rich content**: Result message contains formatted prime summary, not raw stdout
3. **Error handling**: Agent module handles errors, timeouts, parsing failures consistently
4. **Reusable pattern**: Same approach used across ADW scripts, proven and tested
5. **Session tracking**: Returns session_id for potential future use
6. **Logging**: Agent module saves prompts and outputs for debugging
7. **Environment management**: Proper environment variable handling via get_claude_env()

### Alternative Approaches Considered

1. **Parse stdout with regex** - Could try to parse current stdout output
   - Rejected: Fragile, depends on output format, harder to maintain

2. **Implement custom JSONL parsing in worker** - Duplicate the parsing logic
   - Rejected: Violates DRY principle, agent module already does this well

3. **Create new dedicated prime module** - Separate module just for prime operations
   - Rejected: Over-engineering, agent module already provides what we need

4. **Stream output in real-time** - Send prime output as it's generated
   - Rejected: Adds complexity, complete output is fine for this use case

### Dependencies
- No new Python packages required
- Relies on existing `claude` CLI being installed (already required)
- Uses existing agent module from ADW scripts (already in repo)
- Uses existing Redis infrastructure for message passing
- Uses existing MongoDB models for storage

### Future Enhancements
- Add `/git prime <repo_name>` command to manually re-prime a repository
- Store prime history to track how repository understanding evolves
- Add prime summary filters (e.g., "show me just the API routes")
- Support priming specific branches, not just default branch
- Add prime scheduling to automatically re-prime repositories periodically
- Expose prime session_id for advanced debugging or replay
