"""ADW CLI commands."""

from .completion import setup_completion
from .monitor_commands import view_logs, watch_daemon
from .task_commands import add_task, cancel_task, list_tasks, retry_task

__all__ = [
    "add_task",
    "list_tasks",
    "cancel_task",
    "retry_task",
    "watch_daemon",
    "view_logs",
    "setup_completion",
]
