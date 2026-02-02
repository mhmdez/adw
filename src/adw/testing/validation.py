"""Test validation integration for workflows.

Provides high-level test validation that can be integrated into
SDLC and other workflows with automatic retry support.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from ..retry.context import (
    format_test_failure_context,
    select_retry_strategy,
)
from ..retry.escalation import (
    AttemptRecord,
    EscalationReport,
    generate_escalation_report,
)
from .detector import detect_test_framework
from .models import TestResult
from .runner import run_tests

logger = logging.getLogger(__name__)


@dataclass
class ValidationConfig:
    """Configuration for test validation."""

    max_retries: int = 3
    timeout_seconds: int = 300
    skip_tests: bool = False
    test_command: str | None = None  # Auto-detect if None
    retry_delay_seconds: int = 2
    exponential_backoff: bool = True


@dataclass
class ValidationResult:
    """Result of test validation with retry support."""

    success: bool
    test_results: list[TestResult] = field(default_factory=list)
    total_attempts: int = 0
    final_test_result: TestResult | None = None
    escalation_report: EscalationReport | None = None
    retry_context: str | None = None  # Context for next retry if needed

    @property
    def needs_retry(self) -> bool:
        """Check if validation needs retry."""
        return not self.success and self.retry_context is not None

    def summary(self) -> str:
        """Generate summary string."""
        if self.success:
            if self.final_test_result:
                return f"✅ {self.final_test_result.summary()}"
            return "✅ Tests passed"
        else:
            if self.final_test_result:
                return f"❌ {self.final_test_result.summary()} after {self.total_attempts} attempts"
            return f"❌ Tests failed after {self.total_attempts} attempts"


def validate_tests(
    path: Path | None = None,
    config: ValidationConfig | None = None,
    on_progress: Callable[[str], None] | None = None,
    task_id: str | None = None,
    task_description: str | None = None,
) -> ValidationResult:
    """Run tests and return validation result.

    This is a single-shot validation without retries. Use validate_with_retry
    for retry support within the same function, or use the retry_context
    from the result to implement external retry logic.

    Args:
        path: Working directory. Defaults to current directory.
        config: Validation configuration.
        on_progress: Optional progress callback.
        task_id: Optional task ID for logging.
        task_description: Optional task description for escalation.

    Returns:
        ValidationResult with test outcome.
    """
    config = config or ValidationConfig()

    if config.skip_tests:
        if on_progress:
            on_progress("Test validation skipped (--no-tests)")
        return ValidationResult(success=True)

    if path is None:
        path = Path.cwd()

    # Detect or use configured test command
    test_command = config.test_command
    if test_command is None:
        framework_info = detect_test_framework(path)
        if framework_info is None:
            if on_progress:
                on_progress("No test framework detected, skipping tests")
            return ValidationResult(success=True)
        test_command = framework_info.command
        if on_progress:
            on_progress(f"Detected {framework_info.framework.value}, using: {test_command}")

    # Run tests
    if on_progress:
        on_progress(f"Running tests: {test_command}")

    test_result = run_tests(
        command=test_command,
        path=path,
        timeout=config.timeout_seconds,
    )

    if test_result.success:
        if on_progress:
            on_progress(f"✅ {test_result.summary()}")
        return ValidationResult(
            success=True,
            test_results=[test_result],
            total_attempts=1,
            final_test_result=test_result,
        )
    else:
        if on_progress:
            on_progress(f"❌ {test_result.summary()}")

        # Generate retry context for external retry handling
        retry_context = format_test_failure_context(
            test_result=test_result,
            phase="test",
            attempt_number=1,
            max_attempts=config.max_retries,
        )

        return ValidationResult(
            success=False,
            test_results=[test_result],
            total_attempts=1,
            final_test_result=test_result,
            retry_context=retry_context,
        )


def validate_with_retry(
    path: Path | None = None,
    config: ValidationConfig | None = None,
    on_progress: Callable[[str], None] | None = None,
    on_retry: Callable[[str, int], bool] | None = None,
    task_id: str | None = None,
    task_description: str | None = None,
) -> ValidationResult:
    """Run tests with automatic retry support.

    The on_retry callback is called when tests fail and returns True if
    the caller has attempted to fix the issue (e.g., by running the agent
    again with error context). If on_retry returns False or is not provided,
    validation stops and returns the failed result.

    Args:
        path: Working directory. Defaults to current directory.
        config: Validation configuration.
        on_progress: Optional progress callback.
        on_retry: Callback(retry_context, attempt_number) -> bool indicating
                  whether a fix was attempted. If True, tests are re-run.
        task_id: Optional task ID for escalation reports.
        task_description: Optional task description for escalation.

    Returns:
        ValidationResult with final outcome.
    """
    config = config or ValidationConfig()

    if config.skip_tests:
        if on_progress:
            on_progress("Test validation skipped (--no-tests)")
        return ValidationResult(success=True)

    if path is None:
        path = Path.cwd()

    # Detect or use configured test command
    test_command = config.test_command
    if test_command is None:
        framework_info = detect_test_framework(path)
        if framework_info is None:
            if on_progress:
                on_progress("No test framework detected, skipping tests")
            return ValidationResult(success=True)
        test_command = framework_info.command
        if on_progress:
            on_progress(f"Detected {framework_info.framework.value}")

    test_results: list[TestResult] = []
    attempt_records: list[AttemptRecord] = []
    max_attempts = config.max_retries + 1  # +1 for initial attempt

    for attempt in range(1, max_attempts + 1):
        if on_progress:
            on_progress(f"Test attempt {attempt}/{max_attempts}: {test_command}")

        test_result = run_tests(
            command=test_command,
            path=path,
            timeout=config.timeout_seconds,
        )
        test_results.append(test_result)

        if test_result.success:
            if on_progress:
                on_progress(f"✅ {test_result.summary()}")
            return ValidationResult(
                success=True,
                test_results=test_results,
                total_attempts=attempt,
                final_test_result=test_result,
            )

        # Test failed
        if on_progress:
            on_progress(f"❌ Attempt {attempt}: {test_result.summary()}")

        # Record the attempt
        strategy = select_retry_strategy(attempt, max_attempts)
        attempt_records.append(
            AttemptRecord(
                attempt_number=attempt,
                phase="test",
                error_message=test_result.to_retry_context(),
                strategy=strategy.value,
                duration_seconds=test_result.duration_seconds,
            )
        )

        # Check if we should retry
        if attempt < max_attempts and on_retry:
            retry_context = format_test_failure_context(
                test_result=test_result,
                phase="test",
                attempt_number=attempt,
                max_attempts=max_attempts,
            )

            # Apply backoff delay
            if config.retry_delay_seconds > 0:
                import time

                delay = config.retry_delay_seconds
                if config.exponential_backoff:
                    delay = delay * (2 ** (attempt - 1))
                if on_progress:
                    on_progress(f"Waiting {delay}s before retry...")
                time.sleep(delay)

            # Call retry handler
            fix_attempted = on_retry(retry_context, attempt)
            if not fix_attempted:
                if on_progress:
                    on_progress("Retry handler returned False, stopping validation")
                break
        else:
            break

    # All retries exhausted
    final_result = test_results[-1] if test_results else None

    # Generate escalation report if task info provided
    escalation = None
    if task_id and task_description and attempt_records:
        escalation = generate_escalation_report(
            task_id=task_id,
            task_description=task_description,
            workflow_type="test_validation",
            attempts=attempt_records,
            output_dir=Path(f"agents/{task_id}") if task_id else None,
        )
        if on_progress:
            on_progress(f"Generated escalation report for task {task_id}")

    return ValidationResult(
        success=False,
        test_results=test_results,
        total_attempts=len(test_results),
        final_test_result=final_result,
        escalation_report=escalation,
        retry_context=final_result.to_retry_context() if final_result else None,
    )


def get_test_report(
    test_result: TestResult,
    include_details: bool = True,
) -> str:
    """Format test result as a report string.

    Args:
        test_result: The test result to format.
        include_details: Whether to include failure details.

    Returns:
        Formatted report string.
    """
    lines = [
        "Test Results",
        "=" * 40,
        test_result.summary(),
    ]

    if include_details and test_result.failed_tests:
        lines.append("")
        lines.append("Failed Tests:")
        for ft in test_result.failed_tests:
            lines.append(f"  • {ft.name}")
            if ft.error_message:
                # Truncate long error messages
                msg = ft.error_message[:200]
                if len(ft.error_message) > 200:
                    msg += "..."
                lines.append(f"    {msg}")

    if test_result.coverage_percent is not None:
        lines.append("")
        lines.append(f"Coverage: {test_result.coverage_percent:.1f}%")

    lines.append("=" * 40)
    return "\n".join(lines)
