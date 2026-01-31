# ADW UX/Architecture Specification

> **Vision**: A terminal-native dashboard where users manage AI agents without ever "jumping into" Claude. Agents work in the background while users monitor, guide, and intervene from a unified interface.

---

## Table of Contents

1. [Design Philosophy](#1-design-philosophy)
2. [Architecture Overview](#2-architecture-overview)
3. [TUI Framework Decision](#3-tui-framework-decision)
4. [Screen Layouts](#4-screen-layouts)
5. [Agent Communication Protocol](#5-agent-communication-protocol)
6. [Live Log Streaming](#6-live-log-streaming)
7. [Message Injection](#7-message-injection)
8. [Interaction Model](#8-interaction-model)
9. [State Synchronization](#9-state-synchronization)
10. [Implementation Details](#10-implementation-details)

---

## 1. Design Philosophy

### 1.1 Core Principles

1. **User Stays in Control**
   - ADW TUI is the primary interface
   - Claude runs as background processes
   - User never needs to "be in" Claude

2. **Visibility Without Noise**
   - See all running agents at a glance
   - Drill into details on demand
   - Filter noise, surface important events

3. **Non-Blocking Interaction**
   - Start tasks without waiting
   - Monitor multiple agents simultaneously
   - Intervene without stopping workflow

4. **Terminal-Native**
   - Works over SSH
   - No browser required
   - Keyboard-first navigation
   - Mouse support as enhancement

### 1.2 User Journey

```
┌──────────────────────────────────────────────────────────────────┐
│                         USER JOURNEY                              │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│   $ adw                                                          │
│        │                                                          │
│        ▼                                                          │
│   ┌─────────────┐                                                │
│   │  Dashboard  │ ◄─── See all tasks, agents, status             │
│   └──────┬──────┘                                                │
│          │                                                        │
│    ┌─────┴─────┬──────────────┬───────────────┐                  │
│    ▼           ▼              ▼               ▼                  │
│ [n]ew      [Enter]        [Tab]           [q]uit                 │
│ task       select         switch                                  │
│    │       task           panel                                   │
│    ▼           │              │                                   │
│ ┌──────┐      ▼              ▼                                   │
│ │Prompt│  ┌────────┐    ┌────────┐                               │
│ │ box  │  │Task    │    │Switch  │                               │
│ │      │  │Detail  │    │focus   │                               │
│ └──┬───┘  │View    │    │area    │                               │
│    │      └────────┘    └────────┘                               │
│    ▼                                                              │
│ Agent                                                             │
│ spawned ──► Background execution ──► Status updates to TUI       │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

### 1.3 What We're NOT Building

- A web dashboard (terminal only)
- A replacement for Claude Code (we use it underneath)
- A chat interface (task-oriented, not conversational)
- An IDE plugin (standalone CLI tool)

---

## 2. Architecture Overview

### 2.1 System Components

```
┌─────────────────────────────────────────────────────────────────┐
│                          USER                                    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        TUI LAYER                                 │
│  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐       │
│  │ Dashboard │ │Task Detail│ │ Log View  │ │  Input    │       │
│  │   View    │ │   View    │ │           │ │  Handler  │       │
│  └───────────┘ └───────────┘ └───────────┘ └───────────┘       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     EVENT BUS (async)                            │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Task Events │ Log Events │ Agent Events │ User Events  │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
                              │
            ┌─────────────────┼─────────────────┐
            ▼                 ▼                 ▼
┌───────────────────┐ ┌───────────────┐ ┌───────────────┐
│   AGENT MANAGER   │ │  LOG WATCHER  │ │ STATE MANAGER │
│                   │ │               │ │               │
│ - Spawn agents    │ │ - Tail files  │ │ - tasks.md    │
│ - Track processes │ │ - Parse JSONL │ │ - adw_state   │
│ - Handle signals  │ │ - Filter/fmt  │ │ - Sync disk   │
└───────────────────┘ └───────────────┘ └───────────────┘
            │                 │                 │
            ▼                 ▼                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                      FILE SYSTEM                                 │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐               │
│  │ agents/     │ │ tasks.md    │ │ .adw/       │               │
│  │ {adw_id}/   │ │             │ │ state/      │               │
│  └─────────────┘ └─────────────┘ └─────────────┘               │
└─────────────────────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────────┐
│                   CLAUDE CODE PROCESSES                          │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐               │
│  │ Agent 1     │ │ Agent 2     │ │ Agent 3     │               │
│  │ (abc123)    │ │ (def456)    │ │ (ghi789)    │               │
│  └─────────────┘ └─────────────┘ └─────────────┘               │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Process Model

```
ADW Main Process (TUI)
│
├── Event Loop (async)
│   ├── Handle keyboard input
│   ├── Process file system events
│   ├── Update UI state
│   └── Render frames
│
├── Agent Manager
│   ├── Spawns Claude Code as subprocess
│   ├── Tracks PID → ADW ID mapping
│   ├── Handles process signals
│   └── Manages message queues
│
├── Log Watcher (async)
│   ├── inotify/fsevents on agents/*/
│   ├── Tails *.jsonl files
│   ├── Parses and routes events
│   └── Buffers for UI
│
└── State Manager
    ├── Watches tasks.md for changes
    ├── Syncs adw_state.json files
    └── Provides reactive state
```

### 2.3 Data Flow

```
User Action                    System Response
───────────────────────────────────────────────────────

[n] new task
      │
      ▼
┌─────────────┐
│ Input modal │──── User types description
└─────────────┘
      │
      ▼
┌─────────────┐
│ Create task │──── Write to tasks.md (status: [])
└─────────────┘
      │
      ▼
┌─────────────┐
│ Spawn agent │──── subprocess.Popen(claude...)
└─────────────┘          │
      │                  ▼
      │         ┌─────────────────────┐
      │         │ Claude Code runs    │
      │         │ Writes to agents/   │
      │         └─────────────────────┘
      │                  │
      ▼                  ▼
┌─────────────┐  ┌─────────────────────┐
│ Update UI   │◄─│ Log watcher detects │
│ task → 🟡   │  │ new file content    │
└─────────────┘  └─────────────────────┘
      │
      ▼
┌─────────────┐
│ Live logs   │──── Stream to log panel
│ appear      │
└─────────────┘
```

---

## 3. TUI Framework Decision

### 3.1 Options Evaluated

| Framework | Pros | Cons |
|-----------|------|------|
| **Textual** | Full widget system, async native, beautiful | Heavy dependency, learning curve |
| **Rich Live** | Already using Rich, simpler | Limited interactivity |
| **Urwid** | Mature, lightweight | Dated API, less pretty |
| **Blessed/curses** | Zero deps, full control | Low-level, lots of code |
| **Custom Rich** | Tailored exactly, minimal | More work upfront |

### 3.2 Decision: Textual

**Textual** is the right choice because:

1. **Async-native**: Built on asyncio, perfect for our event-driven model
2. **CSS-like styling**: Easy to make beautiful, themeable
3. **Widget composition**: Build complex layouts from simple parts
4. **Rich integration**: Uses Rich for rendering (we already depend on it)
5. **Active development**: Modern, well-maintained
6. **Terminal features**: Mouse support, scrolling, focus management

**Dependencies**:
```toml
dependencies = [
    "textual>=0.50.0",
    "rich>=13.0.0",  # Already have this
]
```

### 3.3 Textual Architecture

```python
# High-level structure
from textual.app import App
from textual.widgets import Header, Footer, DataTable, RichLog, Input

class ADWApp(App):
    """Main ADW dashboard application."""

    BINDINGS = [
        ("n", "new_task", "New Task"),
        ("q", "quit", "Quit"),
        ("tab", "focus_next", "Next Panel"),
        ("escape", "cancel", "Cancel"),
    ]

    def compose(self):
        yield Header()
        yield TaskList()      # Left panel
        yield TaskDetail()    # Right panel
        yield LogViewer()     # Bottom panel
        yield CommandInput()  # Input bar
        yield Footer()
```

---

## 4. Screen Layouts

### 4.1 Main Dashboard

```
┌─────────────────────────────────────────────────────────────────┐
│ ADW Dashboard                                    v0.2.0  [?]Help│
├─────────────────────────┬───────────────────────────────────────┤
│ TASKS                   │ SELECTED TASK                         │
│ ───────────────────     │ ─────────────────────────────────     │
│                         │                                       │
│ 🟡 abc123 OAuth login   │ ID: abc123                           │
│ 🟡 def456 Fix bug   ◄── │ Task: Add OAuth login with Google    │
│ ⏳ ghi789 Dark mode     │ Status: implementing (3/5)           │
│ ✅ jkl012 Add tests     │ Worktree: oauth-abc123               │
│ ❌ mno345 Refactor      │ Model: opus                          │
│                         │ Duration: 4m 23s                      │
│                         │                                       │
│ [5 tasks, 2 active]     │ Files: 6 modified, 2 created         │
│                         │                                       │
├─────────────────────────┴───────────────────────────────────────┤
│ LOGS: abc123 - Add OAuth login                          [Clear] │
│ ─────────────────────────────────────────────────────────────── │
│ 14:23:45 │ Reading src/auth/config.ts                          │
│ 14:23:46 │ Planning OAuth flow implementation                  │
│ 14:23:48 │ Creating src/auth/providers/google.ts               │
│ 14:23:52 │ Writing OAuth callback handler                      │
│ 14:23:55 │ Adding environment variables to .env.example        │
│ 14:23:58 │ Running type checker...                             │▼
├─────────────────────────────────────────────────────────────────┤
│ > Send to agent: _                                              │
├─────────────────────────────────────────────────────────────────┤
│ [n]ew  [d]etail  [l]ogs  [k]ill  [Tab]switch  [q]uit           │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 New Task Modal

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│                                                                 │
│    ┌─────────────────────────────────────────────────────┐     │
│    │              NEW TASK                          [x]  │     │
│    ├─────────────────────────────────────────────────────┤     │
│    │                                                     │     │
│    │  Description:                                       │     │
│    │  ┌─────────────────────────────────────────────┐   │     │
│    │  │ Add user authentication with OAuth         _│   │     │
│    │  └─────────────────────────────────────────────┘   │     │
│    │                                                     │     │
│    │  Workflow:  ○ Auto  ● Standard  ○ Full SDLC        │     │
│    │                                                     │     │
│    │  Model:     ● Auto  ○ Sonnet  ○ Opus               │     │
│    │                                                     │     │
│    │  Tags:      {prototype:vite_vue} (optional)        │     │
│    │                                                     │     │
│    │          [Cancel]              [Start Task]         │     │
│    │                                                     │     │
│    └─────────────────────────────────────────────────────┘     │
│                                                                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 4.3 Task Detail View (Expanded)

```
┌─────────────────────────────────────────────────────────────────┐
│ TASK: abc123 - Add OAuth login                          [Back] │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  STATUS          PROGRESS                                       │
│  ─────────       ────────────────────────────────               │
│  🟡 In Progress  [████████░░░░░░░░] 3/5 phases                  │
│                                                                 │
│  PHASES                                                         │
│  ──────                                                         │
│  ✅ Plan      → specs/plan-abc123-oauth.md                     │
│  ✅ Implement → 6 files changed                                │
│  🟡 Test      → Running pytest...                              │
│  ⏳ Review    → Waiting                                         │
│  ⏳ Document  → Waiting                                         │
│                                                                 │
│  FILES CHANGED                                                  │
│  ─────────────                                                  │
│  M src/auth/oauth.ts                                           │
│  M src/auth/config.ts                                          │
│  A src/auth/providers/google.ts                                │
│  A src/auth/providers/github.ts                                │
│  M src/routes/callback.ts                                      │
│  M .env.example                                                │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│ LIVE OUTPUT                                                     │
│ ─────────────────────────────────────────────────────────────── │
│ Running: pytest tests/auth/                                     │
│ tests/auth/test_oauth.py::test_google_flow PASSED              │
│ tests/auth/test_oauth.py::test_github_flow PASSED              │
│ tests/auth/test_oauth.py::test_token_refresh RUNNING...        │
├─────────────────────────────────────────────────────────────────┤
│ > _                                                             │
├─────────────────────────────────────────────────────────────────┤
│ [m]essage  [k]ill  [r]etry  [Back]                              │
└─────────────────────────────────────────────────────────────────┘
```

### 4.4 Layout Modes

**Compact Mode** (small terminals):
```
┌────────────────────────────────────┐
│ ADW                       2 active │
├────────────────────────────────────┤
│ 🟡 abc123 OAuth      implementing │
│ 🟡 def456 Bug fix    testing      │
│ ⏳ ghi789 Dark mode  queued       │
├────────────────────────────────────┤
│ > abc123: Running tests...        │
├────────────────────────────────────┤
│ [n]ew [Enter]select [q]uit        │
└────────────────────────────────────┘
```

**Wide Mode** (large terminals):
```
┌─────────────────┬─────────────────────┬─────────────────────────┐
│ TASKS           │ TASK DETAIL         │ LOGS                    │
│                 │                     │                         │
│ (list)          │ (selected task)     │ (live logs)             │
│                 │                     │                         │
└─────────────────┴─────────────────────┴─────────────────────────┘
```

---

## 5. Agent Communication Protocol

### 5.1 Overview

Agents communicate with the TUI through:
1. **File system** (primary): Structured output files
2. **Stdout/stderr** (captured): Process output
3. **Message files** (bidirectional): User → Agent messages

### 5.2 Output Directory Structure

```
agents/{adw_id}/
├── adw_state.json           # State (read by TUI)
├── adw_messages.jsonl       # Messages TO agent (written by TUI)
├── adw_events.jsonl         # Events FROM agent (written by hooks)
│
├── {phase}-{adw_id}/
│   ├── cc_raw_output.jsonl  # Claude Code stream
│   ├── cc_events.jsonl      # Parsed events for TUI
│   └── cc_final_result.txt  # Final output
│
└── workflow_summary.json    # Completion summary
```

### 5.3 Event Types

**File**: `src/adw/protocol/events.py`

```python
from enum import Enum
from pydantic import BaseModel
from datetime import datetime


class EventType(str, Enum):
    # Lifecycle events
    AGENT_STARTED = "agent_started"
    AGENT_COMPLETED = "agent_completed"
    AGENT_FAILED = "agent_failed"

    # Phase events
    PHASE_STARTED = "phase_started"
    PHASE_COMPLETED = "phase_completed"
    PHASE_FAILED = "phase_failed"

    # Tool events
    TOOL_STARTED = "tool_started"
    TOOL_COMPLETED = "tool_completed"

    # File events
    FILE_READ = "file_read"
    FILE_WRITTEN = "file_written"
    FILE_EDITED = "file_edited"

    # User interaction
    MESSAGE_RECEIVED = "message_received"
    QUESTION_ASKED = "question_asked"

    # Progress
    PROGRESS_UPDATE = "progress_update"
    LOG_MESSAGE = "log_message"


class AgentEvent(BaseModel):
    """Event emitted by an agent for TUI consumption."""

    timestamp: datetime
    adw_id: str
    event_type: EventType
    phase: str | None = None

    # Event-specific data
    tool_name: str | None = None
    file_path: str | None = None
    message: str | None = None
    progress: float | None = None  # 0.0 - 1.0

    # For errors
    error: str | None = None
    recoverable: bool = True


class AgentMessage(BaseModel):
    """Message from TUI to agent."""

    timestamp: datetime
    message: str
    priority: str = "normal"  # normal, high, interrupt
```

### 5.4 Event Flow

```
Claude Code Process
        │
        ▼
┌───────────────┐
│  ADW Hooks    │──── Write events to adw_events.jsonl
└───────────────┘
        │
        ▼
┌───────────────┐
│  Log Watcher  │──── inotify/fsevents detects changes
└───────────────┘
        │
        ▼
┌───────────────┐
│  Event Bus    │──── Parse, validate, route events
└───────────────┘
        │
        ├────────────────┐
        ▼                ▼
┌───────────────┐ ┌───────────────┐
│  State Update │ │  UI Update    │
│  (reactive)   │ │  (render)     │
└───────────────┘ └───────────────┘
```

---

## 6. Live Log Streaming

### 6.1 Architecture

```python
from watchfiles import awatch
import asyncio


class LogWatcher:
    """Watch agent output files and stream to TUI."""

    def __init__(self, agents_dir: Path):
        self.agents_dir = agents_dir
        self.subscribers: dict[str, list[Callable]] = {}  # adw_id -> callbacks

    async def watch(self):
        """Main watch loop using watchfiles."""
        async for changes in awatch(self.agents_dir):
            for change_type, path in changes:
                await self._handle_change(change_type, Path(path))

    async def _handle_change(self, change_type: str, path: Path):
        """Handle a file change event."""
        # Extract ADW ID from path
        # agents/{adw_id}/...
        parts = path.relative_to(self.agents_dir).parts
        if len(parts) < 1:
            return

        adw_id = parts[0]

        # Handle different file types
        if path.name == "adw_events.jsonl":
            await self._handle_events_file(adw_id, path)
        elif path.name == "cc_raw_output.jsonl":
            await self._handle_raw_output(adw_id, path)

    async def _handle_events_file(self, adw_id: str, path: Path):
        """Process new events from adw_events.jsonl."""
        # Read new lines (tail -f behavior)
        # Parse as AgentEvent
        # Notify subscribers
        pass

    def subscribe(self, adw_id: str, callback: Callable):
        """Subscribe to events for a specific ADW ID."""
        if adw_id not in self.subscribers:
            self.subscribers[adw_id] = []
        self.subscribers[adw_id].append(callback)
```

### 6.2 Log Display Formatting

```python
from rich.text import Text
from datetime import datetime


class LogFormatter:
    """Format log events for TUI display."""

    ICONS = {
        EventType.FILE_READ: "📖",
        EventType.FILE_WRITTEN: "📝",
        EventType.FILE_EDITED: "✏️",
        EventType.TOOL_STARTED: "🔧",
        EventType.TOOL_COMPLETED: "✅",
        EventType.PHASE_STARTED: "▶️",
        EventType.PHASE_COMPLETED: "✓",
        EventType.LOG_MESSAGE: "│",
        EventType.AGENT_FAILED: "❌",
    }

    def format_event(self, event: AgentEvent) -> Text:
        """Format an event for display."""
        icon = self.ICONS.get(event.event_type, "•")
        time = event.timestamp.strftime("%H:%M:%S")

        text = Text()
        text.append(f"{time} ", style="dim")
        text.append(f"{icon} ", style="bold")

        if event.event_type == EventType.FILE_READ:
            text.append(f"Reading ", style="cyan")
            text.append(event.file_path, style="white")
        elif event.event_type == EventType.FILE_WRITTEN:
            text.append(f"Creating ", style="green")
            text.append(event.file_path, style="white")
        elif event.event_type == EventType.PHASE_STARTED:
            text.append(f"Starting phase: ", style="yellow")
            text.append(event.phase, style="bold yellow")
        elif event.message:
            text.append(event.message)

        return text
```

### 6.3 Buffering Strategy

```python
from collections import deque


class LogBuffer:
    """Buffer logs with automatic pruning."""

    def __init__(self, max_lines: int = 1000):
        self.max_lines = max_lines
        self.buffers: dict[str, deque] = {}  # adw_id -> lines

    def add(self, adw_id: str, line: Text):
        """Add a line to the buffer."""
        if adw_id not in self.buffers:
            self.buffers[adw_id] = deque(maxlen=self.max_lines)
        self.buffers[adw_id].append(line)

    def get_recent(self, adw_id: str, count: int = 50) -> list[Text]:
        """Get recent lines for display."""
        if adw_id not in self.buffers:
            return []
        return list(self.buffers[adw_id])[-count:]

    def clear(self, adw_id: str):
        """Clear buffer for an ADW ID."""
        if adw_id in self.buffers:
            self.buffers[adw_id].clear()
```

---

## 7. Message Injection

### 7.1 Concept

Users can send messages to running agents. These messages are:
1. Written to `agents/{adw_id}/adw_messages.jsonl`
2. Picked up by a Claude Code hook
3. Injected into the agent's context

### 7.2 Message File Format

```jsonl
{"timestamp": "2024-01-15T14:30:00", "message": "Use the existing AuthContext", "priority": "normal"}
{"timestamp": "2024-01-15T14:32:00", "message": "STOP - wait for my review", "priority": "interrupt"}
```

### 7.3 Hook for Message Injection

**File**: `.claude/hooks/check_messages.py`

```python
#!/usr/bin/env uv run
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Check for and surface user messages to agent."""

import json
import os
import sys
from pathlib import Path


def main():
    # Get ADW ID from environment (set by ADW when spawning)
    adw_id = os.environ.get("ADW_ID")
    if not adw_id:
        sys.exit(0)

    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
    messages_file = Path(project_dir) / "agents" / adw_id / "adw_messages.jsonl"
    processed_file = Path(project_dir) / "agents" / adw_id / "adw_messages_processed.jsonl"

    if not messages_file.exists():
        sys.exit(0)

    # Read all messages
    messages = []
    for line in messages_file.read_text().strip().split("\n"):
        if line:
            messages.append(json.loads(line))

    # Read processed messages
    processed = set()
    if processed_file.exists():
        for line in processed_file.read_text().strip().split("\n"):
            if line:
                processed.add(line)

    # Find new messages
    new_messages = []
    for msg in messages:
        msg_key = json.dumps(msg, sort_keys=True)
        if msg_key not in processed:
            new_messages.append(msg)
            # Mark as processed
            with open(processed_file, "a") as f:
                f.write(msg_key + "\n")

    if new_messages:
        # Output message for Claude to see
        print("\n" + "="*60)
        print("📨 MESSAGE FROM USER:")
        for msg in new_messages:
            print(f"  {msg['message']}")
        print("="*60 + "\n")

        # If interrupt priority, suggest stopping
        if any(m.get("priority") == "interrupt" for m in new_messages):
            print("⚠️  HIGH PRIORITY - Please address this before continuing.\n")

    sys.exit(0)


if __name__ == "__main__":
    main()
```

### 7.4 TUI Message Input

```python
from textual.widgets import Input
from textual.message import Message


class MessageInput(Input):
    """Input widget for sending messages to agents."""

    class MessageSubmitted(Message):
        """Message submitted to agent."""
        def __init__(self, adw_id: str, message: str):
            self.adw_id = adw_id
            self.message = message
            super().__init__()

    def __init__(self, adw_id: str):
        super().__init__(placeholder="Send message to agent...")
        self.adw_id = adw_id

    async def on_input_submitted(self, event: Input.Submitted):
        """Handle message submission."""
        if event.value.strip():
            # Write to messages file
            await self._write_message(event.value.strip())
            # Clear input
            self.value = ""
            # Notify parent
            self.post_message(self.MessageSubmitted(self.adw_id, event.value))

    async def _write_message(self, message: str):
        """Write message to agent's message file."""
        import json
        from datetime import datetime
        from pathlib import Path

        messages_file = Path("agents") / self.adw_id / "adw_messages.jsonl"
        messages_file.parent.mkdir(parents=True, exist_ok=True)

        entry = {
            "timestamp": datetime.now().isoformat(),
            "message": message,
            "priority": "high" if message.upper().startswith("STOP") else "normal",
        }

        with open(messages_file, "a") as f:
            f.write(json.dumps(entry) + "\n")
```

---

## 8. Interaction Model

### 8.1 Keyboard Shortcuts

**Global**:
| Key | Action |
|-----|--------|
| `n` | New task |
| `q` | Quit (with confirmation if tasks running) |
| `?` | Help |
| `Tab` | Cycle focus between panels |
| `Shift+Tab` | Cycle focus backwards |
| `Escape` | Cancel / Close modal |

**Task List**:
| Key | Action |
|-----|--------|
| `↑/↓` or `j/k` | Navigate tasks |
| `Enter` | Select task (show details) |
| `d` | Delete task (with confirmation) |
| `r` | Retry failed task |
| `k` | Kill running task |

**Log Panel**:
| Key | Action |
|-----|--------|
| `↑/↓` | Scroll logs |
| `g` | Go to top |
| `G` | Go to bottom (follow mode) |
| `c` | Clear logs |
| `/` | Search logs |

**Input**:
| Key | Action |
|-----|--------|
| `Enter` | Send message |
| `Ctrl+C` | Clear input |
| `↑` | Previous message (history) |

### 8.2 Mouse Support

- Click task to select
- Click panel to focus
- Scroll wheel in log panel
- Click buttons in modals

### 8.3 Command Palette

Press `:` or `Ctrl+P` for command palette:

```
┌─────────────────────────────────────┐
│ > _                                 │
├─────────────────────────────────────┤
│ new         Create new task         │
│ kill        Kill selected task      │
│ kill-all    Kill all running tasks  │
│ retry       Retry failed task       │
│ clear       Clear log buffer        │
│ theme       Change color theme      │
│ config      Open configuration      │
│ quit        Exit ADW                │
└─────────────────────────────────────┘
```

---

## 9. State Synchronization

### 9.1 Reactive State Model

```python
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class TaskState:
    """State for a single task."""
    adw_id: str
    description: str
    status: str
    phase: str | None = None
    progress: float = 0.0
    worktree: str | None = None
    pid: int | None = None
    started_at: str | None = None

    # Computed
    @property
    def is_running(self) -> bool:
        return self.status == "in_progress"


@dataclass
class AppState:
    """Global application state."""
    tasks: dict[str, TaskState] = field(default_factory=dict)
    selected_task: str | None = None
    focused_panel: str = "tasks"

    _subscribers: list[Callable] = field(default_factory=list, repr=False)

    def subscribe(self, callback: Callable):
        """Subscribe to state changes."""
        self._subscribers.append(callback)

    def notify(self):
        """Notify all subscribers of state change."""
        for callback in self._subscribers:
            callback(self)

    def update_task(self, adw_id: str, **updates):
        """Update a task and notify."""
        if adw_id in self.tasks:
            for key, value in updates.items():
                setattr(self.tasks[adw_id], key, value)
            self.notify()

    def add_task(self, task: TaskState):
        """Add a new task."""
        self.tasks[task.adw_id] = task
        self.notify()

    def remove_task(self, adw_id: str):
        """Remove a task."""
        if adw_id in self.tasks:
            del self.tasks[adw_id]
            if self.selected_task == adw_id:
                self.selected_task = None
            self.notify()
```

### 9.2 File → State Synchronization

```python
class StateManager:
    """Synchronize file system state with app state."""

    def __init__(self, state: AppState):
        self.state = state
        self.tasks_file = Path("tasks.md")

    async def sync_from_files(self):
        """Initial sync from files."""
        # Parse tasks.md
        tasks = parse_tasks_md(self.tasks_file.read_text())

        for worktree in tasks:
            for task in worktree.tasks:
                if task.adw_id:
                    # Load additional state from adw_state.json
                    state_file = Path("agents") / task.adw_id / "adw_state.json"
                    extra = {}
                    if state_file.exists():
                        extra = json.loads(state_file.read_text())

                    self.state.add_task(TaskState(
                        adw_id=task.adw_id,
                        description=task.description,
                        status=task.status.value,
                        phase=extra.get("current_phase"),
                        worktree=task.worktree_name,
                    ))

    async def watch_tasks_file(self):
        """Watch tasks.md for external changes."""
        async for changes in awatch(self.tasks_file.parent):
            for _, path in changes:
                if Path(path).name == "tasks.md":
                    await self.sync_from_files()
```

---

## 10. Implementation Details

### 10.1 Main Application

**File**: `src/adw/tui/app.py`

```python
"""Main ADW TUI application."""

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Header, Footer, Static
from textual.binding import Binding

from .widgets.task_list import TaskList
from .widgets.task_detail import TaskDetail
from .widgets.log_viewer import LogViewer
from .widgets.message_input import MessageInput
from .state import AppState, StateManager
from .log_watcher import LogWatcher


class ADWApp(App):
    """ADW Dashboard Application."""

    CSS_PATH = "styles.tcss"
    TITLE = "ADW Dashboard"

    BINDINGS = [
        Binding("n", "new_task", "New Task"),
        Binding("q", "quit", "Quit"),
        Binding("?", "help", "Help"),
        Binding("tab", "focus_next", "Next"),
        Binding("shift+tab", "focus_previous", "Previous"),
        Binding("escape", "cancel", "Cancel"),
        Binding(":", "command_palette", "Commands"),
    ]

    def __init__(self):
        super().__init__()
        self.state = AppState()
        self.state_manager = StateManager(self.state)
        self.log_watcher = LogWatcher(Path("agents"))

        # Subscribe to state changes
        self.state.subscribe(self._on_state_change)

    def compose(self) -> ComposeResult:
        """Create UI layout."""
        yield Header()

        with Horizontal(id="main"):
            # Left panel: Task list
            with Vertical(id="left-panel"):
                yield Static("TASKS", classes="panel-title")
                yield TaskList(id="task-list")

            # Right panel: Task detail
            with Vertical(id="right-panel"):
                yield Static("SELECTED TASK", classes="panel-title")
                yield TaskDetail(id="task-detail")

        # Bottom: Log viewer
        with Vertical(id="bottom-panel"):
            yield Static("LOGS", classes="panel-title")
            yield LogViewer(id="log-viewer")

        # Input bar
        yield MessageInput(id="message-input")

        yield Footer()

    async def on_mount(self):
        """Initialize on mount."""
        # Sync initial state
        await self.state_manager.sync_from_files()

        # Start background watchers
        self.run_worker(self.log_watcher.watch())
        self.run_worker(self.state_manager.watch_tasks_file())

    def _on_state_change(self, state: AppState):
        """Handle state changes."""
        # Update task list
        task_list = self.query_one("#task-list", TaskList)
        task_list.update_tasks(state.tasks)

        # Update detail view
        if state.selected_task:
            task_detail = self.query_one("#task-detail", TaskDetail)
            task_detail.update_task(state.tasks.get(state.selected_task))

    async def action_new_task(self):
        """Show new task modal."""
        from .modals.new_task import NewTaskModal
        result = await self.push_screen(NewTaskModal())
        if result:
            await self._create_task(result)

    async def _create_task(self, task_info: dict):
        """Create and start a new task."""
        from ..agent.executor import generate_adw_id
        from ..workflows.standard import run_standard_workflow
        import subprocess
        import sys

        adw_id = generate_adw_id()

        # Add to state immediately
        self.state.add_task(TaskState(
            adw_id=adw_id,
            description=task_info["description"],
            status="pending",
        ))

        # Spawn workflow in background
        cmd = [
            sys.executable, "-m", "adw.workflows.standard",
            "--adw-id", adw_id,
            "--worktree-name", f"task-{adw_id}",
            "--task", task_info["description"],
        ]

        process = subprocess.Popen(
            cmd,
            start_new_session=True,
            env={**os.environ, "ADW_ID": adw_id},
        )

        # Update state with PID
        self.state.update_task(adw_id, status="in_progress", pid=process.pid)

    async def action_quit(self):
        """Quit with confirmation if tasks running."""
        running = [t for t in self.state.tasks.values() if t.is_running]

        if running:
            from .modals.confirm import ConfirmModal
            confirmed = await self.push_screen(
                ConfirmModal(f"{len(running)} task(s) still running. Quit anyway?")
            )
            if not confirmed:
                return

        self.exit()
```

### 10.2 Stylesheet

**File**: `src/adw/tui/styles.tcss`

```css
/* ADW TUI Styles */

Screen {
    background: $surface;
}

Header {
    dock: top;
    background: $primary;
}

Footer {
    dock: bottom;
    background: $primary;
}

#main {
    height: 60%;
}

#left-panel {
    width: 40%;
    border: solid $primary;
    padding: 1;
}

#right-panel {
    width: 60%;
    border: solid $primary;
    padding: 1;
}

#bottom-panel {
    height: 35%;
    border: solid $primary;
    padding: 1;
}

.panel-title {
    text-style: bold;
    color: $primary;
    padding-bottom: 1;
}

#message-input {
    dock: bottom;
    height: 3;
    border: solid $secondary;
    padding: 0 1;
}

/* Task list styles */
.task-item {
    height: 1;
    padding: 0 1;
}

.task-item:hover {
    background: $primary 20%;
}

.task-item.selected {
    background: $primary 40%;
}

.task-status-running {
    color: $warning;
}

.task-status-done {
    color: $success;
}

.task-status-failed {
    color: $error;
}

/* Log viewer */
LogViewer {
    scrollbar-gutter: stable;
}

.log-timestamp {
    color: $text-muted;
}

.log-icon {
    width: 3;
}
```

### 10.3 Task List Widget

**File**: `src/adw/tui/widgets/task_list.py`

```python
"""Task list widget."""

from textual.widgets import ListItem, ListView
from textual.message import Message
from rich.text import Text

from ..state import TaskState


class TaskList(ListView):
    """List of tasks with status indicators."""

    class TaskSelected(Message):
        """Task was selected."""
        def __init__(self, adw_id: str):
            self.adw_id = adw_id
            super().__init__()

    STATUS_ICONS = {
        "pending": "⏳",
        "in_progress": "🟡",
        "done": "✅",
        "failed": "❌",
        "blocked": "⏰",
    }

    def update_tasks(self, tasks: dict[str, TaskState]):
        """Update the task list."""
        self.clear()

        for task in sorted(tasks.values(), key=lambda t: t.started_at or "", reverse=True):
            icon = self.STATUS_ICONS.get(task.status, "•")

            text = Text()
            text.append(f"{icon} ", style="bold")
            text.append(f"{task.adw_id[:8]} ", style="dim")
            text.append(task.description[:30])

            if task.phase:
                text.append(f" ({task.phase})", style="italic dim")

            item = ListItem(Static(text), id=f"task-{task.adw_id}")
            item.adw_id = task.adw_id
            self.append(item)

    def on_list_view_selected(self, event: ListView.Selected):
        """Handle task selection."""
        if hasattr(event.item, "adw_id"):
            self.post_message(self.TaskSelected(event.item.adw_id))
```

### 10.4 Entry Point Update

**File**: `src/adw/cli.py` (updated)

```python
@main.command()
def dashboard():
    """Open the interactive TUI dashboard."""
    from .tui.app import ADWApp
    app = ADWApp()
    app.run()


# Update default command
@click.group(invoke_without_command=True)
@click.option("--version", "-v", is_flag=True, help="Show version")
@click.pass_context
def main(ctx: click.Context, version: bool) -> None:
    """ADW - AI Developer Workflow CLI."""
    if version:
        console.print(f"adw version {__version__}")
        return

    if ctx.invoked_subcommand is None:
        # Default: run TUI dashboard
        from .tui.app import ADWApp
        app = ADWApp()
        app.run()
```

---

## Summary

This UX/Architecture specification defines:

1. **Design Philosophy**: User stays in control, Claude runs in background
2. **System Architecture**: TUI layer, event bus, agent manager, log watcher
3. **Framework**: Textual for async, widget-based TUI
4. **Layouts**: Dashboard, modals, responsive modes
5. **Communication**: File-based events, message injection via hooks
6. **Log Streaming**: watchfiles + JSONL parsing + buffered display
7. **Interaction**: Keyboard-first with mouse support
8. **State Management**: Reactive state synced from filesystem

The implementation uses:
- **Textual** for the TUI framework
- **watchfiles** for file system watching
- **Pydantic** for event models
- **asyncio** for non-blocking operations

This creates a cohesive experience where users manage their AI development workflows without ever leaving the ADW interface.
