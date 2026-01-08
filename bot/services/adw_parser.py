import re
import structlog
from typing import Dict, Any, Optional

logger = structlog.get_logger()


class ADWParser:
    """Parser for AI-Driven Workflow (ADW) commands."""

    # Regex patterns
    JIRA_PATTERN = r"\b([A-Z]+-\d+)\b"
    GITHUB_REPO_PATTERN = r"(?:github\.com/|repo:?\s*)([a-zA-Z0-9_-]+/[a-zA-Z0-9_.-]+)"
    WORKFLOW_PATTERN = r"workflow:?\s*(\w+)"

    @staticmethod
    def parse(command_text: str) -> Dict[str, Any]:
        """
        Parse /adw command to extract workflow parameters.

        Args:
            command_text: The text after /adw command

        Returns:
            Dictionary with parsed parameters:
            - workflow_name: Name of workflow (default: plan_build_test)
            - jira_ticket: Jira ticket ID if found
            - github_repo: GitHub repository if found
            - task_description: Task description text
        """
        result = {
            "workflow_name": "plan_build_test",  # default
            "jira_ticket": None,
            "github_repo": None,
            "task_description": command_text.strip()
        }

        # Extract workflow name
        workflow_match = re.search(
            ADWParser.WORKFLOW_PATTERN,
            command_text,
            re.IGNORECASE
        )
        if workflow_match:
            result["workflow_name"] = workflow_match.group(1)
            # Remove workflow specification from task description
            command_text = re.sub(
                ADWParser.WORKFLOW_PATTERN,
                "",
                command_text,
                flags=re.IGNORECASE
            )

        # Extract Jira ticket
        jira_match = re.search(ADWParser.JIRA_PATTERN, command_text)
        if jira_match:
            result["jira_ticket"] = jira_match.group(1).upper()

        # Extract GitHub repository
        repo_match = re.search(
            ADWParser.GITHUB_REPO_PATTERN,
            command_text,
            re.IGNORECASE
        )
        if repo_match:
            result["github_repo"] = repo_match.group(1)
            # Remove repo specification from task description
            command_text = re.sub(
                ADWParser.GITHUB_REPO_PATTERN,
                "",
                command_text,
                flags=re.IGNORECASE
            )

        # Clean up task description
        result["task_description"] = command_text.strip()

        logger.info("Parsed ADW command", **result)
        return result

    @staticmethod
    def validate(parsed_data: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """
        Validate parsed ADW command data.

        Args:
            parsed_data: Parsed command data

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check if we have either a GitHub repo or Jira ticket
        if not parsed_data.get("github_repo") and not parsed_data.get("jira_ticket"):
            return False, "Please specify either a GitHub repository or a Jira ticket"

        # Check if task description is not empty
        if not parsed_data.get("task_description"):
            return False, "Please provide a task description"

        return True, None
