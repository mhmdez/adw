"""Data models for test execution and results."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class TestFramework(str, Enum):
    """Supported test frameworks."""

    PYTEST = "pytest"
    JEST = "jest"
    VITEST = "vitest"
    NPM_TEST = "npm_test"
    BUN_TEST = "bun_test"
    GO_TEST = "go_test"
    CARGO_TEST = "cargo_test"
    UNKNOWN = "unknown"


@dataclass
class FailedTest:
    """Details about a failed test."""

    name: str
    error_message: str
    file_path: str | None = None
    line_number: int | None = None

    def __str__(self) -> str:
        """Format failed test for display."""
        location = ""
        if self.file_path:
            location = f" ({self.file_path}"
            if self.line_number:
                location += f":{self.line_number}"
            location += ")"
        return f"{self.name}{location}: {self.error_message[:100]}"


@dataclass
class TestResult:
    """Result of running tests."""

    passed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: int = 0
    total: int = 0
    duration_seconds: float = 0.0
    coverage_percent: float | None = None
    failed_tests: list[FailedTest] = field(default_factory=list)
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    framework: TestFramework = TestFramework.UNKNOWN
    command: str = ""
    timed_out: bool = False
    error_message: str | None = None

    @property
    def success(self) -> bool:
        """Check if all tests passed."""
        return self.exit_code == 0 and self.failed == 0 and self.errors == 0

    @property
    def has_failures(self) -> bool:
        """Check if there are any test failures."""
        return self.failed > 0 or self.errors > 0

    def summary(self) -> str:
        """Generate a summary string."""
        parts = []
        if self.passed > 0:
            parts.append(f"{self.passed} passed")
        if self.failed > 0:
            parts.append(f"{self.failed} failed")
        if self.skipped > 0:
            parts.append(f"{self.skipped} skipped")
        if self.errors > 0:
            parts.append(f"{self.errors} errors")

        result = f"Tests: {', '.join(parts) or 'no tests run'}"
        if self.duration_seconds > 0:
            result += f" ({self.duration_seconds:.1f}s)"
        if self.coverage_percent is not None:
            result += f" | Coverage: {self.coverage_percent:.1f}%"
        return result

    def format_failures(self, max_failures: int = 5) -> str:
        """Format failed test details for error context.

        Args:
            max_failures: Maximum number of failures to include.

        Returns:
            Formatted string with failure details.
        """
        if not self.failed_tests:
            return ""

        lines = ["Failed tests:"]
        for test in self.failed_tests[:max_failures]:
            lines.append(f"  - {test}")

        if len(self.failed_tests) > max_failures:
            remaining = len(self.failed_tests) - max_failures
            lines.append(f"  ... and {remaining} more failures")

        return "\n".join(lines)

    def to_retry_context(self) -> str:
        """Format test result for retry context injection.

        Returns:
            Formatted string suitable for including in a retry prompt.
        """
        lines = [
            "TESTS FAILED:",
            f"Command: {self.command}",
            f"Result: {self.summary()}",
        ]

        if self.failed_tests:
            lines.append("")
            lines.append(self.format_failures())

        if self.error_message:
            lines.append("")
            lines.append(f"Error: {self.error_message}")

        # Include relevant stderr (truncated)
        if self.stderr and not self.timed_out:
            stderr_lines = self.stderr.strip().split("\n")
            # Get last 20 lines of stderr (usually contains the actual errors)
            relevant_stderr = stderr_lines[-20:]
            if relevant_stderr:
                lines.append("")
                lines.append("Error output (last 20 lines):")
                lines.extend(f"  {line}" for line in relevant_stderr)

        lines.append("")
        lines.append("Please fix these test failures and try again.")

        return "\n".join(lines)
