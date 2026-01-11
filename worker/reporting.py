"""Message filtering and reporting utilities for ADW workflows."""

import re
from typing import Literal

MessageCategory = Literal["technical", "workflow", "agent", "error", "completion"]
ReportingLevel = Literal["minimal", "basic", "detailed", "verbose"]


class MessageFilter:
    """Filters messages based on reporting level and message category."""

    # Technical keywords that indicate low-level operations
    TECHNICAL_KEYWORDS = [
        "setup",
        "copying",
        "copied",
        "installing",
        "installed",
        "created json",
        "prepared",
        "switching to",
        "updating repository",
        "cloning repository",
        "running git",
    ]

    # Workflow keywords that indicate high-level progress
    WORKFLOW_KEYWORDS = [
        "starting workflow",
        "running adw",
        "workflow started",
        "executing",
        "planning",
        "building",
        "testing",
    ]

    # Error keywords
    ERROR_KEYWORDS = [
        "error",
        "failed",
        "failure",
        "exception",
        "traceback",
    ]

    @staticmethod
    def should_send_message(
        message: str,
        reporting_level: ReportingLevel,
        category: MessageCategory
    ) -> bool:
        """
        Determine if a message should be sent based on reporting level and category.

        Args:
            message: The message text
            reporting_level: The reporting verbosity level
            category: The message category

        Returns:
            True if the message should be sent, False otherwise
        """
        # Verbose mode: send everything
        if reporting_level == "verbose":
            return True

        # Minimal mode: only completion and error messages
        if reporting_level == "minimal":
            return category in ["completion", "error"]

        # Basic mode: completion, error, and workflow messages (filter out technical)
        if reporting_level == "basic":
            if category in ["completion", "error"]:
                return True
            if category == "workflow":
                return True
            if category == "technical":
                return False
            # For uncategorized messages, check if they contain technical keywords
            if MessageFilter._is_technical_message(message):
                return False
            return True

        # Detailed mode: completion, error, workflow, and some technical messages
        if reporting_level == "detailed":
            if category in ["completion", "error", "workflow"]:
                return True
            if category == "technical":
                # Allow some technical messages in detailed mode
                return MessageFilter._is_high_level_technical(message)
            return True

        # Default: send the message
        return True

    @staticmethod
    def _is_technical_message(message: str) -> bool:
        """Check if message contains technical keywords."""
        message_lower = message.lower()
        return any(keyword in message_lower for keyword in MessageFilter.TECHNICAL_KEYWORDS)

    @staticmethod
    def _is_high_level_technical(message: str) -> bool:
        """
        Check if technical message is high-level enough for detailed mode.
        Filters out very low-level operations like "created json file".
        """
        message_lower = message.lower()
        # Exclude very low-level operations
        low_level_patterns = [
            "created json",
            "copied adw",
            "installing dependencies",
            "git checkout",
            "git fetch",
        ]
        return not any(pattern in message_lower for pattern in low_level_patterns)

    @staticmethod
    def categorize_message(message: str) -> MessageCategory:
        """
        Automatically categorize a message based on its content.

        Args:
            message: The message text

        Returns:
            The message category
        """
        message_lower = message.lower()

        # Check for error messages
        if any(keyword in message_lower for keyword in MessageFilter.ERROR_KEYWORDS):
            return "error"

        # Check for completion messages
        if any(keyword in message_lower for keyword in ["completed", "finished", "done", "success"]):
            return "completion"

        # Check for workflow messages
        if any(keyword in message_lower for keyword in MessageFilter.WORKFLOW_KEYWORDS):
            return "workflow"

        # Check for technical messages
        if MessageFilter._is_technical_message(message):
            return "technical"

        # Default to agent category (Claude Code agent output)
        return "agent"


def generate_completion_summary(
    repo_dir: str,
    branch_name: str = None,
    plan_file: str = None,
    commits_made: int = 0,
    tests_run: bool = False,
    tests_passed: bool = False
) -> str:
    """
    Generate a brief completion summary for ADW workflow.

    Args:
        repo_dir: Repository directory path
        branch_name: Branch name if created/used
        plan_file: Plan file path if created
        commits_made: Number of commits made
        tests_run: Whether tests were run
        tests_passed: Whether tests passed

    Returns:
        Brief summary text
    """
    summary_parts = []

    if branch_name:
        summary_parts.append(f"Branch: {branch_name}")

    if plan_file:
        summary_parts.append(f"Plan: {plan_file}")

    if commits_made > 0:
        summary_parts.append(f"Commits: {commits_made}")

    if tests_run:
        status = "passed" if tests_passed else "failed"
        summary_parts.append(f"Tests: {status}")

    if summary_parts:
        return "\n".join(f"• {part}" for part in summary_parts)
    else:
        return "Workflow completed successfully"
