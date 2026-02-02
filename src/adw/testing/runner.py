"""Test execution and result parsing.

Runs tests using detected or specified test frameworks and parses
the output to extract structured results.
"""

from __future__ import annotations

import re
import subprocess
import time
from pathlib import Path

from .detector import TestFrameworkInfo, detect_test_framework
from .models import FailedTest, TestFramework, TestResult

# Default timeout for test execution (5 minutes)
DEFAULT_TIMEOUT = 300


def run_tests(
    command: str | None = None,
    path: Path | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    env: dict[str, str] | None = None,
) -> TestResult:
    """Run tests and return parsed results.

    Args:
        command: Explicit test command to run. If not provided, will auto-detect.
        path: Working directory for test execution. Defaults to current directory.
        timeout: Maximum time in seconds for test execution.
        env: Additional environment variables to set.

    Returns:
        TestResult with parsed output.
    """
    if path is None:
        path = Path.cwd()

    # Auto-detect framework if no command provided
    framework_info: TestFrameworkInfo | None = None
    if command is None:
        framework_info = detect_test_framework(path)
        if framework_info is None:
            return TestResult(
                error_message="No test framework detected",
                framework=TestFramework.UNKNOWN,
            )
        command = framework_info.command
        framework = framework_info.framework
    else:
        # Try to infer framework from command
        framework = _infer_framework_from_command(command)

    start_time = time.time()

    try:
        # Build subprocess environment
        import os

        proc_env = os.environ.copy()
        proc_env["PYTHONUNBUFFERED"] = "1"
        # Force color output for better parsing
        proc_env["FORCE_COLOR"] = "1"
        proc_env["PYTEST_ADDOPTS"] = "--color=yes"
        if env:
            proc_env.update(env)

        result = subprocess.run(
            command,
            shell=True,
            cwd=path,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=proc_env,
        )

        duration = time.time() - start_time

        # Parse based on framework
        test_result = _parse_output(
            stdout=result.stdout,
            stderr=result.stderr,
            exit_code=result.returncode,
            framework=framework,
        )
        test_result.duration_seconds = duration
        test_result.command = command
        test_result.framework = framework

        return test_result

    except subprocess.TimeoutExpired as e:
        duration = time.time() - start_time
        # Handle stdout/stderr which can be bytes or str
        stdout_raw = e.stdout if hasattr(e, "stdout") else None
        stderr_raw = e.stderr if hasattr(e, "stderr") else None
        stdout_str = stdout_raw.decode() if isinstance(stdout_raw, bytes) else (stdout_raw or "")
        stderr_str = stderr_raw.decode() if isinstance(stderr_raw, bytes) else (stderr_raw or "")
        return TestResult(
            timed_out=True,
            error_message=f"Test execution timed out after {timeout}s",
            stdout=stdout_str,
            stderr=stderr_str,
            exit_code=-1,
            duration_seconds=duration,
            command=command,
            framework=framework,
        )

    except Exception as e:
        duration = time.time() - start_time
        return TestResult(
            error_message=f"Test execution failed: {e}",
            exit_code=-1,
            duration_seconds=duration,
            command=command,
            framework=framework,
        )


def _infer_framework_from_command(command: str) -> TestFramework:
    """Infer test framework from command string."""
    cmd_lower = command.lower()

    if "pytest" in cmd_lower:
        return TestFramework.PYTEST
    elif "vitest" in cmd_lower:
        return TestFramework.VITEST
    elif "jest" in cmd_lower:
        return TestFramework.JEST
    elif "bun test" in cmd_lower:
        return TestFramework.BUN_TEST
    # Check cargo test BEFORE go test since "cargo test" contains "go test"
    elif "cargo test" in cmd_lower:
        return TestFramework.CARGO_TEST
    elif "go test" in cmd_lower:
        return TestFramework.GO_TEST
    elif "npm test" in cmd_lower or "npm run test" in cmd_lower:
        return TestFramework.NPM_TEST
    else:
        return TestFramework.UNKNOWN


def _parse_output(
    stdout: str,
    stderr: str,
    exit_code: int,
    framework: TestFramework,
) -> TestResult:
    """Parse test output based on framework."""
    parsers = {
        TestFramework.PYTEST: _parse_pytest_output,
        TestFramework.JEST: _parse_jest_output,
        TestFramework.VITEST: _parse_vitest_output,
        TestFramework.GO_TEST: _parse_go_test_output,
        TestFramework.CARGO_TEST: _parse_cargo_test_output,
        TestFramework.BUN_TEST: _parse_bun_test_output,
    }

    parser = parsers.get(framework, _parse_generic_output)
    result = parser(stdout, stderr, exit_code)
    result.stdout = stdout
    result.stderr = stderr
    result.exit_code = exit_code

    return result


def _parse_pytest_output(stdout: str, stderr: str, exit_code: int) -> TestResult:
    """Parse pytest output.

    Pytest summary line formats:
    - "1 passed in 0.05s"
    - "5 passed, 2 failed in 1.23s"
    - "3 passed, 1 error, 2 skipped in 0.50s"
    """
    result = TestResult()
    combined = stdout + "\n" + stderr

    # Parse summary line (e.g., "5 passed, 2 failed, 1 skipped in 0.05s")
    summary_pattern = r"=+\s*([\d\w\s,]+)\s+in\s+([\d.]+)s\s*=+"
    summary_match = re.search(summary_pattern, combined)

    if summary_match:
        summary_text = summary_match.group(1)

        # Extract counts
        passed_match = re.search(r"(\d+)\s+passed", summary_text)
        failed_match = re.search(r"(\d+)\s+failed", summary_text)
        skipped_match = re.search(r"(\d+)\s+skipped", summary_text)
        error_match = re.search(r"(\d+)\s+error", summary_text)

        result.passed = int(passed_match.group(1)) if passed_match else 0
        result.failed = int(failed_match.group(1)) if failed_match else 0
        result.skipped = int(skipped_match.group(1)) if skipped_match else 0
        result.errors = int(error_match.group(1)) if error_match else 0

    result.total = result.passed + result.failed + result.skipped + result.errors

    # Parse failed test names and errors
    # Pattern: "FAILED tests/test_file.py::test_name - Error message"
    failed_pattern = r"FAILED\s+([\w/._-]+)::(\w+)(?:\s*-\s*(.+))?"
    for match in re.finditer(failed_pattern, combined):
        file_path = match.group(1)
        test_name = match.group(2)
        error_msg = match.group(3) or "Test failed"
        result.failed_tests.append(
            FailedTest(
                name=f"{file_path}::{test_name}",
                error_message=error_msg.strip(),
                file_path=file_path,
            )
        )

    # Also try short format failures
    short_failed = r"^(FAILED|ERROR)\s+([\w/._:]+)"
    for match in re.finditer(short_failed, combined, re.MULTILINE):
        name = match.group(2)
        # Don't duplicate
        if not any(ft.name == name for ft in result.failed_tests):
            result.failed_tests.append(
                FailedTest(
                    name=name,
                    error_message="Test failed",
                )
            )

    # Parse coverage if available
    coverage_pattern = r"TOTAL\s+\d+\s+\d+\s+(\d+)%"
    coverage_match = re.search(coverage_pattern, combined)
    if coverage_match:
        result.coverage_percent = float(coverage_match.group(1))

    return result


def _parse_jest_output(stdout: str, stderr: str, exit_code: int) -> TestResult:
    """Parse Jest output.

    Jest summary formats:
    - "Tests:  2 passed, 2 total"
    - "Tests:  1 failed, 2 passed, 3 total"
    """
    result = TestResult()
    combined = stdout + "\n" + stderr

    # Parse test summary
    tests_pattern = (
        r"Tests:\s+(?:(\d+)\s+failed,?\s*)?"
        r"(?:(\d+)\s+skipped,?\s*)?"
        r"(?:(\d+)\s+passed,?\s*)?(\d+)\s+total"
    )
    tests_match = re.search(tests_pattern, combined)

    if tests_match:
        result.failed = int(tests_match.group(1) or 0)
        result.skipped = int(tests_match.group(2) or 0)
        result.passed = int(tests_match.group(3) or 0)
        result.total = int(tests_match.group(4) or 0)

    # Parse failed test names
    # Jest format: "● test name"
    failed_pattern = r"●\s+(.+)"
    for match in re.finditer(failed_pattern, combined):
        test_name = match.group(1).strip()
        # Skip if it's a suite name (contains " › ")
        if " › " in test_name:
            parts = test_name.split(" › ")
            test_name = parts[-1]

        result.failed_tests.append(
            FailedTest(
                name=test_name,
                error_message="Test failed (see output above)",
            )
        )

    # Parse time
    time_pattern = r"Time:\s+([\d.]+)\s*s"
    time_match = re.search(time_pattern, combined)
    if time_match:
        result.duration_seconds = float(time_match.group(1))

    return result


def _parse_vitest_output(stdout: str, stderr: str, exit_code: int) -> TestResult:
    """Parse Vitest output.

    Vitest is similar to Jest but with some differences.
    """
    result = TestResult()
    combined = stdout + "\n" + stderr

    # Vitest summary line
    summary_pattern = r"Tests\s+(\d+)\s+failed\s*\|\s*(\d+)\s+passed"
    summary_match = re.search(summary_pattern, combined)

    if summary_match:
        result.failed = int(summary_match.group(1))
        result.passed = int(summary_match.group(2))
    else:
        # Alternative format: "Test Files  1 passed (1)"
        passed_pattern = r"Tests\s+(\d+)\s+passed"
        passed_match = re.search(passed_pattern, combined)
        if passed_match:
            result.passed = int(passed_match.group(1))

    result.total = result.passed + result.failed + result.skipped

    # Parse failed tests (vitest uses ❌ or FAIL marker)
    failed_pattern = r"(?:❌|FAIL)\s+(.+?)(?:\s+\d+ms)?"
    for match in re.finditer(failed_pattern, combined):
        test_name = match.group(1).strip()
        result.failed_tests.append(
            FailedTest(
                name=test_name,
                error_message="Test failed",
            )
        )

    return result


def _parse_go_test_output(stdout: str, stderr: str, exit_code: int) -> TestResult:
    """Parse Go test output.

    Go test formats:
    - "ok      package     0.005s"
    - "FAIL    package     0.010s"
    - "--- FAIL: TestName (0.00s)"
    """
    result = TestResult()
    combined = stdout + "\n" + stderr

    # Count passed/failed packages
    ok_count = len(re.findall(r"^ok\s+", combined, re.MULTILINE))
    fail_count = len(re.findall(r"^FAIL\s+", combined, re.MULTILINE))

    # Count individual test results
    # "--- PASS: TestName" or "--- FAIL: TestName"
    passed = len(re.findall(r"---\s+PASS:\s+", combined))
    failed = len(re.findall(r"---\s+FAIL:\s+", combined))
    skipped = len(re.findall(r"---\s+SKIP:\s+", combined))

    result.passed = passed if passed > 0 else ok_count
    result.failed = failed if failed > 0 else fail_count
    result.skipped = skipped
    result.total = result.passed + result.failed + result.skipped

    # Extract failed test names
    failed_pattern = r"---\s+FAIL:\s+(\w+)\s+\(([\d.]+)s\)"
    for match in re.finditer(failed_pattern, combined):
        test_name = match.group(1)
        result.failed_tests.append(
            FailedTest(
                name=test_name,
                error_message="Test failed",
            )
        )

    return result


def _parse_cargo_test_output(stdout: str, stderr: str, exit_code: int) -> TestResult:
    """Parse Cargo (Rust) test output.

    Cargo test formats:
    - "test result: ok. 10 passed; 0 failed; 0 ignored"
    - "test tests::test_name ... ok"
    - "test tests::test_name ... FAILED"
    """
    result = TestResult()
    combined = stdout + "\n" + stderr

    # Parse summary line
    summary_pattern = r"test result: \w+\.\s*(\d+)\s+passed;\s*(\d+)\s+failed;\s*(\d+)\s+ignored"
    summary_match = re.search(summary_pattern, combined)

    if summary_match:
        result.passed = int(summary_match.group(1))
        result.failed = int(summary_match.group(2))
        result.skipped = int(summary_match.group(3))
        result.total = result.passed + result.failed + result.skipped

    # Extract failed test names
    failed_pattern = r"test\s+([\w:]+)\s+\.\.\.\s+FAILED"
    for match in re.finditer(failed_pattern, combined):
        test_name = match.group(1)
        result.failed_tests.append(
            FailedTest(
                name=test_name,
                error_message="Test failed",
            )
        )

    return result


def _parse_bun_test_output(stdout: str, stderr: str, exit_code: int) -> TestResult:
    """Parse Bun test output.

    Bun test is similar to Jest/Vitest.
    """
    # Bun test output is similar to Jest
    result = _parse_jest_output(stdout, stderr, exit_code)

    # Bun-specific patterns if Jest parsing didn't work well
    if result.total == 0:
        combined = stdout + "\n" + stderr

        # Try counting ✓ and ✗ marks
        passed = len(re.findall(r"✓", combined))
        failed = len(re.findall(r"✗", combined))

        if passed > 0 or failed > 0:
            result.passed = passed
            result.failed = failed
            result.total = passed + failed

    return result


def _parse_generic_output(stdout: str, stderr: str, exit_code: int) -> TestResult:
    """Generic output parsing for unknown frameworks.

    Tries common patterns and falls back to exit code analysis.
    """
    result = TestResult()
    combined = stdout + "\n" + stderr

    # Try common patterns
    # "X passed, Y failed"
    common_pattern = r"(\d+)\s+(?:tests?\s+)?passed.*?(\d+)\s+(?:tests?\s+)?failed"
    match = re.search(common_pattern, combined, re.IGNORECASE)
    if match:
        result.passed = int(match.group(1))
        result.failed = int(match.group(2))
        result.total = result.passed + result.failed
        return result

    # Just "X passed"
    passed_pattern = r"(\d+)\s+(?:tests?\s+)?passed"
    passed_match = re.search(passed_pattern, combined, re.IGNORECASE)
    if passed_match:
        result.passed = int(passed_match.group(1))

    # Just "X failed"
    failed_pattern = r"(\d+)\s+(?:tests?\s+)?failed"
    failed_match = re.search(failed_pattern, combined, re.IGNORECASE)
    if failed_match:
        result.failed = int(failed_match.group(1))

    result.total = result.passed + result.failed

    # If we couldn't parse anything, use exit code
    if result.total == 0:
        if exit_code == 0:
            result.passed = 1  # Assume at least one test passed
            result.total = 1
        else:
            result.failed = 1
            result.total = 1
            result.error_message = "Tests failed (unable to parse output)"

    return result
