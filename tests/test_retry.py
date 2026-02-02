"""Tests for retry system."""

from pathlib import Path

import pytest

from adw.retry import build_retry_context, RetryStrategy, generate_escalation_report
from adw.retry.context import (
    select_retry_strategy,
    _truncate_stack_trace,
    _strategy_description,
    RetryContext,
)
from adw.retry.escalation import AttemptRecord, EscalationReport


class TestRetryContext:
    """Tests for retry context building."""

    def test_build_basic_context(self) -> None:
        """Test basic context building."""
        context = build_retry_context(
            error="TypeError: 'NoneType' has no attribute 'strip'",
            phase="implement",
        )
        assert "PREVIOUS ATTEMPT FAILED" in context
        assert "implement" in context
        assert "TypeError" in context

    def test_build_context_with_attempt_number(self) -> None:
        """Test context with attempt tracking."""
        context = build_retry_context(
            error="Test error",
            phase="test",
            attempt_number=2,
            max_attempts=3,
        )
        assert "Attempt: 2 of 3" in context
        assert "1 attempt(s) remaining" in context

    def test_build_context_with_strategy(self) -> None:
        """Test context with different strategies."""
        context = build_retry_context(
            error="Error",
            phase="implement",
            strategy=RetryStrategy.ALTERNATIVE,
        )
        assert "alternative" in context.lower()
        assert "different solution" in context.lower()

    def test_build_context_simplify_strategy(self) -> None:
        """Test context with simplify strategy."""
        context = build_retry_context(
            error="Error",
            phase="implement",
            strategy=RetryStrategy.SIMPLIFY,
        )
        assert "simplify" in context.lower()

    def test_build_context_with_stack_trace(self) -> None:
        """Test context with stack trace."""
        stack_trace = """Traceback (most recent call last):
  File "test.py", line 10, in test_func
    raise ValueError("test")
ValueError: test"""

        context = build_retry_context(
            error="Test error",
            phase="test",
            stack_trace=stack_trace,
        )
        assert "Stack trace" in context
        assert "ValueError" in context

    def test_build_context_with_previous_attempts(self) -> None:
        """Test context with previous attempt history."""
        context = build_retry_context(
            error="Error",
            phase="implement",
            previous_attempts=[
                "Attempt 1: TypeError",
                "Attempt 2: ValueError",
            ],
        )
        assert "Previous attempts" in context
        assert "TypeError" in context
        assert "ValueError" in context

    def test_build_context_with_extra_instructions(self) -> None:
        """Test context with additional instructions."""
        context = build_retry_context(
            error="Error",
            phase="implement",
            extra_instructions="Focus on the database connection",
        )
        assert "Additional guidance" in context
        assert "database connection" in context


class TestRetryStrategy:
    """Tests for retry strategy selection."""

    def test_select_strategy_first_attempt(self) -> None:
        """Test strategy for first attempt."""
        strategy = select_retry_strategy(1, 3)
        assert strategy == RetryStrategy.SAME_APPROACH

    def test_select_strategy_second_attempt(self) -> None:
        """Test strategy for second attempt."""
        strategy = select_retry_strategy(2, 3)
        assert strategy == RetryStrategy.SAME_APPROACH

    def test_select_strategy_third_attempt(self) -> None:
        """Test strategy for third attempt."""
        strategy = select_retry_strategy(3, 4)
        assert strategy == RetryStrategy.ALTERNATIVE

    def test_select_strategy_final_attempt(self) -> None:
        """Test strategy for final attempt."""
        strategy = select_retry_strategy(4, 4)
        assert strategy == RetryStrategy.SIMPLIFY

    def test_strategy_descriptions(self) -> None:
        """Test strategy descriptions."""
        assert "error context" in _strategy_description(RetryStrategy.SAME_APPROACH).lower()
        assert "alternative" in _strategy_description(RetryStrategy.ALTERNATIVE).lower()
        assert "simplify" in _strategy_description(RetryStrategy.SIMPLIFY).lower()


class TestStackTraceTruncation:
    """Tests for stack trace truncation."""

    def test_short_trace_unchanged(self) -> None:
        """Test that short traces are not truncated."""
        trace = "Line 1\nLine 2\nLine 3"
        truncated = _truncate_stack_trace(trace, max_lines=10)
        assert truncated == trace

    def test_long_trace_truncated(self) -> None:
        """Test that long traces are truncated."""
        lines = [f"Line {i}" for i in range(30)]
        trace = "\n".join(lines)
        truncated = _truncate_stack_trace(trace, max_lines=15)

        # Should contain first few and last few
        assert "Line 0" in truncated
        assert "Line 29" in truncated
        assert "omitted" in truncated


class TestRetryContextClass:
    """Tests for RetryContext dataclass."""

    def test_format_method(self) -> None:
        """Test format method."""
        ctx = RetryContext(
            attempt_number=2,
            max_attempts=3,
            phase="test",
            error_message="Assertion failed",
            strategy=RetryStrategy.SAME_APPROACH,
        )
        formatted = ctx.format()
        assert "Assertion failed" in formatted
        assert "test" in formatted


class TestAttemptRecord:
    """Tests for AttemptRecord."""

    def test_creation(self) -> None:
        """Test record creation."""
        record = AttemptRecord(
            attempt_number=1,
            phase="implement",
            error_message="Error",
            strategy="same_approach",
            duration_seconds=5.5,
        )
        assert record.attempt_number == 1
        assert record.phase == "implement"
        assert record.duration_seconds == 5.5
        assert record.timestamp is not None


class TestEscalationReport:
    """Tests for escalation reports."""

    def test_create_report(self) -> None:
        """Test report creation."""
        attempts = [
            AttemptRecord(
                attempt_number=1,
                phase="test",
                error_message="Test failed",
                strategy="same_approach",
                duration_seconds=10.0,
            ),
            AttemptRecord(
                attempt_number=2,
                phase="test",
                error_message="Test failed again",
                strategy="alternative",
                duration_seconds=15.0,
            ),
        ]

        report = EscalationReport(
            task_id="abc123",
            task_description="Implement feature X",
            workflow_type="sdlc",
            attempts=attempts,
            suggested_actions=["Review the code", "Check dependencies"],
        )

        assert report.task_id == "abc123"
        assert len(report.attempts) == 2
        assert len(report.suggested_actions) == 2

    def test_to_markdown(self) -> None:
        """Test markdown conversion."""
        attempts = [
            AttemptRecord(
                attempt_number=1,
                phase="test",
                error_message="Test failed",
                strategy="same_approach",
                duration_seconds=10.0,
            ),
        ]

        report = EscalationReport(
            task_id="abc123",
            task_description="Implement feature X",
            workflow_type="sdlc",
            attempts=attempts,
            suggested_actions=["Review the code"],
            modified_files=["src/module.py"],
        )

        md = report.to_markdown()

        assert "# Escalation Report" in md
        assert "abc123" in md
        assert "Implement feature X" in md
        assert "Attempt 1" in md
        assert "src/module.py" in md
        assert "Review the code" in md

    def test_generate_escalation_report(self, tmp_path: Path) -> None:
        """Test generate_escalation_report function."""
        attempts = [
            AttemptRecord(
                attempt_number=1,
                phase="test",
                error_message="ImportError: No module named 'missing'",
                strategy="same_approach",
                duration_seconds=5.0,
            ),
        ]

        report = generate_escalation_report(
            task_id="def456",
            task_description="Add authentication",
            workflow_type="standard",
            attempts=attempts,
            modified_files=["src/auth.py"],
            output_dir=tmp_path,
        )

        # Check report was created
        assert report.task_id == "def456"

        # Check suggestions include import-related advice
        suggestions_text = " ".join(report.suggested_actions).lower()
        assert "import" in suggestions_text or "dependencies" in suggestions_text

        # Check file was written
        report_file = tmp_path / "escalation.md"
        assert report_file.exists()
        content = report_file.read_text()
        assert "def456" in content

    def test_generate_suggestions_timeout(self) -> None:
        """Test suggestions for timeout errors."""
        attempts = [
            AttemptRecord(
                attempt_number=1,
                phase="test",
                error_message="timeout after 300 seconds",
                strategy="same_approach",
                duration_seconds=300.0,
            ),
        ]

        report = generate_escalation_report(
            task_id="timeout123",
            task_description="Run long test",
            workflow_type="test",
            attempts=attempts,
        )

        suggestions_text = " ".join(report.suggested_actions).lower()
        assert "timeout" in suggestions_text or "chunk" in suggestions_text

    def test_generate_suggestions_permission(self) -> None:
        """Test suggestions for permission errors."""
        attempts = [
            AttemptRecord(
                attempt_number=1,
                phase="implement",
                error_message="Permission denied: /etc/config",
                strategy="same_approach",
                duration_seconds=1.0,
            ),
        ]

        report = generate_escalation_report(
            task_id="perm123",
            task_description="Write config",
            workflow_type="simple",
            attempts=attempts,
        )

        suggestions_text = " ".join(report.suggested_actions).lower()
        assert "permission" in suggestions_text
