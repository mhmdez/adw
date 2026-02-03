"""ADW external integrations (GitHub, Notion, etc.)."""

from __future__ import annotations

from .github import (
    GitHubIssue,
    add_issue_comment,
    create_pull_request,
    get_issue,
    get_open_issues_with_label,
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
    # Notion
    "NotionClient",
    "NotionConfig",
    "NotionTask",
    "NotionWatcher",
    "process_notion_tasks",
    "run_notion_watcher",
    "test_notion_connection",
]
