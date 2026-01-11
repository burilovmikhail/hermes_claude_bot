# Feature: Add Claude Commands Check and Copy to Cloned Repositories

## Feature Description
This feature ensures that all cloned repositories have access to the custom Claude Code commands (`.claude/commands/`) before running the prime command or any ADW workflows. Currently, the worker service copies the `adws/` scripts directory to cloned repositories but does NOT copy the `.claude/commands/` directory, which means cloned repositories cannot use custom Claude Code slash commands like `/prime`, `/feature`, `/bug`, `/chore`, etc.

This feature will:
1. Mount/copy the `.claude/commands/` directory from the Hermes source repository to the worker service (similar to how `adws/` scripts are currently handled)
2. Copy the `.claude/commands/` directory to each cloned repository immediately after cloning
3. Check if a repository already has a `.claude/commands/` directory, and only copy if it's missing
4. Ensure this happens BEFORE the prime command is executed in the `handle_git_add` flow

## User Story
As a developer using the Hermes bot to work with multiple repositories
I want all cloned repositories to have access to the custom Claude Code commands
So that the prime command and ADW workflows can execute successfully using the standardized command templates

## Problem Statement
The current implementation has a critical gap: when the worker service clones a repository and runs the prime command, Claude Code may fail or use default behavior because it cannot find the custom command templates defined in `.claude/commands/`. The `copy_adw_scripts()` function only copies the `adws/` directory but ignores the `.claude/` directory structure, which contains:
- Custom slash command definitions (`/prime`, `/feature`, `/bug`, `/chore`, etc.)
- Claude Code settings and permissions (`settings.json`)

This causes:
- Prime command execution to potentially fail or produce inconsistent results
- ADW workflows that rely on custom commands to not work as expected
- Lack of standardized Claude Code behavior across different repositories

## Solution Statement
Implement a comprehensive solution that mirrors the existing `adws/` copying pattern:

1. **Docker Build Phase**: Update the worker Dockerfile to copy the `.claude/` directory from the project root to `/app/.claude/` (similar to how `adws/` is copied at line 60 of `worker/Dockerfile`)

2. **Worker Service Enhancement**: Create a new `copy_claude_commands()` function that:
   - Checks if the target repository already has a `.claude/commands/` directory
   - If NOT present, copies the entire `.claude/` directory from the worker's source location to the repository
   - If present, logs that the repository already has commands and skips copying
   - Handles both Docker and development environments (similar to `copy_adw_scripts()` logic)

3. **Integration into Repository Setup**: Call `copy_claude_commands()` in two key locations:
   - In `handle_git_add()` immediately AFTER cloning and BEFORE running prime command
   - In `setup_repository()` immediately AFTER cloning/updating a repository for ADW workflows

This ensures every repository has access to custom commands before any Claude Code execution.

## Relevant Files
Use these files to implement the feature:

- **`worker/Dockerfile`** (lines 59-60)
  - Currently copies `adws/` directory from project root to `/app/adws`
  - Needs to also copy `.claude/` directory to `/app/.claude`

- **`worker/main.py`** (lines 230-292)
  - Contains the `copy_adw_scripts()` function that serves as the pattern to follow
  - Handles both Docker (`/app/adws`) and development (`../adws`) source locations
  - Copies scripts, installs dependencies, includes error handling

- **`worker/main.py`** (lines 590-737)
  - `handle_git_add()` function that clones repositories and runs prime
  - Line 649: Repository is cloned
  - Lines 651-715: Prime command is executed
  - **New code needed**: Call `copy_claude_commands()` between lines 649-651

- **`worker/main.py`** (lines 161-179)
  - `handle_adw_task()` function that calls `setup_repository()` then `copy_adw_scripts()`
  - Line 167: Repository setup completes
  - Line 179: ADW scripts are copied
  - **New code needed**: Call `copy_claude_commands()` after line 167

- **`worker/main.py`** (lines 446-588)
  - `setup_repository()` function that clones or updates repositories
  - Returns the repository directory path
  - **New code needed**: Could optionally call `copy_claude_commands()` at the end, but better to keep it separate

- **`.claude/commands/`** (entire directory)
  - Source location of custom Claude Code command templates
  - Contains: `prime.md`, `feature.md`, `bug.md`, `chore.md`, `commit.md`, `pull_request.md`, etc.
  - Also contains `.claude/settings.json` with permissions configuration
  - This entire directory needs to be available to the worker and copied to cloned repos

- **`.claude/settings.json`**
  - Claude Code permissions configuration
  - Defines allowed and denied operations
  - Critical for Claude Code execution with proper security constraints

### New Files
No new files need to be created. This feature modifies existing files only.

## Implementation Plan

### Phase 1: Foundation
Prepare the worker service Docker image and runtime environment to have access to the `.claude/` directory from the source repository. This mirrors the existing pattern used for `adws/` scripts where they are copied during Docker build and then made available to the worker service at runtime.

### Phase 2: Core Implementation
Create the `copy_claude_commands()` function following the same pattern as `copy_adw_scripts()`. This function will handle:
- Detecting the source location of `.claude/` directory (Docker vs development environment)
- Checking if the target repository already has a `.claude/commands/` directory
- Copying the directory only if needed
- Proper error handling and logging

### Phase 3: Integration
Integrate the new function into the two critical flows:
1. `handle_git_add()` flow: Ensure commands are available before prime execution
2. `handle_adw_task()` flow: Ensure commands are available before ADW workflows

Test both flows to verify that cloned repositories can successfully use custom Claude Code commands.

## Step by Step Tasks
IMPORTANT: Execute every step in order, top to bottom.

### Step 1: Update Worker Dockerfile to Copy .claude Directory
- Open `worker/Dockerfile`
- Locate line 60 where `COPY adws /app/adws` exists
- Add a new line immediately after: `COPY .claude /app/.claude`
- Verify that the `.claude/` directory contains the `commands/` subdirectory and `settings.json`
- Ensure proper ownership is set (this happens automatically via line 67: `chown -R worker:worker /app`)

### Step 2: Create copy_claude_commands Function
- Open `worker/main.py`
- Locate the `copy_adw_scripts()` function (lines 230-292) to use as a template
- After the `copy_adw_scripts()` function, create a new function: `copy_claude_commands()`
- Function signature: `async def copy_claude_commands(self, repo_dir: Path, task_id: str, telegram_id: int, reporting_level: ReportingLevel = "basic")`
- Implement the following logic:
  - Get the worker directory: `worker_dir = Path(__file__).parent`
  - Try Docker location first: `claude_source = worker_dir / ".claude"`
  - If not found, try development location: `claude_source = worker_dir.parent / ".claude"`
  - If still not found, raise `FileNotFoundError(f"Claude commands not found at: {claude_source}")`
  - Set target: `claude_target = repo_dir / ".claude"`
  - Check if target already exists: `if claude_target.exists():`
    - Log that commands already exist and skip copying
    - Return early
  - If target doesn't exist:
    - Copy the entire directory: `shutil.copytree(claude_source, claude_target)`
    - Log successful copy with source and target paths
- Add comprehensive error handling with try/except
- Do NOT install dependencies (no requirements.txt for .claude/)

### Step 3: Integrate into handle_git_add Flow
- Open `worker/main.py`
- Locate the `handle_git_add()` function (lines 590-737)
- Find line 649 where the clone operation completes (after the git clone check)
- Between the successful clone and the prime command execution (before line 651):
  - Add a log message: `logger.info("Copying Claude commands to repository", repo_url=repo_url)`
  - Add try/except block to call `copy_claude_commands()`:
    ```python
    try:
        await self.copy_claude_commands(repo_dir, task_id, telegram_id, "basic")
    except Exception as e:
        await self.send_git_response(
            task_id,
            telegram_id,
            "failed",
            f"Failed to copy Claude commands: {str(e)}",
            "git_add",
            repo_id
        )
        logger.error("Failed to copy Claude commands", error=str(e))
        return
    ```
- Ensure this happens BEFORE line 651 (where the prime command setup begins)

### Step 4: Integrate into handle_adw_task Flow
- Open `worker/main.py`
- Locate the `handle_adw_task()` function (lines 124-228)
- Find line 179 where `copy_adw_scripts()` is called
- Immediately after line 179, add:
  - Progress status message:
    ```python
    await self.send_status(
        task_id,
        telegram_id,
        "progress",
        "Copying Claude commands...",
        reporting_level,
        "technical"
    )
    ```
  - Call to copy Claude commands:
    ```python
    await self.copy_claude_commands(repo_dir, task_id, telegram_id, reporting_level)
    ```
- Add try/except error handling around the call to catch and propagate exceptions

### Step 5: Add Logging and Validation
- In the `copy_claude_commands()` function, ensure comprehensive logging:
  - Log when source directory is found: `"Found Claude commands source"`
  - Log when target already exists: `"Repository already has Claude commands, skipping copy"`
  - Log when copying: `"Copying Claude commands"`
  - Log success: `"Claude commands copied successfully"`
  - Log errors: `"Failed to copy Claude commands"`
- Verify that the commands directory contains expected files:
  - Check that `commands/` subdirectory exists in the source
  - Check that `settings.json` exists in the source
  - Log a warning if key files are missing but continue with the copy

### Step 6: Test Docker Build
- Build the worker Docker image to verify the `.claude/` directory is copied:
  ```bash
  docker-compose build worker
  ```
- Verify no build errors occur
- Optionally, inspect the built image to confirm `/app/.claude` exists:
  ```bash
  docker run --rm --entrypoint ls hermes_claude_bot-worker -la /app/.claude
  ```

### Step 7: Create Unit Tests for copy_claude_commands
- Create a new test file: `worker/tests/test_copy_claude_commands.py`
- Import required modules: `pytest`, `pathlib.Path`, `shutil`, `worker.main.WorkerService`
- Test case 1: `test_copy_claude_commands_success`
  - Setup: Create temp directory with mock `.claude/` structure
  - Execute: Call `copy_claude_commands()` with temp target directory
  - Assert: Target directory exists and contains expected files
- Test case 2: `test_copy_claude_commands_already_exists`
  - Setup: Create target directory with existing `.claude/` folder
  - Execute: Call `copy_claude_commands()`
  - Assert: Function returns early without error, logs skip message
- Test case 3: `test_copy_claude_commands_source_not_found`
  - Setup: Point to non-existent source directory
  - Execute: Call `copy_claude_commands()`
  - Assert: Raises `FileNotFoundError`

### Step 8: Test Integration with git_add Flow
- Start the worker service in test environment
- Execute a `/git add` command from the Telegram bot with a test repository
- Monitor logs to verify:
  - Clone operation completes successfully
  - `copy_claude_commands()` is called
  - `.claude/` directory is copied to the cloned repository
  - Prime command executes successfully
  - No errors in the flow
- Verify the cloned repository in `/workspace/{telegram_id}/{repo_name}/.claude/` exists and contains commands

### Step 9: Test Integration with ADW Workflow Flow
- Start the worker service in test environment
- Execute an ADW command from the Telegram bot (e.g., feature planning)
- Monitor logs to verify:
  - Repository setup completes
  - ADW scripts are copied
  - `copy_claude_commands()` is called
  - `.claude/` directory is copied
  - ADW workflow executes successfully
- Verify the repository has both `adws/` and `.claude/` directories

### Step 10: Test Edge Case - Repository Already Has Commands
- Manually create a test repository with an existing `.claude/commands/` directory
- Clone this repository using `/git add`
- Verify that:
  - The function detects the existing directory
  - Logs a message about skipping the copy
  - Does NOT overwrite the existing commands
  - Prime command still executes successfully

## Testing Strategy

### Unit Tests
1. **Test `copy_claude_commands()` function in isolation**
   - Verify successful copy from source to target
   - Verify skip behavior when target already exists
   - Verify error handling when source is not found
   - Verify proper logging at each step

2. **Test Docker image build**
   - Verify `.claude/` directory is copied to `/app/.claude` during build
   - Verify directory structure and files are intact
   - Verify proper permissions are set

3. **Mock integration tests**
   - Mock `shutil.copytree` to test flow without actual file operations
   - Test error propagation to `send_git_response()` and `send_status()`
   - Test reporting level filtering for progress messages

### Integration Tests
1. **End-to-end git_add flow**
   - Clone a new repository using `/git add` command
   - Verify `.claude/` is copied before prime execution
   - Verify prime command completes successfully
   - Verify repository is registered in MongoDB with primed status

2. **End-to-end ADW workflow flow**
   - Execute a feature/bug/chore workflow
   - Verify repository has both `adws/` and `.claude/` directories
   - Verify ADW scripts can access custom commands
   - Verify workflow completes successfully

### Edge Cases
1. **Repository already has `.claude/commands/`**
   - Test with a repository that has its own custom commands
   - Verify existing commands are NOT overwritten
   - Verify function logs skip message and continues

2. **Source directory not found (corrupted Docker image)**
   - Simulate missing `/app/.claude` directory
   - Verify appropriate error is raised and logged
   - Verify task fails gracefully with user-friendly error message

3. **Permission errors during copy**
   - Simulate permission denied error during `shutil.copytree`
   - Verify error is caught and logged
   - Verify task fails with clear error message to user

4. **Partial copy failure**
   - Simulate disk space or I/O error mid-copy
   - Verify partial directory is cleaned up or error is reported
   - Verify system can recover on retry

5. **Development vs Docker environment**
   - Test in local development mode (source at `../. claude`)
   - Test in Docker mode (source at `/app/.claude`)
   - Verify correct source is found in both cases

6. **Multiple concurrent clones**
   - Execute multiple `/git add` commands simultaneously
   - Verify each repository gets its own copy of `.claude/`
   - Verify no race conditions or file conflicts

## Acceptance Criteria
1. ✅ Worker Docker image includes `.claude/` directory copied from project root
2. ✅ `copy_claude_commands()` function exists and follows the same pattern as `copy_adw_scripts()`
3. ✅ Function correctly detects Docker vs development environment source locations
4. ✅ Function checks if target repository already has `.claude/commands/` directory
5. ✅ Function skips copying if commands already exist in target repository
6. ✅ Function copies `.claude/` directory to target repository if not present
7. ✅ Function is called in `handle_git_add()` after clone and before prime command
8. ✅ Function is called in `handle_adw_task()` after repository setup and ADW scripts copy
9. ✅ Prime command executes successfully with access to custom commands
10. ✅ ADW workflows execute successfully with access to custom commands
11. ✅ Comprehensive error handling with user-friendly error messages
12. ✅ Detailed logging at each step for debugging
13. ✅ No breaking changes to existing functionality
14. ✅ Unit tests pass for the new function
15. ✅ Integration tests pass for git_add and ADW workflow flows

## Notes

### Implementation Pattern to Follow
This feature should closely mirror the existing `copy_adw_scripts()` implementation in `worker/main.py` (lines 230-292). Key patterns to replicate:
- Try Docker location first, fall back to development location
- Use `shutil.copytree` for directory copying
- Log each step with structured logging
- Include comprehensive error handling
- Do NOT raise exceptions that would crash the worker (except for truly fatal errors)

### Why NOT Install Dependencies for .claude/
Unlike `adws/` which has a `requirements.txt`, the `.claude/` directory only contains:
- Markdown command templates (`.md` files)
- JSON configuration (`settings.json`)

These are static files with no Python dependencies, so there's no need to run `pip install` after copying.

### Order of Operations in handle_git_add
The correct order is critical:
1. Clone repository
2. Copy Claude commands ← **NEW STEP**
3. Create prime output directory
4. Execute prime command

This ensures prime command has access to custom commands when it runs.

### Relationship to Existing Issues
This feature is related to:
- `specs/issue-8fe7e5c9-*-rewrite-git-commands.md`: Originally introduced the git_add flow with prime
- `specs/issue-2e957ffb-*-add-prime-output-chat.md`: Enhanced prime to use agent module
- Current branch: `feature-issue-2231a55b-adw-4819486a-add-claude-commands-check`

The current branch name suggests this feature is specifically about adding the "commands check" - verifying and ensuring commands are available.

### Future Considerations
- Consider adding a validation step that checks for specific required commands (e.g., `/prime`, `/feature`)
- Consider supporting custom commands per repository (not overwriting if they exist)
- Consider a configuration option to force-overwrite commands if needed
- Consider adding a `/commands` Telegram command to list available Claude commands
- Consider syncing commands when they're updated in the source repository

### Security Considerations
- The `.claude/settings.json` file defines permissions for Claude Code operations
- Ensure this file is copied along with commands to maintain consistent security policies
- Do NOT modify repository-specific permissions if `.claude/` already exists in the target
- Log when skipping copy to provide transparency about which repositories use custom commands

### Performance Considerations
- Copying `.claude/` directory is fast (small files, ~50KB total)
- No performance impact expected vs current `copy_adw_scripts()` operation
- Could be optimized in the future by only copying if commands have changed (checksum comparison)
