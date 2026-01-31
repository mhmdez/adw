"""Main ADW TUI application."""

from __future__ import annotations

from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Header, Footer, Static, Placeholder, Input

from .widgets.status_bar import StatusBar
from .widgets.log_viewer import LogViewer
from .widgets.task_list import TaskList
from .widgets.task_detail import TaskDetail
from .state import AppState
from .log_watcher import LogWatcher, LogEvent
from ..agent.manager import AgentManager
from ..agent.task_updater import mark_in_progress
from ..agent.utils import generate_adw_id
from ..protocol.messages import write_message, MessagePriority


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
        Binding("shift+tab", "focus_previous", "Prev"),
        Binding("escape", "cancel", "Cancel"),
        Binding("c", "clear_logs", "Clear"),
    ]

    def __init__(self):
        super().__init__()
        self.state = AppState()
        self.agent_manager = AgentManager()
        self.log_watcher = LogWatcher()

        self.state.subscribe(self._on_state_change)
        self.agent_manager.subscribe(self._on_agent_event)
        self.log_watcher.subscribe_all(self._on_log_event)

    def compose(self) -> ComposeResult:
        """Create the UI layout."""
        yield Header()

        with Container(id="app-container"):
            with Horizontal(id="main-panels"):
                # Left: Task list
                with Vertical(id="left-panel", classes="panel"):
                    yield Static("TASKS", classes="panel-title")
                    yield TaskList(id="task-list")

                # Right: Task detail
                with Vertical(id="right-panel", classes="panel"):
                    yield Static("DETAILS", classes="panel-title")
                    yield TaskDetail(id="task-detail")

            # Bottom: Logs
            with Vertical(id="bottom-panel", classes="panel"):
                yield Static("LOGS", classes="panel-title")
                yield LogViewer(id="log-viewer")

            # Status/input bar
            yield StatusBar(id="status-bar")

        yield Footer()

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

        # Filter logs to selected task
        log_viewer = self.query_one("#log-viewer", LogViewer)
        if state.selected_task:
            log_viewer.filter_by_agent(state.selected_task.adw_id)
        else:
            log_viewer.filter_by_agent(None)

    def _on_agent_event(self, event: str, adw_id: str, data: dict) -> None:
        """Handle agent events."""
        if event == "spawned":
            self.notify(f"Agent {adw_id} started")
        elif event == "completed":
            self.notify(f"Agent {adw_id} completed")
            self.state.load_from_tasks_md()  # Refresh
        elif event == "failed":
            self.notify(f"Agent {adw_id} failed", severity="error")
            self.state.load_from_tasks_md()

    def _on_log_event(self, event: LogEvent) -> None:
        """Handle log event."""
        log_viewer = self.query_one("#log-viewer", LogViewer)
        log_viewer.on_log_event(event)

    async def on_mount(self) -> None:
        """Load initial state and start polling."""
        self.state.load_from_tasks_md()
        self.set_interval(2.0, self._poll_agents)
        self.run_worker(self.log_watcher.watch())

    def _poll_agents(self) -> None:
        """Poll for agent completion."""
        completed = self.agent_manager.poll()
        if completed:
            self.state.load_from_tasks_md()

    def on_task_list_task_selected(self, event: TaskList.TaskSelected) -> None:
        """Handle task selection."""
        self.state.select_task(event.key)

    def action_refresh(self) -> None:
        """Refresh from tasks.md."""
        self.state.load_from_tasks_md()
        self.notify("Refreshed")

    async def action_new_task(self) -> None:
        """Create and start new task."""
        # Simple implementation - just prompt for description
        # Full modal comes in later phase
        self.notify("Enter task in status bar input")

    def spawn_task(self, description: str) -> None:
        """Spawn a new task agent."""
        adw_id = generate_adw_id()
        worktree = f"task-{adw_id}"

        # Mark in progress in tasks.md
        tasks_file = Path("tasks.md")
        mark_in_progress(tasks_file, description, adw_id)

        # Spawn agent
        self.agent_manager.spawn_workflow(
            task_description=description,
            worktree_name=worktree,
            adw_id=adw_id,
        )

        # Refresh state
        self.state.load_from_tasks_md()

    def action_show_help(self) -> None:
        """Show help."""
        self.notify("Help: n=new, q=quit, tab=switch panels")

    def action_cancel(self) -> None:
        """Cancel current action."""
        pass

    def action_clear_logs(self) -> None:
        """Clear log viewer."""
        log_viewer = self.query_one("#log-viewer", LogViewer)
        log_viewer.clear_logs()

    async def action_quit(self) -> None:
        """Quit the application."""
        self.exit()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission from status bar."""
        if event.input.id != "status-input-field":
            return

        message = event.value.strip()
        if not message:
            return

        # Clear the input
        event.input.value = ""

        # Determine priority based on message content
        priority = MessagePriority.NORMAL
        if message.upper().startswith("STOP"):
            priority = MessagePriority.INTERRUPT
        elif message.startswith("!"):
            priority = MessagePriority.HIGH
            message = message[1:].strip()

        # Send to selected task if any
        if self.state.selected_task and self.state.selected_task.adw_id:
            write_message(
                adw_id=self.state.selected_task.adw_id,
                message=message,
                priority=priority
            )
            self.notify(f"Message sent to {self.state.selected_task.adw_id[:8]}")
        else:
            # No task selected - could spawn new task if it looks like a task description
            self.notify("No task selected. Select a task first or press 'n' to create new task.")


def run_tui() -> None:
    """Run the TUI application."""
    app = ADWApp()
    app.run()
