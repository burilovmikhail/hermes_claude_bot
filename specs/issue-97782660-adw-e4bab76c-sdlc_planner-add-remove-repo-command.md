# Feature: Add Remove Repository Command

## Feature Description
Currently, users can add repositories using `/git add` and list them with `/git list`, but there is no way to remove repositories that are no longer needed. This feature adds a `/git remove` (or `/git rm`) command that allows users to delete a repository from both the MongoDB database and the worker filesystem. Additionally, the `/help` command documentation needs to be updated to reflect the current git commands (currently shows outdated `clone` and `pull` operations instead of `add` and `list`).

## User Story
As a developer using the Hermes bot
I want to remove repositories I no longer need
So that I can keep my repository list clean and free up disk space on the worker service

## Problem Statement
Users currently have no way to remove repositories after adding them. This creates several issues:
- Repository list becomes cluttered with unused repositories
- No way to correct mistakes when adding a repository with the wrong parameters
- Disk space on worker service is consumed by unused cloned repositories
- Database contains stale repository records
- Help command shows outdated git command documentation (clone/pull instead of add/list/remove)

## Solution Statement
Implement a `/git remove <short_name>` command that:
1. Parses the command using OpenAI (extending existing GitCommandParser)
2. Validates that the repository exists and belongs to the requesting user
3. Deletes the repository record from MongoDB
4. Queues a worker task to remove the repository folder from the filesystem
5. Sends confirmation to the user via Telegram

Additionally, update the `/help` command to show the correct and current git command documentation.

This maintains consistency with existing git command patterns and reuses the established Redis-based task queue for filesystem operations.

## Relevant Files
Use these files to implement the feature:

- `bot/services/git_parser.py` - Contains GitCommandParser that uses OpenAI to parse git commands
  - Why: Need to add parsing support for "remove" operation, add validation method for remove operation

- `bot/handlers/git_handlers.py` - Contains git command handler and operation handlers
  - Why: Need to add `handle_remove` function and route "remove" operations to it in the main git_handler

- `bot/models/repository.py` - Repository model for MongoDB
  - Why: Need to query and delete repository records

- `worker/main.py` - Worker service that processes background tasks
  - Why: Need to add `handle_git_remove` function to clean up repository folders from the filesystem

- `bot/handlers/common_handlers.py` - Contains help_handler function
  - Why: Need to update the help message to reflect current git commands (add/list/remove instead of clone/pull)

### New Files
No new files need to be created. All functionality can be added by extending existing files.

## Implementation Plan

### Phase 1: Foundation
Update the command parser to support the remove operation:
1. Extend GitCommandParser in `bot/services/git_parser.py` to recognize "remove" or "rm" operations
2. Add system prompt instructions for extracting the short_name from remove commands
3. Add validation method for remove operation data

### Phase 2: Core Implementation
Implement the remove command handler in the bot:
1. Add `handle_remove` function in `bot/handlers/git_handlers.py`
2. Validate that the repository exists and belongs to the user
3. Delete the repository record from MongoDB
4. Queue a task to the worker service via Redis to clean up the filesystem
5. Route "remove" operations in the main `git_handler` function

### Phase 3: Worker Integration
Implement filesystem cleanup in the worker service:
1. Add `handle_git_remove` function in `worker/main.py`
2. Remove the repository directory from the workspace
3. Send success/failure response back to the bot via Redis
4. Handle edge cases (directory doesn't exist, permission errors)

### Phase 4: Documentation Update
Update the help command with current information:
1. Update `help_handler` in `bot/handlers/common_handlers.py`
2. Replace outdated git command examples (clone/pull) with current commands (add/list/remove)
3. Ensure examples are clear and accurate

## Step by Step Tasks
IMPORTANT: Execute every step in order, top to bottom.

### 1. Extend GitCommandParser for Remove Operation
- Read `bot/services/git_parser.py` to understand current parsing implementation
- Update the system prompt in `GitCommandParser.parse()` to recognize "remove" or "rm" operations
- Add instructions to extract the short_name parameter for remove operations
- Add example inputs and outputs for remove operations in the system prompt

### 2. Add Remove Operation Validation
- In `bot/services/git_parser.py`, add `validate_remove_data` static method
- Follow the pattern of `validate_add_data` and `validate_list_data`
- Validate that operation is "remove" and short_name is present
- Return tuple of (is_valid, error_message)

### 3. Implement Bot Handler for Remove Operation
- Read `bot/handlers/git_handlers.py` to understand handler patterns
- Add `handle_remove` async function that takes (update, telegram_id, parsed)
- Validate parsed data using `GitCommandParser.validate_remove_data`
- Query MongoDB to find repository by telegram_id and short_name
- If not found, send error message to user
- If found, delete the repository from MongoDB using `await repo.delete()`
- Queue a task to Redis with operation "git_remove" including task_id, telegram_id, repo_id, and short_name
- Send confirmation message to user that removal is in progress

### 4. Route Remove Operation in Main Handler
- In `bot/handlers/git_handlers.py`, update the `git_handler` function
- Add elif branch for `operation == "remove"` after the "list" operation
- Call `await handle_remove(update, telegram_id, parsed)`
- Update the usage message to include remove command example

### 5. Implement Worker Handler for Filesystem Cleanup
- Read `worker/main.py` to understand worker task routing
- Update `process_task` method to route "git_remove" operation to new handler
- Add `handle_git_remove` async function
- Extract task_id, telegram_id, short_name from task_data
- Construct repo_dir path as `self.workspace / str(telegram_id) / short_name`
- Check if directory exists
- If exists, use `shutil.rmtree(repo_dir)` to remove it recursively
- If doesn't exist, log warning but still send success response (already cleaned up)
- Send success or failure response via `send_git_response`
- Add proper error handling and logging

### 6. Handle Remove Response in Bot
- Read `bot/handlers/git_handlers.py:handle_git_response` to understand response handling
- Verify it already handles responses for any operation type
- Confirm no changes needed (operation type doesn't affect response formatting)
- The existing response handler should work for "git_remove" operations

### 7. Update Help Command Documentation
- Read `bot/handlers/common_handlers.py:help_handler`
- Update the "Repository Management:" section
- Remove outdated commands: `/git clone` and `/git pull`
- Add current commands:
  - `/git add <short_name> <jira_prefix> <repo_url>` with example
  - `/git list` with description
  - `/git remove <short_name>` with example
- Ensure formatting is consistent with other sections

### 8. Test Error Cases and Edge Conditions
- Test removing a repository that doesn't exist (should show error)
- Test removing a repository that belongs to another user (should not find it)
- Test removing a repository when directory is already deleted (should succeed)
- Test concurrent remove operations on the same repository
- Verify error messages are clear and helpful

## Testing Strategy

### Unit Tests
Since this project doesn't have a formal test suite yet, manual testing should cover:
- Parsing various remove command formats ("remove backend", "rm api", "delete repo-name")
- Database operations (finding, deleting repository records)
- Filesystem operations (removing directories, handling missing directories)
- Redis message flow (task queuing, response handling)

### Edge Cases
- **Repository doesn't exist**: User tries to remove non-existent repository → Should show clear error message
- **Repository belongs to different user**: User tries to remove another user's repository → Should not find it (filtered by telegram_id)
- **Short name with special characters**: Repository name has hyphens, underscores → Should handle correctly
- **Directory already deleted**: Repository record exists but filesystem directory is gone → Should still succeed and clean up database
- **Directory has uncommitted changes**: Repository has local modifications → Should still remove (user responsibility to back up)
- **Invalid short_name**: Empty or null short_name → Should show validation error
- **Case sensitivity**: Repository added as "Backend" but remove uses "backend" → Should handle appropriately (exact match or case-insensitive)
- **Worker service down**: Redis task queued but worker not processing → Should handle gracefully (task will process when worker restarts)
- **Permission errors**: Worker can't delete directory due to permissions → Should catch exception and report failure

## Acceptance Criteria
- Users can remove repositories using `/git remove <short_name>` command
- Alternative syntax `/git rm <short_name>` also works
- Repository record is deleted from MongoDB
- Repository directory is removed from worker filesystem at `workspace/<telegram_id>/<short_name>`
- User receives confirmation message when removal succeeds
- User receives clear error message when repository doesn't exist
- User can only remove their own repositories (filtered by telegram_id)
- Worker handles missing directories gracefully (logs warning, sends success)
- Worker handles filesystem errors gracefully (logs error, sends failure)
- `/help` command shows current git commands: add, list, remove (not clone/pull)
- Help examples are accurate and match actual command syntax
- System logs all operations (parse, database delete, filesystem delete) for debugging

## Notes

### Implementation Considerations
- Use exact match for short_name (case-sensitive) to avoid accidentally removing wrong repository
- Consider adding confirmation step for remove operation in future (e.g., inline keyboard with Yes/No)
- Repository removal is permanent - users should be warned in the confirmation message
- If a repository is being used by an active ADW task, removal could cause issues - document this limitation

### Future Enhancements
- Add confirmation dialog before removing (inline keyboard)
- Add `/git rename <old_name> <new_name>` command
- Add ability to update jira_prefix without removing/re-adding
- Show disk space freed when removing repository
- Add bulk operations: `/git remove all` or `/git remove backend,frontend,api`
- Add "soft delete" with ability to restore recently removed repositories

### Security Considerations
- User can only remove their own repositories (queries filtered by telegram_id)
- Worker operates in isolated workspace per user (workspace/<telegram_id>/)
- Path traversal protection implicit in using Path objects and controlled short_name
- No additional authorization needed beyond existing @authorized_users_only decorator

### Performance Considerations
- Removing large repositories may take time - filesystem operations are async via worker
- User gets immediate confirmation that removal is queued, then final confirmation when complete
- Consider adding timeout to filesystem operations if repositories are very large (>1GB)

### Logging and Monitoring
- Log all remove operations with telegram_id, short_name, repo_id
- Log filesystem operations (directory size, removal time)
- Monitor failed removals (permission errors, missing directories)
- Track remove command usage (frequency, errors)
