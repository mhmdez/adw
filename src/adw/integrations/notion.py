"""Notion integration for ADW.

Enables ADW to poll a Notion database for tasks and sync status bidirectionally.

Configuration:
    Environment variables:
    - NOTION_API_KEY: Notion integration API key (required)
    - NOTION_DATABASE_ID: Database ID to poll (required)

    Or via config file (~/.adw/config.toml):
    [notion]
    api_key = "secret_..."
    database_id = "abc123..."
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from rich.console import Console

console = Console()


class NotionStatus(Enum):
    """Standard Notion task statuses mapped to ADW."""

    NOT_STARTED = "not_started"
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    CANCELED = "canceled"


# Mapping from Notion status names to ADW status
NOTION_TO_ADW_STATUS = {
    "not started": "pending",
    "todo": "pending",
    "to do": "pending",
    "backlog": "pending",
    "in progress": "in_progress",
    "doing": "in_progress",
    "working": "in_progress",
    "done": "completed",
    "complete": "completed",
    "completed": "completed",
    "canceled": "failed",
    "cancelled": "failed",
}

# Mapping from ADW status back to Notion
ADW_TO_NOTION_STATUS = {
    "pending": "To Do",
    "in_progress": "In Progress",
    "completed": "Done",
    "failed": "Canceled",
}


@dataclass
class NotionConfig:
    """Configuration for Notion integration.

    Attributes:
        api_key: Notion integration API key.
        database_id: ID of the database to poll.
        poll_interval: Seconds between polls (default: 60).
        status_property: Name of status property (default: "Status").
        title_property: Name of title property (default: "Name").
        workflow_property: Name of workflow property (default: "Workflow").
        model_property: Name of model property (default: "Model").
        priority_property: Name of priority property (default: "Priority").
        adw_id_property: Name of ADW ID property for tracking (default: "ADW ID").
        filter_status: Only process tasks with these statuses.
    """

    api_key: str
    database_id: str
    poll_interval: int = 60
    status_property: str = "Status"
    title_property: str = "Name"
    workflow_property: str = "Workflow"
    model_property: str = "Model"
    priority_property: str = "Priority"
    adw_id_property: str = "ADW ID"
    filter_status: list[str] = field(default_factory=lambda: ["To Do", "Not Started"])

    @classmethod
    def from_env(cls) -> NotionConfig | None:
        """Create config from environment variables.

        Returns:
            NotionConfig or None if required vars not set.
        """
        api_key = os.environ.get("NOTION_API_KEY", "")
        database_id = os.environ.get("NOTION_DATABASE_ID", "")

        if not api_key or not database_id:
            return None

        return cls(
            api_key=api_key,
            database_id=database_id,
            poll_interval=int(os.environ.get("NOTION_POLL_INTERVAL", "60")),
        )

    @classmethod
    def from_config_file(cls, path: Path | None = None) -> NotionConfig | None:
        """Load config from TOML file.

        Args:
            path: Path to config file (default: ~/.adw/config.toml).

        Returns:
            NotionConfig or None if not configured.
        """
        if path is None:
            path = Path.home() / ".adw" / "config.toml"

        if not path.exists():
            return None

        try:
            import tomli  # type: ignore[import-not-found]

            with open(path, "rb") as f:
                config = tomli.load(f)
        except ImportError:
            # Fallback: simple TOML parsing for [notion] section
            config = _parse_simple_toml(path)

        notion_config = config.get("notion", {})
        if not notion_config.get("api_key") or not notion_config.get("database_id"):
            return None

        return cls(
            api_key=notion_config["api_key"],
            database_id=notion_config["database_id"],
            poll_interval=notion_config.get("poll_interval", 60),
            status_property=notion_config.get("status_property", "Status"),
            title_property=notion_config.get("title_property", "Name"),
            workflow_property=notion_config.get("workflow_property", "Workflow"),
            model_property=notion_config.get("model_property", "Model"),
            priority_property=notion_config.get("priority_property", "Priority"),
            adw_id_property=notion_config.get("adw_id_property", "ADW ID"),
            filter_status=notion_config.get("filter_status", ["To Do", "Not Started"]),
        )

    @classmethod
    def load(cls) -> NotionConfig | None:
        """Load config from environment or config file.

        Prefers environment variables over config file.

        Returns:
            NotionConfig or None if not configured.
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
            "database_id": self.database_id,
            "poll_interval": self.poll_interval,
            "status_property": self.status_property,
            "title_property": self.title_property,
            "workflow_property": self.workflow_property,
            "model_property": self.model_property,
            "priority_property": self.priority_property,
            "adw_id_property": self.adw_id_property,
            "filter_status": self.filter_status,
        }


@dataclass
class NotionTask:
    """A task from Notion database.

    Attributes:
        page_id: Notion page ID (used for updates).
        title: Task title/description.
        status: Current status in Notion.
        workflow: Workflow to use (simple, standard, sdlc).
        model: Model to use (sonnet, opus, haiku).
        priority: Task priority (p0-p3).
        adw_id: ADW ID if already being processed.
        url: Notion page URL.
        properties: Raw Notion properties dict.
        created_time: When the task was created.
        last_edited_time: When last edited.
    """

    page_id: str
    title: str
    status: str = "pending"
    workflow: str | None = None
    model: str | None = None
    priority: str | None = None
    adw_id: str | None = None
    url: str = ""
    properties: dict[str, Any] = field(default_factory=dict)
    created_time: datetime | None = None
    last_edited_time: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "page_id": self.page_id,
            "title": self.title,
            "status": self.status,
            "workflow": self.workflow,
            "model": self.model,
            "priority": self.priority,
            "adw_id": self.adw_id,
            "url": self.url,
            "created_time": self.created_time.isoformat() if self.created_time else None,
            "last_edited_time": (self.last_edited_time.isoformat() if self.last_edited_time else None),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NotionTask:
        """Create from dictionary."""
        return cls(
            page_id=data["page_id"],
            title=data["title"],
            status=data.get("status", "pending"),
            workflow=data.get("workflow"),
            model=data.get("model"),
            priority=data.get("priority"),
            adw_id=data.get("adw_id"),
            url=data.get("url", ""),
            properties=data.get("properties", {}),
            created_time=(datetime.fromisoformat(data["created_time"]) if data.get("created_time") else None),
            last_edited_time=(
                datetime.fromisoformat(data["last_edited_time"]) if data.get("last_edited_time") else None
            ),
        )

    def get_workflow_or_default(self) -> str:
        """Get workflow, defaulting based on priority."""
        if self.workflow:
            return self.workflow
        # High priority tasks get full SDLC
        if self.priority in ("p0", "p1"):
            return "sdlc"
        return "standard"

    def get_model_or_default(self) -> str:
        """Get model, defaulting based on priority."""
        if self.model:
            return self.model
        if self.priority == "p0":
            return "opus"
        return "sonnet"


# =============================================================================
# Notion API Client
# =============================================================================


class NotionClient:
    """Simple Notion API client using urllib (no external dependencies).

    Uses the official Notion API v1.
    """

    BASE_URL = "https://api.notion.com/v1"
    API_VERSION = "2022-06-28"

    def __init__(self, api_key: str) -> None:
        """Initialize client with API key.

        Args:
            api_key: Notion integration API key.
        """
        self.api_key = api_key

    def _request(
        self,
        method: str,
        endpoint: str,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Make an API request.

        Args:
            method: HTTP method (GET, POST, PATCH).
            endpoint: API endpoint (e.g., /databases/{id}/query).
            data: Request body data (for POST/PATCH).

        Returns:
            Response JSON or None on error.
        """
        url = f"{self.BASE_URL}{endpoint}"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Notion-Version": self.API_VERSION,
            "Content-Type": "application/json",
        }

        body = json.dumps(data).encode("utf-8") if data else None

        req = urllib.request.Request(url, data=body, headers=headers, method=method)

        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                result: dict[str, Any] = json.loads(response.read().decode("utf-8"))
                return result
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8") if e.fp else ""
            console.print(f"[red]Notion API error {e.code}: {error_body}[/red]")
            return None
        except urllib.error.URLError as e:
            console.print(f"[red]Notion connection error: {e.reason}[/red]")
            return None
        except Exception as e:
            console.print(f"[red]Notion request failed: {e}[/red]")
            return None

    def query_database(
        self,
        database_id: str,
        filter_obj: dict[str, Any] | None = None,
        sorts: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """Query a Notion database.

        Args:
            database_id: Database ID to query.
            filter_obj: Optional Notion filter object.
            sorts: Optional sort configuration.

        Returns:
            List of page objects.
        """
        data: dict[str, Any] = {}
        if filter_obj:
            data["filter"] = filter_obj
        if sorts:
            data["sorts"] = sorts

        result = self._request("POST", f"/databases/{database_id}/query", data)
        if not result:
            return []

        results: list[dict[str, Any]] = result.get("results", [])
        return results

    def get_page(self, page_id: str) -> dict[str, Any] | None:
        """Get a page by ID.

        Args:
            page_id: Page ID.

        Returns:
            Page object or None.
        """
        return self._request("GET", f"/pages/{page_id}")

    def update_page(
        self,
        page_id: str,
        properties: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Update page properties.

        Args:
            page_id: Page ID to update.
            properties: Properties to update.

        Returns:
            Updated page object or None.
        """
        return self._request("PATCH", f"/pages/{page_id}", {"properties": properties})


# =============================================================================
# Property Parsing
# =============================================================================


def _extract_text_from_property(prop: dict[str, Any]) -> str:
    """Extract text value from a Notion property.

    Args:
        prop: Notion property object.

    Returns:
        Extracted text value.
    """
    prop_type = prop.get("type", "")

    if prop_type == "title":
        title_items = prop.get("title", [])
        return "".join(item.get("plain_text", "") for item in title_items)

    elif prop_type == "rich_text":
        text_items = prop.get("rich_text", [])
        return "".join(item.get("plain_text", "") for item in text_items)

    elif prop_type == "select":
        select = prop.get("select")
        return select.get("name", "") if select else ""

    elif prop_type == "multi_select":
        items = prop.get("multi_select", [])
        return ", ".join(item.get("name", "") for item in items)

    elif prop_type == "status":
        status = prop.get("status")
        return status.get("name", "") if status else ""

    elif prop_type == "number":
        return str(prop.get("number", ""))

    elif prop_type == "checkbox":
        return "true" if prop.get("checkbox") else "false"

    elif prop_type == "date":
        date = prop.get("date")
        return date.get("start", "") if date else ""

    elif prop_type == "url":
        return prop.get("url", "") or ""

    return ""


def parse_notion_page(
    page: dict[str, Any],
    config: NotionConfig,
) -> NotionTask:
    """Parse a Notion page into a NotionTask.

    Args:
        page: Notion page object.
        config: Notion configuration.

    Returns:
        Parsed NotionTask.
    """
    properties = page.get("properties", {})

    # Extract title
    title = ""
    title_prop = properties.get(config.title_property, {})
    title = _extract_text_from_property(title_prop)

    # Extract status
    status = "pending"
    status_prop = properties.get(config.status_property, {})
    status_text = _extract_text_from_property(status_prop).lower()
    status = NOTION_TO_ADW_STATUS.get(status_text, "pending")

    # Extract workflow
    workflow = None
    workflow_prop = properties.get(config.workflow_property, {})
    workflow_text = _extract_text_from_property(workflow_prop).lower()
    if workflow_text in ("simple", "standard", "sdlc"):
        workflow = workflow_text

    # Extract model
    model = None
    model_prop = properties.get(config.model_property, {})
    model_text = _extract_text_from_property(model_prop).lower()
    if model_text in ("sonnet", "opus", "haiku"):
        model = model_text

    # Extract priority
    priority = None
    priority_prop = properties.get(config.priority_property, {})
    priority_text = _extract_text_from_property(priority_prop).lower()
    if priority_text in ("p0", "p1", "p2", "p3"):
        priority = priority_text
    elif priority_text in ("critical", "high", "medium", "low"):
        priority_map = {"critical": "p0", "high": "p1", "medium": "p2", "low": "p3"}
        priority = priority_map.get(priority_text)

    # Extract ADW ID if present
    adw_id = None
    adw_id_prop = properties.get(config.adw_id_property, {})
    adw_id_text = _extract_text_from_property(adw_id_prop)
    if adw_id_text:
        adw_id = adw_id_text

    # Parse timestamps
    created_time = None
    if page.get("created_time"):
        try:
            created_time = datetime.fromisoformat(page["created_time"].replace("Z", "+00:00"))
        except (ValueError, TypeError):
            pass

    last_edited_time = None
    if page.get("last_edited_time"):
        try:
            last_edited_time = datetime.fromisoformat(page["last_edited_time"].replace("Z", "+00:00"))
        except (ValueError, TypeError):
            pass

    return NotionTask(
        page_id=page.get("id", ""),
        title=title,
        status=status,
        workflow=workflow,
        model=model,
        priority=priority,
        adw_id=adw_id,
        url=page.get("url", ""),
        properties=properties,
        created_time=created_time,
        last_edited_time=last_edited_time,
    )


# =============================================================================
# Status Update
# =============================================================================


def build_status_property(status: str, config: NotionConfig) -> dict[str, Any]:
    """Build a Notion property update for status.

    Attempts to determine property type from config.

    Args:
        status: ADW status (pending, in_progress, completed, failed).
        config: Notion configuration.

    Returns:
        Notion property update object.
    """
    notion_status = ADW_TO_NOTION_STATUS.get(status, "To Do")

    # Default to status type (most common for status properties)
    return {
        "status": {"name": notion_status},
    }


def build_adw_id_property(adw_id: str) -> dict[str, Any]:
    """Build a Notion property update for ADW ID.

    Args:
        adw_id: ADW task ID.

    Returns:
        Notion property update object.
    """
    return {
        "rich_text": [{"text": {"content": adw_id}}],
    }


# =============================================================================
# Watcher
# =============================================================================


class NotionWatcher:
    """Watches a Notion database for tasks and triggers workflows.

    Polls the database at configured intervals and processes tasks
    that match the filter criteria.
    """

    def __init__(self, config: NotionConfig) -> None:
        """Initialize watcher with configuration.

        Args:
            config: Notion configuration.
        """
        self.config = config
        self.client = NotionClient(config.api_key)
        self._processed_ids: set[str] = set()  # Track processed in this session

    def build_filter(self) -> dict[str, Any] | None:
        """Build Notion filter for task query.

        Returns:
            Filter object or None for no filtering.
        """
        if not self.config.filter_status:
            return None

        # Build OR filter for multiple statuses
        status_filters = []
        for status_name in self.config.filter_status:
            status_filters.append(
                {
                    "property": self.config.status_property,
                    "status": {"equals": status_name},
                }
            )

        if len(status_filters) == 1:
            return status_filters[0]

        return {"or": status_filters}

    def get_pending_tasks(self) -> list[NotionTask]:
        """Get tasks ready for processing.

        Returns:
            List of tasks to process.
        """
        filter_obj = self.build_filter()

        # Sort by created time (oldest first)
        sorts = [{"timestamp": "created_time", "direction": "ascending"}]

        pages = self.client.query_database(
            self.config.database_id,
            filter_obj=filter_obj,
            sorts=sorts,
        )

        tasks = []
        for page in pages:
            task = parse_notion_page(page, self.config)

            # Skip if already has an ADW ID (being processed)
            if task.adw_id:
                continue

            # Skip if we already processed this in this session
            if task.page_id in self._processed_ids:
                continue

            tasks.append(task)

        return tasks

    def mark_task_started(self, task: NotionTask, adw_id: str) -> bool:
        """Mark a task as started in Notion.

        Args:
            task: Task to update.
            adw_id: ADW ID to assign.

        Returns:
            True if successful.
        """
        properties = {
            self.config.status_property: build_status_property("in_progress", self.config),
            self.config.adw_id_property: build_adw_id_property(adw_id),
        }

        result = self.client.update_page(task.page_id, properties)
        if result:
            self._processed_ids.add(task.page_id)
            return True
        return False

    def mark_task_completed(self, task: NotionTask) -> bool:
        """Mark a task as completed in Notion.

        Args:
            task: Task to update.

        Returns:
            True if successful.
        """
        properties = {
            self.config.status_property: build_status_property("completed", self.config),
        }

        result = self.client.update_page(task.page_id, properties)
        return result is not None

    def mark_task_failed(self, task: NotionTask) -> bool:
        """Mark a task as failed in Notion.

        Args:
            task: Task to update.

        Returns:
            True if successful.
        """
        properties = {
            self.config.status_property: build_status_property("failed", self.config),
        }

        result = self.client.update_page(task.page_id, properties)
        return result is not None


# =============================================================================
# Polling Functions
# =============================================================================


def process_notion_tasks(
    config: NotionConfig,
    dry_run: bool = False,
) -> int:
    """Process pending tasks from Notion database.

    Args:
        config: Notion configuration.
        dry_run: If True, don't actually process tasks.

    Returns:
        Number of tasks processed.
    """
    from ..agent.utils import generate_adw_id
    from ..workflows.standard import run_standard_workflow

    watcher = NotionWatcher(config)
    tasks = watcher.get_pending_tasks()

    if not tasks:
        console.print("[dim]No pending tasks in Notion database[/dim]")
        return 0

    processed = 0

    for task in tasks:
        adw_id = generate_adw_id()
        workflow = task.get_workflow_or_default()
        model = task.get_model_or_default()

        console.print(f"[cyan]Processing: {task.title}[/cyan]")
        console.print(f"[dim]  Workflow: {workflow}, Model: {model}, Priority: {task.priority or 'default'}[/dim]")

        if dry_run:
            console.print(f"[yellow]DRY RUN: Would process with ADW ID {adw_id}[/yellow]")
            continue

        # Mark as started in Notion
        if not watcher.mark_task_started(task, adw_id):
            console.print("[red]Failed to update Notion status[/red]")
            continue

        # Build task description
        task_description = task.title
        if task.url:
            task_description += f"\n\nNotion URL: {task.url}"

        # Create worktree name
        worktree_name = f"notion-{adw_id}"

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

            # Update Notion with result
            if success:
                watcher.mark_task_completed(task)
                console.print(f"[green]✓ Completed: {task.title}[/green]")
            else:
                watcher.mark_task_failed(task)
                console.print(f"[red]✗ Failed: {task.title}[/red]")

        except Exception as e:
            console.print(f"[red]Error processing task: {e}[/red]")
            watcher.mark_task_failed(task)

        processed += 1

    return processed


def run_notion_watcher(
    config: NotionConfig,
    dry_run: bool = False,
) -> None:
    """Continuously poll Notion for tasks.

    Args:
        config: Notion configuration.
        dry_run: If True, don't actually process tasks.
    """
    console.print("[bold]Starting Notion task watcher[/bold]")
    console.print(f"[dim]Database: {config.database_id[:8]}...[/dim]")
    console.print(f"[dim]Poll interval: {config.poll_interval}s[/dim]")
    if dry_run:
        console.print("[yellow]DRY RUN MODE[/yellow]")
    console.print()

    try:
        while True:
            process_notion_tasks(config, dry_run)
            time.sleep(config.poll_interval)

    except KeyboardInterrupt:
        console.print("\n[yellow]Stopping watcher...[/yellow]")


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

                config[current_section][key] = value

    return config


def test_notion_connection(config: NotionConfig) -> bool:
    """Test connection to Notion API.

    Args:
        config: Notion configuration.

    Returns:
        True if connection successful.
    """
    client = NotionClient(config.api_key)

    # Try to query the database (empty query)
    pages = client.query_database(config.database_id)

    # If we got here without error, connection works
    console.print("[green]✓ Connected to Notion[/green]")
    console.print(f"[dim]Found {len(pages)} pages in database[/dim]")
    return True
