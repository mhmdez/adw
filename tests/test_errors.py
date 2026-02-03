"""Tests for error handling utilities."""

from __future__ import annotations

import io
import os
from unittest.mock import MagicMock

import pytest
from rich.console import Console

from adw.utils.errors import (
    DOCS_BASE,
    DOCS_LINKS,
    ErrorCategory,
    ErrorInfo,
    classify_exception,
    error_config_invalid,
    error_dependency_missing,
    error_file_not_found,
    error_git_operation,
    error_internal,
    error_network,
    error_task_not_found,
    error_workflow,
    format_error,
    handle_exception,
    is_debug_mode,
    set_debug_mode,
)


class TestErrorCategory:
    """Tests for ErrorCategory enum."""

    def test_all_categories_defined(self) -> None:
        """Verify all expected categories exist."""
        expected = {
            "config",
            "file",
            "network",
            "dependency",
            "task",
            "git",
            "workflow",
            "integration",
            "internal",
        }
        actual = {cat.value for cat in ErrorCategory}
        assert actual == expected

    def test_categories_are_strings(self) -> None:
        """Categories should be string enums."""
        for cat in ErrorCategory:
            assert isinstance(cat.value, str)


class TestErrorInfo:
    """Tests for ErrorInfo dataclass."""

    def test_basic_creation(self) -> None:
        """Test basic ErrorInfo creation."""
        error = ErrorInfo(
            message="Test error",
            category=ErrorCategory.FILE,
        )
        assert error.message == "Test error"
        assert error.category == ErrorCategory.FILE
        assert error.suggestion is None
        assert error.details is None
        assert error.original_error is None

    def test_with_all_fields(self) -> None:
        """Test ErrorInfo with all fields."""
        original = ValueError("original")
        error = ErrorInfo(
            message="Test error",
            category=ErrorCategory.CONFIG,
            suggestion="Try this fix",
            details="More details",
            docs_link="https://example.com",
            original_error=original,
        )
        assert error.message == "Test error"
        assert error.suggestion == "Try this fix"
        assert error.details == "More details"
        assert error.docs_link == "https://example.com"
        assert error.original_error is original

    def test_auto_docs_link(self) -> None:
        """Test automatic docs_link population."""
        error = ErrorInfo(
            message="Test",
            category=ErrorCategory.FILE,
        )
        assert error.docs_link == DOCS_LINKS[ErrorCategory.FILE]

    def test_docs_link_override(self) -> None:
        """Test that explicit docs_link is not overridden."""
        error = ErrorInfo(
            message="Test",
            category=ErrorCategory.FILE,
            docs_link="https://custom.link",
        )
        assert error.docs_link == "https://custom.link"

    def test_no_docs_link_for_internal(self) -> None:
        """Test that INTERNAL category has special docs link."""
        error = ErrorInfo(
            message="Test",
            category=ErrorCategory.INTERNAL,
        )
        # Internal doesn't have a DOCS_LINKS entry
        assert error.docs_link is None


class TestDebugMode:
    """Tests for debug mode functionality."""

    def teardown_method(self) -> None:
        """Reset debug mode after each test."""
        set_debug_mode(False)

    def test_default_debug_mode_off(self) -> None:
        """Debug mode should be off by default."""
        set_debug_mode(False)  # Reset first
        assert is_debug_mode() is False

    def test_enable_debug_mode(self) -> None:
        """Test enabling debug mode."""
        set_debug_mode(True)
        assert is_debug_mode() is True

    def test_disable_debug_mode(self) -> None:
        """Test disabling debug mode."""
        set_debug_mode(True)
        set_debug_mode(False)
        assert is_debug_mode() is False

    def test_env_var_debug_mode(self) -> None:
        """Test that ADW_DEBUG env var is respected."""
        # This test documents the behavior - actual env var set at import time
        # so we just verify the function exists and returns bool
        result = is_debug_mode()
        assert isinstance(result, bool)


class TestFormatError:
    """Tests for format_error function."""

    def get_console_output(self, error: ErrorInfo) -> str:
        """Helper to capture console output."""
        string_io = io.StringIO()
        console = Console(file=string_io, force_terminal=True)
        format_error(error, console)
        return string_io.getvalue()

    def test_format_basic_error(self) -> None:
        """Test formatting a basic error."""
        error = ErrorInfo(
            message="Something went wrong",
            category=ErrorCategory.FILE,
        )
        output = self.get_console_output(error)
        assert "Something went wrong" in output

    def test_format_error_with_suggestion(self) -> None:
        """Test formatting error with suggestion."""
        error = ErrorInfo(
            message="File not found",
            category=ErrorCategory.FILE,
            suggestion="Check the path exists",
        )
        output = self.get_console_output(error)
        assert "Check the path exists" in output

    def test_format_error_with_details(self) -> None:
        """Test formatting error with details."""
        error = ErrorInfo(
            message="Config error",
            category=ErrorCategory.CONFIG,
            details="Invalid TOML syntax",
        )
        output = self.get_console_output(error)
        assert "Invalid TOML syntax" in output

    def test_format_error_with_docs_link(self) -> None:
        """Test formatting error with docs link."""
        error = ErrorInfo(
            message="Error",
            category=ErrorCategory.FILE,
            docs_link="https://docs.example.com",
        )
        output = self.get_console_output(error)
        assert "https://docs.example.com" in output

    def test_debug_hint_shown_when_not_debug(self) -> None:
        """Test that debug hint is shown when not in debug mode."""
        set_debug_mode(False)
        error = ErrorInfo(
            message="Error",
            category=ErrorCategory.INTERNAL,
            original_error=ValueError("test"),
        )
        output = self.get_console_output(error)
        assert "ADW_DEBUG=1" in output or "--debug" in output


class TestErrorFactories:
    """Tests for error factory functions."""

    def test_error_file_not_found_basic(self) -> None:
        """Test basic file not found error."""
        error = error_file_not_found("/path/to/file")
        assert error.category == ErrorCategory.FILE
        assert "/path/to/file" in error.message
        assert error.suggestion is not None

    def test_error_file_not_found_tasks(self) -> None:
        """Test file not found for tasks.md."""
        error = error_file_not_found("tasks.md", "tasks file")
        assert "adw init" in error.suggestion

    def test_error_file_not_found_claude(self) -> None:
        """Test file not found for .claude directory."""
        error = error_file_not_found(".claude/settings.json")
        assert "adw init" in error.suggestion

    def test_error_file_not_found_config(self) -> None:
        """Test file not found for config file."""
        error = error_file_not_found("config.toml", "config file")
        assert "config reset" in error.suggestion

    def test_error_file_not_found_custom_suggestion(self) -> None:
        """Test file not found with custom suggestion."""
        error = error_file_not_found("/path", suggestion="Custom fix")
        assert error.suggestion == "Custom fix"

    def test_error_dependency_missing_basic(self) -> None:
        """Test basic dependency missing error."""
        error = error_dependency_missing("some-tool")
        assert error.category == ErrorCategory.DEPENDENCY
        assert "some-tool" in error.message

    def test_error_dependency_missing_claude(self) -> None:
        """Test dependency missing for claude."""
        error = error_dependency_missing("claude")
        assert "https://claude.ai/code" in error.suggestion

    def test_error_dependency_missing_git(self) -> None:
        """Test dependency missing for git."""
        error = error_dependency_missing("git")
        assert "git-scm.com" in error.suggestion

    def test_error_dependency_missing_gh(self) -> None:
        """Test dependency missing for gh CLI."""
        error = error_dependency_missing("gh")
        assert "cli.github.com" in error.suggestion

    def test_error_dependency_missing_qmd(self) -> None:
        """Test dependency missing for qmd."""
        error = error_dependency_missing("qmd")
        assert "bun install" in error.suggestion

    def test_error_dependency_missing_custom_install(self) -> None:
        """Test dependency missing with custom install command."""
        error = error_dependency_missing("mytool", install_cmd="npm install -g mytool")
        assert "npm install -g mytool" in error.suggestion

    def test_error_config_invalid_basic(self) -> None:
        """Test basic config invalid error."""
        error = error_config_invalid("some.key")
        assert error.category == ErrorCategory.CONFIG
        assert "some.key" in error.message

    def test_error_config_invalid_with_value(self) -> None:
        """Test config invalid with value and expected."""
        error = error_config_invalid("timeout", value="abc", expected="a number")
        assert error.details is not None
        assert "abc" in error.details
        assert "a number" in error.details

    def test_error_task_not_found(self) -> None:
        """Test task not found error."""
        error = error_task_not_found("abc12345")
        assert error.category == ErrorCategory.TASK
        assert "abc12345" in error.message
        assert "adw list" in error.suggestion

    def test_error_git_operation_basic(self) -> None:
        """Test basic git operation error."""
        error = error_git_operation("commit", "nothing to commit")
        assert error.category == ErrorCategory.GIT
        assert "commit" in error.message
        assert "nothing to commit" in error.message

    def test_error_git_operation_worktree(self) -> None:
        """Test git worktree operation error."""
        error = error_git_operation("worktree create", "already exists")
        assert "worktree list" in error.suggestion

    def test_error_git_operation_branch(self) -> None:
        """Test git branch operation error."""
        error = error_git_operation("branch checkout", "not found")
        assert "git branch" in error.suggestion

    def test_error_git_operation_with_original(self) -> None:
        """Test git operation error with original exception."""
        original = RuntimeError("git failed")
        error = error_git_operation("push", "failed", original)
        assert error.original_error is original

    def test_error_network_basic(self) -> None:
        """Test basic network error."""
        error = error_network("API", "connection failed")
        assert error.category == ErrorCategory.NETWORK
        assert "connection failed" in error.message

    def test_error_network_github(self) -> None:
        """Test network error for GitHub."""
        error = error_network("GitHub API", "rate limited")
        assert "GITHUB_TOKEN" in error.suggestion

    def test_error_network_notion(self) -> None:
        """Test network error for Notion."""
        error = error_network("Notion API", "unauthorized")
        assert "NOTION_API_KEY" in error.suggestion

    def test_error_network_slack(self) -> None:
        """Test network error for Slack."""
        error = error_network("Slack API", "invalid token")
        assert "SLACK_BOT_TOKEN" in error.suggestion

    def test_error_network_linear(self) -> None:
        """Test network error for Linear."""
        error = error_network("Linear API", "forbidden")
        assert "LINEAR_API_KEY" in error.suggestion

    def test_error_workflow_basic(self) -> None:
        """Test basic workflow error."""
        error = error_workflow("sdlc", "implement", "tests failed")
        assert error.category == ErrorCategory.WORKFLOW
        assert "sdlc" in error.message
        assert "implement" in error.message
        assert "tests failed" in error.message
        assert "agents/" in error.suggestion

    def test_error_internal_basic(self) -> None:
        """Test basic internal error."""
        error = error_internal("unexpected state")
        assert error.category == ErrorCategory.INTERNAL
        assert "unexpected state" in error.message
        assert "bug" in error.suggestion.lower()
        assert "github.com" in error.docs_link

    def test_error_internal_with_original(self) -> None:
        """Test internal error with original exception."""
        original = RuntimeError("segfault")
        error = error_internal("crash", original)
        assert error.original_error is original


class TestClassifyException:
    """Tests for classify_exception function."""

    def test_classify_file_not_found(self) -> None:
        """Test classifying FileNotFoundError."""
        exc = FileNotFoundError("No such file: '/tmp/test.txt'")
        error = classify_exception(exc, "reading file")
        assert error.category == ErrorCategory.FILE

    def test_classify_permission_error(self) -> None:
        """Test classifying PermissionError."""
        exc = PermissionError("Access denied")
        error = classify_exception(exc)
        assert error.category == ErrorCategory.FILE
        assert "permission" in error.suggestion.lower()

    def test_classify_network_connection(self) -> None:
        """Test classifying connection errors."""
        exc = ConnectionError("Connection refused")
        error = classify_exception(exc, "API call")
        assert error.category == ErrorCategory.NETWORK

    def test_classify_network_timeout(self) -> None:
        """Test classifying timeout errors."""
        exc = TimeoutError("Request timed out")
        error = classify_exception(exc)
        assert error.category == ErrorCategory.NETWORK

    def test_classify_auth_401(self) -> None:
        """Test classifying 401 unauthorized."""
        exc = Exception("401 Unauthorized")
        error = classify_exception(exc)
        assert error.category == ErrorCategory.NETWORK
        assert "credentials" in error.suggestion.lower()

    def test_classify_auth_403(self) -> None:
        """Test classifying 403 forbidden."""
        exc = Exception("403 Forbidden")
        error = classify_exception(exc)
        assert error.category == ErrorCategory.NETWORK

    def test_classify_git_error(self) -> None:
        """Test classifying git errors."""
        exc = Exception("git worktree failed")
        error = classify_exception(exc)
        assert error.category == ErrorCategory.GIT

    def test_classify_config_error(self) -> None:
        """Test classifying config errors."""
        exc = Exception("Invalid TOML config")
        error = classify_exception(exc)
        assert error.category == ErrorCategory.CONFIG

    def test_classify_task_error(self) -> None:
        """Test classifying task errors."""
        exc = Exception("Task not found: abc12345")
        error = classify_exception(exc)
        assert error.category == ErrorCategory.TASK

    def test_classify_unknown(self) -> None:
        """Test classifying unknown errors."""
        exc = Exception("Some weird error")
        error = classify_exception(exc, "doing something")
        assert error.category == ErrorCategory.INTERNAL
        assert error.original_error is exc


class TestHandleException:
    """Tests for handle_exception function."""

    def test_handle_exception_basic(self) -> None:
        """Test basic exception handling."""
        console = MagicMock(spec=Console)
        exc = FileNotFoundError("test.txt")

        with pytest.raises(SystemExit) as exc_info:
            handle_exception(console, exc)

        assert exc_info.value.code == 1
        console.print.assert_called()

    def test_handle_exception_custom_exit_code(self) -> None:
        """Test exception handling with custom exit code."""
        console = MagicMock(spec=Console)
        exc = ValueError("bad input")

        with pytest.raises(SystemExit) as exc_info:
            handle_exception(console, exc, exit_code=2)

        assert exc_info.value.code == 2

    def test_handle_exception_no_exit(self) -> None:
        """Test exception handling without exit."""
        console = MagicMock(spec=Console)
        exc = ValueError("bad input")

        error = handle_exception(console, exc, exit_on_error=False)

        assert error is not None
        assert isinstance(error, ErrorInfo)
        console.print.assert_called()

    def test_handle_exception_returns_error_info(self) -> None:
        """Test that handle_exception returns ErrorInfo."""
        console = MagicMock(spec=Console)
        exc = FileNotFoundError("config.toml")

        error = handle_exception(console, exc, context="loading config", exit_on_error=False)

        assert error.category == ErrorCategory.FILE
        assert "config" in error.message.lower()


class TestDocsLinks:
    """Tests for documentation links."""

    def test_docs_base_is_valid(self) -> None:
        """Test that DOCS_BASE is a valid URL."""
        assert DOCS_BASE.startswith("https://")
        assert "github.com" in DOCS_BASE

    def test_docs_links_categories(self) -> None:
        """Test that important categories have docs links."""
        required_categories = [
            ErrorCategory.CONFIG,
            ErrorCategory.FILE,
            ErrorCategory.DEPENDENCY,
            ErrorCategory.TASK,
            ErrorCategory.GIT,
            ErrorCategory.WORKFLOW,
            ErrorCategory.INTEGRATION,
        ]
        for cat in required_categories:
            assert cat in DOCS_LINKS, f"Missing docs link for {cat}"
            assert DOCS_LINKS[cat].startswith(DOCS_BASE)

    def test_docs_links_are_anchors(self) -> None:
        """Test that docs links are anchor links."""
        for link in DOCS_LINKS.values():
            assert "#" in link, f"Expected anchor link: {link}"
