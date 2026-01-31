"""Test Phase 5: Log Streaming Implementation."""

import json
import asyncio
from pathlib import Path
from datetime import datetime
from tempfile import TemporaryDirectory

import pytest

from src.adw.tui.log_watcher import LogWatcher, LogEvent
from src.adw.tui.log_formatter import format_event
from src.adw.tui.log_buffer import LogBuffer


class TestLogEvent:
    """Test LogEvent dataclass."""

    def test_event_creation(self):
        """Test creating a log event."""
        event = LogEvent(
            timestamp=datetime.now(),
            adw_id="abc123de",
            event_type="assistant",
            message="Test message",
            tool_name="Read",
            file_path="/test/file.py",
            phase="implement",
        )
        assert event.adw_id == "abc123de"
        assert event.event_type == "assistant"
        assert event.message == "Test message"
        assert event.tool_name == "Read"
        assert event.file_path == "/test/file.py"
        assert event.phase == "implement"


class TestLogFormatter:
    """Test log formatting."""

    def test_format_assistant_event(self):
        """Test formatting assistant message."""
        event = LogEvent(
            timestamp=datetime.now(),
            adw_id="abc123de",
            event_type="assistant",
            message="Test assistant message",
        )
        formatted = format_event(event)
        assert "💬" in str(formatted)
        assert "abc123de" in str(formatted)

    def test_format_tool_event(self):
        """Test formatting tool use."""
        event = LogEvent(
            timestamp=datetime.now(),
            adw_id="abc123de",
            event_type="tool",
            message="Using Read",
            tool_name="Read",
        )
        formatted = format_event(event)
        assert "🔧" in str(formatted)

    def test_format_error_event(self):
        """Test formatting error."""
        event = LogEvent(
            timestamp=datetime.now(),
            adw_id="abc123de",
            event_type="error",
            message="Something went wrong",
        )
        formatted = format_event(event)
        assert "❌" in str(formatted)


class TestLogBuffer:
    """Test log buffering."""

    def test_buffer_add_and_retrieve(self):
        """Test adding and retrieving events."""
        buffer = LogBuffer(max_lines=100)
        event = LogEvent(
            timestamp=datetime.now(),
            adw_id="abc123de",
            event_type="assistant",
            message="Test message",
        )

        line = buffer.add(event)
        assert line is not None

        # Test retrieving all
        all_lines = buffer.get_all(count=50)
        assert len(all_lines) == 1

        # Test retrieving for specific agent
        agent_lines = buffer.get_for_agent("abc123de", count=50)
        assert len(agent_lines) == 1

    def test_buffer_max_capacity(self):
        """Test buffer capacity limits."""
        buffer = LogBuffer(max_lines=5)

        # Add 10 events
        for i in range(10):
            event = LogEvent(
                timestamp=datetime.now(),
                adw_id="abc123de",
                event_type="assistant",
                message=f"Message {i}",
            )
            buffer.add(event)

        # Should only keep last 5
        all_lines = buffer.get_all(count=100)
        assert len(all_lines) == 5

    def test_buffer_per_agent_separation(self):
        """Test that different agents have separate buffers."""
        buffer = LogBuffer()

        event1 = LogEvent(
            timestamp=datetime.now(),
            adw_id="agent001",
            event_type="assistant",
            message="Agent 1 message",
        )
        event2 = LogEvent(
            timestamp=datetime.now(),
            adw_id="agent002",
            event_type="assistant",
            message="Agent 2 message",
        )

        buffer.add(event1)
        buffer.add(event2)

        agent1_lines = buffer.get_for_agent("agent001")
        agent2_lines = buffer.get_for_agent("agent002")

        assert len(agent1_lines) == 1
        assert len(agent2_lines) == 1

    def test_buffer_clear(self):
        """Test clearing buffer."""
        buffer = LogBuffer()
        event = LogEvent(
            timestamp=datetime.now(),
            adw_id="abc123de",
            event_type="assistant",
            message="Test",
        )
        buffer.add(event)

        # Clear specific agent
        buffer.clear("abc123de")
        assert len(buffer.get_for_agent("abc123de")) == 0

        # Add again and clear all
        buffer.add(event)
        buffer.clear()
        assert len(buffer.get_all()) == 0


class TestLogWatcher:
    """Test log watcher functionality."""

    def test_watcher_initialization(self):
        """Test watcher can be created."""
        with TemporaryDirectory() as tmpdir:
            watcher = LogWatcher(agents_dir=Path(tmpdir))
            assert watcher.agents_dir == Path(tmpdir)
            assert watcher._running is False

    def test_subscribe_and_unsubscribe(self):
        """Test subscription management."""
        watcher = LogWatcher()
        callback = lambda event: None

        # Subscribe
        watcher.subscribe("abc123de", callback)
        assert "abc123de" in watcher._subscribers
        assert callback in watcher._subscribers["abc123de"]

        # Unsubscribe
        watcher.unsubscribe("abc123de", callback)
        assert callback not in watcher._subscribers["abc123de"]

    def test_subscribe_all(self):
        """Test subscribing to all events."""
        watcher = LogWatcher()
        callback = lambda event: None

        watcher.subscribe_all(callback)
        assert "*" in watcher._subscribers
        assert callback in watcher._subscribers["*"]

    def test_parse_assistant_event(self):
        """Test parsing assistant message."""
        watcher = LogWatcher()
        data = {
            "type": "assistant",
            "message": {
                "content": [{"type": "text", "text": "Hello world"}]
            },
        }

        event = watcher._parse_event("abc123de", data)
        assert event is not None
        assert event.event_type == "assistant"
        assert event.message == "Hello world"

    def test_parse_tool_use_event(self):
        """Test parsing tool use."""
        watcher = LogWatcher()
        data = {"type": "tool_use", "tool": {"name": "Read"}}

        event = watcher._parse_event("abc123de", data)
        assert event is not None
        assert event.event_type == "tool"
        assert event.tool_name == "Read"

    def test_parse_error_event(self):
        """Test parsing error."""
        watcher = LogWatcher()
        data = {"type": "error", "error": {"message": "Something failed"}}

        event = watcher._parse_event("abc123de", data)
        assert event is not None
        assert event.event_type == "error"
        assert event.message == "Something failed"

    def test_file_change_detection(self):
        """Test detecting file changes."""
        with TemporaryDirectory() as tmpdir:
            agents_dir = Path(tmpdir)
            agent_dir = agents_dir / "abc123de"
            agent_dir.mkdir()

            watcher = LogWatcher(agents_dir=agents_dir)

            # Track received events
            received_events = []

            def callback(event):
                received_events.append(event)

            watcher.subscribe_all(callback)

            # Write a JSONL log file
            log_file = agent_dir / "agent.jsonl"
            log_file.write_text(
                json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "Test"}]}})
                + "\n"
            )

            # Handle the file change manually (simulating watch loop)
            asyncio.run(watcher._handle_file_change("abc123de", log_file))

            # Should have received the event
            assert len(received_events) == 1
            assert received_events[0].message == "Test"

    def test_notify_subscribers(self):
        """Test notification system."""
        watcher = LogWatcher()

        # Track calls
        specific_calls = []
        all_calls = []

        def specific_cb(event):
            specific_calls.append(event)

        def all_cb(event):
            all_calls.append(event)

        watcher.subscribe("abc123de", specific_cb)
        watcher.subscribe_all(all_cb)

        # Create and notify event
        event = LogEvent(
            timestamp=datetime.now(),
            adw_id="abc123de",
            event_type="assistant",
            message="Test",
        )

        watcher._notify("abc123de", event)

        # Both should have received it
        assert len(specific_calls) == 1
        assert len(all_calls) == 1


def test_integration():
    """Test full integration of log streaming components."""
    # Create watcher
    watcher = LogWatcher()

    # Create buffer
    buffer = LogBuffer()

    # Setup subscription
    def handle_event(event):
        buffer.add(event)

    watcher.subscribe_all(handle_event)

    # Create and notify event
    event = LogEvent(
        timestamp=datetime.now(),
        adw_id="abc123de",
        event_type="assistant",
        message="Integration test",
    )

    watcher._notify("abc123de", event)

    # Check buffer received it
    lines = buffer.get_all()
    assert len(lines) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
