"""TUI slash command registry and handlers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Any

if TYPE_CHECKING:
    from .app import ADWApp


@dataclass
class SlashCommand:
    """A TUI slash command."""
    name: str
    description: str
    handler: Callable[[ADWApp, list[str]], None]
    usage: str | None = None


def handle_help(app: "ADWApp", args: list[str]) -> None:
    """Show command help."""
    lines = ["Available commands:"]
    for cmd in TUI_COMMANDS:
        usage = f" {cmd.usage}" if cmd.usage else ""
        lines.append(f"  /{cmd.name}{usage} - {cmd.description}")
    lines.append("")
    lines.append("Keyboard shortcuts:")
    lines.append("  n - New task")
    lines.append("  r - Refresh task list")
    lines.append("  c - Clear logs")
    lines.append("  ? - Show help")
    lines.append("  Tab - Switch panels")
    lines.append("  Esc - Cancel")
    lines.append("  q - Quit")

    app.notify("\n".join(lines), timeout=10)


def handle_status(app: "ADWApp", args: list[str]) -> None:
    """Show system status summary."""
    state = app.state
    total = len(state.tasks)
    running = state.running_count
    pending = sum(1 for t in state.tasks.values() if t.status.value == "pending")
    done = sum(1 for t in state.tasks.values() if t.status.value == "done")

    status_lines = [
        f"Tasks: {total} total",
        f"  Running: {running}",
        f"  Pending: {pending}",
        f"  Done: {done}",
    ]

    if state.current_activity:
        status_lines.append(f"Activity: {state.current_activity}")

    app.notify("\n".join(status_lines), timeout=5)


def handle_spawn(app: "ADWApp", args: list[str]) -> None:
    """Spawn agent for selected or specified task."""
    if args:
        task_id = args[0]
        # Find task by partial ID match
        for key, task in app.state.tasks.items():
            if task.adw_id and task.adw_id.startswith(task_id):
                if task.is_running:
                    app.notify(f"Task {task.display_id} is already running", severity="warning")
                    return
                app.spawn_task(task.description)
                return
        app.notify(f"Task '{task_id}' not found", severity="error")
    elif app.state.selected_task:
        if app.state.selected_task.is_running:
            app.notify("Selected task is already running", severity="warning")
            return
        app.spawn_task(app.state.selected_task.description)
    else:
        app.notify("No task selected. Use /spawn <task_id> or select a task first.", severity="warning")


def handle_kill(app: "ADWApp", args: list[str]) -> None:
    """Kill running agent."""
    if args:
        adw_id = args[0]
        success = app.agent_manager.kill(adw_id)
        if success:
            app.notify(f"Agent {adw_id} killed")
            app.state.load_from_tasks_md()
        else:
            app.notify(f"Agent '{adw_id}' not found or not running", severity="error")
    elif app.state.selected_task and app.state.selected_task.is_running:
        adw_id = app.state.selected_task.adw_id
        success = app.agent_manager.kill(adw_id)
        if success:
            app.notify(f"Agent {adw_id[:8]} killed")
            app.state.load_from_tasks_md()
        else:
            app.notify("Failed to kill agent", severity="error")
    else:
        app.notify("No running task selected. Use /kill <adw_id> or select a running task.", severity="warning")


def handle_logs(app: "ADWApp", args: list[str]) -> None:
    """Filter logs to specific agent."""
    from .widgets.log_viewer import LogViewer

    log_viewer = app.query_one("#log-viewer", LogViewer)

    if args:
        adw_id = args[0]
        if adw_id.lower() == "all":
            log_viewer.filter_by_agent(None)
            app.notify("Showing all logs")
        else:
            log_viewer.filter_by_agent(adw_id)
            app.notify(f"Filtering logs to agent {adw_id[:8]}")
    else:
        # Toggle between selected task and all
        if log_viewer._filter_adw_id:
            log_viewer.filter_by_agent(None)
            app.notify("Showing all logs")
        elif app.state.selected_task:
            log_viewer.filter_by_agent(app.state.selected_task.adw_id)
            app.notify(f"Filtering logs to {app.state.selected_task.display_id}")
        else:
            app.notify("No task selected for log filtering")


def handle_clear(app: "ADWApp", args: list[str]) -> None:
    """Clear log view."""
    from .widgets.log_viewer import LogViewer

    log_viewer = app.query_one("#log-viewer", LogViewer)
    log_viewer.clear_logs()
    app.notify("Logs cleared")


def handle_refresh(app: "ADWApp", args: list[str]) -> None:
    """Refresh task list."""
    app.state.load_from_tasks_md()
    app.notify("Tasks refreshed")


def handle_message(app: "ADWApp", args: list[str]) -> None:
    """Send message to agent."""
    if len(args) < 2:
        if app.state.selected_task and app.state.selected_task.is_running and len(args) == 1:
            # Single arg is the message, send to selected task
            from ..protocol.messages import write_message, MessagePriority
            write_message(
                adw_id=app.state.selected_task.adw_id,
                message=args[0],
                priority=MessagePriority.NORMAL,
            )
            app.notify(f"Message sent to {app.state.selected_task.display_id}")
        else:
            app.notify("Usage: /message <adw_id> <message> or select a running task", severity="warning")
        return

    adw_id = args[0]
    message = " ".join(args[1:])

    from ..protocol.messages import write_message, MessagePriority
    write_message(adw_id=adw_id, message=message, priority=MessagePriority.NORMAL)
    app.notify(f"Message sent to {adw_id[:8]}")


def handle_update(app: "ADWApp", args: list[str]) -> None:
    """Check for and install updates."""
    from ..update import check_for_update, run_update
    from .. import __version__

    app.notify(f"Current version: {__version__}. Checking for updates...")

    current, latest = check_for_update()

    if latest is None:
        app.notify("Could not check for updates. Package may not be published yet.", severity="warning")
        return

    if latest <= current:
        app.notify(f"Already at latest version ({current})")
        return

    app.notify(f"Update available: {current} → {latest}. Updating...")

    # Run update in background (this will restart the app)
    success = run_update()
    if success:
        app.notify(f"Updated to {latest}! Restart ADW to use new version.", timeout=10)
    else:
        app.notify("Update failed. Try: uv tool upgrade adw", severity="error")


def handle_version(app: "ADWApp", args: list[str]) -> None:
    """Show version information."""
    from .. import __version__
    app.notify(f"ADW version {__version__}")


# Command registry
TUI_COMMANDS: list[SlashCommand] = [
    SlashCommand("help", "Show command help", handle_help),
    SlashCommand("status", "Show system status summary", handle_status),
    SlashCommand("spawn", "Spawn agent for task", handle_spawn, "<task_id>"),
    SlashCommand("kill", "Kill running agent", handle_kill, "<adw_id>"),
    SlashCommand("message", "Send message to agent", handle_message, "<adw_id> <msg>"),
    SlashCommand("logs", "Filter logs to agent", handle_logs, "[adw_id|all]"),
    SlashCommand("clear", "Clear log view", handle_clear),
    SlashCommand("refresh", "Refresh task list", handle_refresh),
    SlashCommand("update", "Check for and install updates", handle_update),
    SlashCommand("version", "Show version info", handle_version),
]


def parse_command(text: str) -> tuple[str, list[str]] | None:
    """Parse a slash command from input text.

    Args:
        text: Input text (e.g., "/spawn abc123")

    Returns:
        Tuple of (command_name, args) or None if not a command
    """
    text = text.strip()
    if not text.startswith("/"):
        return None

    parts = text[1:].split()
    if not parts:
        return None

    return parts[0].lower(), parts[1:]


def execute_command(app: "ADWApp", text: str) -> bool:
    """Execute a slash command.

    Args:
        app: The TUI application instance
        text: Input text to parse and execute

    Returns:
        True if a command was executed, False if not a command
    """
    parsed = parse_command(text)
    if not parsed:
        return False

    cmd_name, args = parsed

    # Find matching command
    for cmd in TUI_COMMANDS:
        if cmd.name == cmd_name:
            try:
                cmd.handler(app, args)
            except Exception as e:
                app.notify(f"Command error: {e}", severity="error")
            return True

    # Unknown command
    app.notify(f"Unknown command: /{cmd_name}. Use /help for available commands.", severity="warning")
    return True
