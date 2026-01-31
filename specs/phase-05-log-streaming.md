# Phase 5: Log Streaming

**ADW Build Phase**: 5 of 12
**Dependencies**: Phase 1-4
**Estimated Complexity**: Medium

---

## Objective

Implement live log streaming from agents to TUI:
- Watch agent output files for changes
- Parse JSONL into displayable events
- Stream to log viewer widget
- Buffer and format logs

---

## Deliverables

### 5.1 Log Watcher

**File**: `src/adw/tui/log_watcher.py`

```python
"""Watch agent output files and stream to TUI."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Callable, AsyncIterator
from dataclasses import dataclass
from datetime import datetime

from watchfiles import awatch, Change


@dataclass
class LogEvent:
    """A single log event."""
    timestamp: datetime
    adw_id: str
    event_type: str
    message: str
    tool_name: str | None = None
    file_path: str | None = None
    phase: str | None = None


class LogWatcher:
    """Watch agent output directories for log events."""

    def __init__(self, agents_dir: Path | None = None):
        self.agents_dir = agents_dir or Path("agents")
        self._subscribers: dict[str, list[Callable]] = {}  # adw_id -> callbacks
        self._file_positions: dict[str, int] = {}  # file -> last read position
        self._running = False

    def subscribe(self, adw_id: str, callback: Callable[[LogEvent], None]) -> None:
        """Subscribe to logs for an ADW ID."""
        if adw_id not in self._subscribers:
            self._subscribers[adw_id] = []
        self._subscribers[adw_id].append(callback)

    def subscribe_all(self, callback: Callable[[LogEvent], None]) -> None:
        """Subscribe to all logs."""
        self.subscribe("*", callback)

    def unsubscribe(self, adw_id: str, callback: Callable) -> None:
        """Unsubscribe from logs."""
        if adw_id in self._subscribers:
            self._subscribers[adw_id] = [
                cb for cb in self._subscribers[adw_id] if cb != callback
            ]

    async def watch(self) -> None:
        """Main watch loop."""
        self._running = True

        if not self.agents_dir.exists():
            self.agents_dir.mkdir(parents=True, exist_ok=True)

        try:
            async for changes in awatch(self.agents_dir):
                if not self._running:
                    break

                for change_type, path_str in changes:
                    path = Path(path_str)

                    # Only handle JSONL files
                    if not path.name.endswith(".jsonl"):
                        continue

                    # Extract ADW ID from path
                    try:
                        rel = path.relative_to(self.agents_dir)
                        adw_id = rel.parts[0]
                    except (ValueError, IndexError):
                        continue

                    # Read new content
                    if change_type in (Change.added, Change.modified):
                        await self._handle_file_change(adw_id, path)

        except Exception as e:
            # Log but don't crash
            pass

    def stop(self) -> None:
        """Stop watching."""
        self._running = False

    async def _handle_file_change(self, adw_id: str, path: Path) -> None:
        """Handle a file change."""
        if not path.exists():
            return

        # Get last position
        path_key = str(path)
        last_pos = self._file_positions.get(path_key, 0)

        try:
            with open(path, "r") as f:
                f.seek(last_pos)
                new_content = f.read()
                self._file_positions[path_key] = f.tell()

            # Parse new lines
            for line in new_content.strip().split("\n"):
                if not line:
                    continue

                try:
                    data = json.loads(line)
                    event = self._parse_event(adw_id, data)
                    if event:
                        self._notify(adw_id, event)
                except json.JSONDecodeError:
                    continue

        except Exception:
            pass

    def _parse_event(self, adw_id: str, data: dict) -> LogEvent | None:
        """Parse raw event data into LogEvent."""
        event_type = data.get("type", "unknown")

        # Map Claude Code message types
        if event_type == "assistant":
            content = data.get("message", {}).get("content", [])
            if content:
                text = ""
                if isinstance(content, list):
                    for c in content:
                        if c.get("type") == "text":
                            text = c.get("text", "")[:100]
                            break
                else:
                    text = str(content)[:100]

                return LogEvent(
                    timestamp=datetime.now(),
                    adw_id=adw_id,
                    event_type="assistant",
                    message=text,
                )

        elif event_type == "tool_use":
            tool = data.get("tool", {})
            return LogEvent(
                timestamp=datetime.now(),
                adw_id=adw_id,
                event_type="tool",
                message=f"Using {tool.get('name', 'unknown')}",
                tool_name=tool.get("name"),
            )

        elif event_type == "tool_result":
            return LogEvent(
                timestamp=datetime.now(),
                adw_id=adw_id,
                event_type="tool_result",
                message="Tool completed",
            )

        elif event_type == "result":
            return LogEvent(
                timestamp=datetime.now(),
                adw_id=adw_id,
                event_type="result",
                message="Agent completed",
            )

        elif event_type == "error":
            error = data.get("error", {})
            return LogEvent(
                timestamp=datetime.now(),
                adw_id=adw_id,
                event_type="error",
                message=error.get("message", "Unknown error"),
            )

        return None

    def _notify(self, adw_id: str, event: LogEvent) -> None:
        """Notify subscribers of event."""
        # Specific subscribers
        for cb in self._subscribers.get(adw_id, []):
            cb(event)

        # All subscribers
        for cb in self._subscribers.get("*", []):
            cb(event)
```

### 5.2 Log Formatter

**File**: `src/adw/tui/log_formatter.py`

```python
"""Format log events for display."""

from __future__ import annotations

from rich.text import Text

from .log_watcher import LogEvent


ICONS = {
    "assistant": "💬",
    "tool": "🔧",
    "tool_result": "✓",
    "result": "✅",
    "error": "❌",
    "file_read": "📖",
    "file_write": "📝",
    "unknown": "•",
}

STYLES = {
    "assistant": "white",
    "tool": "cyan",
    "tool_result": "dim",
    "result": "green",
    "error": "red",
}


def format_event(event: LogEvent) -> Text:
    """Format a log event for display."""
    icon = ICONS.get(event.event_type, "•")
    style = STYLES.get(event.event_type, "white")
    time = event.timestamp.strftime("%H:%M:%S")

    text = Text()
    text.append(f"{time} ", style="dim")
    text.append(f"{icon} ", style="bold")
    text.append(f"[{event.adw_id[:8]}] ", style="cyan dim")
    text.append(event.message[:80], style=style)

    return text
```

### 5.3 Log Buffer

**File**: `src/adw/tui/log_buffer.py`

```python
"""Buffer logs with automatic pruning."""

from __future__ import annotations

from collections import deque
from rich.text import Text

from .log_watcher import LogEvent
from .log_formatter import format_event


class LogBuffer:
    """Buffer log events with max capacity."""

    def __init__(self, max_lines: int = 500):
        self.max_lines = max_lines
        self._buffers: dict[str, deque[Text]] = {}  # adw_id -> lines
        self._all: deque[Text] = deque(maxlen=max_lines)

    def add(self, event: LogEvent) -> Text:
        """Add event to buffer, return formatted line."""
        line = format_event(event)

        # Per-agent buffer
        if event.adw_id not in self._buffers:
            self._buffers[event.adw_id] = deque(maxlen=self.max_lines)
        self._buffers[event.adw_id].append(line)

        # Global buffer
        self._all.append(line)

        return line

    def get_for_agent(self, adw_id: str, count: int = 50) -> list[Text]:
        """Get recent lines for agent."""
        if adw_id not in self._buffers:
            return []
        return list(self._buffers[adw_id])[-count:]

    def get_all(self, count: int = 50) -> list[Text]:
        """Get all recent lines."""
        return list(self._all)[-count:]

    def clear(self, adw_id: str | None = None) -> None:
        """Clear buffer."""
        if adw_id:
            if adw_id in self._buffers:
                self._buffers[adw_id].clear()
        else:
            self._buffers.clear()
            self._all.clear()
```

### 5.4 Log Viewer Widget

**File**: `src/adw/tui/widgets/log_viewer.py`

```python
"""Log viewer widget."""

from __future__ import annotations

from textual.widgets import RichLog
from textual.message import Message
from rich.text import Text

from ..log_watcher import LogEvent
from ..log_buffer import LogBuffer
from ..log_formatter import format_event


class LogViewer(RichLog):
    """Display streaming logs."""

    DEFAULT_CSS = """
    LogViewer {
        height: 100%;
        border: none;
        scrollbar-gutter: stable;
    }
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, highlight=True, markup=True, **kwargs)
        self.buffer = LogBuffer()
        self._filter_adw_id: str | None = None

    def on_log_event(self, event: LogEvent) -> None:
        """Handle incoming log event."""
        # Add to buffer
        line = self.buffer.add(event)

        # Check filter
        if self._filter_adw_id and event.adw_id != self._filter_adw_id:
            return

        # Display
        self.write(line)

    def filter_by_agent(self, adw_id: str | None) -> None:
        """Filter logs to specific agent."""
        self._filter_adw_id = adw_id
        self.clear()

        if adw_id:
            lines = self.buffer.get_for_agent(adw_id)
        else:
            lines = self.buffer.get_all()

        for line in lines:
            self.write(line)

    def clear_logs(self) -> None:
        """Clear displayed logs."""
        self.clear()
        self.buffer.clear(self._filter_adw_id)
```

### 5.5 Wire to TUI App

**Update**: `src/adw/tui/app.py`

Add log watcher integration:

```python
# Add imports
from .log_watcher import LogWatcher, LogEvent
from .widgets.log_viewer import LogViewer

# Update __init__
def __init__(self):
    super().__init__()
    self.state = AppState()
    self.agent_manager = AgentManager()
    self.log_watcher = LogWatcher()

    self.state.subscribe(self._on_state_change)
    self.agent_manager.subscribe(self._on_agent_event)
    self.log_watcher.subscribe_all(self._on_log_event)

# Update compose to use LogViewer
with Vertical(id="bottom-panel", classes="panel"):
    yield Static("LOGS", classes="panel-title")
    yield LogViewer(id="log-viewer")

# Add log event handler
def _on_log_event(self, event: LogEvent) -> None:
    """Handle log event."""
    log_viewer = self.query_one("#log-viewer", LogViewer)
    log_viewer.on_log_event(event)

# Update on_mount to start watcher
async def on_mount(self) -> None:
    self.state.load_from_tasks_md()
    self.set_interval(2.0, self._poll_agents)
    self.run_worker(self.log_watcher.watch())

# Add filter on task selection
def _on_state_change(self, state: AppState) -> None:
    # ... existing code ...

    # Filter logs to selected task
    log_viewer = self.query_one("#log-viewer", LogViewer)
    if state.selected_task:
        log_viewer.filter_by_agent(state.selected_task.adw_id)
    else:
        log_viewer.filter_by_agent(None)

# Add clear logs binding
BINDINGS = [
    # ... existing ...
    Binding("c", "clear_logs", "Clear"),
]

def action_clear_logs(self) -> None:
    """Clear log viewer."""
    log_viewer = self.query_one("#log-viewer", LogViewer)
    log_viewer.clear_logs()
```

---

## Validation

1. **Watcher detects changes**: New files in agents/ trigger events
2. **JSONL parsing works**: Claude Code output parsed into events
3. **Logs display**: Events appear in log viewer
4. **Filtering works**: Selecting task filters to that agent
5. **Buffer limits**: Old logs pruned when max reached
6. **Clear works**: `c` key clears logs

---

## Files to Create

- `src/adw/tui/log_watcher.py`
- `src/adw/tui/log_formatter.py`
- `src/adw/tui/log_buffer.py`
- `src/adw/tui/widgets/log_viewer.py`

## Files to Modify

- `src/adw/tui/app.py` (add log watcher, update compose)
- `src/adw/tui/widgets/__init__.py` (export LogViewer)
