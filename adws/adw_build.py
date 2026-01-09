#!/usr/bin/env -S uv run
# /// script
# dependencies = ["python-dotenv", "pydantic"]
# ///

"""
ADW Build - AI Developer Workflow for agentic building

Usage:
  python adw_build.py <task-id> <adw-id>

Workflow:
1. Find existing plan (from state or by searching)
2. Implement the solution based on plan
3. Commit implementation
4. Push and update PR

Task input is read from task_input.json file (created by Hermes worker).
"""

import sys
import os
import logging
import json
import subprocess
from typing import Optional
from dotenv import load_dotenv

from adw_modules.state import ADWState
from adw_modules.git_ops import commit_changes, finalize_git_operations, get_current_branch, get_repo_url, extract_repo_path
from adw_modules.workflow_ops import (
    implement_plan,
    create_commit_from_task,
    classify_task,
    format_issue_message,
    AGENT_IMPLEMENTOR,
)
from adw_modules.utils import setup_logger, load_task_input


def check_env_vars(logger: Optional[logging.Logger] = None) -> None:
    """Check that all required environment variables are set."""
    required_vars = [
        "ANTHROPIC_API_KEY",
        "CLAUDE_CODE_PATH",
    ]
    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        error_msg = "Error: Missing required environment variables:"
        if logger:
            logger.error(error_msg)
            for var in missing_vars:
                logger.error(f"  - {var}")
        else:
            print(error_msg, file=sys.stderr)
            for var in missing_vars:
                print(f"  - {var}", file=sys.stderr)
        sys.exit(1)


def main():
    """Main entry point."""
    # Load environment variables
    load_dotenv()

    # Parse command line args
    # INTENTIONAL: adw-id is REQUIRED - we cannot search for it because:
    # 1. The plan file is stored in state and identified by adw-id
    # 2. Multiple ADW runs for the same task could exist
    # 3. We need to know exactly which plan to implement
    if len(sys.argv) < 3:
        print("Usage: python adw_build.py <task-id> <adw-id>")
        print("\nError: adw-id is required to locate the plan file created by adw_plan.py")
        print("The plan file is stored at: specs/task-{task_id}-adw-{adw_id}-*.md")
        sys.exit(1)

    task_id = sys.argv[1]
    adw_id = sys.argv[2]

    # Try to load existing state
    temp_logger = setup_logger(adw_id, "adw_build")
    state = ADWState.load(adw_id, temp_logger)
    if state:
        # Found existing state - use the task_id from state if available
        task_id = state.get("task_id", task_id)
        temp_logger.info(f"Found existing state - resuming build")
    else:
        # No existing state found
        logger = setup_logger(adw_id, "adw_build")
        logger.error(f"No state found for ADW ID: {adw_id}")
        logger.error("Run adw_plan.py first to create the plan and state")
        print(f"\nError: No state found for ADW ID: {adw_id}")
        print("Run adw_plan.py first to create the plan and state")
        sys.exit(1)

    # Set up logger with ADW ID from command line
    logger = setup_logger(adw_id, "adw_build")
    logger.info(f"ADW Build starting - ID: {adw_id}, Task ID: {task_id}")

    # Validate environment
    check_env_vars(logger)

    # Load task input from file
    try:
        task_data = load_task_input(task_id, logger)
    except Exception as e:
        logger.error(f"Error loading task input: {e}")
        sys.exit(1)

    logger.info(f"Task: {task_data.get('title')}")
    if task_data.get("jira_ticket"):
        logger.info(f"Jira ticket: {task_data['jira_ticket']}")

    # Ensure we have required state fields
    if not state.get("branch_name"):
        error_msg = "No branch name in state - run adw_plan.py first"
        logger.error(error_msg)
        sys.exit(1)

    if not state.get("plan_file"):
        error_msg = "No plan file in state - run adw_plan.py first"
        logger.error(error_msg)
        sys.exit(1)

    # Checkout the branch from state
    branch_name = state.get("branch_name")
    result = subprocess.run(["git", "checkout", branch_name], capture_output=True, text=True)
    if result.returncode != 0:
        logger.error(f"Failed to checkout branch {branch_name}: {result.stderr}")
        sys.exit(1)
    logger.info(f"Checked out branch: {branch_name}")

    # Get the plan file from state
    plan_file = state.get("plan_file")
    logger.info(f"Using plan file: {plan_file}")

    logger.info("✅ Starting implementation phase")

    # Implement the plan
    logger.info("Implementing solution")

    implement_response = implement_plan(plan_file, adw_id, logger)

    if not implement_response.success:
        logger.error(f"Error implementing solution: {implement_response.output}")
        sys.exit(1)

    logger.debug(f"Implementation response: {implement_response.output}")
    logger.info("✅ Solution implemented")

    # Get task classification from state or classify if needed
    task_command = state.get("task_class") or state.get("issue_class")
    if not task_command:
        logger.info("No task classification in state, running classify_task")
        task_command, error = classify_task(task_data, adw_id, logger)
        if error:
            logger.error(f"Error classifying task: {error}")
            # Default to feature if classification fails
            task_command = "/feature"
            logger.warning("Defaulting to /feature after classification error")
        else:
            # Save the classification for future use
            state.update(task_class=task_command, issue_class=task_command)
            state.save("adw_build")

    # Create commit message
    logger.info("Creating implementation commit")
    commit_msg, error = create_commit_from_task(AGENT_IMPLEMENTOR, task_data, task_command, adw_id, logger)

    if error:
        logger.error(f"Error creating commit message: {error}")
        sys.exit(1)

    # Commit the implementation
    success, error = commit_changes(commit_msg)

    if not success:
        logger.error(f"Error committing implementation: {error}")
        sys.exit(1)

    logger.info(f"Committed implementation: {commit_msg}")

    # Finalize git operations (push and PR)
    finalize_git_operations(state, logger)

    logger.info("✅ Implementation phase completed successfully")

    # Save final state
    state.save("adw_build")


if __name__ == "__main__":
    main()