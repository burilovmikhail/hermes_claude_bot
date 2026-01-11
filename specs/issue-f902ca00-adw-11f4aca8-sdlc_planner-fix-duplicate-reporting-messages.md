# Bug: Duplicate reporting messages in ADW workflow

## Bug Description
Users are receiving duplicate messages during ADW workflow execution in basic reporting mode:

1. **Duplicate "AI-Driven" messages**: When starting a workflow, users get two messages:
   - "🚀 *AI-Driven Workflow Started*" (from bot handler when task is queued)
   - "⚙️ *Workflow Started*" (from worker when task actually starts processing)

2. **Duplicate PR creation messages**: When a pull request is created, users get two messages:
   - "Created pull request: {url}" (from workflow_ops.py logger)
   - "Created PR: {url}" (from git_ops.py logger)

Both logger messages get picked up by the worker's stdout stream reader and sent as progress updates to the user.

**Expected behavior**: In basic mode, users should only receive essential, non-duplicate messages.

**Actual behavior**: Users receive duplicate messages about workflow starting and PR creation.

## Problem Statement
The bot sends redundant status messages that clutter the user experience, especially in basic reporting mode. The issue stems from two problems:

1. The bot handler sends an initial confirmation message when queuing the task, and then the worker sends another "started" status message when it begins processing
2. Both workflow_ops.py and git_ops.py log PR creation messages, which get captured by the worker's stream reader and forwarded to the user

## Solution Statement
1. **Filter "started" status in basic mode**: In basic reporting mode, don't send the "started" status update from the worker since the bot already confirmed task queuing
2. **Remove duplicate PR log message**: Remove the redundant logger.info() call in git_ops.py to eliminate the duplicate PR creation message

## Steps to Reproduce
1. Run `/adw` command with a task that creates a PR
2. Observe two startup messages:
   - "🚀 *AI-Driven Workflow Started*"
   - "⚙️ *Workflow Started*" (should be filtered in basic mode)
3. When PR is created, observe two messages:
   - "Created pull request: {url}"
   - "Created PR: {url}" (duplicate)

## Root Cause Analysis

### Issue 1: Duplicate "AI-Driven" startup messages
**Location**: `bot/handlers/adw_handlers.py:211-234` and `worker/main.py:142-148`

**Root cause**: The ADW handler sends a confirmation message immediately after queuing the task to Redis. Then, when the worker picks up the task, it sends a "started" status that triggers another message. Both messages serve similar purposes but the second one is redundant in basic mode.

The worker's send_status() in `worker/main.py:54-100` currently filters "progress" messages based on reporting level but doesn't filter "started", "finished", or "failed" messages (line 79-89).

### Issue 2: Duplicate PR creation messages
**Location**: `adws/adw_modules/workflow_ops.py:603` and `adws/adw_modules/git_ops.py:151`

**Root cause**: Both files log PR creation:
- `workflow_ops.py:603`: `logger.info(f"Created pull request: {pr_url}")`
- `git_ops.py:151`: `logger.info(f"Created PR: {pr_url}")`

The worker's stream reader in `worker/main.py:417` checks if any line contains "created" keyword and sends it as a progress update. Since both log messages contain "created", both get sent to the user.

The git_ops.py message is redundant since workflow_ops.py is the function that actually creates the PR and returns the result. The git_ops.py call is just logging the returned value.

## Relevant Files
Use these files to fix the bug:

### `worker/main.py`
- Contains the `send_status()` method that filters messages based on reporting level
- Line 79-89: Currently only filters "progress" status messages, not "started" status
- **Fix needed**: Add logic to filter "started" status in basic/minimal reporting modes

### `adws/adw_modules/git_ops.py`
- Line 151: Contains duplicate PR creation log message `logger.info(f"Created PR: {pr_url}")`
- **Fix needed**: Remove this redundant log statement since workflow_ops.py already logs PR creation

## Step by Step Tasks

### Remove duplicate PR log message
- Open `adws/adw_modules/git_ops.py`
- Locate line 151: `logger.info(f"Created PR: {pr_url}")`
- Remove this line completely
- Keep the surrounding if/else logic intact, only remove the duplicate log statement

### Filter "started" status in basic mode
- Open `worker/main.py`
- Locate the `send_status()` method (lines 54-100)
- Currently line 79-89 only filters "progress" messages: `if status == "progress":`
- Modify the filtering logic to also filter "started" status in basic and minimal modes
- The "started" message is redundant because the bot handler already sends "🚀 *AI-Driven Workflow Started*" when queuing the task
- Keep "finished" and "failed" status messages unfiltered (always send these important messages)
- Apply the same MessageFilter logic: in basic/minimal mode, don't send "started" status

## Notes
- This is a minimal fix targeting only the duplicate messages
- The bot handler's initial "🚀 *AI-Driven Workflow Started*" message should remain as immediate user feedback
- The worker's "started" status becomes redundant in basic mode since the user already knows the workflow started
- Only remove the duplicate log in git_ops.py, not the one in workflow_ops.py (which is the source of truth)
- Don't modify the stream reader keyword logic - just remove the duplicate log source
