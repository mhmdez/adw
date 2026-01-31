"""GitHub-based triggers for ADW workflows."""

from __future__ import annotations

import time
from pathlib import Path

from rich.console import Console

from ..agent.executor import generate_adw_id
from ..agent.task_updater import mark_in_progress
from ..integrations.github import get_open_issues_with_label, add_issue_comment
from ..workflows.standard import run_standard_workflow


console = Console()


def process_github_issues(
    label: str = "adw",
    dry_run: bool = False,
) -> int:
    """Process GitHub issues with ADW label.

    Args:
        label: Label to look for.
        dry_run: If True, don't actually process.

    Returns:
        Number of issues processed.
    """
    issues = get_open_issues_with_label(label)

    if not issues:
        console.print(f"[dim]No open issues with label '{label}'[/dim]")
        return 0

    processed = 0

    for issue in issues:
        adw_id = generate_adw_id()

        console.print(f"[cyan]Processing issue #{issue.number}: {issue.title}[/cyan]")

        if dry_run:
            console.print(f"[yellow]DRY RUN: Would process with ADW ID {adw_id}[/yellow]")
            continue

        # Comment on issue to show we're working on it
        add_issue_comment(
            issue.number,
            f"🤖 ADW is working on this issue.\n\n**ADW ID**: `{adw_id}`",
            adw_id,
        )

        # Run workflow
        worktree_name = f"issue-{issue.number}-{adw_id}"
        success = run_standard_workflow(
            task_description=f"{issue.title}\n\n{issue.body}",
            worktree_name=worktree_name,
            adw_id=adw_id,
        )

        # Update issue with result
        if success:
            add_issue_comment(
                issue.number,
                f"✅ Implementation complete!\n\nADW ID: `{adw_id}`\n\nPlease review the PR.",
                adw_id,
            )
        else:
            add_issue_comment(
                issue.number,
                f"❌ Implementation failed.\n\nADW ID: `{adw_id}`\n\nCheck logs in `agents/{adw_id}/`",
                adw_id,
            )

        processed += 1

    return processed


def run_github_cron(
    label: str = "adw",
    interval: int = 60,
    dry_run: bool = False,
) -> None:
    """Continuously poll GitHub for issues.

    Args:
        label: Label to look for.
        interval: Seconds between checks.
        dry_run: If True, don't actually process.
    """
    console.print(f"[bold]Starting GitHub issue monitor[/bold]")
    console.print(f"Label: {label}")
    console.print(f"Interval: {interval}s")

    try:
        while True:
            process_github_issues(label, dry_run)
            time.sleep(interval)

    except KeyboardInterrupt:
        console.print("\n[yellow]Stopping...[/yellow]")
