#!/usr/bin/env -S uv run
# /// script
# dependencies = ["python-dotenv", "pydantic"]
# ///

"""
ADW Plan & Build - AI Developer Workflow for agentic planning and building

Usage: python adw_plan_build.py <task-id> [adw-id]

This script runs:
1. adw_plan.py - Planning phase
2. adw_build.py - Implementation phase

The scripts are chained together via persistent state (adw_state.json).
Task input is read from task_input.json file (created by Hermes worker).
"""

import subprocess
import sys
import os

# Add the parent directory to Python path to import modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from adw_modules.workflow_ops import ensure_adw_id
from adw_modules.utils import load_task_input


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python adw_plan_build.py <task-id> [adw-id]")
        print("\nNote: This script expects task_input.json to exist in the adws directory.")
        print("The task_input.json file is created by the Hermes worker service.")
        sys.exit(1)

    task_id = sys.argv[1]
    adw_id = sys.argv[2] if len(sys.argv) > 2 else None

    # Load task input from file
    try:
        task_input = load_task_input(task_id)
        print(f"Loaded task: {task_input.get('title')}")
        if task_input.get('jira_ticket'):
            print(f"Jira ticket: {task_input['jira_ticket']}")
    except Exception as e:
        print(f"Error loading task input: {e}")
        print("Make sure task_input.json exists in the adws directory.")
        sys.exit(1)

    # Ensure ADW ID exists with initialized state
    # Note: We use task_id instead of issue_number for the second parameter
    adw_id = ensure_adw_id(task_id, adw_id)
    print(f"Using ADW ID: {adw_id}")

    # Get the directory where this script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Run plan with the ADW ID
    plan_cmd = [
        "python",
        os.path.join(script_dir, "adw_plan.py"),
        task_id,
        adw_id,
    ]
    print(f"Running: {' '.join(plan_cmd)}")
    plan = subprocess.run(plan_cmd)
    if plan.returncode != 0:
        print(f"Planning phase failed with exit code {plan.returncode}")
        sys.exit(1)

    # Run build with the ADW ID
    build_cmd = [
        "python",
        os.path.join(script_dir, "adw_build.py"),
        task_id,
        adw_id,
    ]
    print(f"Running: {' '.join(build_cmd)}")
    build = subprocess.run(build_cmd)
    if build.returncode != 0:
        print(f"Build phase failed with exit code {build.returncode}")
        sys.exit(1)

    print(f"\n✅ Workflow completed successfully!")
    print(f"Task ID: {task_id}")
    print(f"ADW ID: {adw_id}")


if __name__ == "__main__":
    main()
