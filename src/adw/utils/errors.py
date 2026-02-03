"""Error handling utilities for ADW CLI.

Provides consistent error formatting with:
- Human-friendly messages
- Suggested fixes
- Documentation links
- Hidden stack traces (unless debug mode)
"""

from __future__ import annotations

import os
import sys
import traceback
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rich.console import Console

# Debug mode enabled by ADW_DEBUG=1 or --debug flag
_debug_mode = os.environ.get("ADW_DEBUG", "0") == "1"


class ErrorCategory(str, Enum):
    """Categories of errors for consistent formatting."""

    CONFIG = "config"  # Configuration errors
    FILE = "file"  # File not found, permission errors
    NETWORK = "network"  # Network/API errors
    DEPENDENCY = "dependency"  # Missing dependencies
    TASK = "task"  # Task-related errors
    GIT = "git"  # Git operation errors
    WORKFLOW = "workflow"  # Workflow execution errors
    INTEGRATION = "integration"  # External integration errors
    INTERNAL = "internal"  # Internal/unexpected errors


# Documentation links for common issues
DOCS_BASE = "https://github.com/mhmdez/adw"
DOCS_LINKS = {
    ErrorCategory.CONFIG: f"{DOCS_BASE}#configuration",
    ErrorCategory.FILE: f"{DOCS_BASE}#project-setup",
    ErrorCategory.DEPENDENCY: f"{DOCS_BASE}#installation",
    ErrorCategory.TASK: f"{DOCS_BASE}#task-management",
    ErrorCategory.GIT: f"{DOCS_BASE}#git-worktrees",
    ErrorCategory.WORKFLOW: f"{DOCS_BASE}#workflows",
    ErrorCategory.INTEGRATION: f"{DOCS_BASE}#integrations",
}


@dataclass
class ErrorInfo:
    """Structured error information for consistent display."""

    message: str
    category: ErrorCategory
    suggestion: str | None = None
    details: str | None = None
    docs_link: str | None = None
    original_error: Exception | None = None

    def __post_init__(self) -> None:
        # Auto-populate docs_link if not provided
        if self.docs_link is None and self.category in DOCS_LINKS:
            self.docs_link = DOCS_LINKS[self.category]


def set_debug_mode(enabled: bool) -> None:
    """Enable or disable debug mode for verbose error output."""
    global _debug_mode
    _debug_mode = enabled


def is_debug_mode() -> bool:
    """Check if debug mode is enabled."""
    return _debug_mode


def format_error(error: ErrorInfo, console: Console) -> None:
    """Format and display an error with consistent styling.

    Args:
        error: Structured error information
        console: Rich console for output
    """
    # Main error message
    console.print(f"[bold red]Error:[/bold red] {error.message}")

    # Show details if available (in debug mode or if short)
    if error.details:
        if _debug_mode or len(error.details) < 200:
            console.print(f"[dim]{error.details}[/dim]")

    # Show suggestion
    if error.suggestion:
        console.print()
        console.print(f"[yellow]Suggestion:[/yellow] {error.suggestion}")

    # Show documentation link
    if error.docs_link:
        console.print(f"[dim]Documentation: {error.docs_link}[/dim]")

    # Show stack trace in debug mode
    if _debug_mode and error.original_error:
        console.print()
        console.print("[dim]Stack trace (debug mode):[/dim]")
        tb_lines = traceback.format_exception(
            type(error.original_error),
            error.original_error,
            error.original_error.__traceback__,
        )
        for line in tb_lines:
            console.print(f"[dim]{line.rstrip()}[/dim]")

    # Hint about debug mode
    if not _debug_mode and error.original_error:
        console.print()
        console.print(
            "[dim]Set ADW_DEBUG=1 or use --debug for more details[/dim]"
        )


def error_file_not_found(
    path: str,
    context: str = "file",
    suggestion: str | None = None,
    original: Exception | None = None,
) -> ErrorInfo:
    """Create error info for file not found errors.

    Args:
        path: Path that was not found
        context: What kind of file (e.g., "tasks file", "config file")
        suggestion: Custom suggestion, or auto-generate one
        original: Original exception if available
    """
    if suggestion is None:
        if "tasks" in path.lower():
            suggestion = "Run 'adw init' to initialize the project"
        elif ".claude" in path:
            suggestion = "Run 'adw init' to create Claude configuration"
        elif "config" in path.lower():
            suggestion = "Run 'adw config reset' to create default configuration"
        else:
            suggestion = "Check the path and ensure the file exists"

    return ErrorInfo(
        message=f"{context.capitalize()} not found: {path}",
        category=ErrorCategory.FILE,
        suggestion=suggestion,
        original_error=original,
    )


def error_dependency_missing(
    dependency: str, install_cmd: str | None = None
) -> ErrorInfo:
    """Create error info for missing dependency errors.

    Args:
        dependency: Name of the missing dependency
        install_cmd: Command to install the dependency
    """
    suggestion = f"Install {dependency}"
    if install_cmd:
        suggestion = f"Run: {install_cmd}"

    # Common dependency installation commands
    if install_cmd is None:
        if dependency == "claude":
            suggestion = "Install Claude Code from https://claude.ai/code"
        elif dependency == "git":
            suggestion = "Install git from https://git-scm.com/"
        elif dependency == "gh":
            suggestion = "Install GitHub CLI: brew install gh (macOS) or see https://cli.github.com/"
        elif dependency == "qmd":
            suggestion = "Install qmd: bun install -g qmd"

    return ErrorInfo(
        message=f"Required dependency not found: {dependency}",
        category=ErrorCategory.DEPENDENCY,
        suggestion=suggestion,
    )


def error_config_invalid(
    key: str, value: str | None = None, expected: str | None = None
) -> ErrorInfo:
    """Create error info for invalid configuration errors.

    Args:
        key: Configuration key that is invalid
        value: The invalid value (if known)
        expected: What was expected
    """
    details = None
    if value is not None and expected is not None:
        details = f"Got '{value}', expected {expected}"

    return ErrorInfo(
        message=f"Invalid configuration: {key}",
        category=ErrorCategory.CONFIG,
        suggestion="Run 'adw config show' to view current configuration",
        details=details,
    )


def error_task_not_found(task_id: str) -> ErrorInfo:
    """Create error info for task not found errors.

    Args:
        task_id: The task ID that was not found
    """
    return ErrorInfo(
        message=f"Task not found: {task_id}",
        category=ErrorCategory.TASK,
        suggestion="Run 'adw list' to see available tasks",
    )


def error_git_operation(
    operation: str, message: str, original: Exception | None = None
) -> ErrorInfo:
    """Create error info for git operation errors.

    Args:
        operation: The git operation that failed
        message: Error message from git
        original: Original exception if available
    """
    suggestion = "Check git status and ensure working directory is clean"
    if "worktree" in operation.lower():
        suggestion = "Run 'adw worktree list' to see existing worktrees"
    elif "commit" in operation.lower():
        suggestion = "Ensure there are changes to commit and no conflicts"
    elif "branch" in operation.lower():
        suggestion = "Check if the branch exists: git branch -a"

    return ErrorInfo(
        message=f"Git {operation} failed: {message}",
        category=ErrorCategory.GIT,
        suggestion=suggestion,
        original_error=original,
    )


def error_network(
    service: str, message: str, original: Exception | None = None
) -> ErrorInfo:
    """Create error info for network/API errors.

    Args:
        service: The service that failed (e.g., "GitHub API", "Notion API")
        message: Error message
        original: Original exception if available
    """
    suggestion = "Check your internet connection and API credentials"
    if "github" in service.lower():
        suggestion = "Check GITHUB_TOKEN and network connection"
    elif "notion" in service.lower():
        suggestion = "Check NOTION_API_KEY and database permissions"
    elif "slack" in service.lower():
        suggestion = "Check SLACK_BOT_TOKEN and app configuration"
    elif "linear" in service.lower():
        suggestion = "Check LINEAR_API_KEY and team permissions"

    return ErrorInfo(
        message=f"{service} error: {message}",
        category=ErrorCategory.NETWORK,
        suggestion=suggestion,
        original_error=original,
    )


def error_workflow(
    workflow: str, phase: str, message: str, original: Exception | None = None
) -> ErrorInfo:
    """Create error info for workflow execution errors.

    Args:
        workflow: The workflow name
        phase: The phase that failed
        message: Error message
        original: Original exception if available
    """
    return ErrorInfo(
        message=f"Workflow '{workflow}' failed in {phase} phase: {message}",
        category=ErrorCategory.WORKFLOW,
        suggestion="Check the agent logs in agents/{task_id}/ for details",
        original_error=original,
    )


def error_internal(message: str, original: Exception | None = None) -> ErrorInfo:
    """Create error info for internal/unexpected errors.

    Args:
        message: Error message
        original: Original exception if available
    """
    return ErrorInfo(
        message=f"Internal error: {message}",
        category=ErrorCategory.INTERNAL,
        suggestion="This may be a bug. Please report at https://github.com/mhmdez/adw/issues",
        original_error=original,
        docs_link="https://github.com/mhmdez/adw/issues",
    )


def handle_exception(
    console: Console,
    exception: Exception,
    context: str = "operation",
    exit_code: int = 1,
    exit_on_error: bool = True,
) -> ErrorInfo:
    """Handle an exception and display a formatted error.

    This is a convenience function for catching exceptions and displaying
    them with consistent formatting.

    Args:
        console: Rich console for output
        exception: The exception to handle
        context: Description of what was being done
        exit_code: Exit code to use if exit_on_error is True
        exit_on_error: Whether to exit after displaying the error

    Returns:
        ErrorInfo for the error (useful if not exiting)
    """
    # Classify the error
    error = classify_exception(exception, context)

    # Display the error
    format_error(error, console)

    # Exit if requested
    if exit_on_error:
        sys.exit(exit_code)

    return error


def classify_exception(exception: Exception, context: str = "operation") -> ErrorInfo:
    """Classify an exception into an ErrorInfo.

    Args:
        exception: The exception to classify
        context: Description of what was being done

    Returns:
        ErrorInfo with appropriate categorization
    """
    error_str = str(exception).lower()

    # File errors
    if isinstance(exception, FileNotFoundError):
        path = str(exception).split("'")[1] if "'" in str(exception) else str(exception)
        return error_file_not_found(path, context, original=exception)

    if isinstance(exception, PermissionError):
        return ErrorInfo(
            message=f"Permission denied: {exception}",
            category=ErrorCategory.FILE,
            suggestion="Check file permissions or run with appropriate access",
            original_error=exception,
        )

    # Network errors - check type first, then content
    if isinstance(exception, (ConnectionError, TimeoutError)):
        return error_network(context, str(exception), exception)

    if any(word in error_str for word in ["connection", "timeout", "network", "socket"]):
        return error_network(context, str(exception), exception)

    if any(word in error_str for word in ["401", "403", "unauthorized", "forbidden"]):
        return ErrorInfo(
            message=f"Authentication failed: {exception}",
            category=ErrorCategory.NETWORK,
            suggestion="Check your API credentials and permissions",
            original_error=exception,
        )

    # Git errors
    if any(word in error_str for word in ["git", "worktree", "branch", "commit", "merge"]):
        return error_git_operation(context, str(exception), exception)

    # Config errors
    if any(word in error_str for word in ["config", "toml", "json", "yaml"]):
        return ErrorInfo(
            message=f"Configuration error: {exception}",
            category=ErrorCategory.CONFIG,
            suggestion="Run 'adw config show' to view current configuration",
            original_error=exception,
        )

    # Task errors
    if any(word in error_str for word in ["task", "adw_id"]):
        return error_task_not_found(context)

    # Default to internal error
    return error_internal(f"{context}: {exception}", exception)


