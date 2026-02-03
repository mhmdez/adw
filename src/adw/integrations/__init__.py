"""ADW external integrations (GitHub, Notion, Linear, Slack, etc.)."""

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
]
