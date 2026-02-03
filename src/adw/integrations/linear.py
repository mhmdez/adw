"""Linear integration for ADW.

Enables ADW to poll Linear for issues and sync status bidirectionally.

Configuration:
    Environment variables:
    - LINEAR_API_KEY: Linear API key (required)
    - LINEAR_TEAM_ID: Team ID to poll (optional, defaults to first team)

    Or via config file (~/.adw/config.toml):
    [linear]
    api_key = "lin_api_..."
    team_id = "abc123..."
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from rich.console import Console

console = Console()


# Linear workflow state mapping
LINEAR_TO_ADW_STATUS = {
    "backlog": "pending",
    "unstarted": "pending",
    "triage": "pending",
    "todo": "pending",
    "in progress": "in_progress",
    "in review": "in_progress",
    "done": "completed",
    "completed": "completed",
    "canceled": "failed",
    "cancelled": "failed",
    "duplicate": "failed",
}

# ADW to Linear state names (used for state lookup)
ADW_TO_LINEAR_STATUS = {
    "pending": "Todo",
    "in_progress": "In Progress",
    "completed": "Done",
    "failed": "Canceled",
}


@dataclass
class LinearConfig:
    """Configuration for Linear integration.

    Attributes:
        api_key: Linear API key.
        team_id: Team ID to poll (optional, uses first team if not set).
        poll_interval: Seconds between polls (default: 60).
        filter_states: Only process issues in these states.
        sync_comments: Whether to sync ADW updates as comments.
        label_filter: Only process issues with these labels.
    """

    api_key: str
    team_id: str | None = None
    poll_interval: int = 60
    filter_states: list[str] = field(
        default_factory=lambda: ["Backlog", "Todo", "Triage"]
    )
    sync_comments: bool = True
    label_filter: list[str] = field(default_factory=list)

    @classmethod
    def from_env(cls) -> LinearConfig | None:
        """Create config from environment variables.

        Returns:
            LinearConfig or None if required vars not set.
        """
        api_key = os.environ.get("LINEAR_API_KEY", "")

        if not api_key:
            return None

        return cls(
            api_key=api_key,
            team_id=os.environ.get("LINEAR_TEAM_ID"),
            poll_interval=int(os.environ.get("LINEAR_POLL_INTERVAL", "60")),
        )

    @classmethod
    def from_config_file(cls, path: Path | None = None) -> LinearConfig | None:
        """Load config from TOML file.

        Args:
            path: Path to config file (default: ~/.adw/config.toml).

        Returns:
            LinearConfig or None if not configured.
        """
        if path is None:
            path = Path.home() / ".adw" / "config.toml"

        if not path.exists():
            return None

        try:
            import tomli

            with open(path, "rb") as f:
                config = tomli.load(f)
        except ImportError:
            # Fallback: simple TOML parsing for [linear] section
            config = _parse_simple_toml(path)

        linear_config = config.get("linear", {})
        if not linear_config.get("api_key"):
            return None

        return cls(
            api_key=linear_config["api_key"],
            team_id=linear_config.get("team_id"),
            poll_interval=linear_config.get("poll_interval", 60),
            filter_states=linear_config.get(
                "filter_states", ["Backlog", "Todo", "Triage"]
            ),
            sync_comments=linear_config.get("sync_comments", True),
            label_filter=linear_config.get("label_filter", []),
        )

    @classmethod
    def load(cls) -> LinearConfig | None:
        """Load config from environment or config file.

        Prefers environment variables over config file.

        Returns:
            LinearConfig or None if not configured.
        """
        # Try environment first
        config = cls.from_env()
        if config:
            return config

        # Fall back to config file
        return cls.from_config_file()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "team_id": self.team_id,
            "poll_interval": self.poll_interval,
            "filter_states": self.filter_states,
            "sync_comments": self.sync_comments,
            "label_filter": self.label_filter,
        }


@dataclass
class LinearIssue:
    """A Linear issue.

    Attributes:
        id: Linear issue ID.
        identifier: Issue identifier (e.g., "TEAM-123").
        title: Issue title.
        description: Issue description/body.
        state: Current workflow state name.
        state_id: Workflow state ID.
        priority: Priority level (0=none, 1=urgent, 2=high, 3=medium, 4=low).
        url: Linear issue URL.
        labels: List of label names.
        assignee_id: Assigned user ID.
        team_id: Team ID.
        adw_id: ADW task ID (stored in description or comment).
        created_at: Creation timestamp.
        updated_at: Last update timestamp.
    """

    id: str
    identifier: str
    title: str
    description: str = ""
    state: str = "Backlog"
    state_id: str = ""
    priority: int = 0
    url: str = ""
    labels: list[str] = field(default_factory=list)
    assignee_id: str | None = None
    team_id: str = ""
    adw_id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "identifier": self.identifier,
            "title": self.title,
            "description": self.description,
            "state": self.state,
            "state_id": self.state_id,
            "priority": self.priority,
            "url": self.url,
            "labels": self.labels,
            "assignee_id": self.assignee_id,
            "team_id": self.team_id,
            "adw_id": self.adw_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LinearIssue:
        """Create from dictionary."""
        return cls(
            id=data["id"],
            identifier=data["identifier"],
            title=data["title"],
            description=data.get("description", ""),
            state=data.get("state", "Backlog"),
            state_id=data.get("state_id", ""),
            priority=data.get("priority", 0),
            url=data.get("url", ""),
            labels=data.get("labels", []),
            assignee_id=data.get("assignee_id"),
            team_id=data.get("team_id", ""),
            adw_id=data.get("adw_id"),
            created_at=(
                datetime.fromisoformat(data["created_at"])
                if data.get("created_at")
                else None
            ),
            updated_at=(
                datetime.fromisoformat(data["updated_at"])
                if data.get("updated_at")
                else None
            ),
        )

    def get_workflow_or_default(self) -> str:
        """Get workflow based on priority and labels."""
        # Check for workflow labels
        for label in self.labels:
            label_lower = label.lower()
            if label_lower in ("sdlc", "workflow:sdlc"):
                return "sdlc"
            if label_lower in ("simple", "workflow:simple"):
                return "simple"
            if label_lower in ("standard", "workflow:standard"):
                return "standard"

        # Priority-based defaults
        if self.priority in (1, 2):  # Urgent or High
            return "sdlc"
        return "standard"

    def get_model_or_default(self) -> str:
        """Get model based on priority and labels."""
        # Check for model labels
        for label in self.labels:
            label_lower = label.lower()
            if label_lower in ("opus", "model:opus"):
                return "opus"
            if label_lower in ("haiku", "model:haiku"):
                return "haiku"
            if label_lower in ("sonnet", "model:sonnet"):
                return "sonnet"

        # Priority-based defaults
        if self.priority == 1:  # Urgent
            return "opus"
        return "sonnet"

    def get_priority_string(self) -> str:
        """Get ADW-style priority string (p0-p3)."""
        priority_map = {1: "p0", 2: "p1", 3: "p2", 4: "p3"}
        return priority_map.get(self.priority, "p2")


# =============================================================================
# Linear GraphQL Client
# =============================================================================


class LinearClient:
    """Linear API client using GraphQL.

    Uses urllib for HTTP requests (no external dependencies).
    """

    API_URL = "https://api.linear.app/graphql"

    def __init__(self, api_key: str) -> None:
        """Initialize client with API key.

        Args:
            api_key: Linear API key.
        """
        self.api_key = api_key
        self._rate_limit_reset: float = 0
        self._team_cache: dict[str, str] = {}  # team_id -> team_key
        self._state_cache: dict[str, dict[str, str]] = {}  # team_id -> {name: id}

    def _request(
        self,
        query: str,
        variables: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Make a GraphQL request.

        Args:
            query: GraphQL query string.
            variables: Query variables.

        Returns:
            Response data or None on error.
        """
        # Respect rate limits
        if time.time() < self._rate_limit_reset:
            wait_time = self._rate_limit_reset - time.time()
            console.print(f"[yellow]Rate limited, waiting {wait_time:.1f}s[/yellow]")
            time.sleep(wait_time)

        headers = {
            "Authorization": self.api_key,
            "Content-Type": "application/json",
        }

        body = json.dumps({"query": query, "variables": variables or {}}).encode(
            "utf-8"
        )

        req = urllib.request.Request(
            self.API_URL, data=body, headers=headers, method="POST"
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                # Check for rate limit headers
                remaining = response.headers.get("X-RateLimit-Remaining")
                if remaining and int(remaining) < 10:
                    reset_at = response.headers.get("X-RateLimit-Reset")
                    if reset_at:
                        self._rate_limit_reset = float(reset_at)

                result = json.loads(response.read().decode("utf-8"))

                if "errors" in result:
                    for error in result["errors"]:
                        console.print(f"[red]Linear API error: {error.get('message')}[/red]")
                    return None

                data: dict[str, Any] | None = result.get("data")
                return data

        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8") if e.fp else ""
            if e.code == 429:
                # Rate limited
                retry_after = e.headers.get("Retry-After", "60")
                self._rate_limit_reset = time.time() + float(retry_after)
                console.print(f"[yellow]Rate limited, retry after {retry_after}s[/yellow]")
            else:
                console.print(f"[red]Linear API error {e.code}: {error_body}[/red]")
            return None
        except urllib.error.URLError as e:
            console.print(f"[red]Linear connection error: {e.reason}[/red]")
            return None
        except Exception as e:
            console.print(f"[red]Linear request failed: {e}[/red]")
            return None

    def get_viewer(self) -> dict[str, Any] | None:
        """Get authenticated user info.

        Returns:
            User info dict or None.
        """
        query = """
        query {
            viewer {
                id
                name
                email
            }
        }
        """
        result = self._request(query)
        if result:
            return result.get("viewer")
        return None

    def get_teams(self) -> list[dict[str, Any]]:
        """Get all teams accessible to the user.

        Returns:
            List of team objects.
        """
        query = """
        query {
            teams {
                nodes {
                    id
                    key
                    name
                }
            }
        }
        """
        result = self._request(query)
        if result and result.get("teams"):
            teams: list[dict[str, Any]] = result["teams"].get("nodes", [])
            # Cache team keys
            for team in teams:
                self._team_cache[team["id"]] = team["key"]
            return teams
        return []

    def get_team_states(self, team_id: str) -> list[dict[str, Any]]:
        """Get workflow states for a team.

        Args:
            team_id: Team ID.

        Returns:
            List of workflow state objects.
        """
        query = """
        query($teamId: String!) {
            team(id: $teamId) {
                states {
                    nodes {
                        id
                        name
                        type
                        position
                    }
                }
            }
        }
        """
        result = self._request(query, {"teamId": team_id})
        if result and result.get("team"):
            states: list[dict[str, Any]] = result["team"].get("states", {}).get("nodes", [])
            # Cache state name -> id mapping
            self._state_cache[team_id] = {s["name"].lower(): s["id"] for s in states}
            return states
        return []

    def get_issues(
        self,
        team_id: str | None = None,
        state_names: list[str] | None = None,
        label_names: list[str] | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Get issues matching criteria.

        Args:
            team_id: Filter by team ID.
            state_names: Filter by state names.
            label_names: Filter by label names.
            limit: Maximum issues to return.

        Returns:
            List of issue objects.
        """
        # Build filter
        filters = []
        if team_id:
            filters.append(f'team: {{ id: {{ eq: "{team_id}" }} }}')
        if state_names:
            state_filter = ", ".join(f'"{s}"' for s in state_names)
            filters.append(f"state: {{ name: {{ in: [{state_filter}] }} }}")
        if label_names:
            label_filter = ", ".join(f'"{lbl}"' for lbl in label_names)
            filters.append(f"labels: {{ name: {{ in: [{label_filter}] }} }}")

        filter_clause = ""
        if filters:
            filter_clause = f"filter: {{ {', '.join(filters)} }}"

        query = f"""
        query {{
            issues(first: {limit}, {filter_clause}) {{
                nodes {{
                    id
                    identifier
                    title
                    description
                    priority
                    url
                    createdAt
                    updatedAt
                    state {{
                        id
                        name
                    }}
                    team {{
                        id
                        key
                    }}
                    assignee {{
                        id
                        name
                    }}
                    labels {{
                        nodes {{
                            name
                        }}
                    }}
                }}
            }}
        }}
        """

        result = self._request(query)
        if result and result.get("issues"):
            issues: list[dict[str, Any]] = result["issues"].get("nodes", [])
            return issues
        return []

    def get_issue(self, issue_id: str) -> dict[str, Any] | None:
        """Get a single issue by ID.

        Args:
            issue_id: Issue ID.

        Returns:
            Issue object or None.
        """
        query = """
        query($id: String!) {
            issue(id: $id) {
                id
                identifier
                title
                description
                priority
                url
                createdAt
                updatedAt
                state {
                    id
                    name
                }
                team {
                    id
                    key
                }
                assignee {
                    id
                    name
                }
                labels {
                    nodes {
                        name
                    }
                }
            }
        }
        """
        result = self._request(query, {"id": issue_id})
        if result:
            return result.get("issue")
        return None

    def update_issue(
        self,
        issue_id: str,
        state_id: str | None = None,
        description: str | None = None,
    ) -> bool:
        """Update an issue.

        Args:
            issue_id: Issue ID.
            state_id: New state ID.
            description: New description.

        Returns:
            True if successful.
        """
        updates = []
        if state_id:
            updates.append(f'stateId: "{state_id}"')
        if description is not None:
            # Escape description for GraphQL
            escaped = description.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
            updates.append(f'description: "{escaped}"')

        if not updates:
            return True

        mutation = f"""
        mutation {{
            issueUpdate(id: "{issue_id}", input: {{ {', '.join(updates)} }}) {{
                success
            }}
        }}
        """

        result = self._request(mutation)
        if result and result.get("issueUpdate"):
            success: bool = result["issueUpdate"].get("success", False)
            return success
        return False

    def add_comment(self, issue_id: str, body: str) -> bool:
        """Add a comment to an issue.

        Args:
            issue_id: Issue ID.
            body: Comment body (markdown).

        Returns:
            True if successful.
        """
        # Escape body for GraphQL
        escaped = body.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")

        mutation = f"""
        mutation {{
            commentCreate(input: {{ issueId: "{issue_id}", body: "{escaped}" }}) {{
                success
            }}
        }}
        """

        result = self._request(mutation)
        if result and result.get("commentCreate"):
            success: bool = result["commentCreate"].get("success", False)
            return success
        return False

    def find_state_id(self, team_id: str, state_name: str) -> str | None:
        """Find state ID by name for a team.

        Args:
            team_id: Team ID.
            state_name: State name to find.

        Returns:
            State ID or None.
        """
        # Check cache first
        if team_id in self._state_cache:
            state_id = self._state_cache[team_id].get(state_name.lower())
            if state_id:
                return state_id

        # Fetch and cache states
        self.get_team_states(team_id)

        # Try again from cache
        if team_id in self._state_cache:
            return self._state_cache[team_id].get(state_name.lower())

        return None


# =============================================================================
# Issue Parsing
# =============================================================================


def parse_linear_issue(issue_data: dict[str, Any]) -> LinearIssue:
    """Parse Linear API response into LinearIssue.

    Args:
        issue_data: Issue data from API.

    Returns:
        Parsed LinearIssue.
    """
    # Extract labels
    labels = []
    if issue_data.get("labels"):
        labels = [lbl["name"] for lbl in issue_data["labels"].get("nodes", [])]

    # Extract state info
    state = issue_data.get("state", {})
    state_name = state.get("name", "Backlog") if state else "Backlog"
    state_id = state.get("id", "") if state else ""

    # Extract team
    team = issue_data.get("team", {})
    team_id = team.get("id", "") if team else ""

    # Extract assignee
    assignee = issue_data.get("assignee", {})
    assignee_id = assignee.get("id") if assignee else None

    # Parse timestamps
    created_at = None
    if issue_data.get("createdAt"):
        try:
            created_at = datetime.fromisoformat(
                issue_data["createdAt"].replace("Z", "+00:00")
            )
        except (ValueError, TypeError):
            pass

    updated_at = None
    if issue_data.get("updatedAt"):
        try:
            updated_at = datetime.fromisoformat(
                issue_data["updatedAt"].replace("Z", "+00:00")
            )
        except (ValueError, TypeError):
            pass

    # Check for ADW ID in description
    adw_id = None
    description = issue_data.get("description", "") or ""
    if "ADW:" in description:
        # Extract ADW ID from description
        import re

        match = re.search(r"ADW:\s*([a-f0-9]{8})", description, re.IGNORECASE)
        if match:
            adw_id = match.group(1)

    return LinearIssue(
        id=issue_data.get("id", ""),
        identifier=issue_data.get("identifier", ""),
        title=issue_data.get("title", ""),
        description=description,
        state=state_name,
        state_id=state_id,
        priority=issue_data.get("priority", 0),
        url=issue_data.get("url", ""),
        labels=labels,
        assignee_id=assignee_id,
        team_id=team_id,
        adw_id=adw_id,
        created_at=created_at,
        updated_at=updated_at,
    )


# =============================================================================
# Linear Watcher
# =============================================================================


class LinearWatcher:
    """Watches Linear for issues and triggers workflows.

    Polls Linear at configured intervals and processes issues
    that match the filter criteria.
    """

    def __init__(self, config: LinearConfig) -> None:
        """Initialize watcher with configuration.

        Args:
            config: Linear configuration.
        """
        self.config = config
        self.client = LinearClient(config.api_key)
        self._processed_ids: set[str] = set()
        self._team_id: str | None = config.team_id

    def _ensure_team_id(self) -> str | None:
        """Ensure we have a team ID (fetch if not configured).

        Returns:
            Team ID or None if no teams found.
        """
        if self._team_id:
            return self._team_id

        teams = self.client.get_teams()
        if teams:
            self._team_id = teams[0]["id"]
            console.print(f"[dim]Using team: {teams[0]['name']}[/dim]")
            return self._team_id

        console.print("[red]No teams found in Linear[/red]")
        return None

    def get_pending_issues(self) -> list[LinearIssue]:
        """Get issues ready for processing.

        Returns:
            List of issues to process.
        """
        team_id = self._ensure_team_id()

        issues_data = self.client.get_issues(
            team_id=team_id,
            state_names=self.config.filter_states,
            label_names=self.config.label_filter if self.config.label_filter else None,
        )

        issues = []
        for data in issues_data:
            issue = parse_linear_issue(data)

            # Skip if already has ADW ID (being processed)
            if issue.adw_id:
                continue

            # Skip if already processed in this session
            if issue.id in self._processed_ids:
                continue

            issues.append(issue)

        return issues

    def mark_issue_started(self, issue: LinearIssue, adw_id: str) -> bool:
        """Mark an issue as started.

        Args:
            issue: Issue to update.
            adw_id: ADW task ID.

        Returns:
            True if successful.
        """
        # Find "In Progress" state
        state_id = self.client.find_state_id(issue.team_id, "In Progress")
        if not state_id:
            # Try alternate names
            for name in ["in progress", "doing", "started", "working"]:
                state_id = self.client.find_state_id(issue.team_id, name)
                if state_id:
                    break

        # Update description with ADW ID marker
        new_description = issue.description or ""
        if not new_description.endswith("\n"):
            new_description += "\n"
        new_description += f"\n---\nADW: {adw_id}"

        success = self.client.update_issue(
            issue.id,
            state_id=state_id,
            description=new_description,
        )

        if success:
            self._processed_ids.add(issue.id)

            # Add a comment if configured
            if self.config.sync_comments:
                self.client.add_comment(
                    issue.id,
                    f"🤖 **ADW Started**\n\nTask ID: `{adw_id}`\nProcessing with ADW...",
                )

        return success

    def mark_issue_completed(self, issue: LinearIssue) -> bool:
        """Mark an issue as completed.

        Args:
            issue: Issue to update.

        Returns:
            True if successful.
        """
        # Find "Done" state
        state_id = self.client.find_state_id(issue.team_id, "Done")
        if not state_id:
            for name in ["done", "completed", "closed"]:
                state_id = self.client.find_state_id(issue.team_id, name)
                if state_id:
                    break

        success = self.client.update_issue(issue.id, state_id=state_id)

        if success and self.config.sync_comments:
            self.client.add_comment(
                issue.id,
                "✅ **ADW Completed**\n\nTask completed successfully.",
            )

        return success

    def mark_issue_failed(self, issue: LinearIssue, error: str | None = None) -> bool:
        """Mark an issue as failed.

        Args:
            issue: Issue to update.
            error: Optional error message.

        Returns:
            True if successful.
        """
        # Find "Canceled" or similar state
        state_id = None
        for name in ["canceled", "cancelled", "failed", "blocked"]:
            state_id = self.client.find_state_id(issue.team_id, name)
            if state_id:
                break

        success = True
        if state_id:
            success = self.client.update_issue(issue.id, state_id=state_id)

        if self.config.sync_comments:
            error_text = f"\n\nError: {error}" if error else ""
            self.client.add_comment(
                issue.id,
                f"❌ **ADW Failed**\n\nTask failed during processing.{error_text}",
            )

        return success


# =============================================================================
# Polling Functions
# =============================================================================


def process_linear_issues(
    config: LinearConfig,
    dry_run: bool = False,
) -> int:
    """Process pending issues from Linear.

    Args:
        config: Linear configuration.
        dry_run: If True, don't actually process issues.

    Returns:
        Number of issues processed.
    """
    from ..agent.utils import generate_adw_id
    from ..workflows.standard import run_standard_workflow

    watcher = LinearWatcher(config)
    issues = watcher.get_pending_issues()

    if not issues:
        console.print("[dim]No pending issues in Linear[/dim]")
        return 0

    processed = 0

    for issue in issues:
        adw_id = generate_adw_id()
        workflow = issue.get_workflow_or_default()
        model = issue.get_model_or_default()
        priority = issue.get_priority_string()

        console.print(f"[cyan]Processing: {issue.identifier} - {issue.title}[/cyan]")
        console.print(
            f"[dim]  Workflow: {workflow}, Model: {model}, Priority: {priority}[/dim]"
        )

        if dry_run:
            console.print(f"[yellow]DRY RUN: Would process with ADW ID {adw_id}[/yellow]")
            continue

        # Mark as started in Linear
        if not watcher.mark_issue_started(issue, adw_id):
            console.print("[red]Failed to update Linear status[/red]")
            continue

        # Build task description
        task_description = f"{issue.identifier}: {issue.title}"
        if issue.description:
            task_description += f"\n\n{issue.description}"
        task_description += f"\n\nLinear URL: {issue.url}"

        # Create worktree name
        worktree_name = f"linear-{adw_id}"

        # Run appropriate workflow
        try:
            if workflow == "sdlc":
                from ..workflows.sdlc import run_sdlc_workflow

                success, _ = run_sdlc_workflow(
                    task_description=task_description,
                    worktree_name=worktree_name,
                    adw_id=adw_id,
                )
            elif workflow == "simple":
                from ..workflows.simple import run_simple_workflow

                success = run_simple_workflow(
                    task_description=task_description,
                    worktree_name=worktree_name,
                    adw_id=adw_id,
                    model=model,
                )
            else:
                success = run_standard_workflow(
                    task_description=task_description,
                    worktree_name=worktree_name,
                    adw_id=adw_id,
                    model=model,
                )

            # Update Linear with result
            if success:
                watcher.mark_issue_completed(issue)
                console.print(f"[green]✓ Completed: {issue.identifier}[/green]")
            else:
                watcher.mark_issue_failed(issue)
                console.print(f"[red]✗ Failed: {issue.identifier}[/red]")

        except Exception as e:
            console.print(f"[red]Error processing issue: {e}[/red]")
            watcher.mark_issue_failed(issue, str(e))

        processed += 1

    return processed


def run_linear_watcher(
    config: LinearConfig,
    dry_run: bool = False,
) -> None:
    """Continuously poll Linear for issues.

    Args:
        config: Linear configuration.
        dry_run: If True, don't actually process issues.
    """
    console.print("[bold]Starting Linear issue watcher[/bold]")
    if config.team_id:
        console.print(f"[dim]Team: {config.team_id[:8]}...[/dim]")
    else:
        console.print("[dim]Team: auto-detect[/dim]")
    console.print(f"[dim]Poll interval: {config.poll_interval}s[/dim]")
    console.print(f"[dim]Filter states: {', '.join(config.filter_states)}[/dim]")
    if dry_run:
        console.print("[yellow]DRY RUN MODE[/yellow]")
    console.print()

    try:
        while True:
            process_linear_issues(config, dry_run)
            time.sleep(config.poll_interval)

    except KeyboardInterrupt:
        console.print("\n[yellow]Stopping watcher...[/yellow]")


def sync_linear_issue(
    config: LinearConfig,
    issue_identifier: str,
    dry_run: bool = False,
) -> bool:
    """Sync a specific Linear issue.

    Args:
        config: Linear configuration.
        issue_identifier: Issue identifier (e.g., "TEAM-123").
        dry_run: If True, don't actually process.

    Returns:
        True if successful.
    """
    from ..agent.utils import generate_adw_id
    from ..workflows.standard import run_standard_workflow

    client = LinearClient(config.api_key)

    # Search for issue by identifier
    query = f"""
    query {{
        issueSearch(query: "{issue_identifier}", first: 1) {{
            nodes {{
                id
                identifier
                title
                description
                priority
                url
                createdAt
                updatedAt
                state {{
                    id
                    name
                }}
                team {{
                    id
                    key
                }}
                labels {{
                    nodes {{
                        name
                    }}
                }}
            }}
        }}
    }}
    """

    result = client._request(query)
    if not result or not result.get("issueSearch"):
        console.print(f"[red]Issue not found: {issue_identifier}[/red]")
        return False

    issues_data = result["issueSearch"].get("nodes", [])
    if not issues_data:
        console.print(f"[red]Issue not found: {issue_identifier}[/red]")
        return False

    issue = parse_linear_issue(issues_data[0])
    watcher = LinearWatcher(config)
    watcher._team_id = issue.team_id

    adw_id = generate_adw_id()
    workflow = issue.get_workflow_or_default()
    model = issue.get_model_or_default()

    console.print(f"[cyan]Syncing: {issue.identifier} - {issue.title}[/cyan]")
    console.print(f"[dim]  Workflow: {workflow}, Model: {model}[/dim]")

    if dry_run:
        console.print(f"[yellow]DRY RUN: Would process with ADW ID {adw_id}[/yellow]")
        return True

    # Mark as started
    watcher.mark_issue_started(issue, adw_id)

    # Build task description
    task_description = f"{issue.identifier}: {issue.title}"
    if issue.description:
        task_description += f"\n\n{issue.description}"
    task_description += f"\n\nLinear URL: {issue.url}"

    worktree_name = f"linear-{adw_id}"

    try:
        if workflow == "sdlc":
            from ..workflows.sdlc import run_sdlc_workflow

            success, _ = run_sdlc_workflow(
                task_description=task_description,
                worktree_name=worktree_name,
                adw_id=adw_id,
            )
        elif workflow == "simple":
            from ..workflows.simple import run_simple_workflow

            success = run_simple_workflow(
                task_description=task_description,
                worktree_name=worktree_name,
                adw_id=adw_id,
                model=model,
            )
        else:
            success = run_standard_workflow(
                task_description=task_description,
                worktree_name=worktree_name,
                adw_id=adw_id,
                model=model,
            )

        if success:
            watcher.mark_issue_completed(issue)
            console.print(f"[green]✓ Completed: {issue.identifier}[/green]")
        else:
            watcher.mark_issue_failed(issue)
            console.print(f"[red]✗ Failed: {issue.identifier}[/red]")

        return success

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        watcher.mark_issue_failed(issue, str(e))
        return False


# =============================================================================
# Helper Functions
# =============================================================================


def _parse_simple_toml(path: Path) -> dict[str, Any]:
    """Simple TOML parser for basic key-value sections.

    Args:
        path: Path to TOML file.

    Returns:
        Parsed config dictionary.
    """
    config: dict[str, Any] = {}
    current_section: str | None = None

    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            # Skip empty lines and comments
            if not line or line.startswith("#"):
                continue

            # Section header
            if line.startswith("[") and line.endswith("]"):
                current_section = line[1:-1].strip()
                config[current_section] = {}
                continue

            # Key-value pair
            if "=" in line and current_section:
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip("\"'")

                # Try to parse as number
                try:
                    value = int(value)  # type: ignore
                except ValueError:
                    pass

                # Try to parse as list
                if isinstance(value, str) and value.startswith("[") and value.endswith("]"):
                    # Simple list parsing
                    items = value[1:-1].split(",")
                    value = [item.strip().strip("\"'") for item in items if item.strip()]  # type: ignore

                config[current_section][key] = value

    return config


def test_linear_connection(config: LinearConfig) -> bool:
    """Test connection to Linear API.

    Args:
        config: Linear configuration.

    Returns:
        True if connection successful.
    """
    client = LinearClient(config.api_key)

    # Test authentication
    viewer = client.get_viewer()
    if not viewer:
        console.print("[red]✗ Failed to authenticate with Linear[/red]")
        return False

    console.print(f"[green]✓ Connected as: {viewer.get('name')} ({viewer.get('email')})[/green]")

    # Get teams
    teams = client.get_teams()
    console.print(f"[dim]Found {len(teams)} team(s)[/dim]")

    for team in teams:
        console.print(f"[dim]  - {team['key']}: {team['name']}[/dim]")

    return True
