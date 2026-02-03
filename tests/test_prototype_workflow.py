"""Tests for prototype workflow module."""

from __future__ import annotations

from pathlib import Path

import pytest

from adw.workflows.prototype import (
    PROTOTYPES,
    PrototypeConfig,
    PrototypeResult,
    build_scaffold_prompt,
    build_verify_prompt,
    format_prototype_result,
    get_prototype_config,
    list_prototypes,
)


# =============================================================================
# PrototypeConfig Tests
# =============================================================================


class TestPrototypeConfig:
    """Tests for PrototypeConfig dataclass."""

    def test_create_config(self) -> None:
        """Test creating a prototype config."""
        config = PrototypeConfig(
            name="Test Prototype",
            plan_command="/plan_test",
            description="A test prototype",
            output_dir="apps/{app_name}",
            file_patterns=["main.py", "README.md"],
        )
        assert config.name == "Test Prototype"
        assert config.plan_command == "/plan_test"
        assert config.description == "A test prototype"
        assert "{app_name}" in config.output_dir
        assert len(config.file_patterns) == 2


# =============================================================================
# PrototypeResult Tests
# =============================================================================


class TestPrototypeResult:
    """Tests for PrototypeResult dataclass."""

    def test_create_success_result(self) -> None:
        """Test creating a successful result."""
        result = PrototypeResult(
            success=True,
            output_dir=Path("apps/my-app"),
            files_created=["main.py", "README.md"],
            duration_seconds=15.5,
        )
        assert result.success is True
        assert result.output_dir == Path("apps/my-app")
        assert len(result.files_created) == 2
        assert result.error is None

    def test_create_failure_result(self) -> None:
        """Test creating a failed result."""
        result = PrototypeResult(
            success=False,
            error="Scaffold failed",
            duration_seconds=5.0,
        )
        assert result.success is False
        assert result.error == "Scaffold failed"
        assert result.output_dir is None
        assert result.files_created == []

    def test_default_values(self) -> None:
        """Test default values."""
        result = PrototypeResult(success=True)
        assert result.output_dir is None
        assert result.error is None
        assert result.files_created == []
        assert result.duration_seconds == 0.0


# =============================================================================
# PROTOTYPES Registry Tests
# =============================================================================


class TestPrototypesRegistry:
    """Tests for PROTOTYPES registry."""

    def test_registry_has_vite_vue(self) -> None:
        """Test that vite_vue prototype exists."""
        assert "vite_vue" in PROTOTYPES
        config = PROTOTYPES["vite_vue"]
        assert config.name == "Vite + Vue"
        assert "package.json" in config.file_patterns

    def test_registry_has_uv_script(self) -> None:
        """Test that uv_script prototype exists."""
        assert "uv_script" in PROTOTYPES
        config = PROTOTYPES["uv_script"]
        assert "UV Script" in config.name
        assert "main.py" in config.file_patterns

    def test_registry_has_bun_scripts(self) -> None:
        """Test that bun_scripts prototype exists."""
        assert "bun_scripts" in PROTOTYPES
        config = PROTOTYPES["bun_scripts"]
        assert "Bun" in config.name
        assert "tsconfig.json" in config.file_patterns

    def test_registry_has_uv_mcp(self) -> None:
        """Test that uv_mcp prototype exists."""
        assert "uv_mcp" in PROTOTYPES
        config = PROTOTYPES["uv_mcp"]
        assert "MCP" in config.name
        assert "server.py" in config.file_patterns

    def test_registry_has_fastapi(self) -> None:
        """Test that fastapi prototype exists."""
        assert "fastapi" in PROTOTYPES
        config = PROTOTYPES["fastapi"]
        assert "FastAPI" in config.name
        assert "pyproject.toml" in config.file_patterns

    def test_all_prototypes_have_required_fields(self) -> None:
        """Test that all prototypes have required fields."""
        for name, config in PROTOTYPES.items():
            assert config.name, f"{name} missing name"
            assert config.plan_command, f"{name} missing plan_command"
            assert config.description, f"{name} missing description"
            assert config.output_dir, f"{name} missing output_dir"
            assert config.file_patterns, f"{name} missing file_patterns"
            assert "{app_name}" in config.output_dir, f"{name} output_dir missing {{app_name}}"


# =============================================================================
# Helper Function Tests
# =============================================================================


class TestGetPrototypeConfig:
    """Tests for get_prototype_config function."""

    def test_get_existing_config(self) -> None:
        """Test getting an existing config."""
        config = get_prototype_config("vite_vue")
        assert config is not None
        assert config.name == "Vite + Vue"

    def test_get_nonexistent_config(self) -> None:
        """Test getting a non-existent config returns None."""
        config = get_prototype_config("nonexistent")
        assert config is None

    def test_get_all_registered_configs(self) -> None:
        """Test that all registered configs can be retrieved."""
        for name in PROTOTYPES:
            config = get_prototype_config(name)
            assert config is not None
            assert config.name == PROTOTYPES[name].name


class TestListPrototypes:
    """Tests for list_prototypes function."""

    def test_returns_all_prototypes(self) -> None:
        """Test that list_prototypes returns all registered prototypes."""
        prototypes = list_prototypes()
        assert len(prototypes) == len(PROTOTYPES)

    def test_returns_config_objects(self) -> None:
        """Test that list_prototypes returns PrototypeConfig objects."""
        prototypes = list_prototypes()
        assert all(isinstance(p, PrototypeConfig) for p in prototypes)


# =============================================================================
# Prompt Building Tests
# =============================================================================


class TestBuildScaffoldPrompt:
    """Tests for build_scaffold_prompt function."""

    def test_basic_prompt(self) -> None:
        """Test building a basic scaffold prompt."""
        config = PROTOTYPES["fastapi"]
        prompt = build_scaffold_prompt(
            config=config,
            app_name="my-api",
            description="A REST API for tasks",
            output_dir=Path("apps/my-api"),
        )

        # Check key components
        assert "my-api" in prompt
        assert "A REST API for tasks" in prompt
        assert "apps/my-api" in prompt
        assert "FastAPI" in prompt
        assert "pyproject.toml" in prompt

    def test_prompt_contains_all_file_patterns(self) -> None:
        """Test that prompt contains all file patterns."""
        config = PROTOTYPES["vite_vue"]
        prompt = build_scaffold_prompt(
            config=config,
            app_name="my-app",
            description="Test app",
            output_dir=Path("apps/my-app"),
        )

        for pattern in config.file_patterns:
            assert pattern in prompt, f"Pattern {pattern} not in prompt"

    def test_prompt_empty_description(self) -> None:
        """Test building prompt with empty description."""
        config = PROTOTYPES["uv_script"]
        prompt = build_scaffold_prompt(
            config=config,
            app_name="script",
            description="",
            output_dir=Path("apps/script"),
        )

        assert "script" in prompt
        assert "UV Script" in prompt


class TestBuildVerifyPrompt:
    """Tests for build_verify_prompt function."""

    def test_basic_verify_prompt(self) -> None:
        """Test building a basic verify prompt."""
        config = PROTOTYPES["vite_vue"]
        prompt = build_verify_prompt(
            config=config,
            app_name="my-app",
            output_dir=Path("apps/my-app"),
        )

        assert "my-app" in prompt
        assert "apps/my-app" in prompt
        assert "Vite + Vue" in prompt
        assert "Verification" in prompt

    def test_verify_prompt_mentions_files(self) -> None:
        """Test that verify prompt mentions expected files."""
        config = PROTOTYPES["fastapi"]
        prompt = build_verify_prompt(
            config=config,
            app_name="api",
            output_dir=Path("apps/api"),
        )

        # Should mention file patterns
        for pattern in config.file_patterns:
            assert pattern in prompt, f"Pattern {pattern} not in verify prompt"


# =============================================================================
# Format Result Tests
# =============================================================================


class TestFormatPrototypeResult:
    """Tests for format_prototype_result function."""

    def test_format_success_result(self) -> None:
        """Test formatting a successful result."""
        result = PrototypeResult(
            success=True,
            output_dir=Path("apps/my-app"),
            files_created=["main.py", "README.md", "test.py"],
            duration_seconds=25.5,
        )
        formatted = format_prototype_result(result)

        assert "✅" in formatted
        assert "Success" in formatted
        assert "apps/my-app" in formatted
        assert "3" in formatted  # Files created count
        assert "25.5s" in formatted

    def test_format_failure_result(self) -> None:
        """Test formatting a failed result."""
        result = PrototypeResult(
            success=False,
            error="Connection timeout",
            duration_seconds=10.0,
        )
        formatted = format_prototype_result(result)

        assert "❌" in formatted
        assert "Failed" in formatted
        assert "Connection timeout" in formatted
        assert "10.0s" in formatted

    def test_format_many_files(self) -> None:
        """Test formatting result with many files (should truncate)."""
        files = [f"file{i}.py" for i in range(15)]
        result = PrototypeResult(
            success=True,
            output_dir=Path("apps/test"),
            files_created=files,
            duration_seconds=30.0,
        )
        formatted = format_prototype_result(result)

        # Should show first 10 files
        assert "file0.py" in formatted
        assert "file9.py" in formatted
        # Should indicate more files
        assert "more" in formatted

    def test_format_no_files(self) -> None:
        """Test formatting result with no files created."""
        result = PrototypeResult(
            success=True,
            output_dir=Path("apps/empty"),
            files_created=[],
            duration_seconds=5.0,
        )
        formatted = format_prototype_result(result)

        assert "✅" in formatted
        assert "apps/empty" in formatted


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases."""

    def test_output_dir_formatting(self) -> None:
        """Test output directory string formatting."""
        for name, config in PROTOTYPES.items():
            formatted = config.output_dir.format(app_name="test-app")
            assert "test-app" in formatted
            assert "{" not in formatted  # No unformatted placeholders

    def test_special_characters_in_app_name(self) -> None:
        """Test scaffold prompt with special characters in app name."""
        config = PROTOTYPES["fastapi"]
        prompt = build_scaffold_prompt(
            config=config,
            app_name="my-app_v2",
            description="App with special chars: & < > \"",
            output_dir=Path("apps/my-app_v2"),
        )

        assert "my-app_v2" in prompt
        # Special chars should be preserved
        assert "&" in prompt or "App with special" in prompt
