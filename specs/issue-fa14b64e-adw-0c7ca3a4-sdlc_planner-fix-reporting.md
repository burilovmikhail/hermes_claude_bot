# Bug: Fix Telegram Bot Reporting - Too Much Information

## Bug Description
The Telegram bot is sending too many detailed progress messages during ADW workflow execution, creating noise and overwhelming the user. The reporting needs to be streamlined with:
- Keep the "started" message format (already good)
- Make "completed" message more concise with a brief summary
- Remove the "Progress Update" title from progress messages - just send the message content
- Remove task_id from progress messages (just show the actual progress text)
- Filter out service/technical messages like "created json file", "copied ADW scripts", etc.
- Make reporting verbosity configurable per ADW run (stored in adw_state, unique by adw_id)
- Default to basic reporting with minimal unnecessary details

## Problem Statement
Users receive excessive progress updates during ADW workflow execution that include:
1. Technical service messages (e.g., "Repository setup complete. Copying ADW scripts...", "created json file")
2. Progress messages with redundant headers ("Progress Update") and task IDs
3. No brief summary in completion messages
4. No way to configure reporting verbosity per workflow run

This creates a poor user experience with too much noise in the chat.

## Solution Statement
Implement a configurable reporting system that:
1. Adds a `reporting_level` field to ADWStateData (values: "minimal", "basic", "detailed", "verbose")
2. Filters messages in the worker based on reporting level before sending to bot
3. Simplifies progress message format (removes "Progress Update" title and task_id)
4. Adds brief summary to completion messages
5. Defaults to "basic" level which filters out technical/service messages
6. Allows users to specify reporting level in /adw command (e.g., `/adw report:verbose ...`)

## Steps to Reproduce
1. Run `/adw in the <repo> repo <task>` command
2. Observe multiple progress messages including:
   - "Repository setup complete. Copying ADW scripts..."
   - "Running ADW workflow: plan_build..."
   - Messages from ADW scripts with "created json file", etc.
   - Progress messages with "🔄 *Progress Update*\n\nTask ID: `xxx`\n<actual message>"
3. Note completion message lacks a brief summary of what was accomplished

## Root Cause Analysis
The root causes are:

1. **No message filtering in worker** (worker/main.py:374): All messages containing keywords "error", "failed", "completed", "created" are sent as progress updates without filtering for relevance

2. **Overly verbose progress messages** (worker/main.py:425-440, 508-509, etc.): Technical operations like "Updating repository", "Switching to main branch", "Cloning repository", "Copying ADW scripts" are all sent to users

3. **Progress message format includes unnecessary metadata** (bot/handlers/adw_handlers.py:313): Progress messages include "Progress Update" title and task_id which add clutter

4. **No reporting configuration** (adws/adw_modules/data_types.py:261-277): ADWStateData doesn't have a reporting_level field to control verbosity

5. **No reporting level parsing** (bot/services/adw_parser.py): The ADW command parser doesn't support `report:level` syntax

6. **Completion message lacks summary** (worker/main.py:173-178): The finished status only shows repository URL and workspace path, not what was actually accomplished

## Relevant Files

### Existing Files to Modify

- **adws/adw_modules/data_types.py** (lines 261-277)
  - Add `reporting_level` field to ADWStateData model
  - Define ReportingLevel literal type with values: "minimal", "basic", "detailed", "verbose"

- **bot/services/adw_parser.py**
  - Add support for parsing `report:level` syntax in ADW commands
  - Add reporting_level to parsed output (defaults to "basic")

- **bot/handlers/adw_handlers.py** (lines 159-169, 313)
  - Pass reporting_level from parsed command to task_data
  - Simplify progress message format (line 313) - remove "Progress Update" title and task_id
  - Update completion message format to include brief summary

- **worker/main.py** (lines 53-73, 112-119, 142, 161, 374-380, 425-440, 508-509)
  - Add reporting_level to task_data handling
  - Create message filtering logic based on reporting level
  - Filter technical/service messages at "basic" level
  - Reduce verbosity of repository operations messages
  - Only send filtered messages based on reporting level
  - Generate brief summary for completion status

### New Files

- **worker/reporting.py**
  - Create MessageFilter class with filtering logic
  - Define message categories (technical, progress, error, completion)
  - Implement filtering rules for each reporting level
  - Provide utility functions for determining message relevance

## Step by Step Tasks

### Add Reporting Level to Data Models

- Add `ReportingLevel` literal type to data_types.py with values: "minimal", "basic", "detailed", "verbose"
- Add `reporting_level` field to ADWStateData model with default value "basic"
- Ensure reporting_level is persisted in adw_state.json

### Update ADW Parser to Support Report Syntax

- Modify ADWParser.parse() to recognize `report:level` syntax (similar to `workflow:name`)
- Extract reporting level from command text
- Add `reporting_level` to parsed result dictionary with default "basic"
- Update validation to ensure reporting_level is valid

### Create Message Filtering System in Worker

- Create worker/reporting.py module with MessageFilter class
- Define message categories:
  - "technical": Repository operations, file operations, setup messages
  - "workflow": High-level workflow progress
  - "agent": Claude Code agent outputs
  - "error": Errors and failures
  - "completion": Final results
- Implement filter_message(message: str, reporting_level: str, category: str) -> bool
- Define filtering rules:
  - "minimal": Only completion and error messages
  - "basic": completion, error, and high-level workflow messages (filter out technical details)
  - "detailed": completion, error, workflow, and some technical messages
  - "verbose": All messages (no filtering)

### Update Worker to Use Message Filtering

- Import MessageFilter in worker/main.py
- Modify send_status() to accept optional reporting_level and category parameters
- Apply message filtering before publishing to Redis
- Update all send_status() calls to pass appropriate category
- Categorize existing messages:
  - "Updating repository", "Cloning repository", "Copying ADW scripts" → "technical"
  - "Starting workflow", "Running ADW workflow" → "workflow"
  - ADW script output (line 374) → categorize based on content
- Filter messages containing "created json file", "setup complete", "copied" at "basic" level

### Simplify Progress Message Format in Bot Handler

- Modify handle_adw_response() in bot/handlers/adw_handlers.py (line 313)
- Change progress message format from:
  - `f"🔄 *Progress Update*\n\nTask ID: `{escape_markdown(task_id)}`\n{escape_markdown(message)}"`
- To:
  - `f"🔄 {escape_markdown(message)}"`
- Keep task_id available for debugging in logs but don't show to user

### Add Summary Generation for Completion Messages

- Create generate_completion_summary() function in worker/reporting.py
- Extract key information from workflow execution:
  - Branch created/used
  - Plan file created (if any)
  - Commits made (if any)
  - Tests run status (if applicable)
- Format as brief bullet-point summary
- Modify worker/main.py completion message (line 173-178) to include summary

### Update ADW Handler to Pass Reporting Level

- Modify adw_handler() in bot/handlers/adw_handlers.py (line 166)
- Add `reporting_level` field to task_data from parsed result
- Ensure reporting_level is passed through to worker

### Update Worker Task Processing

- Modify handle_adw_task() in worker/main.py (line 104)
- Extract reporting_level from task_data (default to "basic" if not present)
- Store reporting_level in ADWState for persistence
- Pass reporting_level to all send_status() calls

## Notes

- The reporting_level should be stored in ADWState so that scripts running later in the workflow can access it
- Default "basic" level should filter out messages containing: "setup", "copying", "copied", "installing", "installed", "created json", "prepared", "switching to"
- "minimal" level should only show: workflow started, workflow completed/failed
- "detailed" level should show workflow steps but not individual git operations
- "verbose" level should show everything (current behavior)
- The ADW command syntax would be: `/adw report:verbose in the bot repo fix login bug`
- Backward compatibility: If no report level specified, use "basic" as default
- Consider adding emoji indicators for different message types (keep 🔄 for progress, ✅ for completion, ❌ for errors)
- The completion summary should be concise (3-5 bullet points max) and focus on user-facing results, not technical details
