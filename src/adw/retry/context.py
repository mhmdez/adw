"""Error context building for intelligent retries.

Formats error information to help agents understand and fix issues
on subsequent attempts.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class RetryStrategy(str, Enum):
    """Retry strategies with increasing scope."""

    SAME_APPROACH = "same_approach"  # Try again with error context
    ALTERNATIVE = "alternative"  # Ask for different solution
    SIMPLIFY = "simplify"  # Reduce task scope


@dataclass
class RetryContext:
    """Context for a retry attempt."""

    attempt_number: int
    max_attempts: int
    phase: str
    error_message: str
    strategy: RetryStrategy
    previous_attempts: list[str] | None = None
    stack_trace: str | None = None
    extra_instructions: str | None = None

    def format(self) -> str:
        """Format retry context for injection into agent prompt."""
        return build_retry_context(
            error=self.error_message,
            phase=self.phase,
            attempt_number=self.attempt_number,
            max_attempts=self.max_attempts,
            strategy=self.strategy,
            previous_attempts=self.previous_attempts,
            stack_trace=self.stack_trace,
            extra_instructions=self.extra_instructions,
        )


def build_retry_context(
    error: str,
    phase: str,
    attempt_number: int = 1,
    max_attempts: int = 3,
    strategy: RetryStrategy = RetryStrategy.SAME_APPROACH,
    previous_attempts: list[str] | None = None,
    stack_trace: str | None = None,
    extra_instructions: str | None = None,
) -> str:
    """Build retry context for agent consumption.

    Creates a formatted string that helps the agent understand:
    - What went wrong
    - How many attempts remain
    - What strategy to try

    Args:
        error: The error message that triggered the retry.
        phase: The workflow phase that failed (e.g., "implement", "test").
        attempt_number: Current attempt number (1-indexed).
        max_attempts: Maximum allowed attempts.
        strategy: The retry strategy to use.
        previous_attempts: Optional list of previous attempt summaries.
        stack_trace: Optional stack trace (will be truncated).
        extra_instructions: Optional additional instructions.

    Returns:
        Formatted retry context string.
    """
    lines = [
        "=" * 60,
        "⚠️ PREVIOUS ATTEMPT FAILED - RETRY REQUIRED",
        "=" * 60,
        "",
        f"Phase: {phase}",
        f"Attempt: {attempt_number} of {max_attempts}",
        f"Strategy: {_strategy_description(strategy)}",
        "",
        "Error:",
        _indent(error, "  "),
    ]

    # Add truncated stack trace if provided
    if stack_trace:
        truncated = _truncate_stack_trace(stack_trace)
        lines.extend(
            [
                "",
                "Stack trace (truncated):",
                _indent(truncated, "  "),
            ]
        )

    # Add previous attempts if provided
    if previous_attempts:
        lines.extend(
            [
                "",
                "Previous attempts:",
            ]
        )
        for i, attempt in enumerate(previous_attempts, 1):
            lines.append(f"  {i}. {attempt}")

    # Add strategy-specific instructions
    lines.extend(
        [
            "",
            "Instructions:",
            _indent(_strategy_instructions(strategy, attempt_number, max_attempts), "  "),
        ]
    )

    # Add extra instructions if provided
    if extra_instructions:
        lines.extend(
            [
                "",
                "Additional guidance:",
                _indent(extra_instructions, "  "),
            ]
        )

    lines.extend(
        [
            "",
            "=" * 60,
        ]
    )

    return "\n".join(lines)


def _strategy_description(strategy: RetryStrategy) -> str:
    """Get human-readable description of strategy."""
    descriptions = {
        RetryStrategy.SAME_APPROACH: "Same approach with error context",
        RetryStrategy.ALTERNATIVE: "Try alternative solution",
        RetryStrategy.SIMPLIFY: "Simplify task scope",
    }
    return descriptions.get(strategy, str(strategy))


def _strategy_instructions(
    strategy: RetryStrategy,
    attempt: int,
    max_attempts: int,
) -> str:
    """Get strategy-specific instructions."""
    remaining = max_attempts - attempt

    if strategy == RetryStrategy.SAME_APPROACH:
        return (
            f"Please fix the error above and try again.\n"
            f"You have {remaining} attempt(s) remaining.\n"
            f"Focus on addressing the specific error message."
        )
    elif strategy == RetryStrategy.ALTERNATIVE:
        return (
            f"The previous approach didn't work. Please try a different solution.\n"
            f"You have {remaining} attempt(s) remaining.\n"
            f"Consider:\n"
            f"  - A different algorithm or method\n"
            f"  - Using a different library or API\n"
            f"  - Restructuring the code differently"
        )
    elif strategy == RetryStrategy.SIMPLIFY:
        return (
            "Multiple attempts have failed. Please simplify the task.\n"
            "This is your last attempt.\n"
            "Consider:\n"
            "  - Implementing only the core functionality\n"
            "  - Removing edge case handling temporarily\n"
            "  - Breaking into smaller, testable pieces\n"
            "  - Adding TODO comments for deferred work"
        )
    else:
        return "Please address the error and try again."


def _indent(text: str, prefix: str = "  ") -> str:
    """Indent each line of text."""
    return "\n".join(prefix + line for line in text.split("\n"))


def _truncate_stack_trace(trace: str, max_lines: int = 15) -> str:
    """Truncate stack trace to avoid token overflow.

    Keeps the first few and last few lines which typically contain
    the most useful information.
    """
    lines = trace.strip().split("\n")

    if len(lines) <= max_lines:
        return trace

    # Keep first 5 and last 10 lines (usually error message is at end)
    head_lines = 5
    tail_lines = max_lines - head_lines - 1  # -1 for ellipsis

    head = lines[:head_lines]
    tail = lines[-tail_lines:]
    omitted = len(lines) - max_lines

    return "\n".join(head + [f"  ... ({omitted} lines omitted) ..."] + tail)


def select_retry_strategy(
    attempt_number: int,
    max_attempts: int = 3,
) -> RetryStrategy:
    """Select appropriate retry strategy based on attempt number.

    Default escalation:
    - Attempts 1-2: Same approach with error context
    - Attempt 3: Try alternative solution
    - Attempt 4+: Simplify scope

    Args:
        attempt_number: Current attempt (1-indexed).
        max_attempts: Maximum attempts allowed.

    Returns:
        Appropriate RetryStrategy for this attempt.
    """
    if attempt_number <= 2:
        return RetryStrategy.SAME_APPROACH
    elif attempt_number == 3:
        return RetryStrategy.ALTERNATIVE
    else:
        return RetryStrategy.SIMPLIFY


def format_test_failure_context(
    test_result: Any,  # TestResult type hint avoided for circular import
    phase: str = "test",
    attempt_number: int = 1,
    max_attempts: int = 3,
) -> str:
    """Format test failure as retry context.

    Convenience function that combines test result with retry context.

    Args:
        test_result: TestResult object from testing module.
        phase: Workflow phase name.
        attempt_number: Current attempt number.
        max_attempts: Maximum attempts.

    Returns:
        Formatted retry context string.
    """
    strategy = select_retry_strategy(attempt_number, max_attempts)

    # Build error message from test result
    error_lines = [test_result.summary()]

    if test_result.failed_tests:
        error_lines.append("")
        error_lines.append("Failed tests:")
        for ft in test_result.failed_tests[:5]:
            error_lines.append(f"  - {ft.name}: {ft.error_message}")
        if len(test_result.failed_tests) > 5:
            error_lines.append(f"  ... and {len(test_result.failed_tests) - 5} more")

    error = "\n".join(error_lines)

    # Use stderr as stack trace if available
    stack_trace = None
    if test_result.stderr:
        stack_trace = test_result.stderr

    return build_retry_context(
        error=error,
        phase=phase,
        attempt_number=attempt_number,
        max_attempts=max_attempts,
        strategy=strategy,
        stack_trace=stack_trace,
    )
