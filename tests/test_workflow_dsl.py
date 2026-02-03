"""Tests for workflow DSL module."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from adw.workflows.dsl import (
    LoopCondition,
    PhaseCondition,
    PhaseDefinition,
    PromptTemplate,
    WorkflowDefinition,
    create_workflow,
    delete_workflow,
    ensure_builtin_workflows,
    get_workflow,
    get_workflows_dir,
    list_workflows,
    load_workflow,
    parse_phase_yaml,
    parse_workflow_yaml,
    save_workflow,
    serialize_workflow,
    set_active_workflow,
)


# =============================================================================
# PhaseDefinition Tests
# =============================================================================


class TestPhaseDefinition:
    """Tests for PhaseDefinition dataclass."""

    def test_create_minimal_phase(self) -> None:
        """Test creating a phase with minimal required fields."""
        phase = PhaseDefinition(name="test", prompt="Do something")
        assert phase.name == "test"
        assert phase.prompt == "Do something"
        assert phase.model == "sonnet"
        assert phase.required is True
        assert phase.timeout_seconds == 600
        assert phase.max_retries == 2

    def test_create_phase_with_all_options(self) -> None:
        """Test creating a phase with all options."""
        phase = PhaseDefinition(
            name="implement",
            prompt="/implement {{task}}",
            model="opus",
            required=False,
            timeout_seconds=1200,
            max_retries=5,
            condition=PhaseCondition.HAS_CHANGES,
            loop=LoopCondition.UNTIL_TESTS_PASS,
            loop_max=5,
            tests="npm test",
            test_timeout=600,
            parallel_with=["lint"],
        )
        assert phase.name == "implement"
        assert phase.model == "opus"
        assert phase.required is False
        assert phase.timeout_seconds == 1200
        assert phase.condition == PhaseCondition.HAS_CHANGES
        assert phase.loop == LoopCondition.UNTIL_TESTS_PASS
        assert phase.loop_max == 5
        assert phase.tests == "npm test"
        assert phase.parallel_with == ["lint"]

    def test_phase_validation_empty_name(self) -> None:
        """Test that empty name raises ValueError."""
        with pytest.raises(ValueError, match="Phase name is required"):
            PhaseDefinition(name="", prompt="test")

    def test_phase_validation_empty_prompt(self) -> None:
        """Test that empty prompt raises ValueError."""
        with pytest.raises(ValueError, match="requires a prompt"):
            PhaseDefinition(name="test", prompt="")

    def test_phase_validation_invalid_model(self) -> None:
        """Test that invalid model raises ValueError."""
        with pytest.raises(ValueError, match="Invalid model"):
            PhaseDefinition(name="test", prompt="test", model="gpt4")  # type: ignore

    def test_phase_validation_invalid_timeout(self) -> None:
        """Test that non-positive timeout raises ValueError."""
        with pytest.raises(ValueError, match="Invalid timeout"):
            PhaseDefinition(name="test", prompt="test", timeout_seconds=0)

    def test_phase_validation_negative_retries(self) -> None:
        """Test that negative retries raises ValueError."""
        with pytest.raises(ValueError, match="Invalid max_retries"):
            PhaseDefinition(name="test", prompt="test", max_retries=-1)

    def test_phase_validation_invalid_loop_max(self) -> None:
        """Test that non-positive loop_max raises ValueError."""
        with pytest.raises(ValueError, match="Invalid loop_max"):
            PhaseDefinition(name="test", prompt="test", loop_max=0)


# =============================================================================
# WorkflowDefinition Tests
# =============================================================================


class TestWorkflowDefinition:
    """Tests for WorkflowDefinition dataclass."""

    def test_create_minimal_workflow(self) -> None:
        """Test creating a workflow with minimal required fields."""
        phases = [PhaseDefinition(name="build", prompt="Build it")]
        wf = WorkflowDefinition(name="simple", phases=phases)
        assert wf.name == "simple"
        assert len(wf.phases) == 1
        assert wf.description == ""
        assert wf.version == "1.0.0"
        assert wf.default_model == "sonnet"

    def test_create_workflow_with_options(self) -> None:
        """Test creating a workflow with all options."""
        phases = [
            PhaseDefinition(name="plan", prompt="Plan", required=True),
            PhaseDefinition(name="implement", prompt="Implement", required=True),
            PhaseDefinition(name="review", prompt="Review", required=False),
        ]
        wf = WorkflowDefinition(
            name="custom",
            phases=phases,
            description="A custom workflow",
            version="2.0.0",
            author="test",
            default_model="opus",
            default_timeout=900,
            fail_fast=False,
            tags=["custom", "test"],
        )
        assert wf.description == "A custom workflow"
        assert wf.version == "2.0.0"
        assert wf.author == "test"
        assert wf.default_model == "opus"
        assert wf.fail_fast is False
        assert "custom" in wf.tags

    def test_workflow_validation_empty_name(self) -> None:
        """Test that empty name raises ValueError."""
        with pytest.raises(ValueError, match="Workflow name is required"):
            WorkflowDefinition(
                name="",
                phases=[PhaseDefinition(name="test", prompt="test")],
            )

    def test_workflow_validation_no_phases(self) -> None:
        """Test that empty phases list raises ValueError."""
        with pytest.raises(ValueError, match="has no phases"):
            WorkflowDefinition(name="test", phases=[])

    def test_workflow_validation_duplicate_phases(self) -> None:
        """Test that duplicate phase names raise ValueError."""
        phases = [
            PhaseDefinition(name="build", prompt="Build 1"),
            PhaseDefinition(name="build", prompt="Build 2"),
        ]
        with pytest.raises(ValueError, match="duplicate phase names"):
            WorkflowDefinition(name="test", phases=phases)

    def test_workflow_validation_invalid_parallel_ref(self) -> None:
        """Test that invalid parallel_with reference raises ValueError."""
        phases = [
            PhaseDefinition(name="build", prompt="Build", parallel_with=["nonexistent"]),
        ]
        with pytest.raises(ValueError, match="unknown parallel phase"):
            WorkflowDefinition(name="test", phases=phases)

    def test_get_phase(self) -> None:
        """Test getting a phase by name."""
        phases = [
            PhaseDefinition(name="plan", prompt="Plan"),
            PhaseDefinition(name="implement", prompt="Implement"),
        ]
        wf = WorkflowDefinition(name="test", phases=phases)
        assert wf.get_phase("plan") is not None
        assert wf.get_phase("plan").name == "plan"
        assert wf.get_phase("nonexistent") is None

    def test_get_required_phases(self) -> None:
        """Test getting required phases."""
        phases = [
            PhaseDefinition(name="plan", prompt="Plan", required=True),
            PhaseDefinition(name="implement", prompt="Implement", required=True),
            PhaseDefinition(name="review", prompt="Review", required=False),
        ]
        wf = WorkflowDefinition(name="test", phases=phases)
        required = wf.get_required_phases()
        assert len(required) == 2
        assert all(p.required for p in required)

    def test_get_optional_phases(self) -> None:
        """Test getting optional phases."""
        phases = [
            PhaseDefinition(name="plan", prompt="Plan", required=True),
            PhaseDefinition(name="implement", prompt="Implement", required=True),
            PhaseDefinition(name="review", prompt="Review", required=False),
        ]
        wf = WorkflowDefinition(name="test", phases=phases)
        optional = wf.get_optional_phases()
        assert len(optional) == 1
        assert all(not p.required for p in optional)


# =============================================================================
# YAML Parsing Tests
# =============================================================================


class TestYAMLParsing:
    """Tests for YAML parsing functions."""

    def test_parse_phase_yaml_minimal(self) -> None:
        """Test parsing a minimal phase YAML."""
        data = {"name": "build", "prompt": "Build it"}
        phase = parse_phase_yaml(data, {})
        assert phase.name == "build"
        assert phase.prompt == "Build it"

    def test_parse_phase_yaml_with_defaults(self) -> None:
        """Test parsing phase YAML with workflow defaults."""
        data = {"name": "build", "prompt": "Build it"}
        defaults = {
            "default_model": "opus",
            "default_timeout": 1200,
            "default_max_retries": 5,
        }
        phase = parse_phase_yaml(data, defaults)
        assert phase.model == "opus"
        assert phase.timeout_seconds == 1200
        assert phase.max_retries == 5

    def test_parse_phase_yaml_with_condition(self) -> None:
        """Test parsing phase YAML with condition."""
        data = {"name": "deploy", "prompt": "Deploy", "condition": "has_changes"}
        phase = parse_phase_yaml(data, {})
        assert phase.condition == PhaseCondition.HAS_CHANGES

    def test_parse_phase_yaml_with_condition_value(self) -> None:
        """Test parsing phase YAML with condition and value."""
        data = {"name": "deploy", "prompt": "Deploy", "condition": "file_exists:README.md"}
        phase = parse_phase_yaml(data, {})
        assert phase.condition == PhaseCondition.FILE_EXISTS
        assert phase.condition_value == "README.md"

    def test_parse_phase_yaml_with_loop(self) -> None:
        """Test parsing phase YAML with loop."""
        data = {"name": "fix", "prompt": "Fix", "loop": "until_tests_pass", "loop_max": 5}
        phase = parse_phase_yaml(data, {})
        assert phase.loop == LoopCondition.UNTIL_TESTS_PASS
        assert phase.loop_max == 5

    def test_parse_workflow_yaml_minimal(self) -> None:
        """Test parsing minimal workflow YAML."""
        yaml_content = """
name: simple
phases:
  - name: build
    prompt: Build it
"""
        wf = parse_workflow_yaml(yaml_content)
        assert wf.name == "simple"
        assert len(wf.phases) == 1
        assert wf.phases[0].name == "build"

    def test_parse_workflow_yaml_full(self) -> None:
        """Test parsing full workflow YAML."""
        yaml_content = """
name: full-workflow
description: A complete workflow
version: "2.0.0"
author: test
tags:
  - testing
  - example

default_model: opus
default_timeout: 900
fail_fast: false

phases:
  - name: plan
    prompt: /plan {{task}}
    model: opus
    timeout: 1200
    required: true

  - name: implement
    prompt: /implement {{task}}
    required: true
    loop: until_tests_pass
    loop_max: 3
    tests: npm test

  - name: review
    prompt: /review {{task}}
    required: false
    condition: has_changes
"""
        wf = parse_workflow_yaml(yaml_content)
        assert wf.name == "full-workflow"
        assert wf.description == "A complete workflow"
        assert wf.version == "2.0.0"
        assert wf.default_model == "opus"
        assert wf.fail_fast is False
        assert len(wf.phases) == 3

        # Check plan phase
        plan = wf.get_phase("plan")
        assert plan is not None
        assert plan.model == "opus"
        assert plan.timeout_seconds == 1200

        # Check implement phase
        impl = wf.get_phase("implement")
        assert impl is not None
        assert impl.loop == LoopCondition.UNTIL_TESTS_PASS
        assert impl.tests == "npm test"

        # Check review phase
        review = wf.get_phase("review")
        assert review is not None
        assert review.required is False
        assert review.condition == PhaseCondition.HAS_CHANGES

    def test_parse_workflow_yaml_invalid(self) -> None:
        """Test parsing invalid YAML."""
        with pytest.raises(ValueError, match="Invalid YAML"):
            parse_workflow_yaml("invalid: yaml: content:")

    def test_parse_workflow_yaml_missing_name(self) -> None:
        """Test parsing YAML without name."""
        with pytest.raises(ValueError, match="name.*required"):
            parse_workflow_yaml("phases:\n  - name: test\n    prompt: test")

    def test_parse_workflow_yaml_missing_phases(self) -> None:
        """Test parsing YAML without phases."""
        with pytest.raises(ValueError, match="must have at least one phase"):
            parse_workflow_yaml("name: test")


# =============================================================================
# Serialization Tests
# =============================================================================


class TestSerialization:
    """Tests for workflow serialization."""

    def test_serialize_workflow_minimal(self) -> None:
        """Test serializing a minimal workflow."""
        phases = [PhaseDefinition(name="build", prompt="Build it")]
        wf = WorkflowDefinition(name="simple", phases=phases)
        yaml_content = serialize_workflow(wf)

        # Parse it back
        parsed = parse_workflow_yaml(yaml_content)
        assert parsed.name == wf.name
        assert len(parsed.phases) == len(wf.phases)

    def test_serialize_workflow_full(self) -> None:
        """Test serializing a full workflow."""
        phases = [
            PhaseDefinition(
                name="plan",
                prompt="/plan {{task}}",
                model="opus",
                timeout_seconds=1200,
            ),
            PhaseDefinition(
                name="implement",
                prompt="/implement {{task}}",
                loop=LoopCondition.UNTIL_TESTS_PASS,
                tests="npm test",
            ),
            PhaseDefinition(
                name="review",
                prompt="/review",
                required=False,
                condition=PhaseCondition.HAS_CHANGES,
            ),
        ]
        wf = WorkflowDefinition(
            name="full",
            phases=phases,
            description="Full workflow",
            version="2.0.0",
            author="test",
            fail_fast=False,
            tags=["test"],
        )

        yaml_content = serialize_workflow(wf)
        parsed = parse_workflow_yaml(yaml_content)

        assert parsed.name == wf.name
        assert parsed.description == wf.description
        assert parsed.fail_fast == wf.fail_fast
        assert len(parsed.phases) == len(wf.phases)

    def test_round_trip_serialization(self) -> None:
        """Test that serialize -> parse produces equivalent workflow."""
        phases = [
            PhaseDefinition(name="plan", prompt="/plan"),
            PhaseDefinition(name="build", prompt="/build"),
        ]
        original = WorkflowDefinition(
            name="roundtrip",
            phases=phases,
            description="Test round trip",
        )

        yaml_content = serialize_workflow(original)
        restored = parse_workflow_yaml(yaml_content)

        assert restored.name == original.name
        assert restored.description == original.description
        assert len(restored.phases) == len(original.phases)
        for orig_phase, rest_phase in zip(original.phases, restored.phases):
            assert rest_phase.name == orig_phase.name
            assert rest_phase.prompt == orig_phase.prompt


# =============================================================================
# File I/O Tests
# =============================================================================


class TestFileIO:
    """Tests for file I/O functions."""

    def test_save_and_load_workflow(self, tmp_path: Path) -> None:
        """Test saving and loading a workflow."""
        phases = [PhaseDefinition(name="build", prompt="Build it")]
        wf = WorkflowDefinition(name="test", phases=phases)

        path = tmp_path / "test.yaml"
        save_workflow(wf, path)

        assert path.exists()

        loaded = load_workflow(path)
        assert loaded.name == wf.name
        assert len(loaded.phases) == len(wf.phases)

    def test_load_workflow_not_found(self) -> None:
        """Test loading non-existent workflow file."""
        with pytest.raises(FileNotFoundError):
            load_workflow("/nonexistent/path/workflow.yaml")

    def test_save_workflow_creates_parent_dirs(self, tmp_path: Path) -> None:
        """Test that save_workflow creates parent directories."""
        phases = [PhaseDefinition(name="build", prompt="Build it")]
        wf = WorkflowDefinition(name="test", phases=phases)

        path = tmp_path / "nested" / "dirs" / "test.yaml"
        save_workflow(wf, path)

        assert path.exists()


# =============================================================================
# PromptTemplate Tests
# =============================================================================


class TestPromptTemplate:
    """Tests for PromptTemplate class."""

    def test_render_with_variables(self) -> None:
        """Test rendering template with variables."""
        template = PromptTemplate("Hello {{name}}! Task: {{task}}")
        result = template.render(name="World", task="Build something")
        assert result == "Hello World! Task: Build something"

    def test_render_missing_variable(self) -> None:
        """Test rendering with missing variable keeps placeholder."""
        template = PromptTemplate("Hello {{name}}!")
        result = template.render()
        assert result == "Hello {{name}}!"

    def test_render_with_include(self, tmp_path: Path) -> None:
        """Test rendering with include directive."""
        # Create include file
        include_content = "This is included content."
        include_path = tmp_path / "include.md"
        include_path.write_text(include_content)

        # Create template with include
        template_content = "Before\n{{include include.md}}\nAfter"
        template = PromptTemplate(template_content, base_path=tmp_path)
        result = template.render()

        assert "Before" in result
        assert "This is included content." in result
        assert "After" in result

    def test_render_missing_include(self, tmp_path: Path) -> None:
        """Test rendering with missing include file."""
        template = PromptTemplate("{{include nonexistent.md}}", base_path=tmp_path)
        result = template.render()
        assert "Include not found" in result

    def test_render_max_includes(self, tmp_path: Path) -> None:
        """Test that max includes prevents infinite recursion."""
        # Create self-referencing include
        include_path = tmp_path / "recursive.md"
        include_path.write_text("{{include recursive.md}}")

        template = PromptTemplate("{{include recursive.md}}", base_path=tmp_path, max_includes=3)
        result = template.render()
        assert "Include limit reached" in result

    def test_render_with_conditional(self) -> None:
        """Test rendering with conditional blocks."""
        template = PromptTemplate("Start {{#if show_extra}}Extra content{{/if}} End")

        # With truthy value
        result = template.render(show_extra=True)
        assert "Extra content" in result

        # With falsy value
        result = template.render(show_extra=False)
        assert "Extra content" not in result

        # With missing value
        result = template.render()
        assert "Extra content" not in result

    def test_from_file(self, tmp_path: Path) -> None:
        """Test creating template from file."""
        content = "Template content: {{variable}}"
        path = tmp_path / "template.md"
        path.write_text(content)

        template = PromptTemplate.from_file(path)
        result = template.render(variable="value")
        assert result == "Template content: value"

    def test_from_file_not_found(self) -> None:
        """Test creating template from non-existent file."""
        with pytest.raises(FileNotFoundError):
            PromptTemplate.from_file("/nonexistent/template.md")


# =============================================================================
# Library Management Tests
# =============================================================================


class TestLibraryManagement:
    """Tests for workflow library management."""

    def test_get_workflows_dir(self) -> None:
        """Test getting workflows directory."""
        path = get_workflows_dir()
        assert path.name == "workflows"
        assert ".adw" in str(path)

    def test_ensure_builtin_workflows(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test ensuring built-in workflows exist."""
        # Patch the builtin dir to use temp directory
        builtin_dir = tmp_path / "builtin"
        monkeypatch.setattr(
            "adw.workflows.dsl.get_builtin_workflows_dir",
            lambda: builtin_dir,
        )

        ensure_builtin_workflows()

        assert (builtin_dir / "sdlc.yaml").exists()
        assert (builtin_dir / "simple.yaml").exists()
        assert (builtin_dir / "prototype.yaml").exists()
        assert (builtin_dir / "bug-fix.yaml").exists()

    def test_list_workflows(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test listing workflows."""
        # Setup directories
        user_dir = tmp_path / "user_workflows"
        builtin_dir = tmp_path / "builtin"
        user_dir.mkdir()
        builtin_dir.mkdir()

        # Create test workflows
        (user_dir / "custom.yaml").write_text("name: custom\nphases:\n  - name: test\n    prompt: test")
        (builtin_dir / "sdlc.yaml").write_text("name: sdlc\nphases:\n  - name: test\n    prompt: test")

        monkeypatch.setattr("adw.workflows.dsl.get_workflows_dir", lambda: user_dir)
        monkeypatch.setattr("adw.workflows.dsl.get_builtin_workflows_dir", lambda: builtin_dir)

        workflows = list_workflows()
        names = [w[0] for w in workflows]

        assert "custom" in names
        assert "sdlc" in names

    def test_get_workflow_user_priority(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that user workflows take priority over built-in."""
        user_dir = tmp_path / "user"
        builtin_dir = tmp_path / "builtin"
        user_dir.mkdir()
        builtin_dir.mkdir()

        # Create both user and built-in with same name
        (user_dir / "custom.yaml").write_text("name: custom-user\nphases:\n  - name: test\n    prompt: user")
        (builtin_dir / "custom.yaml").write_text("name: custom-builtin\nphases:\n  - name: test\n    prompt: builtin")

        monkeypatch.setattr("adw.workflows.dsl.get_workflows_dir", lambda: user_dir)
        monkeypatch.setattr("adw.workflows.dsl.get_builtin_workflows_dir", lambda: builtin_dir)

        wf = get_workflow("custom")
        assert wf is not None
        assert wf.name == "custom-user"

    def test_create_workflow(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test creating a new workflow."""
        user_dir = tmp_path / "workflows"
        monkeypatch.setattr("adw.workflows.dsl.get_workflows_dir", lambda: user_dir)

        phases = [{"name": "build", "prompt": "Build it"}]
        path = create_workflow("new-workflow", phases, "Test workflow")

        assert path.exists()
        wf = load_workflow(path)
        assert wf.name == "new-workflow"
        assert wf.description == "Test workflow"

    def test_create_workflow_exists(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test creating workflow that already exists."""
        user_dir = tmp_path / "workflows"
        user_dir.mkdir()
        (user_dir / "existing.yaml").write_text("name: existing\nphases:\n  - name: test\n    prompt: test")
        monkeypatch.setattr("adw.workflows.dsl.get_workflows_dir", lambda: user_dir)

        with pytest.raises(FileExistsError):
            create_workflow("existing", [{"name": "test", "prompt": "test"}])

    def test_create_workflow_overwrite(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test creating workflow with overwrite."""
        user_dir = tmp_path / "workflows"
        user_dir.mkdir()
        (user_dir / "existing.yaml").write_text("name: old\nphases:\n  - name: test\n    prompt: old")
        monkeypatch.setattr("adw.workflows.dsl.get_workflows_dir", lambda: user_dir)

        path = create_workflow("existing", [{"name": "test", "prompt": "new"}], overwrite=True)
        wf = load_workflow(path)
        assert wf.phases[0].prompt == "new"

    def test_delete_workflow(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test deleting a workflow."""
        user_dir = tmp_path / "workflows"
        user_dir.mkdir()
        (user_dir / "deleteme.yaml").write_text("name: deleteme\nphases:\n  - name: test\n    prompt: test")
        monkeypatch.setattr("adw.workflows.dsl.get_workflows_dir", lambda: user_dir)
        monkeypatch.setattr("adw.workflows.dsl.get_builtin_workflows_dir", lambda: tmp_path / "nonexistent")

        assert delete_workflow("deleteme") is True
        assert not (user_dir / "deleteme.yaml").exists()

    def test_delete_workflow_not_found(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test deleting non-existent workflow."""
        user_dir = tmp_path / "workflows"
        user_dir.mkdir()
        monkeypatch.setattr("adw.workflows.dsl.get_workflows_dir", lambda: user_dir)
        monkeypatch.setattr("adw.workflows.dsl.get_builtin_workflows_dir", lambda: tmp_path / "nonexistent")

        assert delete_workflow("nonexistent") is False

    def test_delete_builtin_workflow_fails(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that deleting built-in workflow raises error."""
        builtin_dir = tmp_path / "builtin"
        builtin_dir.mkdir()
        (builtin_dir / "sdlc.yaml").write_text("name: sdlc\nphases:\n  - name: test\n    prompt: test")
        monkeypatch.setattr("adw.workflows.dsl.get_workflows_dir", lambda: tmp_path / "user")
        monkeypatch.setattr("adw.workflows.dsl.get_builtin_workflows_dir", lambda: builtin_dir)

        with pytest.raises(ValueError, match="Cannot delete built-in"):
            delete_workflow("sdlc")

    def test_set_active_workflow(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test setting active workflow."""
        # Setup
        user_dir = tmp_path / "workflows"
        user_dir.mkdir()
        (user_dir / "custom.yaml").write_text("name: custom\nphases:\n  - name: test\n    prompt: test")
        config_dir = tmp_path / ".adw"

        monkeypatch.setattr("adw.workflows.dsl.get_workflows_dir", lambda: user_dir)
        monkeypatch.setattr("adw.workflows.dsl.get_builtin_workflows_dir", lambda: tmp_path / "nonexistent")
        monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

        set_active_workflow("custom")

        config_path = config_dir / "config.toml"
        assert config_path.exists()
        assert 'active_workflow = "custom"' in config_path.read_text()

    def test_set_active_workflow_not_found(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test setting non-existent workflow as active."""
        monkeypatch.setattr("adw.workflows.dsl.get_workflows_dir", lambda: tmp_path / "user")
        monkeypatch.setattr("adw.workflows.dsl.get_builtin_workflows_dir", lambda: tmp_path / "builtin")

        with pytest.raises(ValueError, match="not found"):
            set_active_workflow("nonexistent")


# =============================================================================
# PhaseCondition Tests
# =============================================================================


class TestPhaseCondition:
    """Tests for PhaseCondition enum."""

    def test_all_conditions_exist(self) -> None:
        """Test that all expected conditions exist."""
        assert PhaseCondition.ALWAYS.value == "always"
        assert PhaseCondition.HAS_CHANGES.value == "has_changes"
        assert PhaseCondition.TESTS_PASSED.value == "tests_passed"
        assert PhaseCondition.TESTS_FAILED.value == "tests_failed"
        assert PhaseCondition.FILE_EXISTS.value == "file_exists"
        assert PhaseCondition.ENV_SET.value == "env_set"


class TestLoopCondition:
    """Tests for LoopCondition enum."""

    def test_all_loop_conditions_exist(self) -> None:
        """Test that all expected loop conditions exist."""
        assert LoopCondition.NONE.value == "none"
        assert LoopCondition.UNTIL_SUCCESS.value == "until_success"
        assert LoopCondition.UNTIL_TESTS_PASS.value == "until_tests_pass"
        assert LoopCondition.FIXED_COUNT.value == "fixed_count"


# =============================================================================
# Integration Tests
# =============================================================================


class TestIntegration:
    """Integration tests for workflow DSL."""

    def test_full_workflow_cycle(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test full create -> list -> get -> delete cycle."""
        user_dir = tmp_path / "workflows"
        monkeypatch.setattr("adw.workflows.dsl.get_workflows_dir", lambda: user_dir)
        monkeypatch.setattr("adw.workflows.dsl.get_builtin_workflows_dir", lambda: tmp_path / "builtin")

        # Create
        phases = [
            {"name": "plan", "prompt": "/plan", "model": "opus"},
            {"name": "implement", "prompt": "/implement"},
        ]
        path = create_workflow("test-cycle", phases, "Integration test")
        assert path.exists()

        # List
        workflows = list_workflows()
        assert any(w[0] == "test-cycle" for w in workflows)

        # Get
        wf = get_workflow("test-cycle")
        assert wf is not None
        assert wf.name == "test-cycle"
        assert len(wf.phases) == 2

        # Delete
        assert delete_workflow("test-cycle") is True
        assert get_workflow("test-cycle") is None

    def test_builtin_workflows_valid(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that all built-in workflows are valid."""
        builtin_dir = tmp_path / "builtin"
        monkeypatch.setattr("adw.workflows.dsl.get_builtin_workflows_dir", lambda: builtin_dir)

        ensure_builtin_workflows()

        for yaml_file in builtin_dir.glob("*.yaml"):
            wf = load_workflow(yaml_file)
            assert wf.name  # Name exists
            assert wf.phases  # Has phases
            assert all(p.name and p.prompt for p in wf.phases)  # Phases are valid
