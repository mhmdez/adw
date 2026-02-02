"""Event stream widget for observability events."""

from __future__ import annotations

from rich.text import Text
from textual.widgets import RichLog

from ...observability import Event, EventType, get_db

# Event type icons
EVENT_ICONS = {
    # Tool events
    EventType.TOOL_START: "⚙",
    EventType.TOOL_END: "✓",
    EventType.TOOL_ERROR: "✗",
    # Session events
    EventType.SESSION_START: "▶",
    EventType.SESSION_END: "■",
    # Agent events
    EventType.AGENT_MESSAGE: "💬",
    EventType.AGENT_QUESTION: "❓",
    EventType.AGENT_ANSWER: "💡",
    # Task events
    EventType.TASK_STARTED: "🚀",
    EventType.TASK_COMPLETED: "✅",
    EventType.TASK_FAILED: "❌",
    EventType.TASK_BLOCKED: "⏸",
    # System events
    EventType.SAFETY_BLOCK: "🛑",
    EventType.ERROR: "⚠",
    EventType.WARNING: "⚡",
    EventType.INFO: "ℹ",
    # Hook events
    EventType.PRE_TOOL_USE: "→",
    EventType.POST_TOOL_USE: "←",
    EventType.USER_PROMPT: "👤",
    EventType.STOP: "⏹",
}

# Event type colors
EVENT_COLORS = {
    # Tool events - cyan
    EventType.TOOL_START: "cyan",
    EventType.TOOL_END: "green",
    EventType.TOOL_ERROR: "red",
    # Session events - blue
    EventType.SESSION_START: "blue",
    EventType.SESSION_END: "dim blue",
    # Agent events - yellow
    EventType.AGENT_MESSAGE: "yellow",
    EventType.AGENT_QUESTION: "bold yellow",
    EventType.AGENT_ANSWER: "green",
    # Task events - colored by status
    EventType.TASK_STARTED: "blue",
    EventType.TASK_COMPLETED: "green",
    EventType.TASK_FAILED: "red",
    EventType.TASK_BLOCKED: "yellow",
    # System events
    EventType.SAFETY_BLOCK: "bold red",
    EventType.ERROR: "red",
    EventType.WARNING: "yellow",
    EventType.INFO: "dim",
    # Hook events - dim
    EventType.PRE_TOOL_USE: "dim cyan",
    EventType.POST_TOOL_USE: "dim cyan",
    EventType.USER_PROMPT: "dim magenta",
    EventType.STOP: "dim",
}


class EventStream(RichLog):
    """Real-time event stream panel.

    Displays observability events from the database in real-time.
    Color-coded by event type for quick visual scanning.
    """

    DEFAULT_CSS = """
    EventStream {
        width: 100%;
        height: 1fr;
        border: round #222;
        background: #0a0a0a;
        padding: 0 1;
    }

    EventStream:focus {
        border: round #00D4FF;
    }

    EventStream > #event-header {
        height: 1;
        color: #00D4FF;
        text-style: bold;
        padding-bottom: 1;
    }
    """

    def __init__(self, max_events: int = 50, **kwargs) -> None:  # type: ignore[no-untyped-def]
        """Initialize event stream.

        Args:
            max_events: Maximum number of events to display.
            **kwargs: Additional arguments for RichLog.
        """
        super().__init__(highlight=True, markup=True, wrap=True, **kwargs)
        self.max_events = max_events
        self._event_count = 0
        self._last_event_id: int = 0
        self._filter_task_id: str | None = None

    def on_mount(self) -> None:
        """Load recent events on mount."""
        self._load_recent_events()
        # Poll for new events every second
        self.set_interval(1.0, self._poll_events)

    def _load_recent_events(self) -> None:
        """Load recent events from database."""
        try:
            db = get_db()
            from ...observability import EventFilter

            filter_ = EventFilter(limit=self.max_events)
            if self._filter_task_id:
                filter_.task_id = self._filter_task_id

            events = db.get_events(filter_)

            # Display in chronological order (oldest first)
            for event in reversed(events):
                self._display_event(event)
                if event.id and event.id > self._last_event_id:
                    self._last_event_id = event.id
        except Exception:
            # Database may not exist yet
            pass

    def _poll_events(self) -> None:
        """Poll for new events."""
        try:
            db = get_db()
            from ...observability import EventFilter

            filter_ = EventFilter(limit=20)
            if self._filter_task_id:
                filter_.task_id = self._filter_task_id

            events = db.get_events(filter_)

            # Display any new events
            new_events = []
            for event in events:
                if event.id and event.id > self._last_event_id:
                    new_events.append(event)
                    self._last_event_id = event.id

            # Display in chronological order
            for event in reversed(new_events):
                self._display_event(event)
        except Exception:
            pass

    def _display_event(self, event: Event) -> None:
        """Display a single event.

        Args:
            event: Event to display.
        """
        line = self._format_event(event)
        self.write(line)
        self._event_count += 1

    def _format_event(self, event: Event) -> Text:
        """Format an event for display.

        Args:
            event: Event to format.

        Returns:
            Formatted Rich Text.
        """
        line = Text()

        # Timestamp
        ts = event.timestamp.strftime("%H:%M:%S")
        line.append(f"{ts} ", style="dim")

        # Task ID (truncated)
        if event.task_id:
            line.append(f"[{event.task_id[:6]}] ", style="dim cyan")

        # Icon
        icon = EVENT_ICONS.get(event.event_type, "•")
        color = EVENT_COLORS.get(event.event_type, "white")
        line.append(f"{icon} ", style=color)

        # Event type (shortened for compact display)
        type_name = event.event_type.value.replace("_", " ")
        line.append(f"{type_name}", style=color)

        # Additional details from data
        details = self._get_event_details(event)
        if details:
            line.append(f" → {details}", style="dim")

        return line

    def _get_event_details(self, event: Event) -> str:
        """Extract relevant details from event data.

        Args:
            event: Event to extract details from.

        Returns:
            Detail string or empty string.
        """
        data = event.data
        if not data:
            return ""

        # Tool name
        if "tool_name" in data:
            return str(data["tool_name"])

        # Message
        if "message" in data:
            msg = str(data["message"])
            if len(msg) > 40:
                msg = msg[:40] + "..."
            return msg

        # Status
        if "status" in data:
            return str(data["status"])

        # Duration
        if "duration" in data:
            return str(data["duration"])

        return ""

    def filter_by_task(self, task_id: str | None) -> None:
        """Filter events to specific task.

        Args:
            task_id: Task ID to filter by, or None for all.
        """
        self._filter_task_id = task_id
        self.clear()
        self._event_count = 0
        self._last_event_id = 0
        self._load_recent_events()

    def add_event(self, event: Event) -> None:
        """Add a new event to the stream.

        This can be called directly for real-time events
        that haven't been written to the database yet.

        Args:
            event: Event to add.
        """
        if self._filter_task_id and event.task_id != self._filter_task_id:
            return

        self._display_event(event)
        if event.id and event.id > self._last_event_id:
            self._last_event_id = event.id

    def clear_stream(self) -> None:
        """Clear the event stream."""
        self.clear()
        self._event_count = 0

    @property
    def event_count(self) -> int:
        """Get the number of displayed events."""
        return self._event_count
