#!/usr/bin/env -S uv run
# /// script
# dependencies = ["python-dotenv", "pydantic"]
# ///

"""
ADW Plan - AI Developer Workflow for agentic planning

Usage:
  python adw_plan.py <task-id> [adw-id]

Workflow:
1. Load task details from task_input.json
2. Classify task type (/chore, /bug, /feature)
3. Create feature branch
4. Generate implementation plan
5. Commit plan
6. Push and create/update PR

Task input is read from task_input.json file (created by Hermes worker).
"""

import sys
import os
import logging
import json
from typing import Optional
from dotenv import load_dotenv

from adw_modules.state import ADWState
from adw_modules.git_ops import create_branch, commit_changes, finalize_git_operations, get_repo_url, extract_repo_path
from adw_modules.workflow_ops import (
    classify_task,
    build_plan_from_task,
    get_plan_file,
    generate_branch_name_from_task,
    create_commit_from_task,
    format_issue_message,
    ensure_adw_id,
    AGENT_PLANNER,
)
from adw_modules.utils import setup_logger, load_task_input
from adw_modules.data_types import IssueClassSlashCommand


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
    if len(sys.argv) < 2:
        print("Usage: python adw_plan.py <task-id> [adw-id]")
        print("\nNote: This script expects task_input.json to exist in the adws directory.")
        sys.exit(1)

    task_id = sys.argv[1]
    adw_id = sys.argv[2] if len(sys.argv) > 2 else None

    # Ensure ADW ID exists with initialized state
    temp_logger = setup_logger(adw_id, "adw_plan") if adw_id else None
    adw_id = ensure_adw_id(task_id, adw_id, temp_logger)

    # Load the state that was created/found by ensure_adw_id
    state = ADWState.load(adw_id, temp_logger)

    # Ensure state has the adw_id field
    if not state.get("adw_id"):
        state.update(adw_id=adw_id)

    # Set up logger with ADW ID
    logger = setup_logger(adw_id, "adw_plan")
    logger.info(f"ADW Plan starting - ID: {adw_id}, Task ID: {task_id}")

    # Validate environment
    check_env_vars(logger)

    # Load task input from file
    try:
        task_data = load_task_input(task_id, logger)
    except Exception as e:
        logger.error(f"Error loading task input: {e}")
        sys.exit(1)

    # Store task info in state
    state.update(
        task_id=task_id,
        task_title=task_data.get("title"),
        task_description=task_data.get("description"),
        jira_ticket=task_data.get("jira_ticket")
    )
    state.save("adw_plan")

    logger.info(f"Task: {task_data.get('title')}")
    if task_data.get("jira_ticket"):
        logger.info(f"Jira ticket: {task_data['jira_ticket']}")

    # Classify the task
    task_command, error = classify_task(task_data, adw_id, logger)

    if error:
        logger.error(f"Error classifying task: {error}")
        sys.exit(1)

    state.update(issue_class=task_command, task_class=task_command)
    state.save("adw_plan")
    logger.info(f"Task classified as: {task_command}")

    # Generate branch name
    branch_name, error = generate_branch_name_from_task(task_data, task_command, adw_id, logger)

    if error:
        logger.error(f"Error generating branch name: {error}")
        sys.exit(1)

    # Create git branch
    success, error = create_branch(branch_name)

    if not success:
        logger.error(f"Error creating branch: {error}")
        sys.exit(1)

    state.update(branch_name=branch_name)
    state.save("adw_plan")
    logger.info(f"Working on branch: {branch_name}")

    # Build the implementation plan
    logger.info("Building implementation plan")

    plan_response = build_plan_from_task(task_data, task_command, adw_id, logger)

    if not plan_response.success:
        logger.error(f"Error building plan: {plan_response.output}")
        sys.exit(1)

    logger.debug(f"Plan response: {plan_response.output}")
    logger.info("✅ Implementation plan created")

    # Find the plan file that was created
    logger.info("Finding plan file")
    plan_file_path, error = get_plan_file(
        plan_response.output, task_id, adw_id, logger
    )

    if error:
        logger.error(f"Error finding plan file: {error}")
        sys.exit(1)

    state.update(plan_file=plan_file_path)
    state.save("adw_plan")
    logger.info(f"Plan file created: {plan_file_path}")

    # Create commit message
    logger.info("Creating plan commit")
    commit_msg, error = create_commit_from_task(
        AGENT_PLANNER, task_data, task_command, adw_id, logger
    )

    if error:
        logger.error(f"Error creating commit message: {error}")
        sys.exit(1)

    # Commit the plan
    success, error = commit_changes(commit_msg)

    if success:
        logger.info(f"Committed plan: {commit_msg}")
    else:
        logger.info(f"Plan already commited")    

    # Finalize git operations (push and PR)
    finalize_git_operations(state, logger, task_data)

    logger.info("✅ Planning phase completed successfully")

    # Save final state
    state.save("adw_plan")

    # Log final state summary
    logger.info(f"📋 Final planning state:\n{json.dumps(state.data, indent=2)}")


if __name__ == "__main__":
    main()
