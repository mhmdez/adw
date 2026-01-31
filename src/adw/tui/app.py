"""Main ADW TUI application - Claude Code style interface."""

from __future__ import annotations

from pathlib import Path
from datetime import datetime

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical, Horizontal
from textual.widgets import Static, Input, RichLog
from rich.text import Text

from .commands import execute_command, TUI_COMMANDS
from .state import AppState
from .log_watcher import LogWatcher, LogEvent
from ..agent.manager import AgentManager
from ..agent.task_updater import mark_in_progress
from ..agent.utils import generate_adw_id
from ..protocol.messages import write_message, MessagePriority
from .. import __version__


# ASCII Logo
LOGO = """[bold cyan]
 █▀█ █▀▄ █ █ █  [/bold cyan][white]ADW[/white] [dim]v{version}[/dim]
[dim]AI Developer Workflow[/dim]
"""


class ADWApp(App):
    """ADW - Claude Code style chat interface."""

    CSS = """
    Screen {
        background: $surface;
    }

    #header {
        dock: top;
        height: 4;
        padding: 0 2;
        background: $primary 10%;
    }

    #chat-container {
        height: 1fr;
        padding: 0 2;
    }

    #chat-log {
        height: 1fr;
        scrollbar-gutter: stable;
    }

    #input-container {
        dock: bottom;
        height: 3;
        padding: 0 2;
        background: $surface;
    }

    #prompt-symbol {
        width: 3;
        padding: 1 0;
        color: $success;
    }

    #user-input {
        width: 1fr;
    }

    #user-input:focus {
        border: none;
    }
    """

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", show=False),
        Binding("ctrl+l", "clear", "Clear", show=False),
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(self):
        super().__init__()
        self.state = AppState()
        self.agent_manager = AgentManager()
        self.log_watcher = LogWatcher()
        self._new_task_mode = False

        self.state.subscribe(self._on_state_change)
        self.agent_manager.subscribe(self._on_agent_event)
        self.log_watcher.subscribe_all(self._on_log_event)

    def compose(self) -> ComposeResult:
        """Create the UI layout."""
        # Header with logo
        yield Static(LOGO.format(version=__version__), id="header")

        # Main chat area
        with Container(id="chat-container"):
            yield RichLog(id="chat-log", highlight=True, markup=True)

        # Input area
        with Horizontal(id="input-container"):
            yield Static(">", id="prompt-symbol")
            yield Input(placeholder="Type a message or /command...", id="user-input")

    async def on_mount(self) -> None:
        """Initialize on mount."""
        self.state.load_from_tasks_md()
        self.set_interval(2.0, self._poll_agents)
        self.run_worker(self.log_watcher.watch())

        # Welcome message
        self._log_system("Welcome to ADW - AI Developer Workflow")
        self._log_system("Type [bold]/help[/bold] for available commands")
        self._log_system("")

        # Show current tasks
        self._show_tasks()

        # Focus input
        self.query_one("#user-input", Input).focus()

    def _log_system(self, message: str) -> None:
        """Log a system message."""
        log = self.query_one("#chat-log", RichLog)
        log.write(Text.from_markup(f"[dim]{message}[/dim]"))

    def _log_user(self, message: str) -> None:
        """Log a user message."""
        log = self.query_one("#chat-log", RichLog)
        log.write(Text.from_markup(f"[bold green]>[/bold green] {message}"))

    def _log_response(self, message: str) -> None:
        """Log a response message."""
        log = self.query_one("#chat-log", RichLog)
        log.write(Text.from_markup(message))

    def _log_error(self, message: str) -> None:
        """Log an error message."""
        log = self.query_one("#chat-log", RichLog)
        log.write(Text.from_markup(f"[bold red]Error:[/bold red] {message}"))

    def _show_tasks(self) -> None:
        """Show current tasks."""
        if not self.state.tasks:
            self._log_system("No tasks. Create one with [bold]/new <description>[/bold]")
            return

        self._log_system(f"[bold]Tasks ({len(self.state.tasks)}):[/bold]")
        for key, task in self.state.tasks.items():
            status_icon = {
                "pending": "⏳",
                "in_progress": "🟡",
                "done": "✅",
                "blocked": "⏰",
                "failed": "❌",
            }.get(task.status.value, "○")
            self._log_system(f"  {status_icon} [{task.display_id}] {task.description[:50]}")

    def _on_state_change(self, state: AppState) -> None:
        """Handle state changes."""
        pass  # We update UI reactively via commands

    def _on_agent_event(self, event: str, adw_id: str, data: dict) -> None:
        """Handle agent events."""
        if event == "spawned":
            self._log_response(f"[cyan]Agent {adw_id[:8]} started[/cyan]")
        elif event == "completed":
            self._log_response(f"[green]Agent {adw_id[:8]} completed[/green]")
            self.state.load_from_tasks_md()
        elif event == "failed":
            self._log_error(f"Agent {adw_id[:8]} failed")
            self.state.load_from_tasks_md()

    def _on_log_event(self, event: LogEvent) -> None:
        """Handle log event from agents."""
        icon = {
            "assistant": "💬",
            "tool": "🔧",
            "tool_result": "✓",
            "result": "✅",
            "error": "❌",
        }.get(event.event_type, "•")

        msg = event.message[:80] if event.message else ""
        self._log_response(f"[dim]{icon} [{event.adw_id[:8]}] {msg}[/dim]")

    def _poll_agents(self) -> None:
        """Poll for agent completion."""
        completed = self.agent_manager.poll()
        if completed:
            self.state.load_from_tasks_md()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission."""
        if event.input.id != "user-input":
            return

        message = event.value.strip()
        if not message:
            return

        event.input.value = ""
        self._log_user(message)

        # Handle slash commands
        if message.startswith("/"):
            self._handle_command(message)
            return

        # Otherwise treat as new task
        self._log_response("Creating task and spawning agent...")
        self._spawn_task(message)

    def _handle_command(self, text: str) -> None:
        """Handle a slash command."""
        parts = text[1:].split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        if cmd == "help":
            self._show_help()
        elif cmd == "init":
            self._run_init()
        elif cmd == "tasks" or cmd == "list":
            self.state.load_from_tasks_md()
            self._show_tasks()
        elif cmd == "new":
            if args:
                self._spawn_task(args)
            else:
                self._log_error("Usage: /new <task description>")
        elif cmd == "status":
            self._show_status()
        elif cmd == "clear":
            self.query_one("#chat-log", RichLog).clear()
        elif cmd == "version":
            self._log_response(f"ADW version {__version__}")
        elif cmd == "update":
            self._run_update()
        elif cmd == "quit" or cmd == "exit":
            self.exit()
        else:
            self._log_error(f"Unknown command: /{cmd}. Type /help for commands.")

    def _show_help(self) -> None:
        """Show help message."""
        self._log_response("[bold]Commands:[/bold]")
        self._log_response("  /init        - Initialize ADW in current project")
        self._log_response("  /new <desc>  - Create task and spawn agent")
        self._log_response("  /tasks       - List all tasks")
        self._log_response("  /status      - Show system status")
        self._log_response("  /clear       - Clear screen")
        self._log_response("  /version     - Show version")
        self._log_response("  /update      - Check for updates")
        self._log_response("  /quit        - Exit ADW")
        self._log_response("")
        self._log_response("[dim]Or just type a task description to create and run it[/dim]")

    def _show_status(self) -> None:
        """Show status."""
        total = len(self.state.tasks)
        running = self.state.running_count
        self._log_response(f"[bold]Status:[/bold]")
        self._log_response(f"  Tasks: {total} total, {running} running")
        self._log_response(f"  Version: {__version__}")

    def _run_update(self) -> None:
        """Check for updates."""
        from ..update import check_for_update

        self._log_response("Checking for updates...")
        current, latest = check_for_update()

        if latest is None:
            self._log_error("Could not check for updates")
            return

        if latest <= current:
            self._log_response(f"Already at latest version ({current})")
        else:
            self._log_response(f"Update available: {current} → {latest}")
            self._log_response("Run: uv tool upgrade adw")

    def _run_init(self) -> None:
        """Initialize ADW in current project."""
        from ..init import init_project

        self._log_response("Initializing ADW in current project...")

        try:
            result = init_project(Path.cwd(), force=False)

            if result["created"]:
                self._log_response("[green]Created:[/green]")
                for path in result["created"]:
                    self._log_response(f"  + {path}")

            if result["updated"]:
                self._log_response("[cyan]Updated:[/cyan]")
                for path in result["updated"]:
                    self._log_response(f"  ~ {path}")

            if result["skipped"]:
                self._log_response("[dim]Skipped (already exist):[/dim]")
                for path in result["skipped"]:
                    self._log_response(f"  - {path}")

            self._log_response("")
            self._log_response("[green]ADW initialized![/green] Run /new <task> to get started.")

            # Reload tasks
            self.state.load_from_tasks_md()

        except Exception as e:
            self._log_error(f"Init failed: {e}")

    def _spawn_task(self, description: str) -> None:
        """Spawn a new task."""
        adw_id = generate_adw_id()
        tasks_file = Path("tasks.md")

        # Add task to tasks.md
        if tasks_file.exists():
            content = tasks_file.read_text()
        else:
            content = "# Tasks\n\n## Active Tasks\n\n"

        content = content.rstrip() + f"\n[🟡, {adw_id}] {description}\n"
        tasks_file.write_text(content)

        self._log_response(f"[cyan]Task {adw_id[:8]} created[/cyan]")

        # Spawn agent
        try:
            self.agent_manager.spawn_workflow(
                task_description=description,
                worktree_name=f"task-{adw_id}",
                workflow="standard",
                model="sonnet",
                adw_id=adw_id,
            )
            self._log_response(f"[cyan]Agent spawned for task {adw_id[:8]}[/cyan]")
        except Exception as e:
            self._log_error(f"Failed to spawn agent: {e}")

        self.state.load_from_tasks_md()

    def action_quit(self) -> None:
        """Quit the app."""
        self.exit()

    def action_clear(self) -> None:
        """Clear the log."""
        self.query_one("#chat-log", RichLog).clear()

    def action_cancel(self) -> None:
        """Cancel current input."""
        self.query_one("#user-input", Input).value = ""


def run_tui() -> None:
    """Run the TUI application."""
    app = ADWApp()
    app.run()
