"""Error classification for recovery strategy selection.

Classifies errors into categories to determine the appropriate
recovery strategy:
- retriable: Network, rate limit, timeout errors
- fixable: Test failure, lint error, code syntax
- fatal: Invalid config, missing dependencies
- unknown: Unclassified errors
"""

from __future__ import annotations

import re
from enum import Enum
from typing import NamedTuple


class ErrorClass(str, Enum):
    """Error classification for recovery strategies."""

    RETRIABLE = "retriable"  # Network, rate limit, timeout
    FIXABLE = "fixable"  # Test failure, lint error, code syntax
    FATAL = "fatal"  # Invalid config, missing dependencies
    UNKNOWN = "unknown"  # Unclassified errors


class ClassificationResult(NamedTuple):
    """Result of error classification."""

    error_class: ErrorClass
    confidence: float  # 0.0 to 1.0
    reason: str
    suggested_action: str


# Pattern definitions for each error class
# Each pattern is a tuple of (regex_pattern, reason, suggested_action, confidence)
RETRIABLE_PATTERNS: list[tuple[str, str, str, float]] = [
    # Network errors
    (
        r"connection\s*(refused|reset|timed?\s*out)",
        "Network connection failed",
        "Retry after brief delay",
        0.95,
    ),
    (
        r"(network|socket)\s*(error|unreachable)",
        "Network error",
        "Check network and retry",
        0.9,
    ),
    (
        r"ECONNREFUSED|ENOTFOUND|ETIMEDOUT|ECONNRESET",
        "Network socket error",
        "Retry with backoff",
        0.95,
    ),
    (
        r"failed to fetch|fetch failed",
        "Fetch operation failed",
        "Retry the request",
        0.85,
    ),
    (
        r"DNS\s*(resolution|lookup)\s*failed",
        "DNS resolution failed",
        "Check DNS and retry",
        0.9,
    ),
    # Rate limiting
    (
        r"rate\s*limit(ed)?|too\s*many\s*requests|429",
        "Rate limited",
        "Wait and retry with backoff",
        0.95,
    ),
    (
        r"quota\s*exceeded|usage\s*limit",
        "Quota exceeded",
        "Wait for quota reset",
        0.9,
    ),
    (r"throttl(ed|ing)", "Request throttled", "Reduce request rate", 0.9),
    # Timeouts
    (
        r"timeout|timed?\s*out|deadline\s*exceeded",
        "Operation timed out",
        "Increase timeout and retry",
        0.85,
    ),
    (
        r"operation\s*(took|exceeded)\s*too\s*long",
        "Slow operation",
        "Retry with longer timeout",
        0.8,
    ),
    # Temporary failures
    (
        r"(temporary|transient)\s*(failure|error|unavailable)",
        "Temporary failure",
        "Retry shortly",
        0.9,
    ),
    (
        r"service\s*(temporarily\s*)?(unavailable|down)",
        "Service unavailable",
        "Wait and retry",
        0.85,
    ),
    (r"503|502|504", "Server error", "Retry after delay", 0.8),
    (r"try\s*again\s*later", "Server requested retry", "Retry later", 0.95),
    # API errors
    (r"API\s*(error|unavailable)", "API error", "Retry the API call", 0.75),
    (
        r"claude.*overloaded|anthropic.*capacity",
        "Claude API overloaded",
        "Wait and retry",
        0.95,
    ),
]

FIXABLE_PATTERNS: list[tuple[str, str, str, float]] = [
    # Test failures
    (
        r"test(s)?\s*(failed|failure)|assertion\s*(failed|error)",
        "Test failure",
        "Fix failing tests",
        0.95,
    ),
    (
        r"FAILED|AssertionError|pytest.*failed",
        "Test assertion failed",
        "Review test expectations",
        0.9,
    ),
    (
        r"expected.*but\s*(got|received|was)",
        "Assertion mismatch",
        "Fix implementation or test",
        0.85,
    ),
    (r"(\d+)\s*test(s)?\s*failed", "Multiple test failures", "Review and fix tests", 0.9),
    # Lint/format errors
    (
        r"lint(er|ing)?\s*(error|failed|warning)",
        "Linter error",
        "Fix lint issues",
        0.95,
    ),
    (
        r"(ruff|flake8|eslint|pylint).*error",
        "Linter failed",
        "Run linter fixes",
        0.95,
    ),
    (r"format(ting)?\s*(error|failed|check)", "Format error", "Run formatter", 0.9),
    (r"(black|prettier|rustfmt).*", "Formatter", "Auto-format code", 0.9),
    # Syntax/type errors
    (r"syntax\s*error", "Syntax error", "Fix code syntax", 0.95),
    (r"(parse|parsing)\s*(error|failed)", "Parse error", "Fix code structure", 0.9),
    (r"type\s*(error|mismatch|check)", "Type error", "Fix type annotations", 0.85),
    (r"(mypy|pyright|tsc)\s*.*error", "Type checker error", "Fix type issues", 0.9),
    (
        r"undefined\s*(name|variable|symbol)",
        "Undefined reference",
        "Define or import the symbol",
        0.9,
    ),
    (
        r"name\s*['\"]?\w+['\"]?\s*is\s*not\s*defined",
        "Name not defined",
        "Import or define the name",
        0.95,
    ),
    # Import/module errors
    (r"(import|module)\s*(error|not\s*found)", "Import error", "Fix import statement", 0.85),
    (
        r"cannot\s*(find|import|resolve)\s*(module|package)",
        "Module not found",
        "Install or fix import",
        0.85,
    ),
    (r"no\s*module\s*named", "Module not found", "Install the module", 0.95),
    (r"modulenotfounderror", "Module not found", "Install the module", 0.95),
    # Build errors
    (r"build\s*(error|failed)", "Build error", "Fix build issues", 0.85),
    (r"compilation\s*(error|failed)", "Compilation error", "Fix code errors", 0.9),
    (
        r"(npm|yarn|pnpm)\s*(run|build).*failed",
        "Build script failed",
        "Fix build configuration",
        0.85,
    ),
    # Runtime errors that are likely code bugs
    (
        r"(TypeError|ValueError|KeyError|IndexError|AttributeError)",
        "Python runtime error",
        "Fix the code bug",
        0.85,
    ),
    (
        r"(ReferenceError|RangeError|TypeError)",
        "JavaScript runtime error",
        "Fix the code bug",
        0.85,
    ),
    (r"null\s*pointer|nil\s*reference", "Null reference", "Add null checks", 0.85),
]

FATAL_PATTERNS: list[tuple[str, str, str, float]] = [
    # Configuration errors
    (
        r"(config|configuration)\s*(error|invalid|missing)",
        "Configuration error",
        "Fix configuration file",
        0.9,
    ),
    (
        r"invalid\s*(config|settings|options)",
        "Invalid configuration",
        "Review configuration",
        0.9,
    ),
    (
        r"(yaml|json|toml)\s*(parse|syntax)\s*error",
        "Config parse error",
        "Fix config file syntax",
        0.9,
    ),
    (r"json\s*syntax\s*error", "JSON parse error", "Fix JSON syntax", 0.9),
    # Dependency errors
    (
        r"(dependency|dependencies)\s*(missing|not\s*found|error)",
        "Missing dependencies",
        "Install dependencies",
        0.9,
    ),
    (r"missing\s*dependencies", "Missing dependencies", "Install dependencies", 0.9),
    (r"version\s*conflict", "Version conflict", "Resolve version conflict", 0.9),
    (
        r"(package|module)\s*version\s*(conflict|mismatch)",
        "Version conflict",
        "Resolve version conflict",
        0.85,
    ),
    (
        r"peer\s*dependency|version\s*incompatible",
        "Dependency conflict",
        "Update package versions",
        0.85,
    ),
    (
        r"cannot\s*find\s*(executable|binary|command)",
        "Missing binary",
        "Install required tool",
        0.9,
    ),
    (r"command\s*not\s*found", "Command not found", "Install the command", 0.95),
    # Permission/access errors
    (r"permission\s*denied", "Permission denied", "Fix file permissions", 0.9),
    (r"(access|write)\s*denied|EACCES", "Access denied", "Check permissions", 0.9),
    (r"(read-?only|cannot\s*write)", "Read-only error", "Check write permissions", 0.85),
    # Resource errors
    (r"(disk|storage)\s*(full|space)", "Disk full", "Free up disk space", 0.95),
    (
        r"(memory|ram)\s*(full|exhausted|allocation)",
        "Out of memory",
        "Reduce memory usage",
        0.9,
    ),
    (r"out\s*of\s*memory", "Out of memory", "Reduce memory usage", 0.95),
    (r"(ENOMEM|OOM|killed)", "Out of memory", "Reduce memory footprint", 0.9),
    # Authentication/authorization
    (
        r"(auth|authentication)\s*(failed|error|invalid)",
        "Authentication failed",
        "Check credentials",
        0.9,
    ),
    (
        r"(unauthorized|forbidden|401|403)",
        "Authorization error",
        "Check API key/token",
        0.85,
    ),
    (
        r"invalid\s*(api\s*)?key|token\s*(expired|invalid)",
        "Invalid credentials",
        "Update credentials",
        0.95,
    ),
    # Environment errors
    (
        r"(environment|env)\s*(variable|var)\s*(missing|not\s*set)",
        "Missing env var",
        "Set environment variable",
        0.95,
    ),
    (
        r"python\s*version|node\s*version|requires\s*version",
        "Version requirement",
        "Update runtime version",
        0.85,
    ),
    # Git errors
    (r"git\s*(error|fatal)", "Git error", "Fix git state", 0.8),
    (
        r"(merge\s*conflict|conflict\s*marker)",
        "Merge conflict",
        "Resolve conflicts manually",
        0.95,
    ),
    (r"not\s*a\s*git\s*repository", "Not a git repo", "Initialize git repository", 0.95),
]


def classify_error(error_message: str) -> ClassificationResult:
    """Classify an error message to determine recovery strategy.

    Args:
        error_message: The error message to classify.

    Returns:
        ClassificationResult with error class, confidence, and suggested action.
    """
    if not error_message:
        return ClassificationResult(
            error_class=ErrorClass.UNKNOWN,
            confidence=0.0,
            reason="Empty error message",
            suggested_action="Review the error context",
        )

    # Normalize the error message for matching
    normalized = error_message.lower().strip()

    # Check each pattern category in order of specificity
    best_match: ClassificationResult | None = None
    best_confidence = 0.0

    # Check fatal patterns first (usually most specific)
    for pattern, reason, action, confidence in FATAL_PATTERNS:
        if re.search(pattern, normalized, re.IGNORECASE):
            if confidence > best_confidence:
                best_match = ClassificationResult(
                    error_class=ErrorClass.FATAL,
                    confidence=confidence,
                    reason=reason,
                    suggested_action=action,
                )
                best_confidence = confidence

    # Check retriable patterns
    for pattern, reason, action, confidence in RETRIABLE_PATTERNS:
        if re.search(pattern, normalized, re.IGNORECASE):
            if confidence > best_confidence:
                best_match = ClassificationResult(
                    error_class=ErrorClass.RETRIABLE,
                    confidence=confidence,
                    reason=reason,
                    suggested_action=action,
                )
                best_confidence = confidence

    # Check fixable patterns
    for pattern, reason, action, confidence in FIXABLE_PATTERNS:
        if re.search(pattern, normalized, re.IGNORECASE):
            if confidence > best_confidence:
                best_match = ClassificationResult(
                    error_class=ErrorClass.FIXABLE,
                    confidence=confidence,
                    reason=reason,
                    suggested_action=action,
                )
                best_confidence = confidence

    # Return best match or unknown
    if best_match:
        return best_match

    return ClassificationResult(
        error_class=ErrorClass.UNKNOWN,
        confidence=0.5,
        reason="Could not classify error",
        suggested_action="Review error details and decide manually",
    )


def is_retriable(error_message: str) -> bool:
    """Quick check if an error is retriable.

    Args:
        error_message: The error message to check.

    Returns:
        True if the error is classified as retriable.
    """
    result = classify_error(error_message)
    return result.error_class == ErrorClass.RETRIABLE


def is_fixable(error_message: str) -> bool:
    """Quick check if an error is fixable by code changes.

    Args:
        error_message: The error message to check.

    Returns:
        True if the error is classified as fixable.
    """
    result = classify_error(error_message)
    return result.error_class == ErrorClass.FIXABLE


def is_fatal(error_message: str) -> bool:
    """Quick check if an error is fatal (requires human intervention).

    Args:
        error_message: The error message to check.

    Returns:
        True if the error is classified as fatal.
    """
    result = classify_error(error_message)
    return result.error_class == ErrorClass.FATAL
