"""SQLite database for event observability.

This module provides the core database functionality for logging and
querying events in the ADW observability system.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import Event, EventFilter, EventType, Session, SessionStatus

# Default database location
DEFAULT_DB_PATH = Path(".adw/events.db")

# Thread-local storage for database connections
_local = threading.local()

# Global database instance
_db_instance: EventDB | None = None


class EventDB:
    """SQLite database for storing events and sessions.

    This class provides methods for logging events, managing sessions,
    and querying the event history.

    Attributes:
        db_path: Path to the SQLite database file.
    """

    def __init__(self, db_path: Path | str | None = None):
        """Initialize the event database.

        Args:
            db_path: Path to the database file. Defaults to .adw/events.db
        """
        if db_path is None:
            project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
            db_path = Path(project_dir) / DEFAULT_DB_PATH

        self.db_path = Path(db_path)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Get or create a thread-local database connection."""
        if not hasattr(_local, "connection") or _local.connection is None:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            new_conn = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False,
                timeout=30.0,
            )
            new_conn.row_factory = sqlite3.Row
            # Enable foreign keys
            new_conn.execute("PRAGMA foreign_keys = ON")
            _local.connection = new_conn
        result: sqlite3.Connection = _local.connection
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
            # Events table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    session_id TEXT,
                    task_id TEXT,
                    data TEXT DEFAULT '{}'
                )
                """
            )

            # Sessions table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    start_time TEXT NOT NULL,
                    end_time TEXT,
                    task_id TEXT,
                    status TEXT DEFAULT 'running',
                    metadata TEXT DEFAULT '{}'
                )
                """
            )

            # Indexes for common queries
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_events_timestamp
                ON events(timestamp DESC)
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_events_type
                ON events(event_type)
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_events_session
                ON events(session_id)
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_events_task
                ON events(task_id)
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_sessions_task
                ON sessions(task_id)
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_sessions_status
                ON sessions(status)
                """
            )

    def log_event(
        self,
        event_type: EventType | str,
        session_id: str | None = None,
        task_id: str | None = None,
        data: dict[str, Any] | None = None,
        timestamp: datetime | None = None,
    ) -> int:
        """Log an event to the database.

        Args:
            event_type: Type of event.
            session_id: Associated session ID.
            task_id: Associated task/ADW ID.
            data: Additional event data.
            timestamp: Event timestamp (defaults to now).

        Returns:
            The ID of the inserted event.
        """
        if isinstance(event_type, str):
            event_type = EventType(event_type)

        ts = timestamp or datetime.now()
        data_json = json.dumps(data) if data else "{}"

        with self._cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO events (timestamp, event_type, session_id, task_id, data)
                VALUES (?, ?, ?, ?, ?)
                """,
                (ts.isoformat(), event_type.value, session_id, task_id, data_json),
            )
            return cursor.lastrowid or 0

    def get_events(
        self,
        filter_: EventFilter | None = None,
    ) -> list[Event]:
        """Query events from the database.

        Args:
            filter_: Filter criteria for the query.

        Returns:
            List of matching events.
        """
        filter_ = filter_ or EventFilter()
        where_clause, params = filter_.to_sql_where()

        query = f"""
            SELECT id, timestamp, event_type, session_id, task_id, data
            FROM events
            WHERE {where_clause}
            ORDER BY timestamp DESC
            LIMIT ? OFFSET ?
        """
        params.extend([filter_.limit, filter_.offset])

        with self._cursor() as cursor:
            cursor.execute(query, params)
            rows = cursor.fetchall()

        return [
            Event(
                id=row["id"],
                timestamp=datetime.fromisoformat(row["timestamp"]),
                event_type=EventType(row["event_type"]),
                session_id=row["session_id"],
                task_id=row["task_id"],
                data=json.loads(row["data"]) if row["data"] else {},
            )
            for row in rows
        ]

    def get_event_count(self, filter_: EventFilter | None = None) -> int:
        """Get count of events matching filter.

        Args:
            filter_: Filter criteria.

        Returns:
            Number of matching events.
        """
        filter_ = filter_ or EventFilter()
        where_clause, params = filter_.to_sql_where()

        query = f"""
            SELECT COUNT(*) as count
            FROM events
            WHERE {where_clause}
        """

        with self._cursor() as cursor:
            cursor.execute(query, params)
            row = cursor.fetchone()
            return row["count"] if row else 0

    def start_session(
        self,
        session_id: str,
        task_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Session:
        """Start a new session.

        Args:
            session_id: Unique session identifier.
            task_id: Associated task/ADW ID.
            metadata: Additional session metadata.

        Returns:
            The created Session.
        """
        session = Session(
            id=session_id,
            task_id=task_id,
            status=SessionStatus.RUNNING,
            metadata=metadata or {},
        )

        with self._cursor() as cursor:
            cursor.execute(
                """
                INSERT OR REPLACE INTO sessions
                (id, start_time, end_time, task_id, status, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    session.id,
                    session.start_time.isoformat(),
                    None,
                    session.task_id,
                    session.status.value,
                    json.dumps(session.metadata),
                ),
            )

        # Log session start event
        self.log_event(
            EventType.SESSION_START,
            session_id=session_id,
            task_id=task_id,
            data={"metadata": metadata},
        )

        return session

    def end_session(
        self,
        session_id: str,
        status: SessionStatus = SessionStatus.COMPLETED,
    ) -> Session | None:
        """End a session.

        Args:
            session_id: Session ID to end.
            status: Final session status.

        Returns:
            The updated Session, or None if not found.
        """
        end_time = datetime.now()

        with self._cursor() as cursor:
            cursor.execute(
                """
                UPDATE sessions
                SET end_time = ?, status = ?
                WHERE id = ?
                """,
                (end_time.isoformat(), status.value, session_id),
            )

            if cursor.rowcount == 0:
                return None

        # Log session end event
        session = self.get_session(session_id)
        if session:
            self.log_event(
                EventType.SESSION_END,
                session_id=session_id,
                task_id=session.task_id,
                data={"status": status.value, "duration": session.duration_str},
            )

        return session

    def get_session(self, session_id: str) -> Session | None:
        """Get a session by ID.

        Args:
            session_id: Session ID to fetch.

        Returns:
            The Session, or None if not found.
        """
        with self._cursor() as cursor:
            cursor.execute(
                """
                SELECT id, start_time, end_time, task_id, status, metadata
                FROM sessions
                WHERE id = ?
                """,
                (session_id,),
            )
            row = cursor.fetchone()

        if not row:
            return None

        return Session(
            id=row["id"],
            start_time=datetime.fromisoformat(row["start_time"]),
            end_time=datetime.fromisoformat(row["end_time"]) if row["end_time"] else None,
            task_id=row["task_id"],
            status=SessionStatus(row["status"]),
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
        )

    def get_sessions(
        self,
        task_id: str | None = None,
        status: SessionStatus | None = None,
        limit: int = 50,
    ) -> list[Session]:
        """Query sessions from the database.

        Args:
            task_id: Filter by task ID.
            status: Filter by status.
            limit: Maximum number of sessions to return.

        Returns:
            List of matching sessions.
        """
        conditions = []
        params: list[Any] = []

        if task_id:
            conditions.append("task_id = ?")
            params.append(task_id)

        if status:
            conditions.append("status = ?")
            params.append(status.value)

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        query = f"""
            SELECT id, start_time, end_time, task_id, status, metadata
            FROM sessions
            WHERE {where_clause}
            ORDER BY start_time DESC
            LIMIT ?
        """
        params.append(limit)

        with self._cursor() as cursor:
            cursor.execute(query, params)
            rows = cursor.fetchall()

        return [
            Session(
                id=row["id"],
                start_time=datetime.fromisoformat(row["start_time"]),
                end_time=datetime.fromisoformat(row["end_time"]) if row["end_time"] else None,
                task_id=row["task_id"],
                status=SessionStatus(row["status"]),
                metadata=json.loads(row["metadata"]) if row["metadata"] else {},
            )
            for row in rows
        ]

    def get_session_events(self, session_id: str, limit: int = 1000) -> list[Event]:
        """Get all events for a session.

        Args:
            session_id: Session ID to get events for.
            limit: Maximum number of events.

        Returns:
            List of events for the session.
        """
        return self.get_events(EventFilter(session_id=session_id, limit=limit))

    def get_recent_events(self, limit: int = 50) -> list[Event]:
        """Get most recent events.

        Args:
            limit: Maximum number of events to return.

        Returns:
            List of recent events.
        """
        return self.get_events(EventFilter(limit=limit))

    def cleanup_old_events(self, days: int = 30) -> int:
        """Delete events older than specified days.

        Args:
            days: Number of days to keep.

        Returns:
            Number of deleted events.
        """
        from datetime import timedelta

        cutoff = (datetime.now() - timedelta(days=days)).isoformat()

        with self._cursor() as cursor:
            cursor.execute(
                """
                DELETE FROM events
                WHERE timestamp < ?
                """,
                (cutoff,),
            )
            deleted = cursor.rowcount

        return deleted

    def get_event_summary(
        self,
        since: datetime | None = None,
    ) -> dict[str, int]:
        """Get summary counts of events by type.

        Args:
            since: Only count events after this time.

        Returns:
            Dictionary mapping event type to count.
        """
        params: list[Any] = []
        where_clause = "1=1"

        if since:
            where_clause = "timestamp >= ?"
            params.append(since.isoformat())

        query = f"""
            SELECT event_type, COUNT(*) as count
            FROM events
            WHERE {where_clause}
            GROUP BY event_type
            ORDER BY count DESC
        """

        with self._cursor() as cursor:
            cursor.execute(query, params)
            rows = cursor.fetchall()

        return {row["event_type"]: row["count"] for row in rows}

    def close(self) -> None:
        """Close the database connection."""
        if hasattr(_local, "connection") and _local.connection:
            _local.connection.close()
            _local.connection = None


def get_db(db_path: Path | str | None = None) -> EventDB:
    """Get or create the global database instance.

    Args:
        db_path: Optional path to the database file.

    Returns:
        EventDB instance.
    """
    global _db_instance

    if _db_instance is None:
        _db_instance = EventDB(db_path)

    return _db_instance


# Convenience functions that use the global instance


def log_event(
    event_type: EventType | str,
    session_id: str | None = None,
    task_id: str | None = None,
    data: dict[str, Any] | None = None,
    timestamp: datetime | None = None,
) -> int:
    """Log an event using the global database.

    Args:
        event_type: Type of event.
        session_id: Associated session ID.
        task_id: Associated task/ADW ID.
        data: Additional event data.
        timestamp: Event timestamp (defaults to now).

    Returns:
        The ID of the inserted event.
    """
    return get_db().log_event(event_type, session_id, task_id, data, timestamp)


def get_events(filter_: EventFilter | None = None) -> list[Event]:
    """Query events using the global database.

    Args:
        filter_: Filter criteria for the query.

    Returns:
        List of matching events.
    """
    return get_db().get_events(filter_)


def get_session(session_id: str) -> Session | None:
    """Get a session using the global database.

    Args:
        session_id: Session ID to fetch.

    Returns:
        The Session, or None if not found.
    """
    return get_db().get_session(session_id)


def start_session(
    session_id: str,
    task_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Session:
    """Start a session using the global database.

    Args:
        session_id: Unique session identifier.
        task_id: Associated task/ADW ID.
        metadata: Additional session metadata.

    Returns:
        The created Session.
    """
    return get_db().start_session(session_id, task_id, metadata)


def end_session(
    session_id: str,
    status: SessionStatus = SessionStatus.COMPLETED,
) -> Session | None:
    """End a session using the global database.

    Args:
        session_id: Session ID to end.
        status: Final session status.

    Returns:
        The updated Session, or None if not found.
    """
    return get_db().end_session(session_id, status)
