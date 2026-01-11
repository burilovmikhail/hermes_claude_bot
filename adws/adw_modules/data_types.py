"""Data types for ADW workflows, Jira tickets, and Claude Code agent."""

from datetime import datetime
from typing import Optional, List, Literal, Dict, Any
from pydantic import BaseModel, Field

# Supported slash commands for task classification
# These should align with your custom slash commands in .claude/commands that you want to run
TaskClassSlashCommand = Literal["/chore", "/bug", "/feature"]
IssueClassSlashCommand = TaskClassSlashCommand  # Backward compatibility alias

# ADW workflow types
ADWWorkflow = Literal[
    "adw_plan",           # Planning only
    "adw_build",          # Building only (excluded from webhook)
    "adw_test",           # Testing only
    "adw_plan_build",     # Plan + Build
    "adw_plan_build_test" # Plan + Build + Test
]

# ADW reporting levels
ReportingLevel = Literal[
    "minimal",   # Only completion and error messages
    "basic",     # Completion, error, and high-level workflow messages (default)
    "detailed",  # Completion, error, workflow, and some technical messages
    "verbose"    # All messages (no filtering)
]

# All slash commands used in the ADW system
# Includes issue classification commands and ADW-specific commands
SlashCommand = Literal[
    # Issue classification commands
    "/chore",
    "/bug",
    "/feature",
    # ADW workflow commands
    "/classify_issue",
    "/classify_adw",
    "/find_plan_file",
    "/generate_branch_name",
    "/commit",
    "/pull_request",
    "/implement",
    "/test",
    "/resolve_failed_test",
    "/test_e2e",
    "/resolve_failed_e2e_test",
]


class GitHubUser(BaseModel):
    """GitHub user model."""

    id: Optional[str] = None  # Not always returned by GitHub API
    login: str
    name: Optional[str] = None
    is_bot: bool = Field(default=False, alias="is_bot")


class GitHubLabel(BaseModel):
    """GitHub label model."""

    id: str
    name: str
    color: str
    description: Optional[str] = None


class GitHubMilestone(BaseModel):
    """GitHub milestone model."""

    id: str
    number: int
    title: str
    description: Optional[str] = None
    state: str


class GitHubComment(BaseModel):
    """GitHub comment model."""

    id: str
    author: GitHubUser
    body: str
    created_at: datetime = Field(alias="createdAt")
    updated_at: Optional[datetime] = Field(
        None, alias="updatedAt"
    )  # Not always returned


class GitHubIssueListItem(BaseModel):
    """GitHub issue model for list responses (simplified)."""

    number: int
    title: str
    body: str
    labels: List[GitHubLabel] = []
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")

    class Config:
        populate_by_name = True


class GitHubIssue(BaseModel):
    """GitHub issue model."""

    number: int
    title: str
    body: str
    state: str
    author: GitHubUser
    assignees: List[GitHubUser] = []
    labels: List[GitHubLabel] = []
    milestone: Optional[GitHubMilestone] = None
    comments: List[GitHubComment] = []
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    closed_at: Optional[datetime] = Field(None, alias="closedAt")
    url: str

    class Config:
        populate_by_name = True


class JiraIssue(BaseModel):
    """Jira issue model (from Hermes Jira service)."""

    key: str  # e.g., "MS-1234"
    summary: str  # Issue title
    description: str  # Issue description
    status: str  # e.g., "To Do", "In Progress"
    priority: str  # e.g., "High", "Medium", "Low"
    assignee: str  # Assignee name or "Unassigned"
    reporter: str  # Reporter name
    issue_type: str  # e.g., "Bug", "Story", "Task"
    created: str  # ISO datetime string
    updated: str  # ISO datetime string
    labels: List[str] = []
    components: List[str] = []
    url: str  # Full URL to Jira issue
    comments: List[Dict[str, Any]] = []  # Optional comments


class TaskInput(BaseModel):
    """Generic task input - can be Jira-based or plain text."""

    # Task identification
    task_id: str  # Unique ID for this ADW task

    # Source - either jira or plain_text
    source: Literal["jira", "plain_text"]

    # For Jira tasks
    jira_ticket: Optional[str] = None
    jira_details: Optional[JiraIssue] = None

    # For all tasks
    title: str  # Derived from Jira summary or extracted from description
    description: str  # Full task description

    # Repository info
    repo_url: str  # Repository URL (e.g., "owner/repo" or full URL)

    # Workflow
    workflow_name: str = "plan_build"  # Default workflow

    # User info
    telegram_id: int

    def to_prompt_text(self) -> str:
        """Convert task input to a prompt text for Claude."""
        if self.source == "jira" and self.jira_details:
            lines = [
                f"# Task: {self.title}",
                f"",
                f"**Jira Ticket:** {self.jira_ticket}",
                f"**Type:** {self.jira_details.issue_type}",
                f"**Priority:** {self.jira_details.priority}",
                f"**Status:** {self.jira_details.status}",
                f"",
                f"## Description",
                self.jira_details.description,
            ]

            if self.jira_details.comments:
                lines.extend([
                    "",
                    "## Comments",
                ])
                for comment in self.jira_details.comments:
                    author = comment.get("author", "Unknown")
                    body = comment.get("body", "")
                    lines.append(f"- **{author}:** {body}")

            return "\n".join(lines)
        else:
            return f"# Task: {self.title}\n\n{self.description}"


class AgentPromptRequest(BaseModel):
    """Claude Code agent prompt configuration."""

    prompt: str
    adw_id: str
    agent_name: str = "ops"
    model: Literal["sonnet", "opus"] = "sonnet"
    dangerously_skip_permissions: bool = False
    output_file: str


class AgentPromptResponse(BaseModel):
    """Claude Code agent response."""

    output: str
    success: bool
    session_id: Optional[str] = None


class AgentTemplateRequest(BaseModel):
    """Claude Code agent template execution request."""

    agent_name: str
    slash_command: SlashCommand
    args: List[str]
    adw_id: str
    model: Literal["sonnet", "opus"] = "sonnet"


class ClaudeCodeResultMessage(BaseModel):
    """Claude Code JSONL result message (last line)."""

    type: str
    subtype: str
    is_error: bool
    duration_ms: int
    duration_api_ms: int
    num_turns: int
    result: str
    session_id: str
    total_cost_usd: float


class TestResult(BaseModel):
    """Individual test result from test suite execution."""

    test_name: str
    passed: bool
    execution_command: str
    test_purpose: str
    error: Optional[str] = None


class E2ETestResult(BaseModel):
    """Individual E2E test result from browser automation."""

    test_name: str
    status: Literal["passed", "failed"]
    test_path: str  # Path to the test file for re-execution
    screenshots: List[str] = []
    error: Optional[str] = None

    @property
    def passed(self) -> bool:
        """Check if test passed."""
        return self.status == "passed"


class ADWStateData(BaseModel):
    """Minimal persistent state for ADW workflow.

    Stored in agents/{adw_id}/adw_state.json
    Contains only essential identifiers to connect workflow steps.
    """

    adw_id: str
    task_id: Optional[str] = None  # Unique task ID from Hermes
    issue_number: Optional[str] = None  # Backward compatibility for GitHub workflows
    jira_ticket: Optional[str] = None  # Jira ticket key if applicable
    task_title: Optional[str] = None  # Task title
    task_description: Optional[str] = None  # Task description
    branch_name: Optional[str] = None
    plan_file: Optional[str] = None
    issue_class: Optional[IssueClassSlashCommand] = None
    task_class: Optional[TaskClassSlashCommand] = None  # Same as issue_class, more generic name
    reporting_level: ReportingLevel = "basic"  # Controls message verbosity (default: basic)
