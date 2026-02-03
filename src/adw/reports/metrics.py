"""Task metrics tracking and storage.

This module provides the database and models for tracking per-task metrics
including duration, retry counts, token usage, and commits.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

# Default metrics database location
DEFAULT_METRICS_DB_PATH = Path.home() / ".adw" / "metrics.db"

# Thread-local storage for database connections
_local = threading.local()

# Global database instance
_db_instance: MetricsDB | None = None


@dataclass
class PhaseMetrics:
    """Metrics for a single phase of task execution.

    Attributes:
        name: Phase name (e.g., PLAN, IMPLEMENT, TEST).
        duration_seconds: Time spent in this phase.
        retries: Number of retry attempts.
        input_tokens: Tokens used for input/prompts.
        output_tokens: Tokens generated as output.
        success: Whether the phase completed successfully.
    """

    name: str
    duration_seconds: float = 0.0
    retries: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    success: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "name": self.name,
            "duration_seconds": self.duration_seconds,
            "retries": self.retries,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "success": self.success,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PhaseMetrics:
        """Create from dictionary."""
        return cls(
            name=data["name"],
            duration_seconds=data.get("duration_seconds", 0.0),
            retries=data.get("retries", 0),
            input_tokens=data.get("input_tokens", 0),
            output_tokens=data.get("output_tokens", 0),
            success=data.get("success", True),
        )


@dataclass
class TaskMetrics:
    """Complete metrics for a task execution.

    Attributes:
        task_id: The ADW task ID.
        description: Task description.
        workflow: Workflow type (simple, standard, sdlc).
        status: Final task status (completed, failed).
        start_time: When task execution started.
        end_time: When task execution ended.
        total_duration_seconds: Total execution time.
        phases: Per-phase metrics.
        total_retries: Sum of all retry attempts.
        total_input_tokens: Sum of all input tokens.
        total_output_tokens: Sum of all output tokens.
        commits_generated: Number of commits made.
        files_modified: Number of files changed.
        lines_added: Lines of code added.
        lines_removed: Lines of code removed.
    """

    task_id: str
    description: str = ""
    workflow: str = "standard"
    status: str = "completed"
    start_time: datetime = field(default_factory=datetime.now)
    end_time: datetime | None = None
    total_duration_seconds: float = 0.0
    phases: list[PhaseMetrics] = field(default_factory=list)
    total_retries: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    commits_generated: int = 0
    files_modified: int = 0
    lines_added: int = 0
    lines_removed: int = 0

    @property
    def duration(self) -> timedelta:
        """Get task duration as timedelta."""
        return timedelta(seconds=self.total_duration_seconds)

    @property
    def duration_str(self) -> str:
        """Get human-readable duration string."""
        total_seconds = int(self.total_duration_seconds)
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        if hours:
            return f"{hours}h {minutes}m {seconds}s"
        if minutes:
            return f"{minutes}m {seconds}s"
        return f"{seconds}s"

    @property
    def total_tokens(self) -> int:
        """Get total tokens (input + output)."""
        return self.total_input_tokens + self.total_output_tokens

    def calculate_cost(
        self,
        input_price_per_mtok: float = 15.0,
        output_price_per_mtok: float = 75.0,
    ) -> float:
        """Calculate estimated API cost.

        Args:
            input_price_per_mtok: Price per million input tokens (default: Sonnet).
            output_price_per_mtok: Price per million output tokens (default: Sonnet).

        Returns:
            Estimated cost in USD.
        """
        input_cost = (self.total_input_tokens / 1_000_000) * input_price_per_mtok
        output_cost = (self.total_output_tokens / 1_000_000) * output_price_per_mtok
        return input_cost + output_cost

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "task_id": self.task_id,
            "description": self.description,
            "workflow": self.workflow,
            "status": self.status,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "total_duration_seconds": self.total_duration_seconds,
            "phases": json.dumps([p.to_dict() for p in self.phases]),
            "total_retries": self.total_retries,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "commits_generated": self.commits_generated,
            "files_modified": self.files_modified,
            "lines_added": self.lines_added,
            "lines_removed": self.lines_removed,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TaskMetrics:
        """Create from dictionary."""
        phases_data = data.get("phases", "[]")
        if isinstance(phases_data, str):
            phases_data = json.loads(phases_data)

        return cls(
            task_id=data["task_id"],
            description=data.get("description", ""),
            workflow=data.get("workflow", "standard"),
            status=data.get("status", "completed"),
            start_time=datetime.fromisoformat(data["start_time"])
            if isinstance(data["start_time"], str)
            else data["start_time"],
            end_time=datetime.fromisoformat(data["end_time"])
            if data.get("end_time")
            else None,
            total_duration_seconds=data.get("total_duration_seconds", 0.0),
            phases=[PhaseMetrics.from_dict(p) for p in phases_data],
            total_retries=data.get("total_retries", 0),
            total_input_tokens=data.get("total_input_tokens", 0),
            total_output_tokens=data.get("total_output_tokens", 0),
            commits_generated=data.get("commits_generated", 0),
            files_modified=data.get("files_modified", 0),
            lines_added=data.get("lines_added", 0),
            lines_removed=data.get("lines_removed", 0),
        )


class MetricsDB:
    """SQLite database for storing task metrics.

    This class provides methods for recording and querying task metrics.

    Attributes:
        db_path: Path to the SQLite database file.
    """

    def __init__(self, db_path: Path | str | None = None):
        """Initialize the metrics database.

        Args:
            db_path: Path to the database file. Defaults to ~/.adw/metrics.db
        """
        if db_path is None:
            db_path = DEFAULT_METRICS_DB_PATH

        self.db_path = Path(db_path)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Get or create a thread-local database connection."""
        if not hasattr(_local, "metrics_conn") or _local.metrics_conn is None:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            new_conn = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False,
                timeout=30.0,
            )
            new_conn.row_factory = sqlite3.Row
            _local.metrics_conn = new_conn
        result: sqlite3.Connection = _local.metrics_conn
        return result

    @contextmanager
    def _cursor(self) -> Iterator[sqlite3.Cursor]:
        """Get a database cursor with automatic commit/rollback."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()

    def _init_db(self) -> None:
        """Initialize database schema."""
        with self._cursor() as cursor:
            # Task metrics table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS task_metrics (
                    task_id TEXT PRIMARY KEY,
                    description TEXT,
                    workflow TEXT DEFAULT 'standard',
                    status TEXT DEFAULT 'completed',
                    start_time TEXT NOT NULL,
                    end_time TEXT,
                    total_duration_seconds REAL DEFAULT 0,
                    phases TEXT DEFAULT '[]',
                    total_retries INTEGER DEFAULT 0,
                    total_input_tokens INTEGER DEFAULT 0,
                    total_output_tokens INTEGER DEFAULT 0,
                    commits_generated INTEGER DEFAULT 0,
                    files_modified INTEGER DEFAULT 0,
                    lines_added INTEGER DEFAULT 0,
                    lines_removed INTEGER DEFAULT 0
                )
                """
            )

            # Daily aggregates table for faster queries
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS daily_aggregates (
                    date TEXT PRIMARY KEY,
                    tasks_completed INTEGER DEFAULT 0,
                    tasks_failed INTEGER DEFAULT 0,
                    tasks_in_progress INTEGER DEFAULT 0,
                    total_commits INTEGER DEFAULT 0,
                    total_prs INTEGER DEFAULT 0,
                    total_duration_seconds REAL DEFAULT 0,
                    total_input_tokens INTEGER DEFAULT 0,
                    total_output_tokens INTEGER DEFAULT 0,
                    total_retries INTEGER DEFAULT 0,
                    files_modified INTEGER DEFAULT 0,
                    lines_added INTEGER DEFAULT 0,
                    lines_removed INTEGER DEFAULT 0
                )
                """
            )

            # Indexes for common queries
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_task_metrics_start
                ON task_metrics(start_time DESC)
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_task_metrics_status
                ON task_metrics(status)
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_task_metrics_workflow
                ON task_metrics(workflow)
                """
            )

    def record_metrics(self, metrics: TaskMetrics) -> None:
        """Record task metrics.

        Args:
            metrics: TaskMetrics to record.
        """
        data = metrics.to_dict()

        with self._cursor() as cursor:
            cursor.execute(
                """
                INSERT OR REPLACE INTO task_metrics (
                    task_id, description, workflow, status,
                    start_time, end_time, total_duration_seconds,
                    phases, total_retries,
                    total_input_tokens, total_output_tokens,
                    commits_generated, files_modified,
                    lines_added, lines_removed
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    data["task_id"],
                    data["description"],
                    data["workflow"],
                    data["status"],
                    data["start_time"],
                    data["end_time"],
                    data["total_duration_seconds"],
                    data["phases"],
                    data["total_retries"],
                    data["total_input_tokens"],
                    data["total_output_tokens"],
                    data["commits_generated"],
                    data["files_modified"],
                    data["lines_added"],
                    data["lines_removed"],
                ),
            )

        # Update daily aggregates
        self._update_daily_aggregate(metrics)

    def _update_daily_aggregate(self, metrics: TaskMetrics) -> None:
        """Update daily aggregate for the task's date."""
        date_str = metrics.start_time.strftime("%Y-%m-%d")

        with self._cursor() as cursor:
            # Get existing aggregate
            cursor.execute(
                "SELECT * FROM daily_aggregates WHERE date = ?",
                (date_str,),
            )
            row = cursor.fetchone()

            if row:
                # Update existing
                completed_delta = 1 if metrics.status == "completed" else 0
                failed_delta = 1 if metrics.status == "failed" else 0

                cursor.execute(
                    """
                    UPDATE daily_aggregates SET
                        tasks_completed = tasks_completed + ?,
                        tasks_failed = tasks_failed + ?,
                        total_commits = total_commits + ?,
                        total_duration_seconds = total_duration_seconds + ?,
                        total_input_tokens = total_input_tokens + ?,
                        total_output_tokens = total_output_tokens + ?,
                        total_retries = total_retries + ?,
                        files_modified = files_modified + ?,
                        lines_added = lines_added + ?,
                        lines_removed = lines_removed + ?
                    WHERE date = ?
                    """,
                    (
                        completed_delta,
                        failed_delta,
                        metrics.commits_generated,
                        metrics.total_duration_seconds,
                        metrics.total_input_tokens,
                        metrics.total_output_tokens,
                        metrics.total_retries,
                        metrics.files_modified,
                        metrics.lines_added,
                        metrics.lines_removed,
                        date_str,
                    ),
                )
            else:
                # Insert new
                cursor.execute(
                    """
                    INSERT INTO daily_aggregates (
                        date, tasks_completed, tasks_failed, total_commits,
                        total_duration_seconds, total_input_tokens, total_output_tokens,
                        total_retries, files_modified, lines_added, lines_removed
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        date_str,
                        1 if metrics.status == "completed" else 0,
                        1 if metrics.status == "failed" else 0,
                        metrics.commits_generated,
                        metrics.total_duration_seconds,
                        metrics.total_input_tokens,
                        metrics.total_output_tokens,
                        metrics.total_retries,
                        metrics.files_modified,
                        metrics.lines_added,
                        metrics.lines_removed,
                    ),
                )

    def get_metrics(self, task_id: str) -> TaskMetrics | None:
        """Get metrics for a specific task.

        Args:
            task_id: Task ID to fetch metrics for.

        Returns:
            TaskMetrics or None if not found.
        """
        with self._cursor() as cursor:
            cursor.execute(
                "SELECT * FROM task_metrics WHERE task_id = ?",
                (task_id,),
            )
            row = cursor.fetchone()

        if not row:
            return None

        return TaskMetrics.from_dict(dict(row))

    def get_metrics_for_date(self, date: datetime) -> list[TaskMetrics]:
        """Get all task metrics for a specific date.

        Args:
            date: Date to fetch metrics for.

        Returns:
            List of TaskMetrics for that date.
        """
        date_str = date.strftime("%Y-%m-%d")

        with self._cursor() as cursor:
            cursor.execute(
                """
                SELECT * FROM task_metrics
                WHERE date(start_time) = ?
                ORDER BY start_time DESC
                """,
                (date_str,),
            )
            rows = cursor.fetchall()

        return [TaskMetrics.from_dict(dict(row)) for row in rows]

    def get_metrics_for_range(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> list[TaskMetrics]:
        """Get task metrics for a date range.

        Args:
            start_date: Start of range (inclusive).
            end_date: End of range (inclusive).

        Returns:
            List of TaskMetrics in the range.
        """
        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")

        with self._cursor() as cursor:
            cursor.execute(
                """
                SELECT * FROM task_metrics
                WHERE date(start_time) >= ? AND date(start_time) <= ?
                ORDER BY start_time DESC
                """,
                (start_str, end_str),
            )
            rows = cursor.fetchall()

        return [TaskMetrics.from_dict(dict(row)) for row in rows]

    def get_daily_aggregate(self, date: datetime) -> dict[str, Any] | None:
        """Get daily aggregate for a specific date.

        Args:
            date: Date to fetch aggregate for.

        Returns:
            Dictionary with aggregate values or None.
        """
        date_str = date.strftime("%Y-%m-%d")

        with self._cursor() as cursor:
            cursor.execute(
                "SELECT * FROM daily_aggregates WHERE date = ?",
                (date_str,),
            )
            row = cursor.fetchone()

        return dict(row) if row else None

    def get_daily_aggregates_range(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> list[dict[str, Any]]:
        """Get daily aggregates for a date range.

        Args:
            start_date: Start of range.
            end_date: End of range.

        Returns:
            List of daily aggregate dictionaries.
        """
        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")

        with self._cursor() as cursor:
            cursor.execute(
                """
                SELECT * FROM daily_aggregates
                WHERE date >= ? AND date <= ?
                ORDER BY date DESC
                """,
                (start_str, end_str),
            )
            rows = cursor.fetchall()

        return [dict(row) for row in rows]

    def get_recent_metrics(self, limit: int = 50) -> list[TaskMetrics]:
        """Get most recent task metrics.

        Args:
            limit: Maximum number of metrics to return.

        Returns:
            List of recent TaskMetrics.
        """
        with self._cursor() as cursor:
            cursor.execute(
                """
                SELECT * FROM task_metrics
                ORDER BY start_time DESC
                LIMIT ?
                """,
                (limit,),
            )
            rows = cursor.fetchall()

        return [TaskMetrics.from_dict(dict(row)) for row in rows]

    def get_summary_stats(
        self,
        since: datetime | None = None,
    ) -> dict[str, Any]:
        """Get summary statistics.

        Args:
            since: Only include data after this time.

        Returns:
            Dictionary with summary statistics.
        """
        params: list[Any] = []
        where_clause = "1=1"

        if since:
            where_clause = "start_time >= ?"
            params.append(since.isoformat())

        with self._cursor() as cursor:
            cursor.execute(
                f"""
                SELECT
                    COUNT(*) as total_tasks,
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                    SUM(total_duration_seconds) as total_duration,
                    AVG(total_duration_seconds) as avg_duration,
                    SUM(total_retries) as total_retries,
                    AVG(total_retries) as avg_retries,
                    SUM(total_input_tokens) as total_input_tokens,
                    SUM(total_output_tokens) as total_output_tokens,
                    SUM(commits_generated) as total_commits,
                    SUM(files_modified) as total_files_modified,
                    SUM(lines_added) as total_lines_added,
                    SUM(lines_removed) as total_lines_removed
                FROM task_metrics
                WHERE {where_clause}
                """,
                params,
            )
            row = cursor.fetchone()

        if not row or row["total_tasks"] == 0:
            return {
                "total_tasks": 0,
                "completed": 0,
                "failed": 0,
                "success_rate": 0.0,
                "total_duration_seconds": 0,
                "avg_duration_seconds": 0,
                "total_retries": 0,
                "avg_retries": 0,
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "total_commits": 0,
                "total_files_modified": 0,
                "total_lines_added": 0,
                "total_lines_removed": 0,
            }

        total = row["total_tasks"]
        completed = row["completed"] or 0

        return {
            "total_tasks": total,
            "completed": completed,
            "failed": row["failed"] or 0,
            "success_rate": (completed / total * 100) if total > 0 else 0.0,
            "total_duration_seconds": row["total_duration"] or 0,
            "avg_duration_seconds": row["avg_duration"] or 0,
            "total_retries": row["total_retries"] or 0,
            "avg_retries": row["avg_retries"] or 0,
            "total_input_tokens": row["total_input_tokens"] or 0,
            "total_output_tokens": row["total_output_tokens"] or 0,
            "total_commits": row["total_commits"] or 0,
            "total_files_modified": row["total_files_modified"] or 0,
            "total_lines_added": row["total_lines_added"] or 0,
            "total_lines_removed": row["total_lines_removed"] or 0,
        }

    def close(self) -> None:
        """Close the database connection."""
        if hasattr(_local, "metrics_conn") and _local.metrics_conn:
            _local.metrics_conn.close()
            _local.metrics_conn = None


def get_metrics_db(db_path: Path | str | None = None) -> MetricsDB:
    """Get or create the global metrics database instance.

    Args:
        db_path: Optional path to the database file.

    Returns:
        MetricsDB instance.
    """
    global _db_instance

    if _db_instance is None:
        _db_instance = MetricsDB(db_path)

    return _db_instance


# Convenience functions


def record_task_metrics(metrics: TaskMetrics) -> None:
    """Record task metrics using the global database.

    Args:
        metrics: TaskMetrics to record.
    """
    get_metrics_db().record_metrics(metrics)


def record_task_completion(
    task_id: str,
    description: str = "",
    workflow: str = "standard",
    status: str = "completed",
    duration_seconds: float = 0.0,
    retries: int = 0,
    input_tokens: int = 0,
    output_tokens: int = 0,
    commits: int = 0,
    files_modified: int = 0,
    lines_added: int = 0,
    lines_removed: int = 0,
) -> TaskMetrics:
    """Record a task completion with basic metrics.

    Convenience function for recording task completion without
    creating a full TaskMetrics object.

    Args:
        task_id: Task ID.
        description: Task description.
        workflow: Workflow type.
        status: Final status (completed/failed).
        duration_seconds: Total duration.
        retries: Number of retries.
        input_tokens: Input tokens used.
        output_tokens: Output tokens generated.
        commits: Commits generated.
        files_modified: Files modified.
        lines_added: Lines added.
        lines_removed: Lines removed.

    Returns:
        The created TaskMetrics.
    """
    metrics = TaskMetrics(
        task_id=task_id,
        description=description,
        workflow=workflow,
        status=status,
        start_time=datetime.now() - timedelta(seconds=duration_seconds),
        end_time=datetime.now(),
        total_duration_seconds=duration_seconds,
        total_retries=retries,
        total_input_tokens=input_tokens,
        total_output_tokens=output_tokens,
        commits_generated=commits,
        files_modified=files_modified,
        lines_added=lines_added,
        lines_removed=lines_removed,
    )

    record_task_metrics(metrics)
    return metrics
