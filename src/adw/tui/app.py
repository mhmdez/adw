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
from .log_watcher import LogWatcher, LogEvent, QuestionEvent
from .widgets.task_list import TaskList
from .widgets.log_viewer import LogViewer
from .widgets.question_modal import QuestionModal
from ..protocol.messages import write_answer, AgentQuestion
from ..agent.manager import AgentManager
from ..agent.utils import generate_adw_id
from ..agent.models import TaskStatus
from ..specs import SpecLoader, Spec, SpecStatus
from ..workflow import WorkflowManager, TaskPhase
from .. import __version__
from .branding import COLORS, SPINNERS, LOGO, TAGLINE, get_loading_message, gradient_text
from .styles import APP_CSS


# Spinner frames - now using fun spinners
SPINNER = SPINNERS["dots"]


class TaskInbox(Vertical):
    """Task inbox showing all tasks with live status."""

    DEFAULT_CSS = """
    TaskInbox {
        width: 100%;
        height: auto;
        max-height: 12;
        padding: 0 1;
        background: #111;
        border: round #222;
    }

    TaskInbox > #inbox-header {
        height: 1;
        color: #00D4FF;
        text-style: bold;
        padding-bottom: 1;
    }

    TaskInbox > #task-container {
        height: auto;
        max-height: 10;
    }

    .task-item {
        height: 1;
        padding: 0 1;
    }
    
    .task-item:hover {
        background: #1a1a1a;
    }
    """

    spinner_frame = reactive(0)

    def __init__(self):
        super().__init__()
        self._tasks: dict[str, TaskState] = {}
        self._selected_key: str | None = None
        self._has_running = False

    def compose(self) -> ComposeResult:
        yield Static(f"[bold {COLORS['primary']}]📋 TASKS[/]", id="inbox-header")
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
            # Show blocked with reason indicator
            from .state import BlockedReason
            reason_icons = {
                BlockedReason.DEPENDENCY: "⏳",
                BlockedReason.APPROVAL: "👤",
                BlockedReason.EXTERNAL: "🔗",
                BlockedReason.QUESTION: "❓",
                BlockedReason.ERROR: "⚠️",
                BlockedReason.MANUAL: "🛑",
            }
            icon = reason_icons.get(task.blocked_reason, "◷")
            text.append(f" {icon} ", style="bold yellow")
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
        elif task.status == TaskStatus.BLOCKED:
            text.append(desc, style="yellow")
            # Show blocked summary inline
            if task.blocked_summary:
                text.append(f" [{task.blocked_summary}]", style="dim yellow italic")
        else:
            text.append(desc)

        widget = Static(text, classes="task-item")
        if key == self._selected_key:
            widget.add_class("-selected")
        if task.is_running:
            widget.add_class("-running")
        if task.is_blocked:
            widget.add_class("-blocked")

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
        height: 3;
        padding: 0 2;
        background: #111;
        border-top: solid #222;
    }

    StatusLine > #prompt {
        width: 3;
        color: #00D4FF;
        text-style: bold;
    }

    StatusLine > Input {
        width: 1fr;
        border: none;
        padding: 0 1;
        background: #0a0a0a;
    }

    StatusLine > Input:focus {
        border: none;
        background: #151515;
    }

    StatusLine > #status-info {
        width: auto;
        color: #666;
        padding: 0 1;
    }
    """

    def __init__(self):
        super().__init__()
        self._running_count = 0
        self._total_count = 0
        self._spec_pending = 0
        self._attention: str | None = None

    def compose(self) -> ComposeResult:
        yield Static("❯", id="prompt")
        yield Input(placeholder="Type /help for commands", id="user-input")
        yield Static("", id="status-info")

    def update_specs(self, pending: int, approved: int = 0) -> None:
        """Update spec counts."""
        self._spec_pending = pending
        self._update_status_line()

    def set_attention(self, text: str | None) -> None:
        """Set attention indicator."""
        self._attention = text
        self._update_status_line()

    def update_status(self, running: int, total: int) -> None:
        """Update status display."""
        self._running_count = running
        self._update_status_line(total=total)

    def _update_status_line(self, total: int | None = None) -> None:
        info = self.query_one("#status-info", Static)
        if total is not None:
            self._total_count = total

        parts = []
        if self._running_count > 0:
            parts.append(f"{self._running_count}/{self._total_count} running")
        else:
            parts.append(f"{self._total_count} tasks")

        if self._spec_pending > 0:
            parts.append(f"📋 {self._spec_pending} specs pending")

        base = " | ".join(parts)

        if self._attention:
            info.update(f"[bold yellow]{self._attention}[/] | {base} ")
        else:
            info.update(f" {base} ")


class ADWApp(App):
    """ADW - AI Developer Workflow Dashboard."""

    ENABLE_COMMAND_PALETTE = False
    DESIGN_SYSTEM = ""  # Disable design system for terminal-native look

    CSS = APP_CSS

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
        self.spec_loader = SpecLoader()
        self.workflow_manager = WorkflowManager()
        self._specs: list[Spec] = []
        self._daemon_running = False
        self._pending_questions: dict[str, tuple[str, AgentQuestion]] = {}

        self.state.subscribe(self._on_state_change)
        self.agent_manager.subscribe(self._on_agent_event)
        self.log_watcher.subscribe_all(self._on_log_event)
        self.log_watcher.subscribe_questions(self._on_question_event)

    def compose(self) -> ComposeResult:
        # Beautiful header with gradient
        header_text = f"[bold {COLORS['primary']}]⚡ ADW[/] [dim]v{__version__}[/]  [dim]│[/]  [italic {COLORS['muted']}]Ship features while you sleep[/]"
        yield Static(header_text, id="main-header")

        with Vertical(id="main-container"):
            yield TaskInbox()
            yield DetailPanel()

        yield StatusLine()

    async def on_mount(self) -> None:
        """Initialize on mount."""
        self.state.load_from_tasks_md()
        self.set_interval(2.0, self._poll_agents)
        self.run_worker(self.log_watcher.watch())

        # Beautiful welcome with ASCII art
        detail = self.query_one(DetailPanel)
        
        # Show the big ASCII logo with gradient colors
        for line in LOGO.strip().split('\n'):
            detail.add_message(f"[bold {COLORS['primary']}]{line}[/]")
        
        detail.add_message("")
        detail.add_message(f"[bold {COLORS['accent']}]✨ {TAGLINE}[/]  [dim]—  Ship features while you sleep[/]")
        detail.add_message("")
        detail.add_message(f"[{COLORS['muted']}]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/]")
        detail.add_message("")
        detail.add_message(f"[bold {COLORS['success']}]⚡ Quick Start[/]")
        detail.add_message(f"  [{COLORS['primary']}]/new[/] [dim]<task>[/]     [dim]→[/]  Create a new task")
        detail.add_message(f"  [{COLORS['primary']}]/discuss[/] [dim]<idea>[/] [dim]→[/]  Interactive planning")
        detail.add_message(f"  [{COLORS['primary']}]/run[/] [dim]<task>[/]     [dim]→[/]  Start a task")
        detail.add_message(f"  [{COLORS['primary']}]/help[/]            [dim]→[/]  All commands")
        detail.add_message("")

        # Focus input
        self.query_one("#user-input", Input).focus()

        # Initial UI update
        self._load_specs()
        self._update_ui()

    def _load_specs(self) -> None:
        """Load specs from disk."""
        self._specs = self.spec_loader.load_all()

    def _update_ui(self) -> None:
        """Update all UI components."""
        inbox = self.query_one(TaskInbox)
        inbox.update_tasks(self.state.tasks)
        inbox.select_task(self.state.selected_task_id)

        status = self.query_one(StatusLine)
        status.update_status(self.state.running_count, len(self.state.tasks))
        
        # Update spec counts
        spec_pending = sum(1 for s in self._specs if s.status == SpecStatus.PENDING)
        status.update_specs(pending=spec_pending)
        
        # Set attention for questions or blocked tasks
        blocked_count = sum(1 for t in self.state.tasks.values() if t.is_blocked)
        question_count = len(self._pending_questions)
        
        attention_parts = []
        if question_count:
            attention_parts.append(f"❓ {question_count}")
        if blocked_count:
            attention_parts.append(f"🔴 {blocked_count} blocked")
        
        if attention_parts:
            status.set_attention(" | ".join(attention_parts))
        else:
            status.set_attention(None)

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

    def _on_question_event(self, event: QuestionEvent) -> None:
        """Handle incoming question from agent."""
        self._pending_questions[event.question.id] = (event.adw_id, event.question)
        self.call_from_thread(self._show_question_modal, event.adw_id, event.question)

    def _show_question_modal(self, adw_id: str, question: AgentQuestion) -> None:
        """Show question modal on main thread."""
        async def show_and_handle():
            modal = QuestionModal(question, adw_id)
            answer = await self.push_screen_wait(modal)

            detail = self.query_one(DetailPanel)
            if answer is not None:
                write_answer(
                    adw_id=adw_id,
                    question_id=question.id,
                    answer=answer,
                )
                detail.add_message(f"[green]✓ Answered: {answer[:50]}...[/green]")
            else:
                detail.add_message("[yellow]⏭ Skipped question[/yellow]")

            if question.id in self._pending_questions:
                del self._pending_questions[question.id]

        asyncio.create_task(show_and_handle())

    def _show_pending_questions(self) -> None:
        """Show all pending questions."""
        detail = self.query_one(DetailPanel)
        if not self._pending_questions:
            detail.add_message("[dim]No pending questions[/dim]")
            return

        detail.add_message("[bold]Pending Questions:[/bold]")
        for _, (adw_id, question) in self._pending_questions.items():
            detail.add_message(f"  [{adw_id[:8]}] {question.question[:50]}...")

        detail.add_message("[dim]Questions will show as modals. Use /questions to list.[/dim]")

    def _show_specs(self, filter_arg: str = "") -> None:
        """Show specs with optional status filter."""
        detail = self.query_one(DetailPanel)
        self._load_specs()
        
        specs = self._specs
        if filter_arg:
            try:
                status = SpecStatus(filter_arg.lower())
                specs = [s for s in specs if s.status == status]
            except ValueError:
                specs = [s for s in specs if filter_arg.lower() in (s.phase or "").lower()]
        
        if not specs:
            detail.add_message("[dim]No specs found[/dim]")
            return
        
        detail.add_message("[bold]Specs:[/bold]")
        current_phase = None
        for spec in specs:
            if spec.phase != current_phase:
                current_phase = spec.phase
                detail.add_message(f"\n[bold dim]{current_phase or 'Unphased'}[/]")
            
            icon = {"draft": "📝", "pending": "⏳", "approved": "✅", "rejected": "❌", "implemented": "🎉"}.get(spec.status.value, "?")
            detail.add_message(f"  {icon} {spec.id}: {spec.title[:40]}")
        
        pending = sum(1 for s in self._specs if s.status == SpecStatus.PENDING)
        approved = sum(1 for s in self._specs if s.status == SpecStatus.APPROVED)
        detail.add_message(f"\n[dim]{len(specs)} specs | {pending} pending | {approved} approved[/dim]")

    def _show_spec_detail(self, spec_id: str) -> None:
        """Show detailed spec info."""
        detail = self.query_one(DetailPanel)
        if not spec_id:
            detail.add_message("[red]Usage: /spec <spec-id>[/red]")
            return
        
        spec = self.spec_loader.get_spec(spec_id.upper())
        if not spec:
            detail.add_message(f"[red]Spec {spec_id} not found[/red]")
            return
        
        detail.add_message(f"[bold]{spec.id}: {spec.title}[/bold]")
        detail.add_message(f"Status: {spec.display_status}")
        detail.add_message(f"Phase: {spec.phase or 'None'}")
        detail.add_message(f"File: {spec.file_path}")
        if spec.description:
            detail.add_message(f"\n{spec.description}")

    def _approve_spec(self, spec_id: str) -> None:
        """Approve a spec."""
        detail = self.query_one(DetailPanel)
        
        if not spec_id:
            pending = [s for s in self._specs if s.status == SpecStatus.PENDING]
            if not pending:
                detail.add_message("[dim]No specs pending approval[/dim]")
                return
            detail.add_message("[bold]Pending specs:[/bold]")
            for spec in pending:
                detail.add_message(f"  ⏳ {spec.id}: {spec.title[:40]}")
            detail.add_message("\n[dim]Use /approve <spec-id> to approve[/dim]")
            return
        
        spec = self.spec_loader.get_spec(spec_id.upper())
        if not spec:
            detail.add_message(f"[red]Spec {spec_id} not found[/red]")
            return
        
        if self.spec_loader.update_status(spec_id.upper(), SpecStatus.APPROVED):
            detail.add_message(f"[green]✅ Approved {spec_id}[/green]")
            self._load_specs()
            self._update_ui()
        else:
            detail.add_message(f"[red]Failed to approve {spec_id}[/red]")

    def _reject_spec(self, args: str) -> None:
        """Reject a spec with reason."""
        detail = self.query_one(DetailPanel)
        
        parts = args.split(maxsplit=1)
        spec_id = parts[0] if parts else ""
        reason = parts[1] if len(parts) > 1 else None
        
        if not spec_id:
            detail.add_message("[red]Usage: /reject <spec-id> [reason][/red]")
            return
        
        spec = self.spec_loader.get_spec(spec_id.upper())
        if not spec:
            detail.add_message(f"[red]Spec {spec_id} not found[/red]")
            return
        
        if self.spec_loader.update_status(spec_id.upper(), SpecStatus.REJECTED, reason):
            detail.add_message(f"[yellow]❌ Rejected {spec_id}[/yellow]")
            if reason:
                detail.add_message(f"[dim]Reason: {reason}[/dim]")
            self._load_specs()
            self._update_ui()
        else:
            detail.add_message(f"[red]Failed to reject {spec_id}[/red]")

    def _show_blocked_tasks(self) -> None:
        """Show all blocked tasks with details."""
        detail = self.query_one(DetailPanel)
        from .state import BlockedReason
        
        blocked = [t for t in self.state.tasks.values() if t.is_blocked]
        
        if not blocked:
            detail.add_message("[green]No blocked tasks! 🎉[/green]")
            return
        
        detail.add_message(f"[bold yellow]Blocked Tasks ({len(blocked)}):[/bold yellow]")
        
        by_reason: dict = {}
        for task in blocked:
            reason = task.blocked_reason or BlockedReason.MANUAL
            if reason not in by_reason:
                by_reason[reason] = []
            by_reason[reason].append(task)
        
        reason_names = {
            BlockedReason.DEPENDENCY: "⏳ Waiting on Dependencies",
            BlockedReason.APPROVAL: "👤 Needs Approval",
            BlockedReason.EXTERNAL: "🔗 External Blockers",
            BlockedReason.QUESTION: "❓ Questions Pending",
            BlockedReason.ERROR: "⚠️  Errors",
            BlockedReason.MANUAL: "🛑 Manually Blocked",
        }
        
        for reason, tasks in by_reason.items():
            detail.add_message(f"\n[bold]{reason_names.get(reason, reason.value)}[/bold]")
            for task in tasks:
                detail.add_message(f"  {task.display_id}: {task.description[:40]}")
                if task.blocked_message:
                    detail.add_message(f"    [dim]{task.blocked_message}[/dim]")
                if task.blocked_needs:
                    detail.add_message(f"    [dim]Needs: {', '.join(task.blocked_needs)}[/dim]")
        
        detail.add_message("\n[dim]Use /unblock <id> to unblock a task[/dim]")

    def _unblock_task(self, args: str) -> None:
        """Unblock a task."""
        detail = self.query_one(DetailPanel)
        
        if not args:
            if self.state.selected_task and self.state.selected_task.is_blocked:
                args = self.state.selected_task.adw_id
            else:
                detail.add_message("[red]Usage: /unblock <task-id>[/red]")
                detail.add_message("[dim]Or select a blocked task and run /unblock[/dim]")
                return
        
        task_id = args.strip()
        
        task = self.state.tasks.get(task_id)
        if not task:
            for t in self.state.tasks.values():
                if t.display_id == task_id or (t.adw_id and t.adw_id.startswith(task_id)):
                    task = t
                    break
        
        if not task:
            detail.add_message(f"[red]Task {task_id} not found[/red]")
            return
        
        if not task.is_blocked:
            detail.add_message(f"[yellow]Task {task.display_id} is not blocked[/yellow]")
            return
        
        if self.state.unblock_task(task.adw_id):
            detail.add_message(f"[green]✓ Unblocked {task.display_id}[/green]")
            detail.add_message("[dim]Task moved to pending queue[/dim]")
            self._update_ui()
        else:
            detail.add_message(f"[red]Failed to unblock {task.display_id}[/red]")

    def _block_task(self, args: str) -> None:
        """Manually block a task."""
        detail = self.query_one(DetailPanel)
        from .state import BlockedReason
        
        parts = args.split(maxsplit=1)
        if len(parts) < 2:
            detail.add_message("[red]Usage: /block <task-id> <reason>[/red]")
            return
        
        task_id, reason = parts
        
        task = self.state.tasks.get(task_id)
        if not task:
            for t in self.state.tasks.values():
                if t.display_id == task_id or (t.adw_id and t.adw_id.startswith(task_id)):
                    task = t
                    break
        
        if not task:
            detail.add_message(f"[red]Task {task_id} not found[/red]")
            return
        
        if self.state.block_task(task.adw_id, BlockedReason.MANUAL, reason):
            detail.add_message(f"[yellow]🛑 Blocked {task.display_id}[/yellow]")
            detail.add_message(f"[dim]Reason: {reason}[/dim]")
            self._update_ui()
        else:
            detail.add_message(f"[red]Failed to block {task.display_id}[/red]")

    async def _start_discussion(self, idea: str) -> None:
        """Start interactive discussion for a task."""
        from .widgets.discuss_modal import DiscussModal
        
        detail = self.query_one(DetailPanel)
        detail.add_message(f"[cyan]Starting discussion: {idea}[/cyan]")
        
        modal = DiscussModal(idea)
        result = await self.push_screen_wait(modal)
        
        if result and result.get("action") == "approve":
            await self._create_from_discussion(result)
        else:
            detail.add_message("[dim]Discussion cancelled[/dim]")

    async def _create_from_discussion(self, result: dict) -> None:
        """Create task and spec from discussion result."""
        detail = self.query_one(DetailPanel)
        
        adw_id = generate_adw_id()
        
        # Save spec file
        spec_dir = Path("specs")
        spec_dir.mkdir(exist_ok=True)
        spec_file = spec_dir / f"{adw_id[:8]}.md"
        spec_file.write_text(result["spec"])
        
        detail.add_message(f"[green]✓ Saved spec: {spec_file}[/green]")
        
        # Save discussion log
        discuss_dir = Path(".adw/discussions")
        discuss_dir.mkdir(parents=True, exist_ok=True)
        discuss_file = discuss_dir / f"{adw_id}.md"
        
        discussion_content = f"# Discussion: {result['idea']}\n\n"
        for msg in result["messages"]:
            if msg["role"] == "user":
                discussion_content += f"**User:** {msg['content']}\n\n"
            elif msg["role"] == "assistant":
                discussion_content += f"**AI:** {msg['content']}\n\n"
        discuss_file.write_text(discussion_content)
        
        # Create workflow
        workflow = self.workflow_manager.get_workflow(adw_id)
        workflow.spec_file = str(spec_file)
        workflow.discussion_file = str(discuss_file)
        workflow.transition_to(TaskPhase.SPEC_APPROVED, "Approved during discussion", "human")
        
        # Add to tasks.md
        tasks_file = Path("tasks.md")
        content = tasks_file.read_text() if tasks_file.exists() else "# Tasks\n\n"
        content = content.rstrip() + f"\n[🟡, {adw_id}] {result['idea']}\n"
        tasks_file.write_text(content)
        
        detail.add_message(f"[green]✓ Created task {adw_id[:8]}[/green]")
        detail.add_message("[cyan]Ready to implement! Use /run or /new[/cyan]")
        
        self.state.load_from_tasks_md()
        self._load_specs()
        self._update_ui()

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
        elif cmd == "questions":
            self._show_pending_questions()
        elif cmd == "specs":
            self._show_specs(args)
        elif cmd == "spec":
            self._show_spec_detail(args)
        elif cmd == "approve":
            self._approve_spec(args)
        elif cmd == "reject":
            self._reject_spec(args)
        elif cmd == "blocked":
            self._show_blocked_tasks()
        elif cmd == "unblock":
            self._unblock_task(args)
        elif cmd == "block":
            self._block_task(args)
        elif cmd == "discuss":
            if args:
                await self._start_discussion(args)
            else:
                detail.add_message("[red]Usage: /discuss <task idea>[/red]")
        elif cmd == "version":
            detail.add_message(f"ADW version {__version__}")
        elif cmd == "quit" or cmd == "exit":
            self.exit()
        else:
            detail.add_message(f"[yellow]Unknown command: /{cmd}[/yellow]")
            detail.add_message("[dim]Type /help for available commands[/dim]")

    def _show_help(self) -> None:
        """Show beautiful help."""
        detail = self.query_one(DetailPanel)
        
        detail.add_message(f"[bold {COLORS['primary']}]⚡ ADW Commands[/]\n")
        
        detail.add_message(f"[bold {COLORS['accent']}]📋 Tasks[/]")
        detail.add_message(f"  [{COLORS['primary']}]/new <desc>[/]     Create and run a task")
        detail.add_message(f"  [{COLORS['primary']}]/discuss <idea>[/] Interactive planning session")
        detail.add_message(f"  [{COLORS['primary']}]/tasks[/]          Refresh task list")
        detail.add_message(f"  [{COLORS['primary']}]/kill [id][/]      Kill running agent")
        detail.add_message("")
        
        detail.add_message(f"[bold {COLORS['accent']}]📄 Specs[/]")
        detail.add_message(f"  [{COLORS['primary']}]/specs[/]          List all specs")
        detail.add_message(f"  [{COLORS['primary']}]/approve <id>[/]   Approve a spec")
        detail.add_message(f"  [{COLORS['primary']}]/reject <id>[/]    Reject a spec")
        detail.add_message("")
        
        detail.add_message(f"[bold {COLORS['accent']}]🔴 Blocked[/]")
        detail.add_message(f"  [{COLORS['primary']}]/blocked[/]        Show blocked tasks")
        detail.add_message(f"  [{COLORS['primary']}]/unblock <id>[/]   Unblock a task")
        detail.add_message("")
        
        detail.add_message(f"[bold {COLORS['accent']}]💬 Chat[/]")
        detail.add_message(f"  [{COLORS['primary']}]/ask <question>[/] Ask Claude anything")
        detail.add_message(f"  [{COLORS['muted']}]Just type a question ending with ?[/]")
        detail.add_message("")
        
        detail.add_message(f"[bold {COLORS['accent']}]⚙️  System[/]")
        detail.add_message(f"  [{COLORS['primary']}]/init[/]           Initialize ADW in project")
        detail.add_message(f"  [{COLORS['primary']}]/run[/]            Start autonomous daemon")
        detail.add_message(f"  [{COLORS['primary']}]/status[/]         Show system status")
        detail.add_message("")
        
        detail.add_message(f"[{COLORS['muted']}]⌨️  Shortcuts: n=new, r=refresh, ?=help, Ctrl+C=quit[/]")

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
