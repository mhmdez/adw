"""Data models for observability events and sessions.

This module defines the core models used for event tracking and session
management in the ADW observability system.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any


class EventType(str, Enum):
    """Types of events that can be logged."""

    # Tool events
    TOOL_START = "tool_start"
    TOOL_END = "tool_end"
    TOOL_ERROR = "tool_error"

    # Session events
    SESSION_START = "session_start"
    SESSION_END = "session_end"

    # Agent events
    AGENT_MESSAGE = "agent_message"
    AGENT_QUESTION = "agent_question"
    AGENT_ANSWER = "agent_answer"

    # Task events
    TASK_STARTED = "task_started"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    TASK_BLOCKED = "task_blocked"

    # System events
    SAFETY_BLOCK = "safety_block"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"

    # Hook events
    PRE_TOOL_USE = "pre_tool_use"
    POST_TOOL_USE = "post_tool_use"
    USER_PROMPT = "user_prompt"
    STOP = "stop"


class SessionStatus(str, Enum):
    """Status of a session."""

    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Event:
    """An event in the observability system.

    Attributes:
        id: Unique event identifier (auto-generated).
        timestamp: When the event occurred.
        event_type: The type of event.
        session_id: Associated session ID.
        task_id: Associated task/ADW ID (optional).
        data: Additional event data as JSON.
    """

    event_type: EventType
    session_id: str | None = None
    task_id: str | None = None
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    id: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type.value,
            "session_id": self.session_id,
            "task_id": self.task_id,
            "data": json.dumps(self.data) if self.data else "{}",
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Event:
        """Create Event from dictionary."""
        event_data = data.get("data", "{}")
        if isinstance(event_data, str):
            event_data = json.loads(event_data)

        return cls(
            id=data.get("id"),
            timestamp=datetime.fromisoformat(data["timestamp"])
            if isinstance(data["timestamp"], str)
            else data["timestamp"],
            event_type=EventType(data["event_type"]),
            session_id=data.get("session_id"),
            task_id=data.get("task_id"),
            data=event_data,
        )

    def __str__(self) -> str:
        """String representation for display."""
        task_str = f" [{self.task_id[:8]}]" if self.task_id else ""
        return f"{self.timestamp.strftime('%H:%M:%S')}{task_str} {self.event_type.value}"


@dataclass
class Session:
    """A session in the observability system.

    Attributes:
        id: Unique session identifier.
        start_time: When the session started.
        end_time: When the session ended (None if running).
        task_id: Associated task/ADW ID.
        status: Current session status.
        metadata: Additional session metadata.
    """

    id: str
    task_id: str | None = None
    status: SessionStatus = SessionStatus.RUNNING
    start_time: datetime = field(default_factory=datetime.now)
    end_time: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def duration(self) -> timedelta | None:
        """Get session duration."""
        if self.end_time:
            return self.end_time - self.start_time
        if self.status == SessionStatus.RUNNING:
            return datetime.now() - self.start_time
        return None

    @property
    def duration_str(self) -> str:
        """Get human-readable duration string."""
        duration = self.duration
        if not duration:
            return "unknown"

        total_seconds = int(duration.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        if hours:
            return f"{hours}h {minutes}m {seconds}s"
        if minutes:
            return f"{minutes}m {seconds}s"
        return f"{seconds}s"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "id": self.id,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "task_id": self.task_id,
            "status": self.status.value,
            "metadata": json.dumps(self.metadata) if self.metadata else "{}",
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Session:
        """Create Session from dictionary."""
        metadata = data.get("metadata", "{}")
        if isinstance(metadata, str):
            metadata = json.loads(metadata)

        return cls(
            id=data["id"],
            start_time=datetime.fromisoformat(data["start_time"])
            if isinstance(data["start_time"], str)
            else data["start_time"],
            end_time=datetime.fromisoformat(data["end_time"])
            if data.get("end_time")
            else None,
            task_id=data.get("task_id"),
            status=SessionStatus(data.get("status", "running")),
            metadata=metadata,
        )

    def __str__(self) -> str:
        """String representation for display."""
        task_str = f" [{self.task_id[:8]}]" if self.task_id else ""
        status_str = self.status.value
        return f"Session {self.id[:8]}{task_str}: {status_str} ({self.duration_str})"


@dataclass
class EventFilter:
    """Filter criteria for querying events.

    Attributes:
        event_types: Filter by specific event types.
        session_id: Filter by session ID.
        task_id: Filter by task/ADW ID.
        since: Only events after this time.
        until: Only events before this time.
        limit: Maximum number of events to return.
        offset: Number of events to skip.
    """

    event_types: list[EventType] | None = None
    session_id: str | None = None
    task_id: str | None = None
    since: datetime | None = None
    until: datetime | None = None
    limit: int = 100
    offset: int = 0

    @classmethod
    def from_time_string(cls, time_str: str) -> datetime:
        """Parse a time string like '1h', '30m', '7d' into a datetime.

        Args:
            time_str: Time string with unit suffix (h=hours, m=minutes, d=days, s=seconds).

        Returns:
            datetime representing that time ago from now.

        Raises:
            ValueError: If the time string format is invalid.
        """
        if not time_str:
            raise ValueError("Empty time string")

        unit = time_str[-1].lower()
        try:
            value = int(time_str[:-1])
        except ValueError:
            raise ValueError(f"Invalid time value: {time_str}")

        now = datetime.now()

        if unit == "s":
            return now - timedelta(seconds=value)
        elif unit == "m":
            return now - timedelta(minutes=value)
        elif unit == "h":
            return now - timedelta(hours=value)
        elif unit == "d":
            return now - timedelta(days=value)
        elif unit == "w":
            return now - timedelta(weeks=value)
        else:
            raise ValueError(f"Unknown time unit: {unit}")

    def to_sql_where(self) -> tuple[str, list[Any]]:
        """Convert filter to SQL WHERE clause.

        Returns:
            Tuple of (WHERE clause string, parameters list).
        """
        conditions = []
        params: list[Any] = []

        if self.event_types:
            placeholders = ",".join("?" * len(self.event_types))
            conditions.append(f"event_type IN ({placeholders})")
            params.extend(t.value for t in self.event_types)

        if self.session_id:
            conditions.append("session_id = ?")
            params.append(self.session_id)

        if self.task_id:
            conditions.append("task_id = ?")
            params.append(self.task_id)

        if self.since:
            conditions.append("timestamp >= ?")
            params.append(self.since.isoformat())

        if self.until:
            conditions.append("timestamp <= ?")
            params.append(self.until.isoformat())

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        return where_clause, params
