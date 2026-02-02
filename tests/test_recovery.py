"""Tests for the recovery module (Phase 8).

Tests error classification, recovery strategies, and checkpoint system.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from adw.recovery.classifier import (
    ErrorClass,
    ClassificationResult,
    classify_error,
    is_retriable,
    is_fixable,
    is_fatal,
)
from adw.recovery.strategies import (
    RecoveryStrategyType,
    RecoveryResult,
    RecoveryStrategy,
    RetryRecoveryStrategy,
    FixRecoveryStrategy,
    SimplifyRecoveryStrategy,
    EscalateRecoveryStrategy,
    select_recovery_strategy,
    RecoveryOrchestrator,
)
from adw.recovery.checkpoints import (
    Checkpoint,
    CheckpointManager,
    save_checkpoint,
    load_checkpoint,
    list_checkpoints,
    get_last_checkpoint,
    get_last_successful_checkpoint,
    delete_checkpoint,
    clear_checkpoints,
    clear_old_checkpoints,
    create_wip_commit,
)


# =============================================================================
# Error Classifier Tests
# =============================================================================


class TestErrorClassification:
    """Tests for error classification."""

    def test_classify_empty_error(self):
        """Empty error should return unknown."""
        result = classify_error("")
        assert result.error_class == ErrorClass.UNKNOWN
        assert result.confidence == 0.0

    def test_classify_none_error(self):
        """None-like error should return unknown."""
        result = classify_error("")
        assert result.error_class == ErrorClass.UNKNOWN


class TestRetriableErrors:
    """Tests for retriable error classification."""

    @pytest.mark.parametrize(
        "error_message",
        [
            "Connection refused",
            "connection timed out",
            "Network error: socket unreachable",
            "ECONNREFUSED: connection refused",
            "ETIMEDOUT: timeout reached",
            "DNS resolution failed for api.example.com",
        ],
    )
    def test_network_errors(self, error_message: str):
        """Network errors should be classified as retriable."""
        result = classify_error(error_message)
        assert result.error_class == ErrorClass.RETRIABLE
        assert is_retriable(error_message)

    @pytest.mark.parametrize(
        "error_message",
        [
            "Rate limit exceeded",
            "Error 429: Too many requests",
            "quota exceeded for API",
            "Request throttled, please wait",
        ],
    )
    def test_rate_limit_errors(self, error_message: str):
        """Rate limit errors should be classified as retriable."""
        result = classify_error(error_message)
        assert result.error_class == ErrorClass.RETRIABLE

    @pytest.mark.parametrize(
        "error_message",
        [
            "Operation timeout after 30s",
            "Request timed out",
            "Deadline exceeded",
            "Operation took too long",
        ],
    )
    def test_timeout_errors(self, error_message: str):
        """Timeout errors should be classified as retriable."""
        result = classify_error(error_message)
        assert result.error_class == ErrorClass.RETRIABLE

    @pytest.mark.parametrize(
        "error_message",
        [
            "Service temporarily unavailable",
            "Server returned 503",
            "502 Bad Gateway",
            "Please try again later",
            "Temporary failure, retrying",
        ],
    )
    def test_temporary_errors(self, error_message: str):
        """Temporary server errors should be classified as retriable."""
        result = classify_error(error_message)
        assert result.error_class == ErrorClass.RETRIABLE


class TestFixableErrors:
    """Tests for fixable error classification."""

    @pytest.mark.parametrize(
        "error_message",
        [
            "Tests failed: 3 passed, 2 failed",
            "AssertionError: expected True but got False",
            "FAILED test_module.py::test_function",
            "pytest: 5 tests failed",
            "Expected 42 but received 0",
        ],
    )
    def test_test_failures(self, error_message: str):
        """Test failures should be classified as fixable."""
        result = classify_error(error_message)
        assert result.error_class == ErrorClass.FIXABLE
        assert is_fixable(error_message)

    @pytest.mark.parametrize(
        "error_message",
        [
            "Linter error: line too long",
            "ruff check failed with errors",
            "eslint error: 5 errors found",
            "pylint error: convention violations",
            "Formatting check failed",
            "black format failed",
        ],
    )
    def test_lint_errors(self, error_message: str):
        """Lint and format errors should be classified as fixable."""
        result = classify_error(error_message)
        assert result.error_class == ErrorClass.FIXABLE

    @pytest.mark.parametrize(
        "error_message",
        [
            "SyntaxError: invalid syntax",
            "Parse error: unexpected token",
            "TypeError: cannot add int and str",
            "mypy: found 3 errors",
            "NameError: name 'foo' is not defined",
        ],
    )
    def test_syntax_type_errors(self, error_message: str):
        """Syntax and type errors should be classified as fixable."""
        result = classify_error(error_message)
        assert result.error_class == ErrorClass.FIXABLE

    @pytest.mark.parametrize(
        "error_message",
        [
            "ImportError: No module named 'missing_module'",
            "No module named 'foo'",
            "Cannot find module 'express'",
            "Cannot resolve module ./utils",
        ],
    )
    def test_import_errors(self, error_message: str):
        """Import errors should be classified as fixable."""
        result = classify_error(error_message)
        assert result.error_class == ErrorClass.FIXABLE


class TestFatalErrors:
    """Tests for fatal error classification."""

    @pytest.mark.parametrize(
        "error_message",
        [
            "Configuration error: invalid settings",
            "Invalid config file format",
            "YAML parse error in config.yaml",
            "TOML parse error in pyproject.toml",
        ],
    )
    def test_config_errors(self, error_message: str):
        """Configuration errors should be classified as fatal."""
        result = classify_error(error_message)
        assert result.error_class == ErrorClass.FATAL
        assert is_fatal(error_message)

    @pytest.mark.parametrize(
        "error_message",
        [
            "Missing dependencies: package-x not found",
            "Version conflict between package-a and package-b",
            "Peer dependency not satisfied",
            "Command not found: node",
            "Cannot find executable: python3",
        ],
    )
    def test_dependency_errors(self, error_message: str):
        """Dependency errors should be classified as fatal."""
        result = classify_error(error_message)
        assert result.error_class == ErrorClass.FATAL

    @pytest.mark.parametrize(
        "error_message",
        [
            "Permission denied: /etc/passwd",
            "Access denied to directory",
            "EACCES: cannot write to file",
            "Read-only file system",
        ],
    )
    def test_permission_errors(self, error_message: str):
        """Permission errors should be classified as fatal."""
        result = classify_error(error_message)
        assert result.error_class == ErrorClass.FATAL

    @pytest.mark.parametrize(
        "error_message",
        [
            "Disk full: no space left",
            "Out of memory",
            "OOM killed",
            "Memory allocation failed: ENOMEM",
        ],
    )
    def test_resource_errors(self, error_message: str):
        """Resource exhaustion errors should be classified as fatal."""
        result = classify_error(error_message)
        assert result.error_class == ErrorClass.FATAL

    @pytest.mark.parametrize(
        "error_message",
        [
            "Authentication failed: invalid credentials",
            "Error 401: Unauthorized",
            "403 Forbidden",
            "Invalid API key",
            "Token expired, please re-authenticate",
        ],
    )
    def test_auth_errors(self, error_message: str):
        """Authentication errors should be classified as fatal."""
        result = classify_error(error_message)
        assert result.error_class == ErrorClass.FATAL

    @pytest.mark.parametrize(
        "error_message",
        [
            "Git error: merge conflict",
            "fatal: not a git repository",
            "Conflict markers found in file.py",
        ],
    )
    def test_git_errors(self, error_message: str):
        """Git errors should be classified as fatal."""
        result = classify_error(error_message)
        assert result.error_class == ErrorClass.FATAL


class TestClassificationResult:
    """Tests for ClassificationResult."""

    def test_classification_result_fields(self):
        """Classification result should have all fields."""
        result = classify_error("Connection refused")
        assert hasattr(result, "error_class")
        assert hasattr(result, "confidence")
        assert hasattr(result, "reason")
        assert hasattr(result, "suggested_action")

    def test_confidence_in_range(self):
        """Confidence should be between 0 and 1."""
        for error in [
            "Connection refused",
            "Test failed",
            "Permission denied",
            "Unknown error xyz",
        ]:
            result = classify_error(error)
            assert 0.0 <= result.confidence <= 1.0


# =============================================================================
# Recovery Strategies Tests
# =============================================================================


class TestRetryRecoveryStrategy:
    """Tests for RetryRecoveryStrategy."""

    def test_strategy_type(self):
        """Strategy should report correct type."""
        strategy = RetryRecoveryStrategy()
        assert strategy.strategy_type == RecoveryStrategyType.RETRY

    def test_apply_with_remaining_attempts(self):
        """Should continue when attempts remain."""
        strategy = RetryRecoveryStrategy()
        result = strategy.apply("Network error", attempt_number=1, max_attempts=3)
        assert result.success is True
        assert result.should_continue is True
        assert result.wait_seconds > 0

    def test_apply_max_attempts_exhausted(self):
        """Should stop when max attempts reached."""
        strategy = RetryRecoveryStrategy()
        result = strategy.apply("Network error", attempt_number=4, max_attempts=3)
        assert result.success is False
        assert result.should_continue is False

    def test_exponential_backoff(self):
        """Delay should increase exponentially."""
        strategy = RetryRecoveryStrategy(base_delay=1.0, backoff_factor=2.0)
        result1 = strategy.apply("error", attempt_number=1, max_attempts=5)
        result2 = strategy.apply("error", attempt_number=2, max_attempts=5)
        result3 = strategy.apply("error", attempt_number=3, max_attempts=5)
        assert result2.wait_seconds > result1.wait_seconds
        assert result3.wait_seconds > result2.wait_seconds

    def test_max_delay_cap(self):
        """Delay should not exceed max_delay."""
        strategy = RetryRecoveryStrategy(base_delay=10.0, max_delay=20.0, backoff_factor=2.0)
        result = strategy.apply("error", attempt_number=5, max_attempts=10)
        assert result.wait_seconds <= 20.0

    def test_get_retry_context(self):
        """Should generate retry context."""
        strategy = RetryRecoveryStrategy()
        context = strategy.get_retry_context("Network error", 1, 3)
        assert "RETRY" in context
        assert "Network error" in context
        assert "2 attempt(s) remaining" in context


class TestFixRecoveryStrategy:
    """Tests for FixRecoveryStrategy."""

    def test_strategy_type(self):
        """Strategy should report correct type."""
        strategy = FixRecoveryStrategy()
        assert strategy.strategy_type == RecoveryStrategyType.FIX

    def test_apply_with_remaining_attempts(self):
        """Should continue when attempts remain."""
        strategy = FixRecoveryStrategy()
        result = strategy.apply("Test failed", attempt_number=1, max_attempts=3)
        assert result.success is True
        assert result.should_continue is True

    def test_apply_max_attempts_exhausted(self):
        """Should stop when max attempts reached."""
        strategy = FixRecoveryStrategy()
        result = strategy.apply("Test failed", attempt_number=4, max_attempts=3)
        assert result.success is False
        assert result.should_continue is False

    def test_get_retry_context(self):
        """Should generate fix context."""
        strategy = FixRecoveryStrategy()
        context = strategy.get_retry_context("AssertionError", 1, 3)
        assert "FIX REQUIRED" in context
        assert "AssertionError" in context


class TestSimplifyRecoveryStrategy:
    """Tests for SimplifyRecoveryStrategy."""

    def test_strategy_type(self):
        """Strategy should report correct type."""
        strategy = SimplifyRecoveryStrategy()
        assert strategy.strategy_type == RecoveryStrategyType.SIMPLIFY

    def test_apply(self):
        """Should suggest simplification."""
        strategy = SimplifyRecoveryStrategy()
        result = strategy.apply("Complex error", attempt_number=1, max_attempts=3)
        assert result.success is True
        assert result.should_continue is True

    def test_get_retry_context(self):
        """Should generate simplification context."""
        strategy = SimplifyRecoveryStrategy()
        context = strategy.get_retry_context("Complex error", 3, 3)
        assert "SIMPLIFICATION" in context
        assert "CORE functionality" in context


class TestEscalateRecoveryStrategy:
    """Tests for EscalateRecoveryStrategy."""

    def test_strategy_type(self):
        """Strategy should report correct type."""
        strategy = EscalateRecoveryStrategy()
        assert strategy.strategy_type == RecoveryStrategyType.ESCALATE

    def test_apply(self):
        """Should escalate and stop."""
        strategy = EscalateRecoveryStrategy()
        result = strategy.apply("Fatal error", attempt_number=1, max_attempts=3)
        assert result.success is False
        assert result.should_continue is False

    def test_notify_callback(self):
        """Should call notify callback."""
        callback = MagicMock()
        strategy = EscalateRecoveryStrategy(notify_callback=callback)
        strategy.apply("Fatal error", attempt_number=1, max_attempts=3)
        callback.assert_called_once()

    def test_get_retry_context(self):
        """Should generate escalation context."""
        strategy = EscalateRecoveryStrategy()
        context = strategy.get_retry_context("Fatal error", 1, 3)
        assert "ESCALATION" in context
        assert "human intervention" in context


class TestSelectRecoveryStrategy:
    """Tests for select_recovery_strategy function."""

    def test_retriable_error_gets_retry_strategy(self):
        """Retriable errors should get retry strategy."""
        strategy = select_recovery_strategy("Connection refused", 1, 3)
        assert isinstance(strategy, RetryRecoveryStrategy)

    def test_fixable_error_gets_fix_strategy(self):
        """Fixable errors should get fix strategy."""
        strategy = select_recovery_strategy("Test failed", 1, 3)
        assert isinstance(strategy, FixRecoveryStrategy)

    def test_fatal_error_gets_escalate_strategy(self):
        """Fatal errors should get escalate strategy."""
        strategy = select_recovery_strategy("Permission denied", 1, 3)
        assert isinstance(strategy, EscalateRecoveryStrategy)

    def test_final_attempt_gets_simplify_strategy(self):
        """Final attempt should get simplify strategy."""
        strategy = select_recovery_strategy("Test failed", 3, 3)
        assert isinstance(strategy, SimplifyRecoveryStrategy)

    def test_beyond_max_attempts_gets_escalate(self):
        """Beyond max attempts should get escalate strategy."""
        strategy = select_recovery_strategy("Any error", 5, 3)
        assert isinstance(strategy, EscalateRecoveryStrategy)


class TestRecoveryOrchestrator:
    """Tests for RecoveryOrchestrator."""

    def test_initial_state(self):
        """Should start with zero attempts."""
        orchestrator = RecoveryOrchestrator()
        assert orchestrator.current_attempt == 0
        assert orchestrator.attempts_remaining == 3

    def test_attempt_recovery_increments_attempt(self):
        """attempt_recovery should increment attempt counter."""
        orchestrator = RecoveryOrchestrator()
        orchestrator.attempt_recovery("Test failed")
        assert orchestrator.current_attempt == 1

    def test_attempt_history_recorded(self):
        """Attempts should be recorded in history."""
        orchestrator = RecoveryOrchestrator()
        orchestrator.attempt_recovery("Test failed")
        orchestrator.attempt_recovery("Test failed again")
        assert len(orchestrator.attempt_history) == 2
        assert orchestrator.attempt_history[0]["attempt"] == 1
        assert orchestrator.attempt_history[1]["attempt"] == 2

    def test_should_escalate(self):
        """should_escalate should be True after max attempts."""
        orchestrator = RecoveryOrchestrator(max_attempts=2)
        orchestrator.attempt_recovery("Error")
        assert not orchestrator.should_escalate
        orchestrator.attempt_recovery("Error")
        assert orchestrator.should_escalate

    def test_reset(self):
        """reset should clear state."""
        orchestrator = RecoveryOrchestrator()
        orchestrator.attempt_recovery("Error")
        orchestrator.reset()
        assert orchestrator.current_attempt == 0
        assert orchestrator.attempt_history == []


# =============================================================================
# Checkpoint Tests
# =============================================================================


class TestCheckpoint:
    """Tests for Checkpoint dataclass."""

    def test_to_dict(self):
        """Should convert to dictionary."""
        checkpoint = Checkpoint(
            checkpoint_id="20260202T100000",
            adw_id="abc12345",
            phase="implement",
            step="Create main function",
            timestamp="2026-02-02T10:00:00",
            success=True,
            state_snapshot={"key": "value"},
            files_modified=["src/main.py"],
            git_commit="abc123",
            notes="Test checkpoint",
        )
        data = checkpoint.to_dict()
        assert data["checkpoint_id"] == "20260202T100000"
        assert data["adw_id"] == "abc12345"
        assert data["phase"] == "implement"
        assert data["success"] is True

    def test_from_dict(self):
        """Should create from dictionary."""
        data = {
            "checkpoint_id": "20260202T100000",
            "adw_id": "abc12345",
            "phase": "implement",
            "step": "Create main function",
            "timestamp": "2026-02-02T10:00:00",
            "success": True,
            "state_snapshot": {"key": "value"},
            "files_modified": ["src/main.py"],
            "git_commit": "abc123",
            "notes": "Test checkpoint",
        }
        checkpoint = Checkpoint.from_dict(data)
        assert checkpoint.checkpoint_id == "20260202T100000"
        assert checkpoint.phase == "implement"

    def test_to_json_and_back(self):
        """Should serialize and deserialize via JSON."""
        checkpoint = Checkpoint(
            checkpoint_id="20260202T100000",
            adw_id="abc12345",
            phase="test",
            step="Run tests",
            timestamp="2026-02-02T10:00:00",
            success=True,
            state_snapshot={},
        )
        json_str = checkpoint.to_json()
        restored = Checkpoint.from_json(json_str)
        assert restored.checkpoint_id == checkpoint.checkpoint_id
        assert restored.phase == checkpoint.phase


class TestCheckpointPersistence:
    """Tests for checkpoint save/load functions."""

    @pytest.fixture
    def temp_agents_dir(self, tmp_path: Path, monkeypatch):
        """Create temporary agents directory."""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        monkeypatch.chdir(tmp_path)
        return agents_dir

    def test_save_checkpoint(self, temp_agents_dir: Path):
        """Should save checkpoint to disk."""
        checkpoint = save_checkpoint(
            adw_id="test123",
            phase="implement",
            step="Create function",
            state_snapshot={"progress": 50},
        )
        assert checkpoint.adw_id == "test123"
        assert checkpoint.phase == "implement"

        # Check file exists
        checkpoint_path = temp_agents_dir / "test123" / "checkpoints" / f"{checkpoint.checkpoint_id}.json"
        assert checkpoint_path.exists()

    def test_load_checkpoint(self, temp_agents_dir: Path):
        """Should load checkpoint from disk."""
        saved = save_checkpoint(
            adw_id="test123",
            phase="test",
            step="Run tests",
            state_snapshot={"passed": 5},
        )
        loaded = load_checkpoint("test123", saved.checkpoint_id)
        assert loaded is not None
        assert loaded.phase == "test"
        assert loaded.state_snapshot["passed"] == 5

    def test_load_nonexistent_checkpoint(self, temp_agents_dir: Path):
        """Should return None for nonexistent checkpoint."""
        result = load_checkpoint("test123", "nonexistent")
        assert result is None

    def test_list_checkpoints(self, temp_agents_dir: Path):
        """Should list all checkpoints."""
        save_checkpoint("test123", "plan", "Step 1", {})
        save_checkpoint("test123", "implement", "Step 2", {})
        save_checkpoint("test123", "test", "Step 3", {})

        checkpoints = list_checkpoints("test123")
        assert len(checkpoints) == 3
        # Should be sorted newest first
        assert checkpoints[0].phase == "test"

    def test_get_last_checkpoint(self, temp_agents_dir: Path):
        """Should get most recent checkpoint."""
        save_checkpoint("test123", "plan", "Step 1", {})
        save_checkpoint("test123", "implement", "Step 2", {})

        last = get_last_checkpoint("test123")
        assert last is not None
        assert last.phase == "implement"

    def test_get_last_successful_checkpoint(self, temp_agents_dir: Path):
        """Should get most recent successful checkpoint."""
        save_checkpoint("test123", "plan", "Step 1", {}, success=True)
        save_checkpoint("test123", "implement", "Step 2", {}, success=True)
        save_checkpoint("test123", "test", "Step 3", {}, success=False)

        last = get_last_successful_checkpoint("test123")
        assert last is not None
        assert last.phase == "implement"

    def test_delete_checkpoint(self, temp_agents_dir: Path):
        """Should delete specific checkpoint."""
        saved = save_checkpoint("test123", "plan", "Step 1", {})

        result = delete_checkpoint("test123", saved.checkpoint_id)
        assert result is True

        # Should be gone
        loaded = load_checkpoint("test123", saved.checkpoint_id)
        assert loaded is None

    def test_clear_checkpoints(self, temp_agents_dir: Path):
        """Should clear all checkpoints."""
        save_checkpoint("test123", "plan", "Step 1", {})
        save_checkpoint("test123", "implement", "Step 2", {})

        count = clear_checkpoints("test123")
        assert count == 2

        checkpoints = list_checkpoints("test123")
        assert len(checkpoints) == 0


class TestCheckpointManager:
    """Tests for CheckpointManager."""

    @pytest.fixture
    def temp_agents_dir(self, tmp_path: Path, monkeypatch):
        """Create temporary agents directory."""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        monkeypatch.chdir(tmp_path)
        return agents_dir

    def test_checkpoint_method(self, temp_agents_dir: Path):
        """Should save checkpoint via manager."""
        manager = CheckpointManager("test123")
        cp = manager.checkpoint(
            phase="implement",
            step="Create function",
            state={"progress": 50},
        )
        assert cp.phase == "implement"

    def test_get_latest(self, temp_agents_dir: Path):
        """Should get latest checkpoint."""
        manager = CheckpointManager("test123")
        manager.checkpoint("plan", "Step 1", {})
        manager.checkpoint("implement", "Step 2", {})

        latest = manager.get_latest()
        assert latest is not None
        assert latest.phase == "implement"

    def test_get_all(self, temp_agents_dir: Path):
        """Should get all checkpoints."""
        manager = CheckpointManager("test123")
        manager.checkpoint("plan", "Step 1", {})
        manager.checkpoint("implement", "Step 2", {})

        all_checkpoints = manager.get_all()
        assert len(all_checkpoints) == 2

    def test_format_resume_prompt(self, temp_agents_dir: Path):
        """Should format resume prompt."""
        manager = CheckpointManager("test123")
        manager.checkpoint(
            phase="implement",
            step="Create function",
            state={"progress": 50},
            files_modified=["src/main.py"],
        )

        prompt = manager.format_resume_prompt()
        assert prompt is not None
        assert "RESUMING FROM CHECKPOINT" in prompt
        assert "implement" in prompt

    def test_format_resume_prompt_no_checkpoints(self, temp_agents_dir: Path):
        """Should return None when no checkpoints."""
        manager = CheckpointManager("test123")
        prompt = manager.format_resume_prompt()
        assert prompt is None


class TestWIPCommit:
    """Tests for WIP commit functionality."""

    @patch("subprocess.run")
    def test_create_wip_commit_success(self, mock_run: MagicMock):
        """Should create WIP commit."""
        # Mock git commands
        mock_run.side_effect = [
            MagicMock(returncode=0),  # git add
            MagicMock(returncode=1),  # git diff --cached --quiet (has changes)
            MagicMock(returncode=0),  # git commit
            MagicMock(returncode=0, stdout="abc123456789"),  # git rev-parse
        ]

        result = create_wip_commit("test123", "Partial progress")
        assert result is not None
        assert "abc123456789" in result

    @patch("subprocess.run")
    def test_create_wip_commit_no_changes(self, mock_run: MagicMock):
        """Should return None when no changes to commit."""
        mock_run.side_effect = [
            MagicMock(returncode=0),  # git add
            MagicMock(returncode=0),  # git diff --cached --quiet (no changes)
        ]

        result = create_wip_commit("test123", "No changes")
        assert result is None
