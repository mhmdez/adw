# Phase 2: TUI Shell

**ADW Build Phase**: 2 of 12
**Dependencies**: Phase 1 (Foundation)
**Estimated Complexity**: Medium

---

## Objective

Create the Textual-based TUI application shell with:
- Basic app structure
- Panel layout
- Styling
- Keyboard bindings
- Empty widget placeholders

---

## Deliverables

### 2.1 Dependencies

**Update**: `pyproject.toml`

```toml
dependencies = [
    "click>=8.1.0",
    "rich>=13.0.0",
    "httpx>=0.25.0",
    "pydantic>=2.0.0",
    "textual>=0.50.0",
    "watchfiles>=0.20.0",
]
```

### 2.2 Main Application

**File**: `src/adw/tui/app.py`

```python
"""Main ADW TUI application."""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Header, Footer, Static, Placeholder

from .widgets.status_bar import StatusBar


class ADWApp(App):
    """ADW Dashboard Application."""

    CSS_PATH = "styles.tcss"
    TITLE = "ADW"
    SUB_TITLE = "AI Developer Workflow"

    BINDINGS = [
        Binding("n", "new_task", "New"),
        Binding("q", "quit", "Quit"),
        Binding("?", "show_help", "Help"),
        Binding("tab", "focus_next", "Next"),
        Binding("shift+tab", "focus_previous", "Prev"),
        Binding("escape", "cancel", "Cancel"),
    ]

    def compose(self) -> ComposeResult:
        """Create the UI layout."""
        yield Header()

        with Container(id="app-container"):
            with Horizontal(id="main-panels"):
                # Left: Task list
                with Vertical(id="left-panel", classes="panel"):
                    yield Static("TASKS", classes="panel-title")
                    yield Placeholder("Task List", id="task-list-placeholder")

                # Right: Task detail
                with Vertical(id="right-panel", classes="panel"):
                    yield Static("DETAILS", classes="panel-title")
                    yield Placeholder("Task Details", id="task-detail-placeholder")

            # Bottom: Logs
            with Vertical(id="bottom-panel", classes="panel"):
                yield Static("LOGS", classes="panel-title")
                yield Placeholder("Log Viewer", id="log-placeholder")

            # Status/input bar
            yield StatusBar(id="status-bar")

        yield Footer()

    def action_new_task(self) -> None:
        """Handle new task action."""
        self.notify("New task (not implemented yet)")

    def action_show_help(self) -> None:
        """Show help."""
        self.notify("Help: n=new, q=quit, tab=switch panels")

    def action_cancel(self) -> None:
        """Cancel current action."""
        pass

    async def action_quit(self) -> None:
        """Quit the application."""
        self.exit()


def run_tui() -> None:
    """Run the TUI application."""
    app = ADWApp()
    app.run()
```

### 2.3 Stylesheet

**File**: `src/adw/tui/styles.tcss`

```css
/* ADW TUI Stylesheet */

/* Base */
Screen {
    background: $surface;
}

/* Header */
Header {
    dock: top;
    height: 1;
    background: $primary;
}

/* Footer */
Footer {
    dock: bottom;
    height: 1;
    background: $primary;
}

/* Main container */
#app-container {
    width: 100%;
    height: 100%;
    padding: 0;
}

/* Main panels horizontal layout */
#main-panels {
    height: 60%;
    width: 100%;
}

/* Left panel - task list */
#left-panel {
    width: 35%;
    height: 100%;
    border: solid $primary;
    border-title-color: $primary;
}

/* Right panel - task details */
#right-panel {
    width: 65%;
    height: 100%;
    border: solid $primary;
    border-title-color: $primary;
}

/* Bottom panel - logs */
#bottom-panel {
    height: 35%;
    width: 100%;
    border: solid $primary;
    border-title-color: $primary;
}

/* Panel styling */
.panel {
    padding: 0 1;
}

.panel-title {
    text-style: bold;
    color: $primary;
    padding: 0 0 1 0;
    text-align: center;
}

/* Status bar */
#status-bar {
    dock: bottom;
    height: 3;
    width: 100%;
    border: solid $secondary;
    padding: 0 1;
}

/* Placeholders */
Placeholder {
    height: 100%;
}

/* Focus states */
.panel:focus-within {
    border: solid $accent;
}

/* Responsive - small terminals */
@media (max-width: 80) {
    #main-panels {
        height: 50%;
    }
    #left-panel {
        width: 100%;
        height: 50%;
    }
    #right-panel {
        display: none;
    }
}
```

### 2.4 Status Bar Widget

**File**: `src/adw/tui/widgets/status_bar.py`

```python
"""Status bar widget with input capability."""

from __future__ import annotations

from textual.widgets import Static, Input
from textual.containers import Horizontal
from textual.app import ComposeResult


class StatusBar(Static):
    """Status bar with message display and input."""

    DEFAULT_CSS = """
    StatusBar {
        height: 3;
        layout: horizontal;
    }

    StatusBar > .status-info {
        width: 30%;
        padding: 1;
    }

    StatusBar > .status-input {
        width: 70%;
        padding: 0 1;
    }

    StatusBar Input {
        width: 100%;
    }
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.active_tasks = 0
        self.selected_task = None

    def compose(self) -> ComposeResult:
        """Create status bar content."""
        with Horizontal():
            yield Static(self._get_status_text(), id="status-info", classes="status-info")
            with Static(classes="status-input"):
                yield Input(placeholder="Type message or command...", id="status-input-field")

    def _get_status_text(self) -> str:
        """Get status display text."""
        if self.selected_task:
            return f"Selected: {self.selected_task}"
        return f"Tasks: {self.active_tasks} active"

    def update_status(self, active_tasks: int = 0, selected_task: str | None = None):
        """Update the status display."""
        self.active_tasks = active_tasks
        self.selected_task = selected_task

        info = self.query_one("#status-info", Static)
        info.update(self._get_status_text())
```

### 2.5 Package Init

**File**: `src/adw/tui/__init__.py`

```python
"""ADW TUI module."""

from .app import ADWApp, run_tui

__all__ = ["ADWApp", "run_tui"]
```

**File**: `src/adw/tui/widgets/__init__.py`

```python
"""TUI Widgets."""

from .status_bar import StatusBar

__all__ = ["StatusBar"]
```

### 2.6 CLI Integration

**Update**: `src/adw/cli.py`

Add the dashboard command and make it the default:

```python
# At the top, add import
from .tui import run_tui

# Update the main group
@click.group(invoke_without_command=True)
@click.option("--version", "-v", is_flag=True, help="Show version and exit")
@click.pass_context
def main(ctx: click.Context, version: bool) -> None:
    """ADW - AI Developer Workflow CLI."""
    if version:
        console.print(f"adw version {__version__}")
        return

    if ctx.invoked_subcommand is None:
        # Default: run TUI dashboard
        run_tui()


# Add explicit dashboard command
@main.command()
def dashboard() -> None:
    """Open the interactive TUI dashboard."""
    run_tui()
```

---

## Validation

1. **TUI launches**: `adw` opens the dashboard
2. **Layout renders**: Three panels visible (tasks, details, logs)
3. **Keyboard works**: `q` quits, `tab` switches focus, `?` shows help
4. **Responsive**: Resizing terminal adjusts layout
5. **Status bar visible**: Shows at bottom with input field

---

## Files to Create

- `src/adw/tui/__init__.py`
- `src/adw/tui/app.py`
- `src/adw/tui/styles.tcss`
- `src/adw/tui/widgets/__init__.py`
- `src/adw/tui/widgets/status_bar.py`

## Files to Modify

- `pyproject.toml` (add textual, watchfiles)
- `src/adw/cli.py` (add dashboard command, change default)
