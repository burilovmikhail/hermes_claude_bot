import json
import structlog
from typing import Dict, Any, Optional
from openai import AsyncOpenAI

logger = structlog.get_logger()


class GitCommandParser:
    """Parser for /git commands using OpenAI."""

    def __init__(self, api_key: str):
        """
        Initialize Git command parser.

        Args:
            api_key: OpenAI API key
        """
        self.client = AsyncOpenAI(api_key=api_key)

    async def parse(self, command_text: str) -> Dict[str, Any]:
        """
        Parse /git command using OpenAI to extract structured information.

        Args:
            command_text: The text after /git command

        Returns:
            Dictionary with parsed parameters:
            - operation: 'add' or 'list' or 'remove' or None
            - short_name: Short name for repository (e.g., 'backend')
            - jira_prefix: Jira project prefix (e.g., 'MS', 'PROJ')
            - repo_url: Repository URL (short or full form)
            - error: Error message if parsing failed
        """
        system_prompt = """You are a Git command parser. Analyze the user's command and extract structured information.

Supported operations: 'add', 'list', 'remove'

For 'add' operation, extract:
1. short_name: A short memorable name for the repository (e.g., 'backend', 'frontend', 'api')
2. jira_prefix: The Jira project prefix/key (e.g., 'MS', 'PROJ', 'TEAM')
3. repo_url: The GitHub repository URL in any format:
   - Short form: owner/repo (e.g., 'EcorRouge/mcguire-sponsel-backend')
   - Full form: https://github.com/owner/repo
   - Full form with .git: https://github.com/owner/repo.git

For 'list' operation:
No additional parameters needed - just list all registered repositories

For 'remove' operation, extract:
1. short_name: The short name of the repository to remove (e.g., 'backend', 'api')
Alternative command names: 'rm', 'delete' should map to 'remove' operation

Return JSON in this exact format:
{
    "operation": "add" or "list" or "remove" or null,
    "short_name": "extracted name" or null,
    "jira_prefix": "extracted prefix" or null,
    "repo_url": "extracted url" or null,
    "error": "error message if cannot parse" or null
}

Examples:

Input: "add backend MS EcorRouge/mcguire-sponsel-backend"
Output: {"operation": "add", "short_name": "backend", "jira_prefix": "MS", "repo_url": "EcorRouge/mcguire-sponsel-backend", "error": null}

Input: "add the backend repo for MS project, it's at github.com/EcorRouge/mcguire-sponsel-backend"
Output: {"operation": "add", "short_name": "backend", "jira_prefix": "MS", "repo_url": "EcorRouge/mcguire-sponsel-backend", "error": null}

Input: "list"
Output: {"operation": "list", "short_name": null, "jira_prefix": null, "repo_url": null, "error": null}

Input: "add api PROJ https://github.com/myorg/api-service.git"
Output: {"operation": "add", "short_name": "api", "jira_prefix": "PROJ", "repo_url": "myorg/api-service", "error": null}

Input: "remove backend"
Output: {"operation": "remove", "short_name": "backend", "jira_prefix": null, "repo_url": null, "error": null}

Input: "rm api"
Output: {"operation": "remove", "short_name": "api", "jira_prefix": null, "repo_url": null, "error": null}

Input: "delete the backend repository"
Output: {"operation": "remove", "short_name": "backend", "jira_prefix": null, "repo_url": null, "error": null}

If you cannot determine the operation or required fields are missing, set error field with explanation."""

        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": command_text}
                ],
                response_format={"type": "json_object"},
                temperature=0.0
            )

            result = json.loads(response.choices[0].message.content)
            logger.info("Parsed git command", command=command_text, result=result)
            return result

        except json.JSONDecodeError as e:
            logger.error("Failed to decode OpenAI response", error=str(e))
            return {
                "operation": None,
                "short_name": None,
                "jira_prefix": None,
                "repo_url": None,
                "error": "Failed to parse command"
            }
        except Exception as e:
            logger.error("Error parsing git command", error=str(e))
            return {
                "operation": None,
                "short_name": None,
                "jira_prefix": None,
                "repo_url": None,
                "error": f"Error: {str(e)}"
            }

    @staticmethod
    def normalize_repo_url(repo_url: str) -> tuple[str, str]:
        """
        Normalize repository URL to short form and full form.

        Args:
            repo_url: Repository URL in any format

        Returns:
            Tuple of (short_form, full_url)
            - short_form: owner/repo
            - full_url: https://github.com/owner/repo.git
        """
        # Remove .git suffix if present
        repo_url = repo_url.rstrip("/").replace(".git", "")

        # Extract owner/repo from various formats
        if "github.com/" in repo_url:
            # Full URL format
            parts = repo_url.split("github.com/")[-1]
            short_form = parts.strip("/")
        else:
            # Already in short form
            short_form = repo_url.strip("/")

        # Build full URL
        full_url = f"https://github.com/{short_form}.git"

        return short_form, full_url

    @staticmethod
    def validate_add_data(parsed_data: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """
        Validate parsed data for add operation.

        Args:
            parsed_data: Parsed command data

        Returns:
            Tuple of (is_valid, error_message)
        """
        if parsed_data.get("error"):
            return False, parsed_data["error"]

        if parsed_data.get("operation") != "add":
            return False, "Operation must be 'add'"

        required_fields = ["short_name", "jira_prefix", "repo_url"]
        for field in required_fields:
            if not parsed_data.get(field):
                return False, f"Missing required field: {field}"

        return True, None

    @staticmethod
    def validate_list_data(parsed_data: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """
        Validate parsed data for list operation.

        Args:
            parsed_data: Parsed command data

        Returns:
            Tuple of (is_valid, error_message)
        """
        if parsed_data.get("error"):
            return False, parsed_data["error"]

        if parsed_data.get("operation") != "list":
            return False, "Operation must be 'list'"

        return True, None

    @staticmethod
    def validate_remove_data(parsed_data: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """
        Validate parsed data for remove operation.

        Args:
            parsed_data: Parsed command data

        Returns:
            Tuple of (is_valid, error_message)
        """
        if parsed_data.get("error"):
            return False, parsed_data["error"]

        if parsed_data.get("operation") != "remove":
            return False, "Operation must be 'remove'"

        if not parsed_data.get("short_name"):
            return False, "Missing required field: short_name"

        return True, None
