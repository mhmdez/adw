"""Main ADW TUI application - Dashboard with task inbox and observability."""

from __future__ import annotations

import subprocess
import asyncio
from pathlib import Path
from datetime import datetime

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Static, Input, Footer, Header
from textual.reactive import reactive
from rich.text import Text

from .state import AppState, TaskState
from .log_watcher import LogWatcher, LogEvent
from .widgets.task_list import TaskList
from .widgets.log_viewer import LogViewer
from ..agent.manager import AgentManager
from ..agent.utils import generate_adw_id
from ..agent.models import TaskStatus
from .. import __version__


# Spinner frames
SPINNER = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]


class TaskInbox(Vertical):
    """Task inbox showing all tasks with live status."""

    DEFAULT_CSS = """
    TaskInbox {
        width: 100%;
        height: auto;
        max-height: 10;
        padding: 0 1;
    }

    TaskInbox > #inbox-header {
        height: 1;
        color: #888;
    }

    TaskInbox > #task-container {
        height: auto;
        max-height: 8;
    }

    .task-item {
        height: 1;
    }
    """

    spinner_frame = reactive(0)

    def __init__(self):
        super().__init__()
        self._tasks: dict[str, TaskState] = {}
        self._selected_key: str | None = None
        self._has_running = False

    def compose(self) -> ComposeResult:
        yield Static("TASKS", id="inbox-header")
        yield Container(id="task-container")

    def on_mount(self) -> None:
        self.set_interval(0.1, self._tick_spinner)

    def _tick_spinner(self) -> None:
        # Only update display if there are running tasks (need spinner animation)
        if self._has_running:
            self.spinner_frame = (self.spinner_frame + 1) % len(SPINNER)
            self._update_display()

    def update_tasks(self, tasks: dict[str, TaskState]) -> None:
        """Update the task list."""
        self._tasks = tasks
        self._has_running = any(t.status == TaskStatus.IN_PROGRESS for t in tasks.values())
        self._update_display()

    def select_task(self, key: str | None) -> None:
        """Select a task."""
        self._selected_key = key
        self._update_display()

    def _update_display(self) -> None:
        """Refresh the task display."""
        container = self.query_one("#task-container", Container)
        container.remove_children()

        if not self._tasks:
            container.mount(Static("[dim]No tasks yet. Use /new <task>[/dim]"))
            return

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

        for key, task in sorted(self._tasks.items(), key=sort_key):
            widget = self._make_task_widget(key, task)
            container.mount(widget)

    def _make_task_widget(self, key: str, task: TaskState) -> Static:
        """Create a widget for a single task."""
        text = Text()

        # Status icon with spinner for running
        if task.status == TaskStatus.IN_PROGRESS:
            icon = SPINNER[self.spinner_frame]
            text.append(f" {icon} ", style="bold cyan")
        elif task.status == TaskStatus.DONE:
            text.append(" ✓ ", style="bold green")
        elif task.status == TaskStatus.FAILED:
            text.append(" ✗ ", style="bold red")
        elif task.status == TaskStatus.BLOCKED:
            text.append(" ◷ ", style="bold yellow")
        else:
            text.append(" ○ ", style="dim")

        # Task ID
        text.append(f"{task.display_id} ", style="dim")

        # Description (truncated)
        desc = task.description[:25]
        if len(task.description) > 25:
            desc += "…"

        if task.status == TaskStatus.IN_PROGRESS:
            text.append(desc, style="cyan")
            # Show activity inline for running tasks
            if task.last_activity:
                text.append(f" - {task.last_activity[:20]}", style="dim italic")
        elif task.status == TaskStatus.DONE:
            text.append(desc, style="green")
        elif task.status == TaskStatus.FAILED:
            text.append(desc, style="red")
        else:
            text.append(desc)

        widget = Static(text, classes="task-item")
        if key == self._selected_key:
            widget.add_class("-selected")
        if task.is_running:
            widget.add_class("-running")

        return widget


class DetailPanel(Vertical):
    """Bottom panel showing logs and details for selected task."""

    DEFAULT_CSS = """
    DetailPanel {
        width: 100%;
        height: 1fr;
        padding: 0 1;
    }

    DetailPanel > #detail-header {
        display: none;
    }

    DetailPanel > #log-viewer {
        height: 1fr;
    }
    """

    def __init__(self):
        super().__init__()
        self._selected_task: TaskState | None = None

    def compose(self) -> ComposeResult:
        yield Static("LOGS", id="detail-header")
        yield LogViewer(id="log-viewer")

    def update_task(self, task: TaskState | None) -> None:
        """Update the selected task."""
        self._selected_task = task
        header = self.query_one("#detail-header", Static)
        log_viewer = self.query_one("#log-viewer", LogViewer)

        if task:
            header.update(f"LOGS - {task.display_id}")
            log_viewer.filter_by_agent(task.adw_id)
        else:
            header.update("LOGS")
            log_viewer.filter_by_agent(None)

    def add_log(self, event: LogEvent) -> None:
        """Add a log event."""
        log_viewer = self.query_one("#log-viewer", LogViewer)
        log_viewer.on_log_event(event)

    def add_message(self, message: str, style: str = "") -> None:
        """Add a simple message to the log."""
        log_viewer = self.query_one("#log-viewer", LogViewer)
        if style:
            log_viewer.write(Text(message, style=style))
        else:
            log_viewer.write(message)


class StatusLine(Horizontal):
    """Bottom status line with input."""

    DEFAULT_CSS = """
    StatusLine {
        dock: bottom;
        height: 1;
        padding: 0 1;
    }

    StatusLine > #prompt {
        width: 2;
        color: #4ec9b0;
    }

    StatusLine > Input {
        width: 1fr;
        border: none;
        padding: 0;
    }

    StatusLine > Input:focus {
        border: none;
    }

    StatusLine > #status-info {
        width: auto;
        color: #666;
    }
    """

    def __init__(self):
        super().__init__()
        self._running_count = 0

    def compose(self) -> ComposeResult:
        yield Static("❯", id="prompt")
        yield Input(placeholder="Type /help for commands", id="user-input")
        yield Static("", id="status-info")

    def update_status(self, running: int, total: int) -> None:
        """Update status display."""
        self._running_count = running
        info = self.query_one("#status-info", Static)
        if running > 0:
            info.update(f" {running}/{total} running ")
        else:
            info.update(f" {total} tasks ")


class ADWApp(App):
    """ADW - AI Developer Workflow Dashboard."""

    ENABLE_COMMAND_PALETTE = False
    DESIGN_SYSTEM = ""  # Disable design system for terminal-native look

    CSS = """
    * {
        scrollbar-size: 0 0;
    }

    Screen {
        background: ansi_default;
    }

    #main-header {
        dock: top;
        height: 1;
        padding: 0 1;
    }

    #main-container {
        height: 1fr;
    }

    Input {
        border: none;
        background: ansi_default;
    }

    Input:focus {
        border: none;
    }

    Static {
        background: ansi_default;
    }

    Container {
        background: ansi_default;
    }

    Vertical {
        background: ansi_default;
    }

    Horizontal {
        background: ansi_default;
    }

    RichLog {
        background: ansi_default;
    }
    """

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit"),
        Binding("ctrl+l", "clear_logs", "Clear"),
        Binding("n", "new_task", "New Task", show=False),
        Binding("r", "refresh", "Refresh", show=False),
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("?", "help", "Help", show=False),
        Binding("tab", "focus_next", "Next Panel", show=False),
    ]

    def __init__(self):
        super().__init__()
        self.state = AppState()
        self.agent_manager = AgentManager()
        self.log_watcher = LogWatcher()
        self._daemon_running = False

        self.state.subscribe(self._on_state_change)
        self.agent_manager.subscribe(self._on_agent_event)
        self.log_watcher.subscribe_all(self._on_log_event)

    def compose(self) -> ComposeResult:
        yield Static(f"[bold]ADW[/] [dim]v{__version__}[/]", id="main-header")

        with Vertical(id="main-container"):
            yield TaskInbox()
            yield DetailPanel()

        yield StatusLine()

    async def on_mount(self) -> None:
        """Initialize on mount."""
        self.state.load_from_tasks_md()
        self.set_interval(2.0, self._poll_agents)
        self.run_worker(self.log_watcher.watch())

        # Welcome message
        detail = self.query_one(DetailPanel)
        detail.add_message("Welcome to ADW - AI Developer Workflow", "bold cyan")
        detail.add_message("Type /help for commands, /new <task> to create a task", "dim")
        detail.add_message("")

        # Focus input
        self.query_one("#user-input", Input).focus()

        # Initial UI update
        self._update_ui()

    def _update_ui(self) -> None:
        """Update all UI components."""
        inbox = self.query_one(TaskInbox)
        inbox.update_tasks(self.state.tasks)
        inbox.select_task(self.state.selected_task_id)

        status = self.query_one(StatusLine)
        status.update_status(self.state.running_count, len(self.state.tasks))

    def _on_state_change(self, state: AppState) -> None:
        """Handle state changes."""
        self._update_ui()

    def _on_agent_event(self, event: str, adw_id: str, data: dict) -> None:
        """Handle agent events."""
        detail = self.query_one(DetailPanel)

        if event == "spawned":
            detail.add_message(f"[cyan]▶ Agent {adw_id[:8]} started[/cyan]")
            # Update task activity
            self.state.update_activity(adw_id, "Starting...")
        elif event == "completed":
            detail.add_message(f"[green]✓ Agent {adw_id[:8]} completed[/green]")
            self.state.load_from_tasks_md()
        elif event == "failed":
            return_code = data.get("return_code", "?")
            stderr = data.get("stderr", "")
            detail.add_message(f"[red]✗ Agent {adw_id[:8]} failed (exit {return_code})[/red]")
            if stderr:
                for line in stderr.strip().split("\n")[:5]:
                    detail.add_message(f"  {line}", "dim red")
            self.state.load_from_tasks_md()
        elif event == "killed":
            detail.add_message(f"[yellow]■ Agent {adw_id[:8]} killed[/yellow]")

    def _on_log_event(self, event: LogEvent) -> None:
        """Handle log event from agents."""
        detail = self.query_one(DetailPanel)
        detail.add_log(event)

        # Update task activity
        if event.message:
            self.state.update_activity(event.adw_id, event.message[:50])

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
        detail = self.query_one(DetailPanel)

        # Show user input
        detail.add_message(f"[bold]> {message}[/bold]")

        # Handle slash commands
        if message.startswith("/"):
            await self._handle_command(message)
            return

        # Detect question vs task
        question_starters = ("what", "how", "why", "where", "when", "who", "which",
                           "can", "could", "would", "is", "are", "do", "does",
                           "explain", "describe", "tell", "show")
        is_question = message.endswith("?") or message.lower().startswith(question_starters)

        if is_question:
            await self._ask_question(message)
        else:
            detail.add_message("[dim]Creating task...[/dim]")
            self._spawn_task(message)

    async def _handle_command(self, text: str) -> None:
        """Handle a slash command."""
        parts = text[1:].split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        detail = self.query_one(DetailPanel)

        if cmd == "help":
            self._show_help()
        elif cmd == "new" or cmd == "do" or cmd == "task":
            if args:
                self._spawn_task(args)
            else:
                detail.add_message("[red]Usage: /new <task description>[/red]")
        elif cmd == "ask":
            if args:
                await self._ask_question(args)
            else:
                detail.add_message("[red]Usage: /ask <question>[/red]")
        elif cmd == "tasks" or cmd == "list":
            self.state.load_from_tasks_md()
            detail.add_message(f"[cyan]Loaded {len(self.state.tasks)} tasks[/cyan]")
        elif cmd == "status":
            self._show_status()
        elif cmd == "clear":
            log_viewer = self.query_one("#log-viewer", LogViewer)
            log_viewer.clear_logs()
        elif cmd == "kill":
            self._kill_agent(args)
        elif cmd == "init":
            self._run_init()
        elif cmd == "doctor":
            self._run_doctor()
        elif cmd == "run":
            self._run_daemon()
        elif cmd == "stop":
            self._stop_daemon()
        elif cmd == "version":
            detail.add_message(f"ADW version {__version__}")
        elif cmd == "quit" or cmd == "exit":
            self.exit()
        else:
            detail.add_message(f"[yellow]Unknown command: /{cmd}[/yellow]")
            detail.add_message("[dim]Type /help for available commands[/dim]")

    def _show_help(self) -> None:
        """Show help."""
        detail = self.query_one(DetailPanel)
        help_text = """
[bold cyan]Commands:[/]

[bold]Tasks:[/]
  /new <desc>     Create and run a task
  /tasks          Refresh task list
  /kill [id]      Kill running agent

[bold]Chat:[/]
  /ask <question> Ask Claude a question
  Just type a question ending with ?

[bold]System:[/]
  /init           Initialize ADW in project
  /doctor         Check installation health
  /status         Show system status
  /run            Start autonomous daemon
  /stop           Stop daemon

[bold]Other:[/]
  /clear          Clear logs
  /version        Show version
  /quit           Exit

[bold]Keyboard:[/]
  n       New task
  r       Refresh
  Tab     Switch panels
  ?       This help
  Ctrl+C  Quit
"""
        for line in help_text.strip().split("\n"):
            detail.add_message(line)

    def _show_status(self) -> None:
        """Show status."""
        detail = self.query_one(DetailPanel)
        total = len(self.state.tasks)
        running = self.state.running_count
        pending = sum(1 for t in self.state.tasks.values() if t.status == TaskStatus.PENDING)
        done = sum(1 for t in self.state.tasks.values() if t.status == TaskStatus.DONE)
        failed = sum(1 for t in self.state.tasks.values() if t.status == TaskStatus.FAILED)

        detail.add_message(f"[bold]Status[/]")
        detail.add_message(f"  Version: {__version__}")
        detail.add_message(f"  Tasks: {total} total")
        detail.add_message(f"    ○ Pending: {pending}")
        detail.add_message(f"    ◉ Running: {running}")
        detail.add_message(f"    ✓ Done: {done}")
        if failed:
            detail.add_message(f"    ✗ Failed: {failed}")
        detail.add_message(f"  Daemon: {'[green]running[/]' if self._daemon_running else '[dim]stopped[/]'}")

    def _spawn_task(self, description: str) -> None:
        """Spawn a new task."""
        adw_id = generate_adw_id()
        tasks_file = Path("tasks.md")
        detail = self.query_one(DetailPanel)

        # Add task to tasks.md
        if tasks_file.exists():
            content = tasks_file.read_text()
        else:
            content = "# Tasks\n\n## Active Tasks\n\n"

        content = content.rstrip() + f"\n[🟡, {adw_id}] {description}\n"
        tasks_file.write_text(content)

        detail.add_message(f"[cyan]Task {adw_id[:8]} created[/cyan]")

        # Create agents directory
        agents_dir = Path("agents") / adw_id
        agents_dir.mkdir(parents=True, exist_ok=True)

        # Watch this agent's logs
        self.log_watcher.watch_agent(adw_id)

        # Spawn agent
        try:
            self.agent_manager.spawn_prompt(
                prompt=f"Task ID: {adw_id}\n\nPlease complete this task:\n\n{description}\n\nWork in the current directory. When done, summarize what you accomplished.",
                adw_id=adw_id,
                model="sonnet",
            )
            detail.add_message(f"[cyan]Agent spawned - watching logs...[/cyan]")

            # Select this task
            self.state.load_from_tasks_md()
            self.state.select_task(adw_id)

        except Exception as e:
            detail.add_message(f"[red]Failed to spawn agent: {e}[/red]")

    def _kill_agent(self, args: str) -> None:
        """Kill an agent."""
        detail = self.query_one(DetailPanel)

        if args:
            adw_id = args.strip()
        elif self.state.selected_task and self.state.selected_task.is_running:
            adw_id = self.state.selected_task.adw_id
        else:
            detail.add_message("[yellow]No running task selected. Use /kill <id>[/yellow]")
            return

        success = self.agent_manager.kill(adw_id)
        if success:
            detail.add_message(f"[yellow]Killed agent {adw_id[:8]}[/yellow]")
            self.state.load_from_tasks_md()
        else:
            detail.add_message(f"[red]Agent {adw_id[:8]} not found or not running[/red]")

    async def _ask_question(self, question: str) -> None:
        """Ask Claude a question."""
        detail = self.query_one(DetailPanel)
        detail.add_message("[dim]Thinking...[/dim]")

        try:
            # Include project context
            context = ""
            claude_md = Path.cwd() / "CLAUDE.md"
            if claude_md.exists():
                try:
                    context = f"Project context:\n{claude_md.read_text()[:2000]}\n\n"
                except Exception:
                    pass

            prompt = f"{context}Question: {question}\n\nProvide a concise, helpful answer."

            process = await asyncio.create_subprocess_exec(
                "claude", "--print", prompt,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=120.0)

            if process.returncode == 0 and stdout:
                response = stdout.decode().strip()
                for line in response.split("\n"):
                    detail.add_message(line)
            else:
                detail.add_message("[red]Failed to get response[/red]")
                if stderr:
                    detail.add_message(f"[dim]{stderr.decode()[:200]}[/dim]")

        except asyncio.TimeoutError:
            detail.add_message("[red]Request timed out[/red]")
        except FileNotFoundError:
            detail.add_message("[red]Claude CLI not found. Install with: npm install -g @anthropic-ai/claude-code[/red]")
        except Exception as e:
            detail.add_message(f"[red]Error: {e}[/red]")

    def _run_init(self) -> None:
        """Initialize ADW in project."""
        detail = self.query_one(DetailPanel)

        try:
            from ..init import init_project
            result = init_project(Path.cwd(), force=False)

            if result["created"]:
                detail.add_message("[green]Created:[/green]")
                for path in result["created"]:
                    detail.add_message(f"  + {path}")

            if result["skipped"]:
                detail.add_message("[dim]Already exists:[/dim]")
                for path in result["skipped"]:
                    detail.add_message(f"  - {path}")

            detail.add_message("[green]ADW initialized![/green]")
            self.state.load_from_tasks_md()

        except Exception as e:
            detail.add_message(f"[red]Init failed: {e}[/red]")

    def _run_doctor(self) -> None:
        """Check installation health."""
        detail = self.query_one(DetailPanel)
        detail.add_message("[bold]Health Check[/bold]")

        # Check Claude Code
        try:
            result = subprocess.run(["claude", "--version"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                detail.add_message(f"[green]✓[/green] Claude Code: {result.stdout.strip()}")
            else:
                detail.add_message("[red]✗[/red] Claude Code: not working")
        except FileNotFoundError:
            detail.add_message("[red]✗[/red] Claude Code: not installed")
        except Exception as e:
            detail.add_message(f"[yellow]?[/yellow] Claude Code: {e}")

        # Check project files
        cwd = Path.cwd()
        for file, desc in [("CLAUDE.md", "Project config"), ("tasks.md", "Task file")]:
            if (cwd / file).exists():
                detail.add_message(f"[green]✓[/green] {file}")
            else:
                detail.add_message(f"[yellow]![/yellow] {file} missing (run /init)")

    def _run_daemon(self) -> None:
        """Start autonomous daemon."""
        detail = self.query_one(DetailPanel)

        if self._daemon_running:
            detail.add_message("[yellow]Daemon already running[/yellow]")
            return

        self._daemon_running = True
        self.set_interval(5.0, self._daemon_tick)
        detail.add_message("[green]Daemon started - monitoring tasks.md[/green]")

    def _daemon_tick(self) -> None:
        """Daemon tick."""
        if not self._daemon_running:
            return

        self.state.load_from_tasks_md()

        # Find eligible tasks
        eligible = [t for t in self.state.tasks.values() if t.status == TaskStatus.PENDING]

        if eligible and self.state.running_count < 3:
            task = eligible[0]
            detail = self.query_one(DetailPanel)
            detail.add_message(f"[cyan]Daemon: spawning {task.display_id}[/cyan]")
            self._spawn_task(task.description)

    def _stop_daemon(self) -> None:
        """Stop daemon."""
        detail = self.query_one(DetailPanel)

        if not self._daemon_running:
            detail.add_message("[dim]Daemon not running[/dim]")
            return

        self._daemon_running = False
        detail.add_message("[yellow]Daemon stopped[/yellow]")

    # Actions
    def action_quit(self) -> None:
        self.exit()

    def action_clear_logs(self) -> None:
        log_viewer = self.query_one("#log-viewer", LogViewer)
        log_viewer.clear_logs()

    def action_new_task(self) -> None:
        self.query_one("#user-input", Input).focus()
        self.query_one("#user-input", Input).value = "/new "

    def action_refresh(self) -> None:
        self.state.load_from_tasks_md()
        detail = self.query_one(DetailPanel)
        detail.add_message("[cyan]Refreshed[/cyan]")

    def action_cancel(self) -> None:
        self.query_one("#user-input", Input).value = ""

    def action_help(self) -> None:
        self._show_help()


def run_tui() -> None:
    """Run the TUI application."""
    app = ADWApp()
    app.run()
