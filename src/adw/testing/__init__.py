"""Test framework detection and execution for ADW.

This module provides:
- Test framework detection (pytest, jest, vitest, etc.)
- Test execution with result parsing
- Retry-ready test results
- Test validation with retry support for workflows
"""

from .detector import TestFrameworkInfo, detect_test_framework, get_test_command
from .models import FailedTest, TestFramework, TestResult
from .runner import run_tests
from .validation import (
    ValidationConfig,
    ValidationResult,
    get_test_report,
    validate_tests,
    validate_with_retry,
)

__all__ = [
    # Models
    "TestResult",
    "TestFramework",
    "FailedTest",
    # Detection
    "detect_test_framework",
    "get_test_command",
    "TestFrameworkInfo",
    # Execution
    "run_tests",
    # Validation
    "validate_tests",
    "validate_with_retry",
    "ValidationConfig",
    "ValidationResult",
    "get_test_report",
]
