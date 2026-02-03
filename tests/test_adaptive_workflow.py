"""Tests for the adaptive workflow module."""

from __future__ import annotations

import pytest

from adw.workflows.adaptive import (
    AdaptiveConfig,
    AdaptivePhase,
    PhaseConfig,
    PhaseResult,
    TaskComplexity,
    detect_complexity,
    format_results_summary,
)


class TestTaskComplexity:
    """Tests for TaskComplexity enum."""

    def test_complexity_values(self):
        """Test complexity enum values."""
        assert TaskComplexity.MINIMAL.value == "minimal"
        assert TaskComplexity.STANDARD.value == "standard"
        assert TaskComplexity.FULL.value == "full"

    def test_complexity_count(self):
        """Test number of complexity levels."""
        assert len(TaskComplexity) == 3


class TestAdaptivePhase:
    """Tests for AdaptivePhase enum."""

    def test_phase_values(self):
        """Test phase enum values."""
        assert AdaptivePhase.PLAN.value == "plan"
        assert AdaptivePhase.IMPLEMENT.value == "implement"
        assert AdaptivePhase.TEST.value == "test"
        assert AdaptivePhase.REVIEW.value == "review"
        assert AdaptivePhase.DOCUMENT.value == "document"

    def test_phase_count(self):
        """Test number of phases."""
        assert len(AdaptivePhase) == 5


class TestPhaseConfig:
    """Tests for PhaseConfig dataclass."""

    def test_default_values(self):
        """Test default values for phase config."""
        config = PhaseConfig(
            name=AdaptivePhase.IMPLEMENT,
            prompt_template="/implement {task}",
        )
        assert config.model == "sonnet"
        assert config.required is True
        assert config.max_retries == 2
        assert config.timeout_seconds == 600

    def test_custom_values(self):
        """Test custom values for phase config."""
        config = PhaseConfig(
            name=AdaptivePhase.PLAN,
            prompt_template="/plan {task}",
            model="opus",
            required=True,
            max_retries=3,
            timeout_seconds=900,
        )
        assert config.model == "opus"
        assert config.max_retries == 3
        assert config.timeout_seconds == 900


class TestPhaseResult:
    """Tests for PhaseResult dataclass."""

    def test_success_result(self):
        """Test successful phase result."""
        result = PhaseResult(
            phase=AdaptivePhase.IMPLEMENT,
            success=True,
            output="Implementation complete",
            duration_seconds=45.5,
        )
        assert result.success is True
        assert result.error is None
        assert result.test_result is None

    def test_failure_result(self):
        """Test failed phase result."""
        result = PhaseResult(
            phase=AdaptivePhase.TEST,
            success=False,
            error="Tests failed",
            duration_seconds=30.0,
        )
        assert result.success is False
        assert result.error == "Tests failed"


class TestAdaptiveConfig:
    """Tests for AdaptiveConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = AdaptiveConfig()
        assert config.complexity == TaskComplexity.STANDARD
        assert config.test_validation_enabled is True
        assert config.max_test_retries == 3
        assert config.inject_expertise is True

    def test_minimal_config(self):
        """Test MINIMAL complexity configuration."""
        config = AdaptiveConfig.for_complexity(TaskComplexity.MINIMAL)
        assert config.complexity == TaskComplexity.MINIMAL
        assert len(config.phases) == 1
        assert config.phases[0].name == AdaptivePhase.IMPLEMENT
        assert config.test_validation_enabled is False
        assert config.inject_expertise is False

    def test_standard_config(self):
        """Test STANDARD complexity configuration."""
        config = AdaptiveConfig.for_complexity(TaskComplexity.STANDARD)
        assert config.complexity == TaskComplexity.STANDARD
        assert len(config.phases) == 2
        phase_names = [p.name for p in config.phases]
        assert AdaptivePhase.PLAN in phase_names
        assert AdaptivePhase.IMPLEMENT in phase_names
        assert config.test_validation_enabled is True
        assert config.inject_expertise is True

    def test_full_config(self):
        """Test FULL complexity configuration."""
        config = AdaptiveConfig.for_complexity(TaskComplexity.FULL)
        assert config.complexity == TaskComplexity.FULL
        assert len(config.phases) == 5
        phase_names = [p.name for p in config.phases]
        assert AdaptivePhase.PLAN in phase_names
        assert AdaptivePhase.IMPLEMENT in phase_names
        assert AdaptivePhase.TEST in phase_names
        assert AdaptivePhase.REVIEW in phase_names
        assert AdaptivePhase.DOCUMENT in phase_names

    def test_full_config_models(self):
        """Test FULL complexity uses Opus for plan/review."""
        config = AdaptiveConfig.for_complexity(TaskComplexity.FULL)
        plan_phase = next(p for p in config.phases if p.name == AdaptivePhase.PLAN)
        review_phase = next(p for p in config.phases if p.name == AdaptivePhase.REVIEW)
        impl_phase = next(p for p in config.phases if p.name == AdaptivePhase.IMPLEMENT)

        assert plan_phase.model == "opus"
        assert review_phase.model == "opus"
        assert impl_phase.model == "sonnet"


class TestDetectComplexity:
    """Tests for complexity detection."""

    # MINIMAL complexity detection
    def test_detect_minimal_typo(self):
        """Detect MINIMAL for typo fixes."""
        assert detect_complexity("Fix typo in README") == TaskComplexity.MINIMAL

    def test_detect_minimal_docs(self):
        """Detect MINIMAL for documentation."""
        assert detect_complexity("Update documentation") == TaskComplexity.MINIMAL

    def test_detect_minimal_comment(self):
        """Detect MINIMAL for comment updates."""
        assert detect_complexity("Add comment explaining function") == TaskComplexity.MINIMAL

    def test_detect_minimal_chore(self):
        """Detect MINIMAL for chores."""
        assert detect_complexity("chore: update dependencies") == TaskComplexity.MINIMAL

    def test_detect_minimal_delete_unused(self):
        """Detect MINIMAL for removing unused code."""
        assert detect_complexity("Remove unused imports") == TaskComplexity.MINIMAL

    def test_detect_minimal_minor_fix(self):
        """Detect MINIMAL for minor fixes."""
        assert detect_complexity("Quick fix for alignment") == TaskComplexity.MINIMAL

    # FULL complexity detection
    def test_detect_full_critical(self):
        """Detect FULL for critical issues."""
        assert detect_complexity("Critical bug in login system") == TaskComplexity.FULL

    def test_detect_full_security(self):
        """Detect FULL for security issues."""
        assert detect_complexity("Security vulnerability in auth") == TaskComplexity.FULL

    def test_detect_full_architecture(self):
        """Detect FULL for architecture work."""
        assert detect_complexity("Design new microservices architecture") == TaskComplexity.FULL

    def test_detect_full_refactor(self):
        """Detect FULL for refactoring."""
        assert detect_complexity("Refactor entire payment module") == TaskComplexity.FULL

    def test_detect_full_performance(self):
        """Detect FULL for performance optimization."""
        assert detect_complexity("Performance optimization for database queries") == TaskComplexity.FULL

    def test_detect_full_api(self):
        """Detect FULL for new API endpoints."""
        # Pattern is "api|endpoint" followed by "add|create|implement"
        assert detect_complexity("API endpoint - implement authentication") == TaskComplexity.FULL

    def test_detect_full_database(self):
        """Detect FULL for database work."""
        assert detect_complexity("Database migration for user schema") == TaskComplexity.FULL

    # STANDARD complexity (default)
    def test_detect_standard_default(self):
        """Detect STANDARD for regular features."""
        assert detect_complexity("Add user profile page") == TaskComplexity.STANDARD

    def test_detect_standard_feature(self):
        """Detect STANDARD for feature implementation."""
        assert detect_complexity("Implement dark mode toggle") == TaskComplexity.STANDARD

    def test_detect_standard_bug(self):
        """Detect STANDARD for regular bug fix."""
        assert detect_complexity("Fix button not responding") == TaskComplexity.STANDARD

    # Priority-based detection
    def test_detect_priority_p0(self):
        """p0 priority should be FULL."""
        assert detect_complexity("Some task", priority="p0") == TaskComplexity.FULL

    def test_detect_priority_p3(self):
        """p3 priority should be MINIMAL."""
        assert detect_complexity("Some task", priority="p3") == TaskComplexity.MINIMAL

    def test_detect_priority_p1(self):
        """p1 priority doesn't change default."""
        assert detect_complexity("Some task", priority="p1") == TaskComplexity.STANDARD

    # Tag-based detection
    def test_detect_tags_simple(self):
        """Simple tag should be MINIMAL."""
        assert detect_complexity("Some task", tags=["simple"]) == TaskComplexity.MINIMAL

    def test_detect_tags_minimal(self):
        """Minimal tag should be MINIMAL."""
        assert detect_complexity("Some task", tags=["minimal"]) == TaskComplexity.MINIMAL

    def test_detect_tags_sdlc(self):
        """SDLC tag should be FULL."""
        assert detect_complexity("Some task", tags=["sdlc"]) == TaskComplexity.FULL

    def test_detect_tags_full(self):
        """Full tag should be FULL."""
        assert detect_complexity("Some task", tags=["full"]) == TaskComplexity.FULL

    # Explicit workflow override
    def test_detect_explicit_simple(self):
        """Explicit simple workflow should be MINIMAL."""
        assert detect_complexity("Any task", explicit_workflow="simple") == TaskComplexity.MINIMAL

    def test_detect_explicit_standard(self):
        """Explicit standard workflow should be STANDARD."""
        assert detect_complexity("Any task", explicit_workflow="standard") == TaskComplexity.STANDARD

    def test_detect_explicit_sdlc(self):
        """Explicit sdlc workflow should be FULL."""
        assert detect_complexity("Any task", explicit_workflow="sdlc") == TaskComplexity.FULL

    def test_detect_explicit_full(self):
        """Explicit full workflow should be FULL."""
        assert detect_complexity("Any task", explicit_workflow="full") == TaskComplexity.FULL


class TestFormatResultsSummary:
    """Tests for format_results_summary function."""

    def test_format_success(self):
        """Test formatting successful results."""
        results = [
            PhaseResult(phase=AdaptivePhase.PLAN, success=True, duration_seconds=10.0),
            PhaseResult(phase=AdaptivePhase.IMPLEMENT, success=True, duration_seconds=30.0),
        ]
        summary = format_results_summary(results, TaskComplexity.STANDARD)

        assert "standard" in summary
        assert "✅" in summary
        assert "plan" in summary
        assert "implement" in summary
        assert "2/2" in summary

    def test_format_with_failure(self):
        """Test formatting results with failures."""
        results = [
            PhaseResult(phase=AdaptivePhase.PLAN, success=True, duration_seconds=10.0),
            PhaseResult(phase=AdaptivePhase.IMPLEMENT, success=False, error="Build failed", duration_seconds=20.0),
        ]
        summary = format_results_summary(results, TaskComplexity.STANDARD)

        assert "✅" in summary
        assert "❌" in summary
        assert "Build failed" in summary
        assert "1/2" in summary

    def test_format_empty_results(self):
        """Test formatting empty results."""
        results = []
        summary = format_results_summary(results)

        assert "0/0" in summary

    def test_format_total_time(self):
        """Test total time calculation."""
        results = [
            PhaseResult(phase=AdaptivePhase.PLAN, success=True, duration_seconds=10.5),
            PhaseResult(phase=AdaptivePhase.IMPLEMENT, success=True, duration_seconds=20.5),
        ]
        summary = format_results_summary(results)

        # Should contain total time of ~31 seconds
        assert "31.0s" in summary


class TestBackwardCompatibility:
    """Tests for backward compatibility with legacy workflows."""

    def test_import_simple_workflow(self):
        """Test importing run_simple_workflow from workflows."""
        from adw.workflows import run_simple_workflow
        assert callable(run_simple_workflow)

    def test_import_standard_workflow(self):
        """Test importing run_standard_workflow from workflows."""
        from adw.workflows import run_standard_workflow
        assert callable(run_standard_workflow)

    def test_import_sdlc_workflow(self):
        """Test importing run_sdlc_workflow from workflows."""
        from adw.workflows import run_sdlc_workflow
        assert callable(run_sdlc_workflow)

    def test_import_adaptive_workflow(self):
        """Test importing run_adaptive_workflow from workflows."""
        from adw.workflows import run_adaptive_workflow
        assert callable(run_adaptive_workflow)

    def test_import_detect_complexity(self):
        """Test importing detect_complexity from workflows."""
        from adw.workflows import detect_complexity
        assert callable(detect_complexity)

    def test_import_task_complexity(self):
        """Test importing TaskComplexity from workflows."""
        from adw.workflows import TaskComplexity
        assert TaskComplexity.MINIMAL is not None


class TestAdaptiveConfigEdgeCases:
    """Edge case tests for AdaptiveConfig."""

    def test_empty_phases(self):
        """Test config with no phases."""
        config = AdaptiveConfig(phases=[])
        assert len(config.phases) == 0

    def test_disable_test_validation(self):
        """Test disabling test validation."""
        config = AdaptiveConfig(test_validation_enabled=False)
        assert config.test_validation_enabled is False

    def test_custom_max_retries(self):
        """Test custom max test retries."""
        config = AdaptiveConfig(max_test_retries=5)
        assert config.max_test_retries == 5


class TestComplexityDetectionEdgeCases:
    """Edge case tests for complexity detection."""

    def test_empty_description(self):
        """Test with empty description."""
        result = detect_complexity("")
        assert result == TaskComplexity.STANDARD

    def test_whitespace_description(self):
        """Test with whitespace-only description."""
        result = detect_complexity("   ")
        assert result == TaskComplexity.STANDARD

    def test_case_insensitive(self):
        """Test case insensitivity."""
        assert detect_complexity("CRITICAL BUG") == TaskComplexity.FULL
        assert detect_complexity("fix TYPO") == TaskComplexity.MINIMAL

    def test_partial_match(self):
        """Test partial word matches - 'system' triggers FULL."""
        # "system" triggers FULL, so "documentation system" -> FULL
        # But simple "Update docs" triggers MINIMAL
        assert detect_complexity("Update docs") == TaskComplexity.MINIMAL
        assert detect_complexity("Update documentation system") == TaskComplexity.FULL  # "system" triggers FULL

    def test_none_tags(self):
        """Test with None tags."""
        result = detect_complexity("Some task", tags=None)
        assert result == TaskComplexity.STANDARD

    def test_empty_tags(self):
        """Test with empty tags list."""
        result = detect_complexity("Some task", tags=[])
        assert result == TaskComplexity.STANDARD

    def test_explicit_overrides_pattern(self):
        """Test explicit workflow overrides pattern detection."""
        # Even though "critical" would trigger FULL, explicit simple wins
        result = detect_complexity("Critical task", explicit_workflow="simple")
        assert result == TaskComplexity.MINIMAL

    def test_tags_override_pattern(self):
        """Test tags override pattern detection."""
        # Even though "readme" would trigger MINIMAL, sdlc tag wins
        result = detect_complexity("Update readme", tags=["sdlc"])
        assert result == TaskComplexity.FULL

    def test_priority_p0_overrides_pattern(self):
        """Test p0 priority overrides pattern detection."""
        # Even though "readme" would trigger MINIMAL, p0 priority wins
        result = detect_complexity("Update readme", priority="p0")
        assert result == TaskComplexity.FULL
