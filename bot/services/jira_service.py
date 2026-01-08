import aiohttp
import structlog
from typing import Dict, Any, Optional
from base64 import b64encode

logger = structlog.get_logger()


class JiraService:
    """Service for interacting with Jira Cloud API."""

    def __init__(self, jira_url: str, email: str, api_token: str):
        """
        Initialize Jira service.

        Args:
            jira_url: Jira Cloud URL (e.g., https://your-domain.atlassian.net)
            email: Jira user email
            api_token: Jira API token
        """
        self.jira_url = jira_url.rstrip("/")
        self.email = email
        self.api_token = api_token

        # Create Basic Auth credentials
        credentials = f"{email}:{api_token}"
        self.auth_header = b64encode(credentials.encode()).decode()

    async def get_issue(self, issue_key: str) -> Optional[Dict[str, Any]]:
        """
        Fetch issue details from Jira.

        Args:
            issue_key: Jira issue key (e.g., "MS-1234")

        Returns:
            Dictionary with issue details or None if not found
        """
        url = f"{self.jira_url}/rest/api/3/issue/{issue_key}"

        headers = {
            "Authorization": f"Basic {self.auth_header}",
            "Accept": "application/json",
        }

        # Request specific fields to reduce response size
        params = {
            "fields": "summary,description,status,priority,assignee,reporter,created,updated,issuetype,labels,components"
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        logger.info(
                            "Successfully fetched Jira issue",
                            issue_key=issue_key,
                        )
                        return self._format_issue(data)
                    elif response.status == 404:
                        logger.warning("Jira issue not found", issue_key=issue_key)
                        return None
                    elif response.status == 401:
                        logger.error(
                            "Jira authentication failed",
                            issue_key=issue_key,
                            status=response.status,
                        )
                        raise Exception("Jira authentication failed. Check your credentials.")
                    else:
                        error_text = await response.text()
                        logger.error(
                            "Failed to fetch Jira issue",
                            issue_key=issue_key,
                            status=response.status,
                            error=error_text,
                        )
                        raise Exception(f"Failed to fetch Jira issue: {response.status}")

        except aiohttp.ClientError as e:
            logger.error(
                "Network error fetching Jira issue",
                issue_key=issue_key,
                error=str(e),
            )
            raise Exception(f"Network error: {str(e)}")

    async def get_issue_with_comments(self, issue_key: str) -> Optional[Dict[str, Any]]:
        """
        Fetch issue details including comments from Jira.

        Args:
            issue_key: Jira issue key (e.g., "MS-1234")

        Returns:
            Dictionary with issue details and comments or None if not found
        """
        # First get the issue
        issue = await self.get_issue(issue_key)
        if not issue:
            return None

        # Now get comments
        url = f"{self.jira_url}/rest/api/3/issue/{issue_key}/comment"

        headers = {
            "Authorization": f"Basic {self.auth_header}",
            "Accept": "application/json",
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        comments = self._format_comments(data.get("comments", []))
                        issue["comments"] = comments
                        logger.info(
                            "Successfully fetched Jira issue with comments",
                            issue_key=issue_key,
                            comment_count=len(comments),
                        )
                        return issue
                    else:
                        # If comments fail, still return the issue
                        logger.warning(
                            "Failed to fetch comments, returning issue without comments",
                            issue_key=issue_key,
                            status=response.status,
                        )
                        issue["comments"] = []
                        return issue

        except aiohttp.ClientError as e:
            logger.warning(
                "Network error fetching comments, returning issue without comments",
                issue_key=issue_key,
                error=str(e),
            )
            issue["comments"] = []
            return issue

    def _format_comments(self, raw_comments: list) -> list[Dict[str, Any]]:
        """
        Format raw Jira comments into a cleaner structure.

        Args:
            raw_comments: Raw comments from Jira API

        Returns:
            List of formatted comments
        """
        formatted_comments = []

        for comment in raw_comments:
            author = comment.get("author", {})
            author_name = author.get("displayName", "Unknown")

            # Extract comment body (may be ADF format)
            body = self._extract_description(comment.get("body"))

            formatted_comments.append({
                "author": author_name,
                "created": comment.get("created", ""),
                "body": body
            })

        return formatted_comments

    def _format_issue(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format raw Jira API response into a cleaner structure.

        Args:
            raw_data: Raw response from Jira API

        Returns:
            Formatted issue data
        """
        fields = raw_data.get("fields", {})

        # Extract assignee name
        assignee = fields.get("assignee")
        assignee_name = assignee.get("displayName") if assignee else "Unassigned"

        # Extract reporter name
        reporter = fields.get("reporter")
        reporter_name = reporter.get("displayName") if reporter else "Unknown"

        # Extract status
        status = fields.get("status", {})
        status_name = status.get("name", "Unknown")

        # Extract priority
        priority = fields.get("priority", {})
        priority_name = priority.get("name", "None")

        # Extract issue type
        issue_type = fields.get("issuetype", {})
        issue_type_name = issue_type.get("name", "Unknown")

        # Extract labels
        labels = fields.get("labels", [])

        # Extract components
        components = fields.get("components", [])
        component_names = [c.get("name") for c in components]

        # Get description (may be in ADF format or plain text)
        description = self._extract_description(fields.get("description"))

        return {
            "key": raw_data.get("key"),
            "summary": fields.get("summary", ""),
            "description": description,
            "status": status_name,
            "priority": priority_name,
            "assignee": assignee_name,
            "reporter": reporter_name,
            "issue_type": issue_type_name,
            "created": fields.get("created", ""),
            "updated": fields.get("updated", ""),
            "labels": labels,
            "components": component_names,
            "url": f"{self.jira_url}/browse/{raw_data.get('key')}",
        }

    def _extract_description(self, description: Any) -> str:
        """
        Extract text from Jira description (may be ADF format or plain text).

        Args:
            description: Description field from Jira API

        Returns:
            Plain text description
        """
        if not description:
            return "No description"

        # If it's already a string, return it
        if isinstance(description, str):
            return description

        # If it's ADF (Atlassian Document Format), extract text
        if isinstance(description, dict):
            return self._extract_text_from_adf(description)

        return "No description"

    def _extract_text_from_adf(self, adf_node: Dict[str, Any]) -> str:
        """
        Recursively extract text from Atlassian Document Format.

        Args:
            adf_node: ADF node

        Returns:
            Plain text content
        """
        if not isinstance(adf_node, dict):
            return ""

        text_parts = []

        # If node has text, add it
        if "text" in adf_node:
            text_parts.append(adf_node["text"])

        # Recursively process content
        if "content" in adf_node and isinstance(adf_node["content"], list):
            for child in adf_node["content"]:
                child_text = self._extract_text_from_adf(child)
                if child_text:
                    text_parts.append(child_text)

        return " ".join(text_parts)
