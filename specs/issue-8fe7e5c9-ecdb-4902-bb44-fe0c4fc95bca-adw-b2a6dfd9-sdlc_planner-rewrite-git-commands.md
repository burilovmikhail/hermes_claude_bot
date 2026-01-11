# Feature: Rewrite Git Commands Handling

## Feature Description
This feature rewrites the git command handling system in the Telegram bot to replace the existing `git clone` and `git pull` commands with new commands: `git list` and `git add`. The new `git add` command will delegate repository cloning and priming to the worker service, which will clone the repository, run Claude Code with the `/prime` command, and register the repository in MongoDB upon success. The `git list` command will display all registered repositories with their complete information.

## User Story
As a bot user
I want to register repositories and have them automatically primed by Claude Code
So that I can quickly view all my registered repositories with their details and have them ready for AI-driven workflows

## Problem Statement
The current git command implementation uses `git clone` and `git pull` operations that focus on basic repository management. Users need a more streamlined approach where:
1. Adding a repository automatically primes it using Claude Code's `/prime` command through the worker service
2. Users can quickly list all registered repositories with comprehensive information
3. The system tracks repository registration status and priming results
4. Failed operations are clearly reported with error details

## Solution Statement
Replace the existing `git clone` and `git pull` commands with:
1. **`git add`**: Accepts repository information (short_name, jira_prefix, repo_url), creates a repository record in MongoDB, and sends a task to the worker service to clone the repository and run Claude Code with `/prime` command. Upon success, the repository is marked as registered and the `/prime` output is displayed to the user.
2. **`git list`**: Queries MongoDB for all repositories registered by the user and displays them with all relevant information (short_name, jira_prefix, repo_url, registration status, last_primed timestamp, etc.)

The worker service will handle the actual cloning and priming operations asynchronously, reporting results back to the bot via Redis pub/sub.

## Relevant Files
Use these files to implement the feature:

- **bot/handlers/git_handlers.py** - Contains the current git command handlers (`git_handler`, `handle_clone`, `handle_pull`). This needs to be modified to:
  - Replace `handle_clone` logic to become `handle_add`
  - Remove `handle_pull` function
  - Add new `handle_list` function to display registered repositories
  - Update `git_handler` to route to the new commands

- **bot/models/repository.py** - Contains the Repository MongoDB model. Needs to be updated to:
  - Replace `cloned` field with `registered` and `primed` status fields
  - Add `last_primed` timestamp field
  - Add `prime_output` field to store the output from `/prime` command
  - Update indexes as needed

- **bot/services/git_parser.py** - Contains the GitCommandParser that uses OpenAI to parse git commands. Needs to be updated to:
  - Replace 'clone' operation with 'add' operation
  - Replace 'pull' operation with 'list' operation
  - Update validation methods accordingly
  - Update system prompts and examples

- **worker/main.py** - Contains the WorkerService that processes tasks. Needs to be modified to:
  - Replace `handle_git_clone` with `handle_git_add` that clones AND runs `/prime`
  - Remove `handle_git_pull` function
  - Add logic to execute Claude Code with `/prime` command after cloning
  - Capture `/prime` output and send it back to the bot
  - Update task routing in `process_task` method

- **bot/services/redis_service.py** - Used for communication between bot and worker. No changes needed, but will be used to send new task types.

- **bot/database/mongodb.py** - MongoDB connection manager. No changes needed as it already includes Repository model.

### New Files
No new files are required. All changes will be made to existing files.

## Implementation Plan

### Phase 1: Foundation
Update the data model and parser to support the new command structure. This includes modifying the Repository model to track priming status and updating the git command parser to recognize the new commands.

### Phase 2: Core Implementation
Implement the new `git add` and `git list` handlers in the bot, including the logic to create repository records, send tasks to the worker, and display repository information. Update the worker service to handle the new `git_add` operation including cloning and running `/prime`.

### Phase 3: Integration
Integrate the new handlers with the bot's command routing system, ensure proper Redis communication for the new task types, and verify that repository registration and priming workflows complete successfully end-to-end.

## Step by Step Tasks

### Update Repository Model
- Modify `bot/models/repository.py` to replace the `cloned` boolean field with `registered` and `primed` boolean fields
- Add `last_primed` optional datetime field to track when repository was last primed
- Add `prime_output` optional string field to store the output from Claude Code's `/prime` command
- Update the Repository model's field descriptions to reflect new purpose
- Keep all existing fields (telegram_id, short_name, jira_prefix, repo_url, full_url)

### Update Git Command Parser
- Modify `bot/services/git_parser.py` to change the parser system prompt to recognize 'add' instead of 'clone' and 'list' instead of 'pull'
- Update the example inputs and outputs in the system prompt to reflect new command syntax
- Rename `validate_clone_data` to `validate_add_data` and update its logic to validate 'add' operation
- Rename `validate_pull_data` to `validate_list_data` and update its logic to validate 'list' operation (which requires no parameters besides operation)
- Update all docstrings and comments to reflect new command names

### Update Bot Git Handlers - Remove Old Commands
- In `bot/handlers/git_handlers.py`, update the `git_handler` docstring to document the new commands: `git add` and `git list`
- Update the help text in `git_handler` to show usage examples for `git add` and `git list`
- Remove the existing routing logic for 'clone' and 'pull' operations
- Add new routing logic for 'add' and 'list' operations

### Update Bot Git Handlers - Implement git add
- Rename `handle_clone` function to `handle_add` in `bot/handlers/git_handlers.py`
- Update validation to use `GitCommandParser.validate_add_data`
- Update the repository creation logic to set `registered=False` and `primed=False` initially
- Update the task data sent to Redis to use operation type `git_add` instead of `git_clone`
- Update user-facing messages to reflect "adding" and "priming" terminology instead of "cloning"
- Keep all existing logic for checking duplicate short_name and normalizing repo URLs

### Update Bot Git Handlers - Implement git list
- Remove the `handle_pull` function entirely from `bot/handlers/git_handlers.py`
- Create a new `handle_list` function that queries all repositories for the user
- Format the repository list output to show: short_name, jira_prefix, repo_url, registration status, priming status, and last_primed timestamp
- Handle the case where user has no registered repositories with a friendly message
- Use escape_markdown for all dynamic values in the output

### Update Bot Git Response Handler
- In `bot/handlers/git_handlers.py`, update `handle_git_response` to handle `git_add` operation instead of `git_clone`
- When `git_add` operation succeeds, update repository record to set `registered=True`, `primed=True`, `last_primed=datetime.utcnow()`, and store the `prime_output`
- Update the success message format to include the prime output in the response sent to user
- Remove all logic related to `git_pull` operation
- Ensure error messages clearly indicate whether the failure was during clone or prime step

### Update Worker Service - Remove Old Handlers
- In `worker/main.py`, update the `process_task` method to route `git_add` operation instead of `git_clone`
- Remove routing for `git_pull` operation entirely
- Remove the `handle_git_pull` function completely

### Update Worker Service - Implement git add Handler
- Rename `handle_git_clone` to `handle_git_add` in `worker/main.py`
- Keep the existing clone logic (creating repo directory, checking if exists, running git clone command)
- After successful clone, add logic to execute Claude Code with `/prime` command
- Use subprocess to run the `/prime` command (need to determine exact command syntax - likely `claude-code /prime` or similar)
- Capture both stdout and stderr from the `/prime` command execution
- If `/prime` succeeds, include its output in the success response sent back to bot via `send_git_response`
- If `/prime` fails, send a failure response with error details
- Update the response data structure to include `prime_output` field
- Update all log messages to reflect "add" operation instead of "clone"

### Update Worker Response Communication
- In `worker/main.py`, update `send_git_response` method signature to accept optional `prime_output` parameter
- Include `prime_output` in the response dictionary sent to Redis
- Update all calls to `send_git_response` in `handle_git_add` to pass the prime_output when available

### Test git add Command
- Test `git add` with valid repository (short_name, jira_prefix, repo_url)
- Verify repository record is created in MongoDB with registered=False initially
- Verify task is sent to worker service via Redis
- Verify worker clones the repository successfully
- Verify worker runs `/prime` command and captures output
- Verify success response is sent back to bot with prime_output
- Verify bot updates repository record with registered=True, primed=True, and prime_output
- Verify user receives success message with prime output

### Test git list Command
- Test `git list` with no repositories registered
- Test `git list` with one repository registered
- Test `git list` with multiple repositories registered
- Verify all repository information is displayed correctly (short_name, jira_prefix, repo_url, statuses, timestamps)
- Verify markdown escaping works correctly for all dynamic values

### Test Edge Cases
- Test `git add` with duplicate short_name (should fail with helpful message)
- Test `git add` with invalid repository URL (should fail during clone)
- Test `git add` where clone succeeds but `/prime` fails (should mark registered but not primed)
- Test `git add` with repository URL in different formats (short form, full URL, with .git suffix)
- Test `git list` pagination if user has many repositories (if needed)

## Testing Strategy

### Unit Tests
While this codebase doesn't currently have automated tests, the following areas should be manually tested:

1. **Repository Model Tests**
   - Create repository with new fields (registered, primed, last_primed, prime_output)
   - Verify fields are properly stored and retrieved from MongoDB
   - Test update_timestamp method still works correctly

2. **Git Parser Tests**
   - Parse various `git add` command formats with AI parser
   - Parse `git list` command
   - Validate parsed data with new validation methods
   - Test error handling for malformed commands

3. **Bot Handler Tests**
   - Test `handle_add` with various input formats
   - Test `handle_list` with different repository states
   - Test `handle_git_response` processing add operation results
   - Test help text and error messages

4. **Worker Service Tests**
   - Test `handle_git_add` end-to-end (clone + prime)
   - Test clone success but prime failure scenario
   - Test clone failure scenario
   - Test communication with bot via Redis

### Edge Cases
- **Duplicate Registration**: User tries to add repository with short_name that already exists
- **Invalid Repository**: Repository URL doesn't exist or is inaccessible
- **Prime Command Failure**: Clone succeeds but `/prime` command fails or times out
- **Missing Prime Command**: `/prime` command is not available in the environment
- **Network Issues**: Git clone fails due to network timeout or authentication issues
- **Redis Communication Failure**: Worker cannot send response back to bot
- **MongoDB Failure**: Cannot save or retrieve repository records
- **Large Prime Output**: `/prime` output is very large (may need truncation)
- **Empty Repository List**: User calls `git list` with no repositories registered
- **Special Characters**: Repository URLs or names contain special characters requiring escaping

## Acceptance Criteria
1. **git add Command**: Users can successfully register a repository using `/git add <short_name> <jira_prefix> <repo_url>` and receive confirmation with prime output
2. **Automatic Priming**: When a repository is added, the worker service automatically clones it and runs Claude Code's `/prime` command
3. **Status Tracking**: Repository model correctly tracks both registration and priming status with timestamps
4. **Prime Output Storage**: The output from `/prime` command is stored in MongoDB and displayed to the user
5. **git list Command**: Users can view all their registered repositories with `/git list` showing complete information
6. **Error Handling**: Clear error messages are shown for failed clone operations, failed prime operations, or duplicate registrations
7. **Backwards Compatibility**: Old git clone and git pull commands are completely removed and no longer function
8. **Worker Communication**: Bot and worker communicate successfully via Redis for git add operations
9. **Repository Display**: git list shows short_name, jira_prefix, repo_url, registration status, priming status, and last_primed timestamp in readable format
10. **Duplicate Prevention**: System prevents adding repositories with duplicate short_name for the same user

## Notes
- The `/prime` command is likely a Claude Code command that prepares a repository for AI workflows. We'll need to determine the exact command syntax during implementation (could be `claude-code /prime`, `claude /prime`, or similar).
- Consider adding a timeout for the `/prime` command execution in the worker (e.g., 5 minutes) to prevent hanging on large repositories.
- The prime_output field should have a reasonable size limit in MongoDB. Consider truncating very large outputs or storing them separately if needed.
- Future enhancement: Add a `git remove` command to delete registered repositories
- Future enhancement: Add a `git reprime` command to re-run `/prime` on an already registered repository
- Future enhancement: Add filtering options to `git list` (e.g., by jira_prefix or priming status)
- The worker service will need access to Claude Code CLI - ensure it's installed in the worker Docker container
- Consider adding progress indicators while `/prime` is running since it may take significant time
