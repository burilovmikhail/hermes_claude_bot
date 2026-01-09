"""Git operations for ADW composable architecture.

Provides centralized git operations that build on top of github.py module.
"""

import subprocess
import json
import logging
from typing import Optional, Tuple

# Import GitHub functions from existing module
from adw_modules.github import get_repo_url, extract_repo_path, make_issue_comment


def get_current_branch() -> str:
    """Get current git branch name."""
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True, text=True
    )
    return result.stdout.strip()


def push_branch(branch_name: str) -> Tuple[bool, Optional[str]]:
    """Push current branch to remote. Returns (success, error_message)."""
    result = subprocess.run(
        ["git", "push", "-u", "origin", branch_name],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        return False, result.stderr
    return True, None


def check_pr_exists(branch_name: str) -> Optional[str]:
    """Check if PR exists for branch. Returns PR URL if exists."""
    # Use github.py functions to get repo info
    try:
        repo_url = get_repo_url()
        repo_path = extract_repo_path(repo_url)
    except Exception as e:
        return None
    
    result = subprocess.run(
        ["gh", "pr", "list", "--repo", repo_path, "--head", branch_name, "--json", "url"],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        prs = json.loads(result.stdout)
        if prs:
            return prs[0]["url"]
    return None


def create_branch(branch_name: str) -> Tuple[bool, Optional[str]]:
    """Create and checkout a new branch. Returns (success, error_message)."""
    # Create branch
    result = subprocess.run(
        ["git", "checkout", "-b", branch_name],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        # Check if error is because branch already exists
        if "already exists" in result.stderr:
            # Try to checkout existing branch
            result = subprocess.run(
                ["git", "checkout", branch_name],
                capture_output=True, text=True
            )
            if result.returncode != 0:
                return False, result.stderr
            return True, None
        return False, result.stderr
    return True, None


def ensure_gitignore() -> None:
    """Ensure .gitignore excludes agents directory."""
    import os
    gitignore_path = ".gitignore"
    agents_entry = "agents/"

    # Read existing .gitignore if it exists
    existing_entries = []
    if os.path.exists(gitignore_path):
        with open(gitignore_path, "r") as f:
            existing_entries = f.read().splitlines()

    # Check if agents/ is already ignored
    if agents_entry not in existing_entries:
        # Add agents/ to .gitignore
        with open(gitignore_path, "a") as f:
            if existing_entries and not existing_entries[-1].strip() == "":
                f.write("\n")
            f.write(f"# ADW agent files (auto-generated)\n")
            f.write(f"{agents_entry}\n")


def commit_changes(message: str) -> Tuple[bool, Optional[str]]:
    """Stage all changes and commit. Returns (success, error_message)."""
    # Check if there are changes to commit
    result = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
    if not result.stdout.strip():
        return True, None  # No changes to commit

    # Ensure .gitignore is set up to exclude agents directory
    ensure_gitignore()

    # Stage all changes EXCEPT agents/ directory
    # Using pathspec to exclude agents/
    result = subprocess.run(
        ["git", "add", "-A", "--", ".", ":!agents/"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        return False, result.stderr

    # If agents/ files were already tracked, unstage them
    result = subprocess.run(
        ["git", "reset", "HEAD", "agents/"],
        capture_output=True, text=True
    )
    # Ignore errors from reset (it's ok if agents/ doesn't exist in staging)

    # Commit
    result = subprocess.run(
        ["git", "commit", "-m", message],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        return False, result.stderr
    return True, None


def finalize_git_operations(state: 'ADWState', logger: logging.Logger, task_data: dict = None) -> None:
    """Standard git finalization: push branch and create/update PR.

    Args:
        state: ADW state
        logger: Logger instance
        task_data: Optional task data dictionary (for task-based workflows)
    """
    branch_name = state.get("branch_name")
    if not branch_name:
        # Fallback: use current git branch if not main
        current_branch = get_current_branch()
        if current_branch and current_branch != "main":
            logger.warning(f"No branch name in state, using current branch: {current_branch}")
            branch_name = current_branch
        else:
            logger.error("No branch name in state and current branch is main, skipping git operations")
            return

    # Always push
    success, error = push_branch(branch_name)
    if not success:
        logger.error(f"Failed to push branch: {error}")
        return

    logger.info(f"Pushed branch: {branch_name}")

    # Handle PR
    pr_url = check_pr_exists(branch_name)

    if pr_url:
        logger.info(f"Found existing PR: {pr_url}")
    else:
        # Create new PR using task data or state data
        try:
            # Create a simplified issue-like structure from task data
            issue = None
            if task_data:
                # Convert task data to a format the PR creator can use
                issue = {
                    "number": task_data.get("task_id", ""),
                    "title": task_data.get("title", ""),
                    "body": task_data.get("description", ""),
                    "labels": [],
                }
                if task_data.get("jira_ticket"):
                    issue["title"] = f"[{task_data['jira_ticket']}] {issue['title']}"

            from adw_modules.workflow_ops import create_pull_request
            pr_url, error = create_pull_request(branch_name, issue, state, logger)

            if pr_url:
                logger.info(f"Created PR: {pr_url}")
            else:
                logger.error(f"Failed to create PR: {error}")
        except Exception as e:
            logger.error(f"Failed to create PR: {e}")