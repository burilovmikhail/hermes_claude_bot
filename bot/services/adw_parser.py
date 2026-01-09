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

    # Repo alias patterns - matches "in the <alias> repo" or "in <alias>"
    REPO_ALIAS_PATTERNS = [
        r"(?:in\s+the\s+)([a-zA-Z0-9_-]+)(?:\s+repo)",  # "in the bot repo"
        r"(?:in\s+)([a-zA-Z0-9_-]+)(?:\s+repo)",  # "in bot repo"
        r"(?:repo\s+alias:?\s*)([a-zA-Z0-9_-]+)",  # "repo alias: bot"
    ]

    @staticmethod
    def parse(command_text: str) -> Dict[str, Any]:
        """
        Parse /adw command to extract workflow parameters.

        Args:
            command_text: The text after /adw command

        Returns:
            Dictionary with parsed parameters:
            - workflow_name: Name of workflow (default: plan_build)
            - jira_ticket: Jira ticket ID if found
            - github_repo: GitHub repository if found (owner/repo format)
            - repo_alias: Repository short name/alias if found
            - jira_prefix: Jira project prefix extracted from ticket
            - task_description: Task description text
        """
        original_text = command_text.strip()
        result = {
            "workflow_name": "plan_build",  # default
            "jira_ticket": None,
            "jira_prefix": None,
            "github_repo": None,
            "repo_alias": None,
            "task_description": original_text
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
            # Extract prefix (e.g., "MS" from "MS-1234")
            result["jira_prefix"] = result["jira_ticket"].split("-")[0]

        # Extract GitHub repository (explicit format: repo:owner/repo or github.com/owner/repo)
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

        # Extract repo alias (e.g., "in the bot repo", "in ms-backend repo")
        for pattern in ADWParser.REPO_ALIAS_PATTERNS:
            alias_match = re.search(pattern, command_text, re.IGNORECASE)
            if alias_match:
                result["repo_alias"] = alias_match.group(1).lower()
                # Remove alias specification from task description
                command_text = re.sub(pattern, "", command_text, flags=re.IGNORECASE)
                break

        # Clean up task description (remove extra spaces)
        result["task_description"] = " ".join(command_text.split()).strip()

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
        # Check if we have repository identification (github_repo, repo_alias, or jira_ticket)
        has_repo = (
            parsed_data.get("github_repo") or
            parsed_data.get("repo_alias") or
            parsed_data.get("jira_ticket")
        )

        if not has_repo:
            return False, (
                "Please specify repository identification:\n"
                "- Use 'in the <alias> repo' (e.g., 'in the bot repo')\n"
                "- Or provide a Jira ticket (e.g., 'MS-1234')\n"
                "- Or use 'repo:owner/repo' format"
            )

        # Check if task description is not empty
        if not parsed_data.get("task_description"):
            return False, "Please provide a task description"

        return True, None
