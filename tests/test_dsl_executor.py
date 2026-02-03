"""Tests for DSL workflow executor module."""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from adw.workflows.dsl import (
    LoopCondition,
    PhaseCondition,
    PhaseDefinition,
    WorkflowDefinition,
)
from adw.workflows.dsl_executor import (
    DSLExecutionContext,
    DSLPhaseResult,
    check_env_set,
    check_file_exists,
    check_git_changes,
    evaluate_condition,
    format_dsl_results_summary,
    run_workflow_by_name,
)


# =============================================================================
# DSLPhaseResult Tests
# =============================================================================


class TestDSLPhaseResult:
    """Tests for DSLPhaseResult dataclass."""

    def test_create_minimal_result(self) -> None:
        """Test creating a result with minimal fields."""
        result = DSLPhaseResult(phase_name="test", success=True)
        assert result.phase_name == "test"
        assert result.success is True
        assert result.output == ""
        assert result.error is None
        assert result.duration_seconds == 0.0
        assert result.loop_iterations == 1

    def test_create_result_with_error(self) -> None:
        """Test creating a result with error."""
        result = DSLPhaseResult(
            phase_name="build",
            success=False,
            error="Build failed",
            duration_seconds=15.5,
        )
        assert result.success is False
        assert result.error == "Build failed"
        assert result.duration_seconds == 15.5

    def test_create_result_with_all_fields(self) -> None:
        """Test creating a result with all fields."""
        result = DSLPhaseResult(
            phase_name="implement",
            success=True,
            output="Task completed",
            duration_seconds=120.0,
            loop_iterations=3,
        )
        assert result.phase_name == "implement"
        assert result.success is True
        assert result.output == "Task completed"
        assert result.loop_iterations == 3


# =============================================================================
# DSLExecutionContext Tests
# =============================================================================


class TestDSLExecutionContext:
    """Tests for DSLExecutionContext dataclass."""

    def test_create_minimal_context(self, tmp_path: Path) -> None:
        """Test creating a context with minimal fields."""
        mock_state = MagicMock()
        context = DSLExecutionContext(
            task_description="Test task",
            adw_id="abc12345",
            worktree_path=tmp_path,
            state=mock_state,
        )
        assert context.task_description == "Test task"
        assert context.adw_id == "abc12345"
        assert context.worktree_path == tmp_path
        assert context.last_test_passed is True
        assert context.has_changes is False
        assert context.phase_results == {}

    def test_context_phase_results_initialized(self, tmp_path: Path) -> None:
        """Test that phase_results is initialized to empty dict."""
        mock_state = MagicMock()
        context = DSLExecutionContext(
            task_description="Test",
            adw_id="test123",
            worktree_path=tmp_path,
            state=mock_state,
        )
        assert context.phase_results is not None
        assert isinstance(context.phase_results, dict)

    def test_context_custom_values(self, tmp_path: Path) -> None:
        """Test creating context with custom values."""
        mock_state = MagicMock()
        context = DSLExecutionContext(
            task_description="Custom task",
            adw_id="custom12",
            worktree_path=tmp_path,
            state=mock_state,
            last_test_passed=False,
            has_changes=True,
        )
        assert context.last_test_passed is False
        assert context.has_changes is True


# =============================================================================
# Condition Check Tests
# =============================================================================


class TestConditionChecks:
    """Tests for condition checking functions."""

    def test_check_git_changes_clean(self, tmp_path: Path) -> None:
        """Test git changes check on clean repo."""
        # Initialize a git repo
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=tmp_path,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=tmp_path,
            capture_output=True,
        )

        # Create and commit a file
        (tmp_path / "test.txt").write_text("test")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "initial"],
            cwd=tmp_path,
            capture_output=True,
        )

        # Should have no changes
        assert check_git_changes(tmp_path) is False

    def test_check_git_changes_dirty(self, tmp_path: Path) -> None:
        """Test git changes check on dirty repo."""
        # Initialize a git repo
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=tmp_path,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=tmp_path,
            capture_output=True,
        )

        # Create and commit a file
        (tmp_path / "test.txt").write_text("test")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "initial"],
            cwd=tmp_path,
            capture_output=True,
        )

        # Make a change
        (tmp_path / "test.txt").write_text("modified")

        # Should have changes
        assert check_git_changes(tmp_path) is True

    def test_check_git_changes_not_git_repo(self, tmp_path: Path) -> None:
        """Test git changes check on non-git directory."""
        # Should return False (no error)
        assert check_git_changes(tmp_path) is False

    def test_check_file_exists_true(self, tmp_path: Path) -> None:
        """Test file exists check when file exists."""
        (tmp_path / "README.md").write_text("# Test")
        assert check_file_exists(tmp_path, "README.md") is True

    def test_check_file_exists_false(self, tmp_path: Path) -> None:
        """Test file exists check when file doesn't exist."""
        assert check_file_exists(tmp_path, "nonexistent.md") is False

    def test_check_file_exists_nested(self, tmp_path: Path) -> None:
        """Test file exists check for nested file."""
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text("# Main")
        assert check_file_exists(tmp_path, "src/main.py") is True

    def test_check_env_set_true(self) -> None:
        """Test env check when variable is set."""
        os.environ["TEST_VAR_123"] = "value"
        try:
            assert check_env_set("TEST_VAR_123") is True
        finally:
            del os.environ["TEST_VAR_123"]

    def test_check_env_set_false(self) -> None:
        """Test env check when variable is not set."""
        # Make sure it's not set
        os.environ.pop("DEFINITELY_NOT_SET_VAR", None)
        assert check_env_set("DEFINITELY_NOT_SET_VAR") is False

    def test_check_env_set_empty(self) -> None:
        """Test env check when variable is set but empty."""
        os.environ["EMPTY_VAR_123"] = ""
        try:
            assert check_env_set("EMPTY_VAR_123") is False
        finally:
            del os.environ["EMPTY_VAR_123"]


# =============================================================================
# Evaluate Condition Tests
# =============================================================================


class TestEvaluateCondition:
    """Tests for evaluate_condition function."""

    def test_condition_always(self, tmp_path: Path) -> None:
        """Test ALWAYS condition."""
        mock_state = MagicMock()
        context = DSLExecutionContext(
            task_description="Test",
            adw_id="test123",
            worktree_path=tmp_path,
            state=mock_state,
        )
        assert evaluate_condition(PhaseCondition.ALWAYS, None, context) is True

    def test_condition_tests_passed(self, tmp_path: Path) -> None:
        """Test TESTS_PASSED condition."""
        mock_state = MagicMock()
        context = DSLExecutionContext(
            task_description="Test",
            adw_id="test123",
            worktree_path=tmp_path,
            state=mock_state,
            last_test_passed=True,
        )
        assert evaluate_condition(PhaseCondition.TESTS_PASSED, None, context) is True

        context.last_test_passed = False
        assert evaluate_condition(PhaseCondition.TESTS_PASSED, None, context) is False

    def test_condition_tests_failed(self, tmp_path: Path) -> None:
        """Test TESTS_FAILED condition."""
        mock_state = MagicMock()
        context = DSLExecutionContext(
            task_description="Test",
            adw_id="test123",
            worktree_path=tmp_path,
            state=mock_state,
            last_test_passed=False,
        )
        assert evaluate_condition(PhaseCondition.TESTS_FAILED, None, context) is True

        context.last_test_passed = True
        assert evaluate_condition(PhaseCondition.TESTS_FAILED, None, context) is False

    def test_condition_file_exists(self, tmp_path: Path) -> None:
        """Test FILE_EXISTS condition."""
        mock_state = MagicMock()
        context = DSLExecutionContext(
            task_description="Test",
            adw_id="test123",
            worktree_path=tmp_path,
            state=mock_state,
        )

        # File doesn't exist
        assert evaluate_condition(
            PhaseCondition.FILE_EXISTS, "README.md", context
        ) is False

        # Create file
        (tmp_path / "README.md").write_text("# Test")
        assert evaluate_condition(
            PhaseCondition.FILE_EXISTS, "README.md", context
        ) is True

    def test_condition_file_exists_no_value(self, tmp_path: Path) -> None:
        """Test FILE_EXISTS condition without value defaults to True."""
        mock_state = MagicMock()
        context = DSLExecutionContext(
            task_description="Test",
            adw_id="test123",
            worktree_path=tmp_path,
            state=mock_state,
        )
        # Missing value should default to True
        assert evaluate_condition(PhaseCondition.FILE_EXISTS, None, context) is True

    def test_condition_env_set(self, tmp_path: Path) -> None:
        """Test ENV_SET condition."""
        mock_state = MagicMock()
        context = DSLExecutionContext(
            task_description="Test",
            adw_id="test123",
            worktree_path=tmp_path,
            state=mock_state,
        )

        os.environ["TEST_COND_VAR"] = "set"
        try:
            assert evaluate_condition(
                PhaseCondition.ENV_SET, "TEST_COND_VAR", context
            ) is True
        finally:
            del os.environ["TEST_COND_VAR"]

        assert evaluate_condition(
            PhaseCondition.ENV_SET, "NOT_SET_VAR_XYZ", context
        ) is False

    def test_condition_env_set_no_value(self, tmp_path: Path) -> None:
        """Test ENV_SET condition without value defaults to True."""
        mock_state = MagicMock()
        context = DSLExecutionContext(
            task_description="Test",
            adw_id="test123",
            worktree_path=tmp_path,
            state=mock_state,
        )
        # Missing value should default to True
        assert evaluate_condition(PhaseCondition.ENV_SET, None, context) is True


# =============================================================================
# Format Summary Tests
# =============================================================================


class TestFormatSummary:
    """Tests for format_dsl_results_summary function."""

    def test_format_empty_results(self) -> None:
        """Test formatting empty results."""
        summary = format_dsl_results_summary("test-workflow", [])
        assert "test-workflow" in summary
        assert "0/0 phases" in summary

    def test_format_success_results(self) -> None:
        """Test formatting successful results."""
        results = [
            DSLPhaseResult(phase_name="plan", success=True, duration_seconds=10.5),
            DSLPhaseResult(phase_name="implement", success=True, duration_seconds=60.0),
        ]
        summary = format_dsl_results_summary("my-workflow", results)

        assert "my-workflow" in summary
        assert "✅" in summary
        assert "plan" in summary
        assert "implement" in summary
        assert "2/2 phases" in summary
        assert "70.5s" in summary

    def test_format_failed_results(self) -> None:
        """Test formatting failed results."""
        results = [
            DSLPhaseResult(phase_name="plan", success=True, duration_seconds=10.0),
            DSLPhaseResult(
                phase_name="implement",
                success=False,
                error="Build error",
                duration_seconds=30.0,
            ),
        ]
        summary = format_dsl_results_summary("failed-workflow", results)

        assert "❌" in summary
        assert "Build error" in summary
        assert "1/2 phases" in summary

    def test_format_with_loop_iterations(self) -> None:
        """Test formatting results with loop iterations."""
        results = [
            DSLPhaseResult(
                phase_name="fix",
                success=True,
                duration_seconds=45.0,
                loop_iterations=3,
            ),
        ]
        summary = format_dsl_results_summary("loop-workflow", results)

        assert "3 iterations" in summary


# =============================================================================
# Run Workflow By Name Tests
# =============================================================================


class TestRunWorkflowByName:
    """Tests for run_workflow_by_name function."""

    def test_workflow_not_found(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test running non-existent workflow raises error."""
        # Mock the workflow directories
        monkeypatch.setattr(
            "adw.workflows.dsl.get_workflows_dir",
            lambda: tmp_path / "user_workflows",
        )
        monkeypatch.setattr(
            "adw.workflows.dsl.get_builtin_workflows_dir",
            lambda: tmp_path / "builtin",
        )

        with pytest.raises(ValueError, match="not found"):
            run_workflow_by_name(
                workflow_name="nonexistent-workflow",
                task_description="Test task",
                worktree_name="test",
            )


# =============================================================================
# Workflow Definition Integration Tests
# =============================================================================


class TestWorkflowDefinitionIntegration:
    """Integration tests for workflow definitions with executor."""

    def test_phase_definition_compatible(self) -> None:
        """Test that PhaseDefinition is compatible with executor."""
        phase = PhaseDefinition(
            name="test",
            prompt="Test prompt {{task_description}}",
            model="sonnet",
            condition=PhaseCondition.ALWAYS,
            loop=LoopCondition.NONE,
        )
        assert phase.name == "test"
        assert "{{task_description}}" in phase.prompt

    def test_workflow_definition_compatible(self) -> None:
        """Test that WorkflowDefinition is compatible with executor."""
        phases = [
            PhaseDefinition(name="plan", prompt="Plan it"),
            PhaseDefinition(name="implement", prompt="Build it"),
        ]
        workflow = WorkflowDefinition(
            name="test-workflow",
            phases=phases,
            fail_fast=True,
        )
        assert workflow.name == "test-workflow"
        assert len(workflow.phases) == 2
        assert workflow.fail_fast is True

    def test_loop_condition_values(self) -> None:
        """Test that loop condition values are correct."""
        assert LoopCondition.NONE.value == "none"
        assert LoopCondition.UNTIL_SUCCESS.value == "until_success"
        assert LoopCondition.UNTIL_TESTS_PASS.value == "until_tests_pass"
        assert LoopCondition.FIXED_COUNT.value == "fixed_count"

    def test_phase_condition_values(self) -> None:
        """Test that phase condition values are correct."""
        assert PhaseCondition.ALWAYS.value == "always"
        assert PhaseCondition.HAS_CHANGES.value == "has_changes"
        assert PhaseCondition.TESTS_PASSED.value == "tests_passed"
        assert PhaseCondition.TESTS_FAILED.value == "tests_failed"


# =============================================================================
# Prototype Workflow Tests
# =============================================================================


class TestPrototypeConfig:
    """Tests for prototype configuration."""

    def test_import_prototype_functions(self) -> None:
        """Test that prototype functions are importable."""
        from adw.workflows.prototype import (
            PROTOTYPES,
            PrototypeConfig,
            PrototypeResult,
            get_prototype_config,
            list_prototypes,
        )

        assert len(PROTOTYPES) >= 5
        assert get_prototype_config("vite_vue") is not None
        assert len(list_prototypes()) >= 5

    def test_prototype_config_structure(self) -> None:
        """Test prototype config has required fields."""
        from adw.workflows.prototype import get_prototype_config

        config = get_prototype_config("vite_vue")
        assert config is not None
        assert config.name == "Vite + Vue"
        assert config.plan_command == "/plan_vite_vue"
        assert len(config.file_patterns) > 0

    def test_prototype_result_structure(self) -> None:
        """Test PrototypeResult has correct structure."""
        from adw.workflows.prototype import PrototypeResult

        result = PrototypeResult(success=True)
        assert result.success is True
        assert result.output_dir is None
        assert result.error is None
        assert result.files_created == []
        assert result.duration_seconds == 0.0

    def test_build_scaffold_prompt(self) -> None:
        """Test scaffold prompt building."""
        from adw.workflows.prototype import build_scaffold_prompt, get_prototype_config

        config = get_prototype_config("fastapi")
        assert config is not None

        prompt = build_scaffold_prompt(
            config=config,
            app_name="my-api",
            description="A REST API",
            output_dir=Path("apps/my-api"),
        )

        assert "my-api" in prompt
        assert "A REST API" in prompt
        assert "apps/my-api" in prompt
        assert "FastAPI" in prompt

    def test_build_verify_prompt(self) -> None:
        """Test verify prompt building."""
        from adw.workflows.prototype import build_verify_prompt, get_prototype_config

        config = get_prototype_config("vite_vue")
        assert config is not None

        prompt = build_verify_prompt(
            config=config,
            app_name="my-app",
            output_dir=Path("apps/my-app"),
        )

        assert "my-app" in prompt
        assert "apps/my-app" in prompt
        assert "Vite + Vue" in prompt


# =============================================================================
# Agent Manager Integration Tests
# =============================================================================


class TestAgentManagerDSLSupport:
    """Tests for agent manager DSL workflow support."""

    def test_builtin_workflows_constant(self) -> None:
        """Test that builtin workflows constant exists."""
        from adw.agent.manager import BUILTIN_PYTHON_WORKFLOWS

        assert "simple" in BUILTIN_PYTHON_WORKFLOWS
        assert "standard" in BUILTIN_PYTHON_WORKFLOWS
        assert "sdlc" in BUILTIN_PYTHON_WORKFLOWS

    def test_manager_has_spawn_workflow(self) -> None:
        """Test that AgentManager has spawn_workflow method."""
        from adw.agent.manager import AgentManager

        manager = AgentManager()
        assert hasattr(manager, "spawn_workflow")
        assert callable(manager.spawn_workflow)
