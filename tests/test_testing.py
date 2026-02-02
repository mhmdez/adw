"""Tests for testing framework detection and execution."""

import json
from pathlib import Path

import pytest

from adw.testing import (
    TestResult,
    TestFramework,
    FailedTest,
    detect_test_framework,
    get_test_command,
    ValidationConfig,
)
from adw.testing.models import TestResult as TestResultModel
from adw.testing.detector import (
    _detect_pytest,
    _detect_jest,
    _detect_vitest,
    _detect_go_test,
    _detect_cargo_test,
)
from adw.testing.runner import (
    _parse_pytest_output,
    _parse_jest_output,
    _parse_vitest_output,
    _parse_go_test_output,
    _parse_cargo_test_output,
    _infer_framework_from_command,
)


class TestTestFrameworkDetection:
    """Tests for test framework detection."""

    def test_detect_pytest_ini(self, tmp_path: Path) -> None:
        """Test pytest detection via pytest.ini."""
        pytest_ini = tmp_path / "pytest.ini"
        pytest_ini.write_text("[pytest]\naddopts = -v")

        info = _detect_pytest(tmp_path)
        assert info is not None
        assert info.framework == TestFramework.PYTEST
        assert info.command == "pytest"
        assert info.confidence >= 0.9

    def test_detect_pytest_conftest(self, tmp_path: Path) -> None:
        """Test pytest detection via conftest.py."""
        conftest = tmp_path / "conftest.py"
        conftest.write_text("import pytest")

        info = _detect_pytest(tmp_path)
        assert info is not None
        assert info.framework == TestFramework.PYTEST

    def test_detect_pytest_pyproject(self, tmp_path: Path) -> None:
        """Test pytest detection via pyproject.toml."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[tool.pytest.ini_options]
testpaths = ["tests"]
""")

        info = _detect_pytest(tmp_path)
        assert info is not None
        assert info.framework == TestFramework.PYTEST
        assert info.config_file == "pyproject.toml"

    def test_detect_pytest_tests_dir(self, tmp_path: Path) -> None:
        """Test pytest detection via tests directory."""
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        test_file = tests_dir / "test_example.py"
        test_file.write_text("def test_example(): pass")

        info = _detect_pytest(tmp_path)
        assert info is not None
        assert info.framework == TestFramework.PYTEST
        assert info.confidence <= 0.8  # Lower confidence without explicit config

    def test_detect_jest_config(self, tmp_path: Path) -> None:
        """Test jest detection via jest.config.js."""
        jest_config = tmp_path / "jest.config.js"
        jest_config.write_text("module.exports = {};")

        info = _detect_jest(tmp_path)
        assert info is not None
        assert info.framework == TestFramework.JEST
        assert "jest" in info.command

    def test_detect_jest_package_json(self, tmp_path: Path) -> None:
        """Test jest detection via package.json."""
        package_json = tmp_path / "package.json"
        package_json.write_text(json.dumps({
            "devDependencies": {"jest": "^29.0.0"},
            "scripts": {"test": "jest"}
        }))

        info = _detect_jest(tmp_path)
        assert info is not None
        assert info.framework == TestFramework.JEST

    def test_detect_vitest_config(self, tmp_path: Path) -> None:
        """Test vitest detection via vitest.config.ts."""
        vitest_config = tmp_path / "vitest.config.ts"
        vitest_config.write_text("export default {};")

        info = _detect_vitest(tmp_path)
        assert info is not None
        assert info.framework == TestFramework.VITEST
        assert "vitest" in info.command

    def test_detect_vitest_package_json(self, tmp_path: Path) -> None:
        """Test vitest detection via package.json."""
        package_json = tmp_path / "package.json"
        package_json.write_text(json.dumps({
            "devDependencies": {"vitest": "^1.0.0"}
        }))

        info = _detect_vitest(tmp_path)
        assert info is not None
        assert info.framework == TestFramework.VITEST

    def test_detect_go_test(self, tmp_path: Path) -> None:
        """Test Go test detection."""
        go_mod = tmp_path / "go.mod"
        go_mod.write_text("module example.com/test")
        test_file = tmp_path / "main_test.go"
        test_file.write_text("package main")

        info = _detect_go_test(tmp_path)
        assert info is not None
        assert info.framework == TestFramework.GO_TEST
        assert info.command == "go test ./..."

    def test_detect_cargo_test(self, tmp_path: Path) -> None:
        """Test Cargo test detection."""
        cargo_toml = tmp_path / "Cargo.toml"
        cargo_toml.write_text('[package]\nname = "test"')

        info = _detect_cargo_test(tmp_path)
        assert info is not None
        assert info.framework == TestFramework.CARGO_TEST
        assert info.command == "cargo test"

    def test_detect_no_framework(self, tmp_path: Path) -> None:
        """Test detection on empty directory."""
        info = detect_test_framework(tmp_path)
        assert info is None

    def test_get_test_command(self, tmp_path: Path) -> None:
        """Test get_test_command convenience function."""
        pytest_ini = tmp_path / "pytest.ini"
        pytest_ini.write_text("[pytest]")

        command = get_test_command(tmp_path)
        assert command == "pytest"

    def test_get_test_command_none(self, tmp_path: Path) -> None:
        """Test get_test_command returns None for unknown."""
        command = get_test_command(tmp_path)
        assert command is None


class TestOutputParsing:
    """Tests for test output parsing."""

    def test_parse_pytest_success(self) -> None:
        """Test parsing pytest success output."""
        stdout = """
============================= test session starts ==============================
collected 5 items

tests/test_example.py .....                                              [100%]

============================== 5 passed in 0.05s ===============================
"""
        result = _parse_pytest_output(stdout, "", 0)
        assert result.passed == 5
        assert result.failed == 0
        assert result.total == 5

    def test_parse_pytest_failure(self) -> None:
        """Test parsing pytest failure output."""
        stdout = """
============================= test session starts ==============================
collected 3 items

tests/test_example.py .F.                                                [100%]

=================================== FAILURES ===================================
FAILED tests/test_example.py::test_broken - AssertionError: assert False

=========================== short test summary info ============================
FAILED tests/test_example.py::test_broken - AssertionError: assert False
========================= 2 passed, 1 failed in 0.10s =========================
"""
        result = _parse_pytest_output(stdout, "", 1)
        assert result.passed == 2
        assert result.failed == 1
        assert result.total == 3
        assert len(result.failed_tests) >= 1

    def test_parse_pytest_with_skipped(self) -> None:
        """Test parsing pytest output with skipped tests."""
        stdout = """
============================== 3 passed, 1 skipped in 0.05s ==============================
"""
        result = _parse_pytest_output(stdout, "", 0)
        assert result.passed == 3
        assert result.skipped == 1

    def test_parse_pytest_coverage(self) -> None:
        """Test parsing pytest coverage output."""
        stdout = """
Name                      Stmts   Miss  Cover
---------------------------------------------
src/module.py                50     10    80%
---------------------------------------------
TOTAL                        50     10    80%

============================== 5 passed in 0.05s ===============================
"""
        result = _parse_pytest_output(stdout, "", 0)
        assert result.coverage_percent == 80.0

    def test_parse_jest_success(self) -> None:
        """Test parsing jest success output."""
        stdout = """
 PASS  tests/example.test.js
  ✓ should work (5 ms)
  ✓ should also work (2 ms)

Test Suites: 1 passed, 1 total
Tests:       2 passed, 2 total
Time:        1.234 s
"""
        result = _parse_jest_output(stdout, "", 0)
        assert result.passed == 2
        assert result.failed == 0
        assert result.total == 2

    def test_parse_jest_failure(self) -> None:
        """Test parsing jest failure output."""
        stdout = """
 FAIL  tests/example.test.js
  ● should work

    expect(received).toBe(expected)

Tests:       1 failed, 1 passed, 2 total
Time:        1.234 s
"""
        result = _parse_jest_output(stdout, "", 1)
        assert result.passed == 1
        assert result.failed == 1
        assert result.total == 2

    def test_parse_vitest_success(self) -> None:
        """Test parsing vitest success output."""
        stdout = """
 ✓ tests/example.test.ts (2)
   ✓ should work
   ✓ should also work

 Tests  2 passed (2)
 Duration  123ms
"""
        result = _parse_vitest_output(stdout, "", 0)
        assert result.passed == 2

    def test_parse_go_test_success(self) -> None:
        """Test parsing go test success output."""
        stdout = """
=== RUN   TestExample
--- PASS: TestExample (0.00s)
=== RUN   TestAnother
--- PASS: TestAnother (0.00s)
PASS
ok      example.com/pkg    0.005s
"""
        result = _parse_go_test_output(stdout, "", 0)
        assert result.passed >= 2
        assert result.failed == 0

    def test_parse_go_test_failure(self) -> None:
        """Test parsing go test failure output."""
        stdout = """
=== RUN   TestExample
--- FAIL: TestExample (0.00s)
    example_test.go:10: assertion failed
FAIL
FAIL    example.com/pkg    0.010s
"""
        result = _parse_go_test_output(stdout, "", 1)
        assert result.failed >= 1
        assert len(result.failed_tests) >= 1

    def test_parse_cargo_test_success(self) -> None:
        """Test parsing cargo test success output."""
        stdout = """
running 3 tests
test tests::test_one ... ok
test tests::test_two ... ok
test tests::test_three ... ok

test result: ok. 3 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out
"""
        result = _parse_cargo_test_output(stdout, "", 0)
        assert result.passed == 3
        assert result.failed == 0
        assert result.total == 3

    def test_parse_cargo_test_failure(self) -> None:
        """Test parsing cargo test failure output."""
        stdout = """
running 2 tests
test tests::test_one ... ok
test tests::test_two ... FAILED

test result: FAILED. 1 passed; 1 failed; 0 ignored; 0 measured; 0 filtered out
"""
        result = _parse_cargo_test_output(stdout, "", 1)
        assert result.passed == 1
        assert result.failed == 1
        assert len(result.failed_tests) >= 1


class TestInferFramework:
    """Tests for command to framework inference."""

    def test_infer_pytest(self) -> None:
        assert _infer_framework_from_command("pytest tests/") == TestFramework.PYTEST
        assert _infer_framework_from_command("python -m pytest") == TestFramework.PYTEST

    def test_infer_jest(self) -> None:
        assert _infer_framework_from_command("npx jest") == TestFramework.JEST
        assert _infer_framework_from_command("jest --coverage") == TestFramework.JEST

    def test_infer_vitest(self) -> None:
        assert _infer_framework_from_command("vitest run") == TestFramework.VITEST
        assert _infer_framework_from_command("npx vitest") == TestFramework.VITEST

    def test_infer_go_test(self) -> None:
        assert _infer_framework_from_command("go test ./...") == TestFramework.GO_TEST

    def test_infer_cargo_test(self) -> None:
        assert _infer_framework_from_command("cargo test") == TestFramework.CARGO_TEST

    def test_infer_npm_test(self) -> None:
        assert _infer_framework_from_command("npm test") == TestFramework.NPM_TEST

    def test_infer_unknown(self) -> None:
        assert _infer_framework_from_command("make test") == TestFramework.UNKNOWN


class TestTestResultModel:
    """Tests for TestResult dataclass."""

    def test_success_property(self) -> None:
        """Test success property."""
        result = TestResultModel(passed=5, failed=0, exit_code=0)
        assert result.success is True

        result = TestResultModel(passed=4, failed=1, exit_code=1)
        assert result.success is False

    def test_has_failures_property(self) -> None:
        """Test has_failures property."""
        result = TestResultModel(failed=1)
        assert result.has_failures is True

        result = TestResultModel(errors=1)
        assert result.has_failures is True

        result = TestResultModel(passed=5)
        assert result.has_failures is False

    def test_summary(self) -> None:
        """Test summary generation."""
        result = TestResultModel(passed=5, failed=2, skipped=1)
        summary = result.summary()
        assert "5 passed" in summary
        assert "2 failed" in summary
        assert "1 skipped" in summary

    def test_summary_with_duration(self) -> None:
        """Test summary with duration."""
        result = TestResultModel(passed=5, duration_seconds=1.5)
        summary = result.summary()
        assert "1.5s" in summary

    def test_summary_with_coverage(self) -> None:
        """Test summary with coverage."""
        result = TestResultModel(passed=5, coverage_percent=85.5)
        summary = result.summary()
        assert "85.5%" in summary

    def test_format_failures(self) -> None:
        """Test failure formatting."""
        result = TestResultModel(
            failed=2,
            failed_tests=[
                FailedTest(name="test_one", error_message="assertion failed"),
                FailedTest(name="test_two", error_message="timeout"),
            ]
        )
        formatted = result.format_failures()
        assert "test_one" in formatted
        assert "test_two" in formatted

    def test_to_retry_context(self) -> None:
        """Test retry context generation."""
        result = TestResultModel(
            passed=4,
            failed=1,
            command="pytest tests/",
            failed_tests=[
                FailedTest(name="test_broken", error_message="AssertionError")
            ]
        )
        context = result.to_retry_context()
        assert "TESTS FAILED" in context
        assert "pytest tests/" in context
        assert "test_broken" in context


class TestFailedTest:
    """Tests for FailedTest dataclass."""

    def test_str_basic(self) -> None:
        """Test basic string representation."""
        ft = FailedTest(name="test_example", error_message="failed")
        assert "test_example" in str(ft)
        assert "failed" in str(ft)

    def test_str_with_location(self) -> None:
        """Test string with file location."""
        ft = FailedTest(
            name="test_example",
            error_message="failed",
            file_path="tests/test_example.py",
            line_number=42,
        )
        result = str(ft)
        assert "tests/test_example.py" in result
        assert ":42" in result


class TestValidationConfig:
    """Tests for ValidationConfig."""

    def test_defaults(self) -> None:
        """Test default values."""
        config = ValidationConfig()
        assert config.max_retries == 3
        assert config.timeout_seconds == 300
        assert config.skip_tests is False
        assert config.test_command is None

    def test_custom_values(self) -> None:
        """Test custom values."""
        config = ValidationConfig(
            max_retries=5,
            timeout_seconds=600,
            skip_tests=True,
            test_command="pytest -v",
        )
        assert config.max_retries == 5
        assert config.timeout_seconds == 600
        assert config.skip_tests is True
        assert config.test_command == "pytest -v"
