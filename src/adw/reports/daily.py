"""Daily summary report generation.

This module provides functionality for generating daily summary reports
that aggregate task metrics, commits, and other activity.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from .metrics import MetricsDB, get_metrics_db

# Anthropic pricing (USD per million tokens)
# Sonnet 3.5 pricing as default
PRICING = {
    "sonnet": {"input": 3.0, "output": 15.0},
    "opus": {"input": 15.0, "output": 75.0},
    "haiku": {"input": 0.25, "output": 1.25},
}


@dataclass
class DailySummary:
    """Daily summary report.

    Attributes:
        date: The date of the report.
        tasks_completed: Number of tasks completed.
        tasks_failed: Number of tasks failed.
        tasks_in_progress: Number of tasks still in progress.
        total_commits: Number of commits made.
        prs_created: Number of PRs created.
        prs_merged: Number of PRs merged.
        total_duration_seconds: Total time spent on tasks.
        avg_task_duration_seconds: Average task duration.
        total_retries: Total retry attempts.
        avg_retries_per_task: Average retries per task.
        total_input_tokens: Total input tokens used.
        total_output_tokens: Total output tokens generated.
        estimated_cost: Estimated API cost in USD.
        estimated_time_saved_hours: Estimated developer time saved.
        files_modified: Total files modified.
        lines_added: Total lines added.
        lines_removed: Total lines removed.
        task_details: List of individual task summaries.
    """

    date: datetime
    tasks_completed: int = 0
    tasks_failed: int = 0
    tasks_in_progress: int = 0
    total_commits: int = 0
    prs_created: int = 0
    prs_merged: int = 0
    total_duration_seconds: float = 0.0
    avg_task_duration_seconds: float = 0.0
    total_retries: int = 0
    avg_retries_per_task: float = 0.0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    estimated_cost: float = 0.0
    estimated_time_saved_hours: float = 0.0
    files_modified: int = 0
    lines_added: int = 0
    lines_removed: int = 0
    task_details: list[dict[str, Any]] = field(default_factory=list)

    @property
    def total_tasks(self) -> int:
        """Total tasks processed."""
        return self.tasks_completed + self.tasks_failed + self.tasks_in_progress

    @property
    def success_rate(self) -> float:
        """Success rate as percentage."""
        total = self.tasks_completed + self.tasks_failed
        if total == 0:
            return 0.0
        return (self.tasks_completed / total) * 100

    @property
    def total_duration_str(self) -> str:
        """Human-readable total duration."""
        return _format_duration(self.total_duration_seconds)

    @property
    def avg_duration_str(self) -> str:
        """Human-readable average duration."""
        return _format_duration(self.avg_task_duration_seconds)

    @property
    def date_str(self) -> str:
        """Formatted date string."""
        return self.date.strftime("%Y-%m-%d")

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "date": self.date_str,
            "tasks_completed": self.tasks_completed,
            "tasks_failed": self.tasks_failed,
            "tasks_in_progress": self.tasks_in_progress,
            "total_tasks": self.total_tasks,
            "success_rate": self.success_rate,
            "total_commits": self.total_commits,
            "prs_created": self.prs_created,
            "prs_merged": self.prs_merged,
            "total_duration_seconds": self.total_duration_seconds,
            "total_duration": self.total_duration_str,
            "avg_task_duration_seconds": self.avg_task_duration_seconds,
            "avg_task_duration": self.avg_duration_str,
            "total_retries": self.total_retries,
            "avg_retries_per_task": self.avg_retries_per_task,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_input_tokens + self.total_output_tokens,
            "estimated_cost": self.estimated_cost,
            "estimated_time_saved_hours": self.estimated_time_saved_hours,
            "files_modified": self.files_modified,
            "lines_added": self.lines_added,
            "lines_removed": self.lines_removed,
            "task_details": self.task_details,
        }

    def to_markdown(self) -> str:
        """Generate markdown report."""
        lines = [
            f"# Daily Summary: {self.date_str}",
            "",
            "## Overview",
            "",
            f"- **Tasks Completed:** {self.tasks_completed}",
            f"- **Tasks Failed:** {self.tasks_failed}",
            f"- **Success Rate:** {self.success_rate:.1f}%",
            "",
            "## Activity",
            "",
            f"- **Total Commits:** {self.total_commits}",
            f"- **PRs Created:** {self.prs_created}",
            f"- **PRs Merged:** {self.prs_merged}",
            f"- **Files Modified:** {self.files_modified}",
            f"- **Lines Changed:** +{self.lines_added} / -{self.lines_removed}",
            "",
            "## Performance",
            "",
            f"- **Total Duration:** {self.total_duration_str}",
            f"- **Avg Task Duration:** {self.avg_duration_str}",
            f"- **Total Retries:** {self.total_retries}",
            f"- **Avg Retries/Task:** {self.avg_retries_per_task:.1f}",
            "",
            "## Cost & Efficiency",
            "",
            f"- **Total Tokens:** {self.total_input_tokens + self.total_output_tokens:,}",
            f"  - Input: {self.total_input_tokens:,}",
            f"  - Output: {self.total_output_tokens:,}",
            f"- **Estimated Cost:** ${self.estimated_cost:.2f}",
            f"- **Estimated Time Saved:** {self.estimated_time_saved_hours:.1f} hours",
            "",
        ]

        if self.task_details:
            lines.extend(
                [
                    "## Tasks",
                    "",
                    "| Task ID | Description | Status | Duration | Retries |",
                    "|---------|-------------|--------|----------|---------|",
                ]
            )
            for task in self.task_details:
                desc = task.get("description", "")[:40]
                if len(task.get("description", "")) > 40:
                    desc += "..."
                lines.append(
                    f"| {task['task_id'][:8]} | {desc} | {task['status']} | "
                    f"{_format_duration(task.get('duration', 0))} | {task.get('retries', 0)} |"
                )
            lines.append("")

        lines.extend(
            [
                "---",
                f"*Generated by ADW at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*",
            ]
        )

        return "\n".join(lines)


def _format_duration(seconds: float) -> str:
    """Format seconds as human-readable duration."""
    total_seconds = int(seconds)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)

    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def _get_git_commits_for_date(date: datetime) -> int:
    """Count git commits for a specific date.

    Args:
        date: Date to count commits for.

    Returns:
        Number of commits on that date.
    """
    date_str = date.strftime("%Y-%m-%d")
    try:
        result = subprocess.run(
            [
                "git",
                "log",
                "--oneline",
                f"--after={date_str} 00:00:00",
                f"--before={date_str} 23:59:59",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return len(result.stdout.strip().split("\n")) if result.stdout.strip() else 0
    except Exception:
        pass
    return 0


def _estimate_time_saved(
    tasks_completed: int,
    lines_added: int,
    lines_removed: int,
) -> float:
    """Estimate developer hours saved.

    Uses a heuristic based on:
    - 2 hours base per completed task (planning, implementation, testing)
    - 0.5 minutes per line of code changed (reading, understanding, writing)

    Args:
        tasks_completed: Number of completed tasks.
        lines_added: Lines of code added.
        lines_removed: Lines of code removed.

    Returns:
        Estimated hours saved.
    """
    # Base time per task (planning, implementation, testing, review)
    base_hours = tasks_completed * 2.0

    # Time per line of code (both added and removed lines require work)
    lines_total = lines_added + lines_removed
    lines_hours = (lines_total * 0.5) / 60  # 0.5 minutes per line

    return base_hours + lines_hours


def _calculate_cost(
    input_tokens: int,
    output_tokens: int,
    model: str = "sonnet",
) -> float:
    """Calculate estimated API cost.

    Args:
        input_tokens: Input tokens used.
        output_tokens: Output tokens generated.
        model: Model name (sonnet, opus, haiku).

    Returns:
        Estimated cost in USD.
    """
    pricing = PRICING.get(model, PRICING["sonnet"])
    input_cost = (input_tokens / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]
    return input_cost + output_cost


def generate_daily_summary(
    date: datetime | None = None,
    db: MetricsDB | None = None,
) -> DailySummary:
    """Generate daily summary report.

    Args:
        date: Date to generate report for (default: today).
        db: MetricsDB instance (default: global instance).

    Returns:
        DailySummary for the specified date.
    """
    if date is None:
        date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    if db is None:
        db = get_metrics_db()

    # Get task metrics for the date
    metrics_list = db.get_metrics_for_date(date)

    # Initialize counters
    tasks_completed = 0
    tasks_failed = 0
    total_duration = 0.0
    total_retries = 0
    total_input_tokens = 0
    total_output_tokens = 0
    total_commits = 0
    files_modified = 0
    lines_added = 0
    lines_removed = 0
    task_details = []

    for metrics in metrics_list:
        if metrics.status == "completed":
            tasks_completed += 1
        elif metrics.status == "failed":
            tasks_failed += 1

        total_duration += metrics.total_duration_seconds
        total_retries += metrics.total_retries
        total_input_tokens += metrics.total_input_tokens
        total_output_tokens += metrics.total_output_tokens
        total_commits += metrics.commits_generated
        files_modified += metrics.files_modified
        lines_added += metrics.lines_added
        lines_removed += metrics.lines_removed

        task_details.append(
            {
                "task_id": metrics.task_id,
                "description": metrics.description,
                "status": metrics.status,
                "duration": metrics.total_duration_seconds,
                "retries": metrics.total_retries,
                "tokens": metrics.total_tokens,
            }
        )

    # Calculate averages
    total_tasks = tasks_completed + tasks_failed
    avg_duration = total_duration / total_tasks if total_tasks > 0 else 0.0
    avg_retries = total_retries / total_tasks if total_tasks > 0 else 0.0

    # Get git commits if no commits recorded in metrics
    if total_commits == 0:
        total_commits = _get_git_commits_for_date(date)

    # Calculate estimated cost and time saved
    estimated_cost = _calculate_cost(total_input_tokens, total_output_tokens)
    estimated_time_saved = _estimate_time_saved(tasks_completed, lines_added, lines_removed)

    return DailySummary(
        date=date,
        tasks_completed=tasks_completed,
        tasks_failed=tasks_failed,
        total_commits=total_commits,
        total_duration_seconds=total_duration,
        avg_task_duration_seconds=avg_duration,
        total_retries=total_retries,
        avg_retries_per_task=avg_retries,
        total_input_tokens=total_input_tokens,
        total_output_tokens=total_output_tokens,
        estimated_cost=estimated_cost,
        estimated_time_saved_hours=estimated_time_saved,
        files_modified=files_modified,
        lines_added=lines_added,
        lines_removed=lines_removed,
        task_details=task_details,
    )


def get_daily_summary(
    date: datetime | None = None,
    db: MetricsDB | None = None,
) -> DailySummary:
    """Get daily summary, generating if needed.

    This is an alias for generate_daily_summary for API consistency.

    Args:
        date: Date to get summary for (default: today).
        db: MetricsDB instance (default: global instance).

    Returns:
        DailySummary for the specified date.
    """
    return generate_daily_summary(date, db)


def save_daily_summary(
    summary: DailySummary,
    output_path: Path | None = None,
) -> Path:
    """Save daily summary to file.

    Args:
        summary: DailySummary to save.
        output_path: Output file path (default: .adw/reports/daily-{date}.md).

    Returns:
        Path to the saved file.
    """
    if output_path is None:
        reports_dir = Path(".adw") / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        output_path = reports_dir / f"daily-{summary.date_str}.md"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(summary.to_markdown())

    return output_path
