"""Rich status bar widget with input field and activity tracking."""

from __future__ import annotations

from datetime import datetime
from textual.widgets import Static, Input
from textual.containers import Horizontal
from textual.app import ComposeResult
from textual.reactive import reactive


class StatusBar(Horizontal):
    """Rich status bar with activity display, input field, and shortcuts."""

    DEFAULT_CSS = """
    StatusBar {
        height: 3;
        width: 100%;
        background: $surface;
        border-top: solid $primary;
        padding: 0 1;
    }

    StatusBar > #status-activity {
        width: 20;
        padding: 1 0;
        color: $success;
    }

    StatusBar > #status-input {
        width: 1fr;
        margin: 0 1;
    }

    StatusBar > #status-shortcuts {
        width: auto;
        padding: 1 0;
        color: $text-muted;
    }
    """

    # Spinner frames for activity indication
    SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    # Reactive properties
    is_busy = reactive(False)
    activity_text = reactive("")
    spinner_frame = reactive(0)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.active_tasks = 0
        self.selected_task = None
        self.started_at: datetime | None = None
        self._timer = None

    def compose(self) -> ComposeResult:
        """Create status bar content."""
        yield Static(self._get_activity_text(), id="status-activity")
        yield Input(placeholder="Type message or /command...", id="status-input")
        yield Static(self._get_shortcuts_text(), id="status-shortcuts")

    def on_mount(self) -> None:
        """Start the spinner timer when mounted."""
        self._timer = self.set_interval(0.1, self._tick_spinner)

    def _tick_spinner(self) -> None:
        """Update spinner animation and elapsed time."""
        if self.is_busy:
            self.spinner_frame = (self.spinner_frame + 1) % len(self.SPINNER_FRAMES)
            self._update_activity_display()

    def _format_elapsed(self, started_at: datetime | None) -> str:
        """Format elapsed time as human-readable string."""
        if not started_at:
            return ""

        delta = datetime.now() - started_at
        total_seconds = int(delta.total_seconds())

        if total_seconds < 60:
            return f"{total_seconds}s"
        elif total_seconds < 3600:
            minutes = total_seconds // 60
            seconds = total_seconds % 60
            return f"{minutes}m {seconds:02d}s"
        else:
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            return f"{hours}h {minutes:02d}m"

    def _get_activity_text(self) -> str:
        """Get the activity display text with spinner and elapsed time."""
        if self.is_busy:
            spinner = self.SPINNER_FRAMES[self.spinner_frame]
            elapsed = self._format_elapsed(self.started_at)
            if elapsed:
                return f"{spinner} {self.activity_text} • {elapsed}"
            return f"{spinner} {self.activity_text}"

        if self.selected_task:
            return f"◉ {self.selected_task}"

        if self.active_tasks > 0:
            return f"◉ {self.active_tasks} active"

        return "○ idle"

    def _get_shortcuts_text(self) -> str:
        """Get keyboard shortcuts hint text."""
        return "[n]ew [?]help"

    def _update_activity_display(self) -> None:
        """Update the activity display widget."""
        try:
            activity = self.query_one("#status-activity", Static)
            activity.update(self._get_activity_text())
        except Exception:
            pass

    def update_status(
        self,
        active_tasks: int = 0,
        selected_task: str | None = None,
        activity: str | None = None,
        started_at: datetime | None = None,
    ) -> None:
        """Update the status display."""
        self.active_tasks = active_tasks
        self.selected_task = selected_task
        self.started_at = started_at

        if activity:
            self.is_busy = True
            self.activity_text = activity
        elif active_tasks > 0:
            self.is_busy = True
            self.activity_text = f"{active_tasks} running"
        else:
            self.is_busy = False
            self.activity_text = ""

        self._update_activity_display()

    def set_activity(self, activity: str, started_at: datetime | None = None) -> None:
        """Set the current activity with optional start time."""
        self.is_busy = True
        self.activity_text = activity
        self.started_at = started_at or datetime.now()
        self._update_activity_display()

    def set_idle(self) -> None:
        """Set status to idle."""
        self.is_busy = False
        self.activity_text = ""
        self.started_at = None
        self._update_activity_display()
