# Phase 3: Task System

**ADW Build Phase**: 3 of 12
**Dependencies**: Phase 1 (Foundation), Phase 2 (TUI Shell)
**Estimated Complexity**: Medium

---

## Objective

Implement the task management system:
- Parse tasks.md into structured data
- Update task status atomically
- Sync state to TUI
- Create task list widget
- Create task detail widget

---

## Deliverables

### 3.1 Task Parser

**File**: `src/adw/agent/task_parser.py`

```python
"""Parse tasks.md into structured task objects."""

from __future__ import annotations

import re
from pathlib import Path

from .models import Task, TaskStatus, Worktree


# Regex patterns
WORKTREE_PATTERN = re.compile(r"^##\s+(?:Worktree[:\s]+)?(.+)$", re.IGNORECASE)
TASK_PATTERN = re.compile(
    r"^\[(?P<status>[^\]]*)\]"
    r"(?:\s*,?\s*(?P<adw_id>[a-f0-9]{8}))?"
    r"(?:\s*,?\s*(?P<commit>[a-f0-9]{7,40}))?"
    r"\s+(?P<description>.+?)"
    r"(?:\s*\{(?P<tags>[^}]+)\})?"
    r"(?:\s*//\s*(?P<error>.+))?"
    r"\s*$"
)


def parse_status(status_str: str) -> TaskStatus:
    """Parse status marker to enum."""
    s = status_str.strip().split(",")[0].strip()

    if not s or s == "":
        return TaskStatus.PENDING
    if "⏰" in s:
        return TaskStatus.BLOCKED
    if "🟡" in s:
        return TaskStatus.IN_PROGRESS
    if "✅" in s:
        return TaskStatus.DONE
    if "❌" in s:
        return TaskStatus.FAILED

    return TaskStatus.PENDING


def parse_tags(tags_str: str | None) -> list[str]:
    """Parse comma-separated tags."""
    if not tags_str:
        return []
    return [t.strip().lower() for t in tags_str.split(",") if t.strip()]


def parse_tasks_md(content: str) -> list[Worktree]:
    """Parse tasks.md content."""
    worktrees: list[Worktree] = []
    current: Worktree | None = None

    for line_num, line in enumerate(content.split("\n"), 1):
        line = line.rstrip()

        # Worktree header
        match = WORKTREE_PATTERN.match(line)
        if match:
            if current:
                worktrees.append(current)
            current = Worktree(name=match.group(1).strip())
            continue

        # Task line
        match = TASK_PATTERN.match(line)
        if match and current:
            g = match.groupdict()
            task = Task(
                description=g["description"].strip(),
                status=parse_status(g["status"] or ""),
                adw_id=g.get("adw_id"),
                commit_hash=g.get("commit"),
                error_message=g.get("error"),
                tags=parse_tags(g.get("tags")),
                worktree_name=current.name,
                line_number=line_num,
            )
            current.tasks.append(task)

    if current:
        worktrees.append(current)

    return worktrees


def load_tasks(path: Path | None = None) -> list[Worktree]:
    """Load tasks from file."""
    path = path or Path("tasks.md")
    if not path.exists():
        return []
    return parse_tasks_md(path.read_text())


def get_all_tasks(path: Path | None = None) -> list[Task]:
    """Get flat list of all tasks."""
    tasks = []
    for worktree in load_tasks(path):
        tasks.extend(worktree.tasks)
    return tasks


def get_eligible_tasks(path: Path | None = None) -> list[Task]:
    """Get tasks eligible for execution."""
    eligible = []
    for worktree in load_tasks(path):
        for i, task in enumerate(worktree.tasks):
            if task.status == TaskStatus.PENDING:
                eligible.append(task)
            elif task.status == TaskStatus.BLOCKED:
                # Eligible if all above are done
                above = worktree.tasks[:i]
                if all(t.status == TaskStatus.DONE for t in above):
                    eligible.append(task)
    return eligible


def has_pending_tasks(path: Path | None = None) -> bool:
    """Quick check for pending tasks."""
    path = path or Path("tasks.md")
    if not path.exists():
        return False
    content = path.read_text()
    return bool(re.search(r"\[\s*\]|\[⏰\]", content))
```

### 3.2 Task Updater

**File**: `src/adw/agent/task_updater.py`

```python
"""Atomic task status updates."""

from __future__ import annotations

import re
from pathlib import Path

from .models import TaskStatus


def update_task_status(
    path: Path,
    task_description: str,
    new_status: TaskStatus,
    adw_id: str | None = None,
    commit_hash: str | None = None,
    error_message: str | None = None,
) -> bool:
    """Update task status in tasks.md."""
    if not path.exists():
        return False

    content = path.read_text()
    lines = content.split("\n")
    desc_escaped = re.escape(task_description.strip())
    updated = False

    for i, line in enumerate(lines):
        if not re.search(rf"\]\s*.*{desc_escaped}", line, re.IGNORECASE):
            continue

        # Build status marker
        if new_status == TaskStatus.PENDING:
            marker = "[]"
        elif new_status == TaskStatus.BLOCKED:
            marker = "[⏰]"
        elif new_status == TaskStatus.IN_PROGRESS:
            marker = f"[🟡, {adw_id}]" if adw_id else "[🟡]"
        elif new_status == TaskStatus.DONE:
            parts = ["✅"]
            if commit_hash:
                parts.append(commit_hash[:9])
            if adw_id:
                parts.append(adw_id)
            marker = f"[{', '.join(parts)}]"
        elif new_status == TaskStatus.FAILED:
            marker = f"[❌, {adw_id}]" if adw_id else "[❌]"
        else:
            continue

        # Preserve tags
        tags_match = re.search(r"\{([^}]+)\}", line)
        tags = f" {{{tags_match.group(1)}}}" if tags_match else ""

        # Build new line
        new_line = f"{marker} {task_description.strip()}{tags}"
        if new_status == TaskStatus.FAILED and error_message:
            new_line += f" // Failed: {error_message}"

        lines[i] = new_line
        updated = True
        break

    if updated:
        path.write_text("\n".join(lines))

    return updated


def mark_in_progress(path: Path, description: str, adw_id: str) -> bool:
    """Mark task as in-progress."""
    return update_task_status(path, description, TaskStatus.IN_PROGRESS, adw_id=adw_id)


def mark_done(path: Path, description: str, adw_id: str, commit: str | None = None) -> bool:
    """Mark task as done."""
    return update_task_status(path, description, TaskStatus.DONE, adw_id=adw_id, commit_hash=commit)


def mark_failed(path: Path, description: str, adw_id: str, error: str) -> bool:
    """Mark task as failed."""
    return update_task_status(path, description, TaskStatus.FAILED, adw_id=adw_id, error_message=error)
```

### 3.3 TUI State

**File**: `src/adw/tui/state.py`

```python
"""Reactive state management for TUI."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable
from pathlib import Path

from ..agent.models import Task, TaskStatus
from ..agent.task_parser import get_all_tasks


@dataclass
class TaskState:
    """State for a single task in TUI."""
    adw_id: str | None
    description: str
    status: TaskStatus
    worktree: str | None = None
    phase: str | None = None
    progress: float = 0.0
    pid: int | None = None

    @property
    def is_running(self) -> bool:
        return self.status == TaskStatus.IN_PROGRESS

    @property
    def display_id(self) -> str:
        return self.adw_id[:8] if self.adw_id else "--------"


@dataclass
class AppState:
    """Global application state."""
    tasks: dict[str, TaskState] = field(default_factory=dict)
    selected_task_id: str | None = None
    focused_panel: str = "tasks"

    _subscribers: list[Callable] = field(default_factory=list, repr=False)

    def subscribe(self, callback: Callable) -> None:
        """Subscribe to state changes."""
        self._subscribers.append(callback)

    def notify(self) -> None:
        """Notify subscribers of change."""
        for cb in self._subscribers:
            cb(self)

    def load_from_tasks_md(self, path: Path | None = None) -> None:
        """Load state from tasks.md."""
        self.tasks.clear()
        for task in get_all_tasks(path):
            key = task.adw_id or f"pending-{task.line_number}"
            self.tasks[key] = TaskState(
                adw_id=task.adw_id,
                description=task.description,
                status=task.status,
                worktree=task.worktree_name,
            )
        self.notify()

    def update_task(self, key: str, **updates) -> None:
        """Update a task."""
        if key in self.tasks:
            for k, v in updates.items():
                setattr(self.tasks[key], k, v)
            self.notify()

    def select_task(self, key: str | None) -> None:
        """Select a task."""
        self.selected_task_id = key
        self.notify()

    @property
    def selected_task(self) -> TaskState | None:
        """Get selected task."""
        if self.selected_task_id:
            return self.tasks.get(self.selected_task_id)
        return None

    @property
    def running_count(self) -> int:
        """Count of running tasks."""
        return sum(1 for t in self.tasks.values() if t.is_running)
```

### 3.4 Task List Widget

**File**: `src/adw/tui/widgets/task_list.py`

```python
"""Task list widget."""

from __future__ import annotations

from textual.widgets import ListView, ListItem, Static
from textual.message import Message
from rich.text import Text

from ..state import TaskState
from ...agent.models import TaskStatus


STATUS_ICONS = {
    TaskStatus.PENDING: ("⏳", "dim"),
    TaskStatus.BLOCKED: ("⏰", "yellow"),
    TaskStatus.IN_PROGRESS: ("🟡", "cyan"),
    TaskStatus.DONE: ("✅", "green"),
    TaskStatus.FAILED: ("❌", "red"),
}


class TaskListItem(ListItem):
    """Single task item."""

    def __init__(self, task: TaskState, key: str):
        super().__init__()
        self.task = task
        self.task_key = key

    def compose(self):
        icon, style = STATUS_ICONS.get(self.task.status, ("•", "white"))
        text = Text()
        text.append(f"{icon} ", style="bold")
        text.append(f"{self.task.display_id} ", style="dim")
        text.append(self.task.description[:35], style=style)
        yield Static(text)


class TaskList(ListView):
    """List of tasks."""

    class TaskSelected(Message):
        """Task selected message."""
        def __init__(self, key: str):
            super().__init__()
            self.key = key

    def update_tasks(self, tasks: dict[str, TaskState]) -> None:
        """Update displayed tasks."""
        self.clear()
        # Sort: running first, then pending, then done
        def sort_key(item):
            k, t = item
            order = {
                TaskStatus.IN_PROGRESS: 0,
                TaskStatus.PENDING: 1,
                TaskStatus.BLOCKED: 2,
                TaskStatus.FAILED: 3,
                TaskStatus.DONE: 4,
            }
            return (order.get(t.status, 5), k)

        for key, task in sorted(tasks.items(), key=sort_key):
            self.append(TaskListItem(task, key))

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle selection."""
        if isinstance(event.item, TaskListItem):
            self.post_message(self.TaskSelected(event.item.task_key))
```

### 3.5 Task Detail Widget

**File**: `src/adw/tui/widgets/task_detail.py`

```python
"""Task detail widget."""

from __future__ import annotations

from textual.widgets import Static
from textual.containers import Vertical
from textual.app import ComposeResult
from rich.text import Text
from rich.panel import Panel

from ..state import TaskState


class TaskDetail(Static):
    """Display details for selected task."""

    DEFAULT_CSS = """
    TaskDetail {
        height: 100%;
        padding: 1;
    }
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._task: TaskState | None = None

    def update_task(self, task: TaskState | None) -> None:
        """Update displayed task."""
        self._task = task
        self.refresh()

    def render(self) -> Text:
        """Render task details."""
        if not self._task:
            return Text("No task selected", style="dim")

        t = self._task
        lines = []

        lines.append(("ID: ", "bold"))
        lines.append((t.display_id, "cyan"))
        lines.append(("\n", ""))

        lines.append(("Status: ", "bold"))
        status_style = {
            "pending": "dim",
            "blocked": "yellow",
            "in_progress": "cyan",
            "done": "green",
            "failed": "red",
        }.get(t.status.value, "white")
        lines.append((t.status.value.replace("_", " ").title(), status_style))
        lines.append(("\n", ""))

        if t.worktree:
            lines.append(("Worktree: ", "bold"))
            lines.append((t.worktree, ""))
            lines.append(("\n", ""))

        if t.phase:
            lines.append(("Phase: ", "bold"))
            lines.append((t.phase, ""))
            lines.append(("\n", ""))

        lines.append(("\nDescription:\n", "bold"))
        lines.append((t.description, ""))

        text = Text()
        for content, style in lines:
            text.append(content, style=style)

        return text
```

### 3.6 Update TUI App

**Update**: `src/adw/tui/app.py`

Replace placeholders with real widgets:

```python
"""Main ADW TUI application."""

from __future__ import annotations

from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Header, Footer, Static, Placeholder

from .state import AppState
from .widgets.status_bar import StatusBar
from .widgets.task_list import TaskList
from .widgets.task_detail import TaskDetail


class ADWApp(App):
    """ADW Dashboard Application."""

    CSS_PATH = "styles.tcss"
    TITLE = "ADW"
    SUB_TITLE = "AI Developer Workflow"

    BINDINGS = [
        Binding("n", "new_task", "New"),
        Binding("q", "quit", "Quit"),
        Binding("?", "show_help", "Help"),
        Binding("r", "refresh", "Refresh"),
        Binding("tab", "focus_next", "Next"),
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self):
        super().__init__()
        self.state = AppState()
        self.state.subscribe(self._on_state_change)

    def compose(self) -> ComposeResult:
        yield Header()

        with Container(id="app-container"):
            with Horizontal(id="main-panels"):
                with Vertical(id="left-panel", classes="panel"):
                    yield Static("TASKS", classes="panel-title")
                    yield TaskList(id="task-list")

                with Vertical(id="right-panel", classes="panel"):
                    yield Static("DETAILS", classes="panel-title")
                    yield TaskDetail(id="task-detail")

            with Vertical(id="bottom-panel", classes="panel"):
                yield Static("LOGS", classes="panel-title")
                yield Placeholder("Log viewer coming soon...", id="log-placeholder")

            yield StatusBar(id="status-bar")

        yield Footer()

    async def on_mount(self) -> None:
        """Initialize state on mount."""
        self.state.load_from_tasks_md()

    def _on_state_change(self, state: AppState) -> None:
        """Handle state changes."""
        # Update task list
        task_list = self.query_one("#task-list", TaskList)
        task_list.update_tasks(state.tasks)

        # Update detail
        task_detail = self.query_one("#task-detail", TaskDetail)
        task_detail.update_task(state.selected_task)

        # Update status bar
        status_bar = self.query_one("#status-bar", StatusBar)
        status_bar.update_status(
            active_tasks=state.running_count,
            selected_task=state.selected_task.display_id if state.selected_task else None,
        )

    def on_task_list_task_selected(self, event: TaskList.TaskSelected) -> None:
        """Handle task selection."""
        self.state.select_task(event.key)

    def action_refresh(self) -> None:
        """Refresh from tasks.md."""
        self.state.load_from_tasks_md()
        self.notify("Refreshed")

    def action_new_task(self) -> None:
        self.notify("New task - not implemented yet")

    def action_show_help(self) -> None:
        self.notify("n=new, r=refresh, q=quit, tab=switch")

    async def action_quit(self) -> None:
        self.exit()
```

---

## Validation

1. **Tasks display**: Tasks from tasks.md appear in list
2. **Selection works**: Clicking/entering task shows details
3. **Status icons**: Correct icons for each status
4. **Refresh works**: `r` key reloads from file
5. **Parser handles**: Various task formats, tags, errors

---

## Files to Create

- `src/adw/agent/task_parser.py`
- `src/adw/agent/task_updater.py`
- `src/adw/tui/state.py`
- `src/adw/tui/widgets/task_list.py`
- `src/adw/tui/widgets/task_detail.py`

## Files to Modify

- `src/adw/agent/__init__.py` (export new modules)
- `src/adw/tui/app.py` (use real widgets)
- `src/adw/tui/widgets/__init__.py` (export new widgets)
