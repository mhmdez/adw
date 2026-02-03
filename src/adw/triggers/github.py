"""GitHub-based triggers for ADW workflows."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from rich.console import Console

from ..agent.utils import generate_adw_id
from ..integrations.github import add_issue_comment, get_open_issues_with_label
from ..integrations.issue_parser import (
    merge_template_with_labels,
    parse_issue_body,
)
from ..workflows.standard import run_standard_workflow

console = Console()


def _get_workflow_runner(workflow: str) -> Callable[..., Any]:
    """Get the appropriate workflow runner function.

    Args:
        workflow: Workflow name (simple, standard, sdlc).

    Returns:
        Workflow runner function.
    """
    if workflow == "simple":
        from ..workflows.simple import run_simple_workflow
        return run_simple_workflow
    elif workflow == "sdlc":
        from ..workflows.sdlc import run_sdlc_workflow
        return run_sdlc_workflow
    else:
        return run_standard_workflow


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

        # Parse issue template
        template = parse_issue_body(issue.body, issue.title)

        # Merge with label configuration (labels take precedence)
        template = merge_template_with_labels(template, issue.labels)

        # Determine workflow and model
        workflow = template.get_workflow_or_default()
        model = template.get_model_or_default()

        console.print(f"[cyan]Processing issue #{issue.number}: {issue.title}[/cyan]")
        console.print(
            f"[dim]  Type: {template.issue_type.value}, "
            f"Priority: {template.priority.value}, "
            f"Workflow: {workflow}, Model: {model}[/dim]"
        )

        if dry_run:
            console.print(f"[yellow]DRY RUN: Would process with ADW ID {adw_id}[/yellow]")
            continue

        # Comment on issue to show we're working on it
        add_issue_comment(
            issue.number,
            f"🤖 ADW is working on this issue.\n\n"
            f"**ADW ID**: `{adw_id}`\n"
            f"**Workflow**: {workflow}\n"
            f"**Model**: {model}\n"
            f"**Issue Type**: {template.issue_type.value}\n"
            f"**Priority**: {template.priority.value}",
            adw_id,
        )

        # Build enhanced task description with template context
        context_prompt = template.build_context_prompt()
        task_description = f"{issue.title}\n\n{issue.body}"
        if context_prompt:
            task_description = f"{task_description}\n\n{context_prompt}"

        # Run workflow
        worktree_name = f"issue-{issue.number}-{adw_id}"

        # Different workflows have different signatures
        if workflow == "sdlc":
            from ..workflows.sdlc import run_sdlc_workflow
            # sdlc returns tuple (success, results)
            success, _ = run_sdlc_workflow(
                task_description=task_description,
                worktree_name=worktree_name,
                adw_id=adw_id,
            )
        elif workflow == "simple":
            from ..workflows.simple import run_simple_workflow
            success = run_simple_workflow(
                task_description=task_description,
                worktree_name=worktree_name,
                adw_id=adw_id,
                model=model,
            )
        else:
            success = run_standard_workflow(
                task_description=task_description,
                worktree_name=worktree_name,
                adw_id=adw_id,
                model=model,
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
    console.print("[bold]Starting GitHub issue monitor[/bold]")
    console.print(f"Label: {label}")
    console.print(f"Interval: {interval}s")

    try:
        while True:
            process_github_issues(label, dry_run)
            time.sleep(interval)

    except KeyboardInterrupt:
        console.print("\n[yellow]Stopping...[/yellow]")
