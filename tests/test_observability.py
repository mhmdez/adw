"""Tests for the observability module.

Tests for event database, models, and querying functionality.
"""

from __future__ import annotations

import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from adw.observability import (
    Event,
    EventDB,
    EventFilter,
    EventType,
    Session,
    SessionStatus,
    get_db,
    get_events,
    get_session,
    log_event,
    start_session,
    end_session,
)


# =============================================================================
# Model Tests
# =============================================================================


class TestEventType:
    """Tests for EventType enum."""

    def test_tool_events(self):
        """Test tool event types."""
        assert EventType.TOOL_START == "tool_start"
        assert EventType.TOOL_END == "tool_end"
        assert EventType.TOOL_ERROR == "tool_error"

    def test_session_events(self):
        """Test session event types."""
        assert EventType.SESSION_START == "session_start"
        assert EventType.SESSION_END == "session_end"

    def test_task_events(self):
        """Test task event types."""
        assert EventType.TASK_STARTED == "task_started"
        assert EventType.TASK_COMPLETED == "task_completed"
        assert EventType.TASK_FAILED == "task_failed"

    def test_from_string(self):
        """Test creating EventType from string."""
        assert EventType("tool_start") == EventType.TOOL_START
        assert EventType("error") == EventType.ERROR


class TestSessionStatus:
    """Tests for SessionStatus enum."""

    def test_status_values(self):
        """Test status values."""
        assert SessionStatus.RUNNING == "running"
        assert SessionStatus.COMPLETED == "completed"
        assert SessionStatus.FAILED == "failed"
        assert SessionStatus.CANCELLED == "cancelled"


class TestEvent:
    """Tests for Event model."""

    def test_create_event(self):
        """Test creating an event."""
        event = Event(
            event_type=EventType.TOOL_START,
            session_id="session-123",
            task_id="abc12345",
            data={"tool_name": "Read"},
        )
        assert event.event_type == EventType.TOOL_START
        assert event.session_id == "session-123"
        assert event.task_id == "abc12345"
        assert event.data["tool_name"] == "Read"
        assert event.timestamp is not None

    def test_event_to_dict(self):
        """Test converting event to dict."""
        event = Event(
            event_type=EventType.ERROR,
            task_id="abc12345",
            data={"message": "Something went wrong"},
        )
        d = event.to_dict()
        assert d["event_type"] == "error"
        assert d["task_id"] == "abc12345"
        assert "message" in d["data"]

    def test_event_from_dict(self):
        """Test creating event from dict."""
        d = {
            "id": 1,
            "timestamp": "2026-01-15T10:30:00",
            "event_type": "tool_start",
            "session_id": "session-456",
            "task_id": None,
            "data": '{"tool_name": "Write"}',
        }
        event = Event.from_dict(d)
        assert event.id == 1
        assert event.event_type == EventType.TOOL_START
        assert event.data["tool_name"] == "Write"

    def test_event_str(self):
        """Test event string representation."""
        event = Event(
            event_type=EventType.TASK_COMPLETED,
            task_id="abc12345de",
        )
        s = str(event)
        assert "task_completed" in s
        assert "abc12345" in s  # First 8 chars of task_id


class TestSession:
    """Tests for Session model."""

    def test_create_session(self):
        """Test creating a session."""
        session = Session(
            id="session-123",
            task_id="abc12345",
            status=SessionStatus.RUNNING,
        )
        assert session.id == "session-123"
        assert session.task_id == "abc12345"
        assert session.status == SessionStatus.RUNNING
        assert session.start_time is not None
        assert session.end_time is None

    def test_session_duration_running(self):
        """Test duration of running session."""
        session = Session(
            id="session-123",
            start_time=datetime.now() - timedelta(minutes=5),
        )
        duration = session.duration
        assert duration is not None
        assert duration.total_seconds() >= 300  # At least 5 minutes

    def test_session_duration_completed(self):
        """Test duration of completed session."""
        start = datetime(2026, 1, 15, 10, 0, 0)
        end = datetime(2026, 1, 15, 10, 30, 0)
        session = Session(
            id="session-123",
            start_time=start,
            end_time=end,
            status=SessionStatus.COMPLETED,
        )
        duration = session.duration
        assert duration is not None
        assert duration.total_seconds() == 1800  # 30 minutes

    def test_session_duration_str(self):
        """Test human-readable duration string."""
        start = datetime(2026, 1, 15, 10, 0, 0)
        end = datetime(2026, 1, 15, 11, 30, 45)
        session = Session(
            id="session-123",
            start_time=start,
            end_time=end,
            status=SessionStatus.COMPLETED,
        )
        assert "1h" in session.duration_str
        assert "30m" in session.duration_str
        assert "45s" in session.duration_str

    def test_session_to_dict(self):
        """Test converting session to dict."""
        session = Session(
            id="session-123",
            task_id="abc12345",
            metadata={"workflow": "sdlc"},
        )
        d = session.to_dict()
        assert d["id"] == "session-123"
        assert d["task_id"] == "abc12345"
        assert d["status"] == "running"
        assert "workflow" in d["metadata"]

    def test_session_from_dict(self):
        """Test creating session from dict."""
        d = {
            "id": "session-456",
            "start_time": "2026-01-15T10:00:00",
            "end_time": "2026-01-15T10:30:00",
            "task_id": "def67890",
            "status": "completed",
            "metadata": "{}",
        }
        session = Session.from_dict(d)
        assert session.id == "session-456"
        assert session.status == SessionStatus.COMPLETED
        assert session.end_time is not None


class TestEventFilter:
    """Tests for EventFilter model."""

    def test_default_filter(self):
        """Test default filter values."""
        f = EventFilter()
        assert f.limit == 100
        assert f.offset == 0
        assert f.event_types is None
        assert f.session_id is None

    def test_filter_with_event_types(self):
        """Test filter with event types."""
        f = EventFilter(event_types=[EventType.TOOL_START, EventType.TOOL_END])
        where, params = f.to_sql_where()
        assert "event_type IN" in where
        assert "tool_start" in params
        assert "tool_end" in params

    def test_filter_with_time_range(self):
        """Test filter with time range."""
        now = datetime.now()
        since = now - timedelta(hours=1)
        f = EventFilter(since=since)
        where, params = f.to_sql_where()
        assert "timestamp >=" in where

    def test_from_time_string_hours(self):
        """Test parsing hour time string."""
        dt = EventFilter.from_time_string("2h")
        expected = datetime.now() - timedelta(hours=2)
        # Allow 1 second tolerance
        assert abs((dt - expected).total_seconds()) < 1

    def test_from_time_string_minutes(self):
        """Test parsing minute time string."""
        dt = EventFilter.from_time_string("30m")
        expected = datetime.now() - timedelta(minutes=30)
        assert abs((dt - expected).total_seconds()) < 1

    def test_from_time_string_days(self):
        """Test parsing day time string."""
        dt = EventFilter.from_time_string("7d")
        expected = datetime.now() - timedelta(days=7)
        assert abs((dt - expected).total_seconds()) < 1

    def test_from_time_string_weeks(self):
        """Test parsing week time string."""
        dt = EventFilter.from_time_string("2w")
        expected = datetime.now() - timedelta(weeks=2)
        assert abs((dt - expected).total_seconds()) < 1

    def test_from_time_string_invalid(self):
        """Test invalid time string."""
        with pytest.raises(ValueError):
            EventFilter.from_time_string("xyz")

    def test_from_time_string_empty(self):
        """Test empty time string."""
        with pytest.raises(ValueError):
            EventFilter.from_time_string("")


# =============================================================================
# Database Tests
# =============================================================================


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_events.db"
        db = EventDB(db_path)
        yield db
        db.close()


class TestEventDB:
    """Tests for EventDB class."""

    def test_create_db(self, temp_db):
        """Test creating a database."""
        assert temp_db.db_path.exists()

    def test_log_event(self, temp_db):
        """Test logging an event."""
        event_id = temp_db.log_event(
            event_type=EventType.TOOL_START,
            session_id="session-123",
            task_id="abc12345",
            data={"tool_name": "Read"},
        )
        assert event_id > 0

    def test_log_event_string_type(self, temp_db):
        """Test logging event with string type."""
        event_id = temp_db.log_event(
            event_type="error",
            data={"message": "Test error"},
        )
        assert event_id > 0

    def test_get_events_empty(self, temp_db):
        """Test getting events from empty database."""
        events = temp_db.get_events()
        assert events == []

    def test_get_events_with_data(self, temp_db):
        """Test getting events."""
        temp_db.log_event(EventType.TOOL_START, data={"tool": "Read"})
        temp_db.log_event(EventType.TOOL_END, data={"tool": "Read"})
        temp_db.log_event(EventType.ERROR, data={"message": "Failed"})

        events = temp_db.get_events()
        assert len(events) == 3

    def test_get_events_filtered_by_type(self, temp_db):
        """Test filtering events by type."""
        temp_db.log_event(EventType.TOOL_START)
        temp_db.log_event(EventType.TOOL_END)
        temp_db.log_event(EventType.ERROR)

        f = EventFilter(event_types=[EventType.ERROR])
        events = temp_db.get_events(f)
        assert len(events) == 1
        assert events[0].event_type == EventType.ERROR

    def test_get_events_filtered_by_session(self, temp_db):
        """Test filtering events by session."""
        temp_db.log_event(EventType.TOOL_START, session_id="session-1")
        temp_db.log_event(EventType.TOOL_START, session_id="session-2")

        f = EventFilter(session_id="session-1")
        events = temp_db.get_events(f)
        assert len(events) == 1
        assert events[0].session_id == "session-1"

    def test_get_events_filtered_by_task(self, temp_db):
        """Test filtering events by task."""
        temp_db.log_event(EventType.TASK_STARTED, task_id="task-1")
        temp_db.log_event(EventType.TASK_STARTED, task_id="task-2")

        f = EventFilter(task_id="task-1")
        events = temp_db.get_events(f)
        assert len(events) == 1
        assert events[0].task_id == "task-1"

    def test_get_events_filtered_by_time(self, temp_db):
        """Test filtering events by time."""
        # Log event in the past
        old_time = datetime.now() - timedelta(hours=2)
        temp_db.log_event(EventType.INFO, timestamp=old_time)

        # Log recent event
        temp_db.log_event(EventType.INFO)

        f = EventFilter(since=datetime.now() - timedelta(hours=1))
        events = temp_db.get_events(f)
        assert len(events) == 1

    def test_get_events_with_limit(self, temp_db):
        """Test event limit."""
        for i in range(10):
            temp_db.log_event(EventType.INFO, data={"i": i})

        f = EventFilter(limit=5)
        events = temp_db.get_events(f)
        assert len(events) == 5

    def test_get_event_count(self, temp_db):
        """Test getting event count."""
        for i in range(10):
            temp_db.log_event(EventType.INFO)

        count = temp_db.get_event_count()
        assert count == 10

    def test_get_event_count_filtered(self, temp_db):
        """Test getting filtered event count."""
        for i in range(5):
            temp_db.log_event(EventType.INFO)
        for i in range(3):
            temp_db.log_event(EventType.ERROR)

        f = EventFilter(event_types=[EventType.ERROR])
        count = temp_db.get_event_count(f)
        assert count == 3

    def test_start_session(self, temp_db):
        """Test starting a session."""
        session = temp_db.start_session(
            session_id="session-123",
            task_id="abc12345",
            metadata={"workflow": "sdlc"},
        )
        assert session.id == "session-123"
        assert session.task_id == "abc12345"
        assert session.status == SessionStatus.RUNNING

    def test_end_session(self, temp_db):
        """Test ending a session."""
        temp_db.start_session("session-123")
        session = temp_db.end_session("session-123", SessionStatus.COMPLETED)

        assert session is not None
        assert session.status == SessionStatus.COMPLETED
        assert session.end_time is not None

    def test_end_session_not_found(self, temp_db):
        """Test ending non-existent session."""
        result = temp_db.end_session("nonexistent")
        assert result is None

    def test_get_session(self, temp_db):
        """Test getting a session."""
        temp_db.start_session("session-123", task_id="abc12345")
        session = temp_db.get_session("session-123")

        assert session is not None
        assert session.id == "session-123"
        assert session.task_id == "abc12345"

    def test_get_session_not_found(self, temp_db):
        """Test getting non-existent session."""
        session = temp_db.get_session("nonexistent")
        assert session is None

    def test_get_sessions(self, temp_db):
        """Test getting multiple sessions."""
        temp_db.start_session("session-1", task_id="task-1")
        temp_db.start_session("session-2", task_id="task-2")
        temp_db.end_session("session-2", SessionStatus.COMPLETED)

        sessions = temp_db.get_sessions()
        assert len(sessions) == 2

    def test_get_sessions_filtered_by_task(self, temp_db):
        """Test filtering sessions by task."""
        temp_db.start_session("session-1", task_id="task-1")
        temp_db.start_session("session-2", task_id="task-2")

        sessions = temp_db.get_sessions(task_id="task-1")
        assert len(sessions) == 1
        assert sessions[0].task_id == "task-1"

    def test_get_sessions_filtered_by_status(self, temp_db):
        """Test filtering sessions by status."""
        temp_db.start_session("session-1")
        temp_db.start_session("session-2")
        temp_db.end_session("session-1", SessionStatus.COMPLETED)

        sessions = temp_db.get_sessions(status=SessionStatus.RUNNING)
        assert len(sessions) == 1
        assert sessions[0].id == "session-2"

    def test_get_session_events(self, temp_db):
        """Test getting events for a session."""
        temp_db.log_event(EventType.TOOL_START, session_id="session-1")
        temp_db.log_event(EventType.TOOL_END, session_id="session-1")
        temp_db.log_event(EventType.ERROR, session_id="session-2")

        events = temp_db.get_session_events("session-1")
        assert len(events) == 2
        for event in events:
            assert event.session_id == "session-1"

    def test_get_recent_events(self, temp_db):
        """Test getting recent events."""
        for i in range(100):
            temp_db.log_event(EventType.INFO, data={"i": i})

        events = temp_db.get_recent_events(limit=10)
        assert len(events) == 10

    def test_cleanup_old_events(self, temp_db):
        """Test cleaning up old events."""
        # Log old event
        old_time = datetime.now() - timedelta(days=60)
        temp_db.log_event(EventType.INFO, timestamp=old_time)

        # Log recent event
        temp_db.log_event(EventType.INFO)

        deleted = temp_db.cleanup_old_events(days=30)
        assert deleted == 1

        events = temp_db.get_events()
        assert len(events) == 1

    def test_get_event_summary(self, temp_db):
        """Test getting event summary."""
        for i in range(5):
            temp_db.log_event(EventType.TOOL_START)
        for i in range(3):
            temp_db.log_event(EventType.ERROR)
        temp_db.log_event(EventType.INFO)

        summary = temp_db.get_event_summary()
        assert summary["tool_start"] == 5
        assert summary["error"] == 3
        assert summary["info"] == 1

    def test_get_event_summary_since(self, temp_db):
        """Test event summary with time filter."""
        # Log old event
        old_time = datetime.now() - timedelta(hours=2)
        temp_db.log_event(EventType.ERROR, timestamp=old_time)

        # Log recent events
        temp_db.log_event(EventType.INFO)
        temp_db.log_event(EventType.INFO)

        summary = temp_db.get_event_summary(since=datetime.now() - timedelta(hours=1))
        assert summary.get("error") is None
        assert summary.get("info") == 2

    def test_session_logs_start_event(self, temp_db):
        """Test that starting a session logs a session_start event."""
        temp_db.start_session("session-123")

        events = temp_db.get_events(
            EventFilter(event_types=[EventType.SESSION_START])
        )
        assert len(events) == 1
        assert events[0].session_id == "session-123"

    def test_session_logs_end_event(self, temp_db):
        """Test that ending a session logs a session_end event."""
        temp_db.start_session("session-123")
        temp_db.end_session("session-123", SessionStatus.COMPLETED)

        events = temp_db.get_events(
            EventFilter(event_types=[EventType.SESSION_END])
        )
        assert len(events) == 1
        assert events[0].session_id == "session-123"


# =============================================================================
# Global Function Tests
# =============================================================================


class TestGlobalFunctions:
    """Tests for global convenience functions."""

    def test_get_db_singleton(self):
        """Test that get_db returns a singleton."""
        # Note: This test may interfere with other tests if run in parallel
        # as it uses the global instance
        from adw.observability import db as db_module

        # Reset global instance
        db_module._db_instance = None

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db1 = db_module.get_db(db_path)
            db2 = db_module.get_db()

            assert db1 is db2

            # Cleanup
            db1.close()
            db_module._db_instance = None


# =============================================================================
# Integration Tests
# =============================================================================


class TestIntegration:
    """Integration tests for the observability module."""

    def test_full_session_lifecycle(self, temp_db):
        """Test a full session lifecycle."""
        # Start session
        session = temp_db.start_session(
            session_id="session-full-test",
            task_id="abc12345",
            metadata={"workflow": "sdlc"},
        )
        assert session.status == SessionStatus.RUNNING

        # Log some events
        temp_db.log_event(
            EventType.TOOL_START,
            session_id="session-full-test",
            task_id="abc12345",
            data={"tool_name": "Read"},
        )
        temp_db.log_event(
            EventType.TOOL_END,
            session_id="session-full-test",
            task_id="abc12345",
            data={"tool_name": "Read", "success": True},
        )

        # End session
        session = temp_db.end_session("session-full-test", SessionStatus.COMPLETED)
        assert session is not None
        assert session.status == SessionStatus.COMPLETED

        # Verify all events
        events = temp_db.get_session_events("session-full-test")
        assert len(events) == 4  # start, tool_start, tool_end, end

        event_types = [e.event_type for e in events]
        assert EventType.SESSION_START in event_types
        assert EventType.SESSION_END in event_types
        assert EventType.TOOL_START in event_types
        assert EventType.TOOL_END in event_types

    def test_multiple_sessions_filtering(self, temp_db):
        """Test filtering across multiple sessions."""
        # Create multiple sessions
        temp_db.start_session("session-1", task_id="task-1")
        temp_db.start_session("session-2", task_id="task-2")

        # Log events for each session
        for i in range(5):
            temp_db.log_event(EventType.TOOL_START, session_id="session-1")
        for i in range(3):
            temp_db.log_event(EventType.TOOL_START, session_id="session-2")

        # End sessions
        temp_db.end_session("session-1", SessionStatus.COMPLETED)
        temp_db.end_session("session-2", SessionStatus.FAILED)

        # Test filtering
        s1_events = temp_db.get_session_events("session-1")
        s2_events = temp_db.get_session_events("session-2")

        # Each session has: start event, tool events, end event
        assert len(s1_events) == 7  # 1 start + 5 tools + 1 end
        assert len(s2_events) == 5  # 1 start + 3 tools + 1 end

        # Verify session status
        s1 = temp_db.get_session("session-1")
        s2 = temp_db.get_session("session-2")
        assert s1.status == SessionStatus.COMPLETED
        assert s2.status == SessionStatus.FAILED

    def test_event_data_persistence(self, temp_db):
        """Test that event data is properly persisted and retrieved."""
        complex_data = {
            "tool_name": "Bash",
            "command": "echo 'hello world'",
            "exit_code": 0,
            "output": "hello world",
            "nested": {
                "key": "value",
                "list": [1, 2, 3],
            },
        }

        event_id = temp_db.log_event(
            EventType.TOOL_END,
            data=complex_data,
        )

        events = temp_db.get_events()
        assert len(events) == 1

        retrieved_data = events[0].data
        assert retrieved_data["tool_name"] == "Bash"
        assert retrieved_data["command"] == "echo 'hello world'"
        assert retrieved_data["nested"]["key"] == "value"
        assert retrieved_data["nested"]["list"] == [1, 2, 3]
