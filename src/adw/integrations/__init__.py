"""ADW external integrations (GitHub, Notion, Linear, Slack, Telegram, etc.)."""

from __future__ import annotations

from .github import (
    GitHubIssue,
    add_issue_comment,
    create_pull_request,
    get_issue,
    get_open_issues_with_label,
)
from .linear import (
    LinearClient,
    LinearConfig,
    LinearIssue,
    LinearWatcher,
    process_linear_issues,
    run_linear_watcher,
    sync_linear_issue,
    test_linear_connection,
)
from .notion import (
    NotionClient,
    NotionConfig,
    NotionTask,
    NotionWatcher,
    process_notion_tasks,
    run_notion_watcher,
    test_notion_connection,
)
from .telegram import (
    TelegramClient,
    TelegramConfig,
    TelegramTaskState,
    notify_task_completed,
    notify_task_failed,
    notify_task_started,
    request_approval,
    run_telegram_bot,
    send_test_message,
    test_telegram_connection,
)

__all__ = [
    # GitHub
    "GitHubIssue",
    "get_issue",
    "add_issue_comment",
    "create_pull_request",
    "get_open_issues_with_label",
    # Linear
    "LinearClient",
    "LinearConfig",
    "LinearIssue",
    "LinearWatcher",
    "process_linear_issues",
    "run_linear_watcher",
    "sync_linear_issue",
    "test_linear_connection",
    # Notion
    "NotionClient",
    "NotionConfig",
    "NotionTask",
    "NotionWatcher",
    "process_notion_tasks",
    "run_notion_watcher",
    "test_notion_connection",
    # Telegram
    "TelegramClient",
    "TelegramConfig",
    "TelegramTaskState",
    "run_telegram_bot",
    "test_telegram_connection",
    "send_test_message",
    "notify_task_started",
    "notify_task_completed",
    "notify_task_failed",
    "request_approval",
]
