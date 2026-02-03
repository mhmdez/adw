"""Tests for DSL workflow executor module."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from adw.agent.models import AgentPromptRequest
from adw.workflows.dsl import (
    LoopCondition,
    PhaseCondition,
    PhaseDefinition,
    WorkflowDefinition,
)
from adw.workflows.dsl_executor import (
    DSLExecutionContext,
    DSLPhaseResult,
    build_parallel_groups,
    check_env_set,
    check_file_exists,
    check_git_changes,
    evaluate_condition,
    execute_parallel_phases,
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


# =============================================================================
# Parallel Execution Tests
# =============================================================================


class TestBuildParallelGroups:
    """Tests for build_parallel_groups function."""

    def test_no_parallel_phases(self) -> None:
        """Test with no parallel_with references."""
        phases = [
            PhaseDefinition(name="plan", prompt="Plan"),
            PhaseDefinition(name="implement", prompt="Implement"),
            PhaseDefinition(name="test", prompt="Test"),
        ]
        groups = build_parallel_groups(phases)

        # Each phase should be in its own group
        assert len(groups) == 3
        assert all(len(g) == 1 for g in groups)
        assert groups[0][0].name == "plan"
        assert groups[1][0].name == "implement"
        assert groups[2][0].name == "test"

    def test_two_parallel_phases(self) -> None:
        """Test with two phases that should run in parallel."""
        phases = [
            PhaseDefinition(name="plan", prompt="Plan"),
            PhaseDefinition(name="lint", prompt="Lint", parallel_with=["format"]),
            PhaseDefinition(name="format", prompt="Format"),
            PhaseDefinition(name="test", prompt="Test"),
        ]
        groups = build_parallel_groups(phases)

        # plan, (lint+format), test
        assert len(groups) == 3
        assert len(groups[0]) == 1
        assert groups[0][0].name == "plan"

        # Second group should contain lint and format
        assert len(groups[1]) == 2
        parallel_names = {p.name for p in groups[1]}
        assert parallel_names == {"lint", "format"}

        assert len(groups[2]) == 1
        assert groups[2][0].name == "test"

    def test_three_parallel_phases(self) -> None:
        """Test with three phases that should run in parallel."""
        phases = [
            PhaseDefinition(name="build", prompt="Build"),
            PhaseDefinition(name="lint", prompt="Lint", parallel_with=["format", "typecheck"]),
            PhaseDefinition(name="format", prompt="Format"),
            PhaseDefinition(name="typecheck", prompt="Typecheck"),
        ]
        groups = build_parallel_groups(phases)

        assert len(groups) == 2
        assert len(groups[0]) == 1
        assert groups[0][0].name == "build"

        # Second group should contain lint, format, and typecheck
        assert len(groups[1]) == 3
        parallel_names = {p.name for p in groups[1]}
        assert parallel_names == {"lint", "format", "typecheck"}

    def test_multiple_parallel_groups(self) -> None:
        """Test with multiple independent parallel groups."""
        phases = [
            PhaseDefinition(name="plan", prompt="Plan"),
            PhaseDefinition(name="build_a", prompt="Build A", parallel_with=["build_b"]),
            PhaseDefinition(name="build_b", prompt="Build B"),
            PhaseDefinition(name="test_a", prompt="Test A", parallel_with=["test_b"]),
            PhaseDefinition(name="test_b", prompt="Test B"),
        ]
        groups = build_parallel_groups(phases)

        assert len(groups) == 3
        assert len(groups[0]) == 1  # plan
        assert len(groups[1]) == 2  # build_a, build_b
        assert len(groups[2]) == 2  # test_a, test_b

    def test_empty_phases(self) -> None:
        """Test with empty phases list."""
        groups = build_parallel_groups([])
        assert groups == []

    def test_single_phase(self) -> None:
        """Test with single phase."""
        phases = [PhaseDefinition(name="only", prompt="Only")]
        groups = build_parallel_groups(phases)

        assert len(groups) == 1
        assert len(groups[0]) == 1
        assert groups[0][0].name == "only"


class TestExecuteParallelPhases:
    """Tests for execute_parallel_phases function."""

    def test_single_phase_no_threading(self, tmp_path: Path) -> None:
        """Test that single phase doesn't use threading."""
        mock_state = MagicMock()
        mock_state.save = MagicMock()
        mock_state.add_error = MagicMock()

        context = DSLExecutionContext(
            task_description="Test",
            adw_id="test123",
            worktree_path=tmp_path,
            state=mock_state,
        )

        phases = [
            PhaseDefinition(name="single", prompt="Single phase"),
        ]

        # Mock prompt_with_retry to avoid actual execution
        with patch("adw.workflows.dsl_executor.prompt_with_retry") as mock_prompt:
            mock_prompt.return_value = MagicMock(
                success=True,
                output="Success",
                error_message=None,
            )

            results, _ = execute_parallel_phases(
                phases=phases,
                context=context,
            )

            assert len(results) == 1
            assert results[0].phase_name == "single"
            # Single phase shouldn't be marked as parallel
            assert results[0].was_parallel is False

    def test_two_phases_parallel_execution(self, tmp_path: Path) -> None:
        """Test that two phases execute in parallel."""
        mock_state = MagicMock()
        mock_state.save = MagicMock()
        mock_state.add_error = MagicMock()

        context = DSLExecutionContext(
            task_description="Test",
            adw_id="test123",
            worktree_path=tmp_path,
            state=mock_state,
        )

        phases = [
            PhaseDefinition(name="lint", prompt="Lint"),
            PhaseDefinition(name="format", prompt="Format"),
        ]

        with patch("adw.workflows.dsl_executor.prompt_with_retry") as mock_prompt:
            mock_prompt.return_value = MagicMock(
                success=True,
                output="Success",
                error_message=None,
            )

            results, _ = execute_parallel_phases(
                phases=phases,
                context=context,
            )

            assert len(results) == 2
            # Both should be marked as parallel
            assert all(r.was_parallel for r in results)
            # Results should be sorted by original phase order
            assert results[0].phase_name == "lint"
            assert results[1].phase_name == "format"

    def test_parallel_with_failure(self, tmp_path: Path) -> None:
        """Test parallel execution with one failing phase."""
        mock_state = MagicMock()
        mock_state.save = MagicMock()
        mock_state.add_error = MagicMock()

        context = DSLExecutionContext(
            task_description="Test",
            adw_id="test123",
            worktree_path=tmp_path,
            state=mock_state,
        )

        phases = [
            PhaseDefinition(name="lint", prompt="Lint"),
            PhaseDefinition(name="format", prompt="Format"),
        ]

        def mock_response(request: AgentPromptRequest, max_retries: int = 2) -> MagicMock:
            """Return success for lint, failure for format."""
            result = MagicMock()
            if "lint" in request.agent_name:
                result.success = True
                result.output = "Success"
                result.error_message = None
            else:
                result.success = False
                result.output = ""
                result.error_message = "Format failed"
            return result

        with patch("adw.workflows.dsl_executor.prompt_with_retry", side_effect=mock_response):
            results, _ = execute_parallel_phases(
                phases=phases,
                context=context,
            )

            assert len(results) == 2
            lint_result = next(r for r in results if r.phase_name == "lint")
            format_result = next(r for r in results if r.phase_name == "format")

            assert lint_result.success is True
            assert format_result.success is False
            assert format_result.error == "Format failed"

    def test_parallel_with_exception(self, tmp_path: Path) -> None:
        """Test parallel execution with one phase throwing exception."""
        mock_state = MagicMock()
        mock_state.save = MagicMock()
        mock_state.add_error = MagicMock()

        context = DSLExecutionContext(
            task_description="Test",
            adw_id="test123",
            worktree_path=tmp_path,
            state=mock_state,
        )

        phases = [
            PhaseDefinition(name="lint", prompt="Lint"),
            PhaseDefinition(name="crash", prompt="Crash"),
        ]

        def mock_response(request: AgentPromptRequest, max_retries: int = 2) -> MagicMock:
            """Return success for lint, raise for crash."""
            if "lint" in request.agent_name:
                result = MagicMock()
                result.success = True
                result.output = "Success"
                result.error_message = None
                return result
            else:
                raise RuntimeError("Unexpected crash!")

        with patch("adw.workflows.dsl_executor.prompt_with_retry", side_effect=mock_response):
            results, _ = execute_parallel_phases(
                phases=phases,
                context=context,
            )

            assert len(results) == 2
            lint_result = next(r for r in results if r.phase_name == "lint")
            crash_result = next(r for r in results if r.phase_name == "crash")

            assert lint_result.success is True
            assert crash_result.success is False
            assert "Unexpected crash" in crash_result.error


class TestDSLPhaseResultParallel:
    """Tests for parallel-related DSLPhaseResult fields."""

    def test_was_parallel_default(self) -> None:
        """Test that was_parallel defaults to False."""
        result = DSLPhaseResult(phase_name="test", success=True)
        assert result.was_parallel is False

    def test_was_parallel_explicit(self) -> None:
        """Test setting was_parallel explicitly."""
        result = DSLPhaseResult(phase_name="test", success=True, was_parallel=True)
        assert result.was_parallel is True


class TestFormatSummaryParallel:
    """Tests for format_dsl_results_summary with parallel phases."""

    def test_format_with_parallel_phases(self) -> None:
        """Test formatting results with parallel phases."""
        results = [
            DSLPhaseResult(phase_name="plan", success=True, duration_seconds=10.0),
            DSLPhaseResult(phase_name="lint", success=True, duration_seconds=5.0, was_parallel=True),
            DSLPhaseResult(phase_name="format", success=True, duration_seconds=3.0, was_parallel=True),
            DSLPhaseResult(phase_name="test", success=True, duration_seconds=20.0),
        ]
        summary = format_dsl_results_summary("test-workflow", results)

        # Check parallel indicator
        assert "lint ⚡" in summary
        assert "format ⚡" in summary
        assert "plan:" in summary  # No indicator for non-parallel
        assert "test:" in summary
        assert "(2 parallel)" in summary

    def test_format_without_parallel_phases(self) -> None:
        """Test formatting results without parallel phases."""
        results = [
            DSLPhaseResult(phase_name="plan", success=True, duration_seconds=10.0),
            DSLPhaseResult(phase_name="implement", success=True, duration_seconds=20.0),
        ]
        summary = format_dsl_results_summary("test-workflow", results)

        # No parallel indicator
        assert "⚡" not in summary
        assert "parallel" not in summary


class TestDSLExecutionContextThreadSafe:
    """Tests for thread-safe DSLExecutionContext methods."""

    def test_update_result_thread_safe(self, tmp_path: Path) -> None:
        """Test that update_result is thread-safe."""
        mock_state = MagicMock()
        context = DSLExecutionContext(
            task_description="Test",
            adw_id="test123",
            worktree_path=tmp_path,
            state=mock_state,
        )

        result = DSLPhaseResult(phase_name="test", success=True)
        context.update_result("test", result)

        assert context.phase_results["test"] == result

    def test_get_result_thread_safe(self, tmp_path: Path) -> None:
        """Test that get_result is thread-safe."""
        mock_state = MagicMock()
        context = DSLExecutionContext(
            task_description="Test",
            adw_id="test123",
            worktree_path=tmp_path,
            state=mock_state,
        )

        result = DSLPhaseResult(phase_name="test", success=True)
        context.phase_results["test"] = result

        retrieved = context.get_result("test")
        assert retrieved == result

    def test_get_result_not_found(self, tmp_path: Path) -> None:
        """Test get_result returns None for missing phase."""
        mock_state = MagicMock()
        context = DSLExecutionContext(
            task_description="Test",
            adw_id="test123",
            worktree_path=tmp_path,
            state=mock_state,
        )

        assert context.get_result("nonexistent") is None
