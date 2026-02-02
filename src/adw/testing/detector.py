"""Test framework detection for projects.

Detects which test framework a project uses and provides the appropriate
test command to run.
"""

from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass
from pathlib import Path

from .models import TestFramework


@dataclass
class TestFrameworkInfo:
    """Information about detected test framework."""

    framework: TestFramework
    command: str
    confidence: float  # 0.0 to 1.0
    config_file: str | None = None


def detect_test_framework(path: Path | None = None) -> TestFrameworkInfo | None:
    """Detect test framework from project files.

    Detection order (first match wins within confidence tiers):
    1. Explicit config files (pytest.ini, jest.config.*, vitest.config.*)
    2. Config in pyproject.toml or package.json
    3. Presence of test directories with framework-specific patterns
    4. package.json scripts.test as fallback

    Args:
        path: Project directory to analyze. Defaults to current directory.

    Returns:
        TestFrameworkInfo if detected, None otherwise.
    """
    if path is None:
        path = Path.cwd()

    # Try each detector in priority order
    detectors = [
        _detect_pytest,
        _detect_vitest,
        _detect_jest,
        _detect_bun_test,
        _detect_go_test,
        _detect_cargo_test,
        _detect_npm_test,  # Fallback for generic npm test
    ]

    best: TestFrameworkInfo | None = None

    for detector in detectors:
        result = detector(path)
        if result:
            if best is None or result.confidence > best.confidence:
                best = result

    return best


def get_test_command(path: Path | None = None) -> str | None:
    """Get the test command for a project.

    Convenience function that returns just the command string.

    Args:
        path: Project directory to analyze.

    Returns:
        Test command string, or None if no framework detected.
    """
    info = detect_test_framework(path)
    return info.command if info else None


def _detect_pytest(path: Path) -> TestFrameworkInfo | None:
    """Detect pytest configuration."""
    # Check for pytest.ini
    pytest_ini = path / "pytest.ini"
    if pytest_ini.exists():
        return TestFrameworkInfo(
            framework=TestFramework.PYTEST,
            command="pytest",
            confidence=0.95,
            config_file="pytest.ini",
        )

    # Check for conftest.py
    conftest = path / "conftest.py"
    if conftest.exists():
        return TestFrameworkInfo(
            framework=TestFramework.PYTEST,
            command="pytest",
            confidence=0.9,
            config_file="conftest.py",
        )

    # Check pyproject.toml for [tool.pytest] or [tool.pytest.ini_options]
    pyproject = path / "pyproject.toml"
    if pyproject.exists():
        try:
            data = tomllib.loads(pyproject.read_text())
            tool = data.get("tool", {})
            if "pytest" in tool or "pytest.ini_options" in tool:
                return TestFrameworkInfo(
                    framework=TestFramework.PYTEST,
                    command="pytest",
                    confidence=0.95,
                    config_file="pyproject.toml",
                )
        except (OSError, tomllib.TOMLDecodeError):
            pass

    # Check for tests/ directory with Python test files
    tests_dir = path / "tests"
    if tests_dir.is_dir():
        test_files = list(tests_dir.glob("test_*.py")) + list(tests_dir.glob("*_test.py"))
        if test_files:
            return TestFrameworkInfo(
                framework=TestFramework.PYTEST,
                command="pytest",
                confidence=0.7,
            )

    # Check for test directory (singular)
    test_dir = path / "test"
    if test_dir.is_dir():
        test_files = list(test_dir.glob("test_*.py")) + list(test_dir.glob("*_test.py"))
        if test_files:
            return TestFrameworkInfo(
                framework=TestFramework.PYTEST,
                command="pytest",
                confidence=0.7,
            )

    return None


def _detect_vitest(path: Path) -> TestFrameworkInfo | None:
    """Detect vitest configuration."""
    # Check for vitest.config.* files
    for ext in ["ts", "js", "mts", "mjs"]:
        config_file = path / f"vitest.config.{ext}"
        if config_file.exists():
            return TestFrameworkInfo(
                framework=TestFramework.VITEST,
                command="npx vitest run",
                confidence=0.95,
                config_file=f"vitest.config.{ext}",
            )

    # Check package.json for vitest dependency
    package_json = path / "package.json"
    if package_json.exists():
        try:
            pkg = json.loads(package_json.read_text())
            deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}

            if "vitest" in deps:
                # Check if there's a test script that uses vitest
                scripts = pkg.get("scripts", {})
                test_script = scripts.get("test", "")
                if "vitest" in test_script:
                    return TestFrameworkInfo(
                        framework=TestFramework.VITEST,
                        command="npm test",
                        confidence=0.9,
                        config_file="package.json",
                    )
                return TestFrameworkInfo(
                    framework=TestFramework.VITEST,
                    command="npx vitest run",
                    confidence=0.85,
                    config_file="package.json",
                )
        except (json.JSONDecodeError, OSError):
            pass

    return None


def _detect_jest(path: Path) -> TestFrameworkInfo | None:
    """Detect jest configuration."""
    # Check for jest.config.* files
    for ext in ["ts", "js", "mts", "mjs", "json"]:
        config_file = path / f"jest.config.{ext}"
        if config_file.exists():
            return TestFrameworkInfo(
                framework=TestFramework.JEST,
                command="npx jest",
                confidence=0.95,
                config_file=f"jest.config.{ext}",
            )

    # Check package.json for jest config or dependency
    package_json = path / "package.json"
    if package_json.exists():
        try:
            pkg = json.loads(package_json.read_text())

            # Check for jest config in package.json
            if "jest" in pkg:
                return TestFrameworkInfo(
                    framework=TestFramework.JEST,
                    command="npx jest",
                    confidence=0.9,
                    config_file="package.json",
                )

            # Check for jest dependency
            deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
            if "jest" in deps:
                scripts = pkg.get("scripts", {})
                test_script = scripts.get("test", "")
                if "jest" in test_script:
                    return TestFrameworkInfo(
                        framework=TestFramework.JEST,
                        command="npm test",
                        confidence=0.9,
                        config_file="package.json",
                    )
                return TestFrameworkInfo(
                    framework=TestFramework.JEST,
                    command="npx jest",
                    confidence=0.8,
                    config_file="package.json",
                )
        except (json.JSONDecodeError, OSError):
            pass

    return None


def _detect_bun_test(path: Path) -> TestFrameworkInfo | None:
    """Detect bun test configuration."""
    # Check for bun.lockb (indicates bun is used)
    bun_lock = path / "bun.lockb"
    package_json = path / "package.json"

    if bun_lock.exists() and package_json.exists():
        try:
            pkg = json.loads(package_json.read_text())
            scripts = pkg.get("scripts", {})
            test_script = scripts.get("test", "")

            if "bun test" in test_script:
                return TestFrameworkInfo(
                    framework=TestFramework.BUN_TEST,
                    command="bun test",
                    confidence=0.95,
                    config_file="package.json",
                )

            # If bun is used and there are test files, suggest bun test
            tests_dir = path / "__tests__"
            if not tests_dir.exists():
                tests_dir = path / "tests"
            if tests_dir.exists():
                test_files = list(tests_dir.glob("*.test.ts")) + list(tests_dir.glob("*.test.js"))
                if test_files:
                    return TestFrameworkInfo(
                        framework=TestFramework.BUN_TEST,
                        command="bun test",
                        confidence=0.7,
                    )
        except (json.JSONDecodeError, OSError):
            pass

    return None


def _detect_go_test(path: Path) -> TestFrameworkInfo | None:
    """Detect Go test configuration."""
    go_mod = path / "go.mod"
    if go_mod.exists():
        # Look for _test.go files
        test_files = list(path.glob("*_test.go")) + list(path.rglob("**/*_test.go"))
        if test_files:
            return TestFrameworkInfo(
                framework=TestFramework.GO_TEST,
                command="go test ./...",
                confidence=0.95,
                config_file="go.mod",
            )
    return None


def _detect_cargo_test(path: Path) -> TestFrameworkInfo | None:
    """Detect Cargo (Rust) test configuration."""
    cargo_toml = path / "Cargo.toml"
    if cargo_toml.exists():
        # Rust projects with Cargo always support cargo test
        return TestFrameworkInfo(
            framework=TestFramework.CARGO_TEST,
            command="cargo test",
            confidence=0.95,
            config_file="Cargo.toml",
        )
    return None


def _detect_npm_test(path: Path) -> TestFrameworkInfo | None:
    """Detect npm test as a fallback.

    This catches any project with a test script in package.json
    that wasn't caught by more specific detectors.
    """
    package_json = path / "package.json"
    if package_json.exists():
        try:
            pkg = json.loads(package_json.read_text())
            scripts = pkg.get("scripts", {})
            test_script = scripts.get("test", "")

            # Skip if test script is just an error message
            if test_script and "no test specified" not in test_script.lower():
                return TestFrameworkInfo(
                    framework=TestFramework.NPM_TEST,
                    command="npm test",
                    confidence=0.5,
                    config_file="package.json",
                )
        except (json.JSONDecodeError, OSError):
            pass

    return None
