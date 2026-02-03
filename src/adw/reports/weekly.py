"""Weekly digest report generation.

This module provides functionality for generating weekly digest reports
that aggregate daily summaries and provide week-over-week comparisons.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .daily import DailySummary, generate_daily_summary
from .metrics import MetricsDB, TaskMetrics, get_metrics_db


@dataclass
class WeeklyDigest:
    """Weekly digest report.

    Aggregates daily summaries for a week and provides
    week-over-week comparison metrics.

    Attributes:
        week_start: Start date of the week (Monday).
        week_end: End date of the week (Sunday).
        daily_summaries: List of DailySummary for each day.
        tasks_completed: Total tasks completed in the week.
        tasks_failed: Total tasks failed in the week.
        total_commits: Total commits for the week.
        prs_created: Total PRs created.
        prs_merged: Total PRs merged.
        total_duration_seconds: Total time spent on tasks.
        avg_task_duration_seconds: Average task duration.
        total_retries: Total retry attempts.
        total_input_tokens: Total input tokens used.
        total_output_tokens: Total output tokens generated.
        estimated_cost: Estimated API cost in USD.
        estimated_time_saved_hours: Estimated developer time saved.
        files_modified: Total files modified.
        lines_added: Total lines added.
        lines_removed: Total lines removed.
        best_task: Task with best performance (fastest completion).
        worst_task: Task with worst performance (most retries or failed).
        prev_week_comparison: Comparison with previous week.
    """

    week_start: datetime
    week_end: datetime
    daily_summaries: list[DailySummary] = field(default_factory=list)
    tasks_completed: int = 0
    tasks_failed: int = 0
    total_commits: int = 0
    prs_created: int = 0
    prs_merged: int = 0
    total_duration_seconds: float = 0.0
    avg_task_duration_seconds: float = 0.0
    total_retries: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    estimated_cost: float = 0.0
    estimated_time_saved_hours: float = 0.0
    files_modified: int = 0
    lines_added: int = 0
    lines_removed: int = 0
    best_task: dict[str, Any] | None = None
    worst_task: dict[str, Any] | None = None
    prev_week_comparison: dict[str, Any] = field(default_factory=dict)

    @property
    def total_tasks(self) -> int:
        """Total tasks processed."""
        return self.tasks_completed + self.tasks_failed

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
    def week_str(self) -> str:
        """Formatted week string (e.g., '2026-W05')."""
        return self.week_start.strftime("%Y-W%W")

    @property
    def date_range_str(self) -> str:
        """Formatted date range string."""
        return f"{self.week_start.strftime('%Y-%m-%d')} to {self.week_end.strftime('%Y-%m-%d')}"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "week": self.week_str,
            "week_start": self.week_start.strftime("%Y-%m-%d"),
            "week_end": self.week_end.strftime("%Y-%m-%d"),
            "tasks_completed": self.tasks_completed,
            "tasks_failed": self.tasks_failed,
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
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_input_tokens + self.total_output_tokens,
            "estimated_cost": self.estimated_cost,
            "estimated_time_saved_hours": self.estimated_time_saved_hours,
            "files_modified": self.files_modified,
            "lines_added": self.lines_added,
            "lines_removed": self.lines_removed,
            "best_task": self.best_task,
            "worst_task": self.worst_task,
            "prev_week_comparison": self.prev_week_comparison,
            "daily_summaries": [d.to_dict() for d in self.daily_summaries],
        }

    def to_markdown(self) -> str:
        """Generate markdown report."""
        lines = [
            f"# Weekly Digest: {self.week_str}",
            f"**Period:** {self.date_range_str}",
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

        # Week-over-week comparison
        if self.prev_week_comparison:
            lines.extend(
                [
                    "## Week-over-Week Comparison",
                    "",
                ]
            )
            for key, value in self.prev_week_comparison.items():
                direction = "↑" if value > 0 else "↓" if value < 0 else "→"
                formatted_key = key.replace("_", " ").title()
                if isinstance(value, float):
                    lines.append(f"- **{formatted_key}:** {direction} {abs(value):.1f}%")
                else:
                    lines.append(f"- **{formatted_key}:** {direction} {abs(value)}")
            lines.append("")

        # Best and worst tasks
        if self.best_task:
            lines.extend(
                [
                    "## Highlights",
                    "",
                    f"**Best Performing Task:** `{self.best_task.get('task_id', 'N/A')[:8]}`",
                    f"  - {self.best_task.get('description', 'N/A')[:50]}",
                    f"  - Duration: {_format_duration(self.best_task.get('duration', 0))}",
                    "",
                ]
            )

        if self.worst_task:
            lines.extend(
                [
                    f"**Needs Attention:** `{self.worst_task.get('task_id', 'N/A')[:8]}`",
                    f"  - {self.worst_task.get('description', 'N/A')[:50]}",
                    f"  - Retries: {self.worst_task.get('retries', 0)}",
                    "",
                ]
            )

        # Daily breakdown
        if self.daily_summaries:
            lines.extend(
                [
                    "## Daily Breakdown",
                    "",
                    "| Day | Tasks | Success Rate | Duration | Cost |",
                    "|-----|-------|--------------|----------|------|",
                ]
            )
            for summary in self.daily_summaries:
                lines.append(
                    f"| {summary.date.strftime('%a %m/%d')} | "
                    f"{summary.total_tasks} | "
                    f"{summary.success_rate:.0f}% | "
                    f"{summary.total_duration_str} | "
                    f"${summary.estimated_cost:.2f} |"
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


def _get_week_bounds(date: datetime) -> tuple[datetime, datetime]:
    """Get the Monday and Sunday of the week containing the given date.

    Args:
        date: Any date within the week.

    Returns:
        Tuple of (monday, sunday) datetimes.
    """
    # Get Monday (weekday 0)
    monday = date - timedelta(days=date.weekday())
    monday = monday.replace(hour=0, minute=0, second=0, microsecond=0)

    # Get Sunday
    sunday = monday + timedelta(days=6)
    sunday = sunday.replace(hour=23, minute=59, second=59, microsecond=999999)

    return monday, sunday


def _calculate_comparison(current: WeeklyDigest, previous: WeeklyDigest) -> dict[str, float]:
    """Calculate week-over-week comparison percentages.

    Args:
        current: Current week's digest.
        previous: Previous week's digest.

    Returns:
        Dictionary with percentage changes for key metrics.
    """

    def pct_change(curr: float, prev: float) -> float:
        if prev == 0:
            return 100.0 if curr > 0 else 0.0
        return ((curr - prev) / prev) * 100

    return {
        "tasks_completed": pct_change(current.tasks_completed, previous.tasks_completed),
        "success_rate": current.success_rate - previous.success_rate,
        "total_commits": pct_change(current.total_commits, previous.total_commits),
        "avg_duration": pct_change(
            current.avg_task_duration_seconds,
            previous.avg_task_duration_seconds,
        ),
        "estimated_cost": pct_change(current.estimated_cost, previous.estimated_cost),
        "time_saved": pct_change(
            current.estimated_time_saved_hours,
            previous.estimated_time_saved_hours,
        ),
    }


def _find_best_worst_tasks(
    metrics_list: list[TaskMetrics],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Find best and worst performing tasks.

    Best = completed with fastest duration
    Worst = failed or most retries

    Args:
        metrics_list: List of task metrics.

    Returns:
        Tuple of (best_task, worst_task) dictionaries.
    """
    if not metrics_list:
        return None, None

    best_task = None
    worst_task = None
    best_duration = float("inf")
    worst_retries = -1

    for metrics in metrics_list:
        task_dict = {
            "task_id": metrics.task_id,
            "description": metrics.description,
            "status": metrics.status,
            "duration": metrics.total_duration_seconds,
            "retries": metrics.total_retries,
        }

        # Best: completed with fastest duration
        if metrics.status == "completed" and metrics.total_duration_seconds < best_duration:
            best_duration = metrics.total_duration_seconds
            best_task = task_dict

        # Worst: failed or most retries
        if metrics.status == "failed":
            if worst_task is None or metrics.total_retries > worst_retries:
                worst_retries = metrics.total_retries
                worst_task = task_dict
        elif metrics.total_retries > worst_retries:
            worst_retries = metrics.total_retries
            worst_task = task_dict

    return best_task, worst_task


def generate_weekly_digest(
    date: datetime | None = None,
    db: MetricsDB | None = None,
    include_previous_week: bool = True,
) -> WeeklyDigest:
    """Generate weekly digest report.

    Args:
        date: Any date within the desired week (default: current week).
        db: MetricsDB instance (default: global instance).
        include_previous_week: Whether to include week-over-week comparison.

    Returns:
        WeeklyDigest for the specified week.
    """
    if date is None:
        date = datetime.now()

    if db is None:
        db = get_metrics_db()

    week_start, week_end = _get_week_bounds(date)

    # Generate daily summaries for each day of the week
    daily_summaries = []
    current_day = week_start
    while current_day <= week_end:
        summary = generate_daily_summary(current_day, db)
        daily_summaries.append(summary)
        current_day += timedelta(days=1)

    # Get all task metrics for the week
    metrics_list = db.get_metrics_for_range(week_start, week_end)

    # Aggregate from daily summaries
    tasks_completed = sum(s.tasks_completed for s in daily_summaries)
    tasks_failed = sum(s.tasks_failed for s in daily_summaries)
    total_commits = sum(s.total_commits for s in daily_summaries)
    prs_created = sum(s.prs_created for s in daily_summaries)
    prs_merged = sum(s.prs_merged for s in daily_summaries)
    total_duration = sum(s.total_duration_seconds for s in daily_summaries)
    total_retries = sum(s.total_retries for s in daily_summaries)
    total_input_tokens = sum(s.total_input_tokens for s in daily_summaries)
    total_output_tokens = sum(s.total_output_tokens for s in daily_summaries)
    estimated_cost = sum(s.estimated_cost for s in daily_summaries)
    estimated_time_saved = sum(s.estimated_time_saved_hours for s in daily_summaries)
    files_modified = sum(s.files_modified for s in daily_summaries)
    lines_added = sum(s.lines_added for s in daily_summaries)
    lines_removed = sum(s.lines_removed for s in daily_summaries)

    # Calculate averages
    total_tasks = tasks_completed + tasks_failed
    avg_duration = total_duration / total_tasks if total_tasks > 0 else 0.0

    # Find best and worst tasks
    best_task, worst_task = _find_best_worst_tasks(metrics_list)

    # Create the digest
    digest = WeeklyDigest(
        week_start=week_start,
        week_end=week_end,
        daily_summaries=daily_summaries,
        tasks_completed=tasks_completed,
        tasks_failed=tasks_failed,
        total_commits=total_commits,
        prs_created=prs_created,
        prs_merged=prs_merged,
        total_duration_seconds=total_duration,
        avg_task_duration_seconds=avg_duration,
        total_retries=total_retries,
        total_input_tokens=total_input_tokens,
        total_output_tokens=total_output_tokens,
        estimated_cost=estimated_cost,
        estimated_time_saved_hours=estimated_time_saved,
        files_modified=files_modified,
        lines_added=lines_added,
        lines_removed=lines_removed,
        best_task=best_task,
        worst_task=worst_task,
    )

    # Get previous week comparison if requested
    if include_previous_week:
        prev_week_start = week_start - timedelta(days=7)
        prev_digest = generate_weekly_digest(prev_week_start, db, include_previous_week=False)
        digest.prev_week_comparison = _calculate_comparison(digest, prev_digest)

    return digest


def get_weekly_digest(
    date: datetime | None = None,
    db: MetricsDB | None = None,
) -> WeeklyDigest:
    """Get weekly digest, generating if needed.

    This is an alias for generate_weekly_digest for API consistency.

    Args:
        date: Any date within the desired week (default: current week).
        db: MetricsDB instance (default: global instance).

    Returns:
        WeeklyDigest for the specified week.
    """
    return generate_weekly_digest(date, db)


def save_weekly_digest(
    digest: WeeklyDigest,
    output_path: Path | None = None,
) -> Path:
    """Save weekly digest to file.

    Args:
        digest: WeeklyDigest to save.
        output_path: Output file path (default: .adw/reports/weekly-{week}.md).

    Returns:
        Path to the saved file.
    """
    if output_path is None:
        reports_dir = Path(".adw") / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        output_path = reports_dir / f"weekly-{digest.week_str}.md"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(digest.to_markdown())

    return output_path
