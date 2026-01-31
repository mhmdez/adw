"""Tests for test_utils module.

Tests the test utility functions created as part of workflow validation.
ADW ID: 793a7295
"""

from __future__ import annotations

import pytest

from adw.test_utils import (
    format_task_status,
    parse_task_line,
    validate_adw_id,
)


class TestValidateAdwId:
    """Tests for validate_adw_id function."""

    def test_valid_id(self) -> None:
        """Test that valid ADW IDs are accepted."""
        assert validate_adw_id("793a7295") is True
        assert validate_adw_id("abc12345") is True
        assert validate_adw_id("0885689d") is True
        assert validate_adw_id("DEADBEEF") is True

    def test_invalid_length(self) -> None:
        """Test that IDs with wrong length are rejected."""
        assert validate_adw_id("") is False
        assert validate_adw_id("123") is False
        assert validate_adw_id("123456789") is False

    def test_invalid_characters(self) -> None:
        """Test that IDs with non-hex characters are rejected."""
        assert validate_adw_id("invalid!") is False
        assert validate_adw_id("gggggggg") is False
        assert validate_adw_id("test1234") is False

    def test_invalid_type(self) -> None:
        """Test that non-string inputs are rejected."""
        assert validate_adw_id(12345678) is False  # type: ignore[arg-type]
        assert validate_adw_id(None) is False  # type: ignore[arg-type]


class TestFormatTaskStatus:
    """Tests for format_task_status function."""

    def test_ready_status(self) -> None:
        """Test formatting ready status."""
        assert format_task_status("ready") == "[]"

    def test_blocked_status(self) -> None:
        """Test formatting blocked status."""
        assert format_task_status("blocked") == "[⏰]"

    def test_in_progress_status(self) -> None:
        """Test formatting in_progress status."""
        assert format_task_status("in_progress", "793a7295") == "[🟡, 793a7295]"

    def test_completed_status(self) -> None:
        """Test formatting completed status."""
        assert format_task_status("completed", "abc12345") == "[✅, abc12345]"

    def test_failed_status(self) -> None:
        """Test formatting failed status."""
        assert format_task_status("failed", "deadbeef") == "[❌, deadbeef]"

    def test_invalid_status(self) -> None:
        """Test that invalid status raises ValueError."""
        with pytest.raises(ValueError, match="Invalid status"):
            format_task_status("invalid")

    def test_missing_adw_id(self) -> None:
        """Test that missing ADW ID for statuses that need it raises ValueError."""
        with pytest.raises(ValueError, match="ADW ID required"):
            format_task_status("in_progress")
        with pytest.raises(ValueError, match="ADW ID required"):
            format_task_status("completed")


class TestParseTaskLine:
    """Tests for parse_task_line function."""

    def test_parse_completed_task(self) -> None:
        """Test parsing completed task line."""
        result = parse_task_line("[✅, 793a7295] Create test utils")
        assert result["status"] == "completed"
        assert result["adw_id"] == "793a7295"
        assert result["description"] == "Create test utils"

    def test_parse_in_progress_task(self) -> None:
        """Test parsing in_progress task line."""
        result = parse_task_line("[🟡, abc12345] Working on feature")
        assert result["status"] == "in_progress"
        assert result["adw_id"] == "abc12345"
        assert result["description"] == "Working on feature"

    def test_parse_failed_task(self) -> None:
        """Test parsing failed task line."""
        result = parse_task_line("[❌, deadbeef] Failed task")
        assert result["status"] == "failed"
        assert result["adw_id"] == "deadbeef"
        assert result["description"] == "Failed task"

    def test_parse_blocked_task(self) -> None:
        """Test parsing blocked task line."""
        result = parse_task_line("[⏰] Blocked task")
        assert result["status"] == "blocked"
        assert result["adw_id"] is None
        assert result["description"] == "Blocked task"

    def test_parse_ready_task(self) -> None:
        """Test parsing ready task line."""
        result = parse_task_line("[] Ready task")
        assert result["status"] == "ready"
        assert result["adw_id"] is None
        assert result["description"] == "Ready task"

    def test_parse_unknown_format(self) -> None:
        """Test parsing line with unknown format."""
        result = parse_task_line("Some random text")
        assert result["status"] == "unknown"
        assert result["adw_id"] is None
        assert result["description"] == "Some random text"

    def test_parse_with_whitespace(self) -> None:
        """Test parsing handles whitespace correctly."""
        result = parse_task_line("  [✅, 793a7295]   Create test utils  ")
        assert result["status"] == "completed"
        assert result["adw_id"] == "793a7295"
        assert result["description"] == "Create test utils"
