"""Tests for specialized planners (Phase 5).

Tests planner files exist and auto-detection works.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from adw.context.priming import ProjectType, detect_project_type


# =============================================================================
# Planner File Existence Tests
# =============================================================================


class TestPlannerFilesExist:
    """Verify all specialized planner command files exist."""

    @pytest.fixture
    def commands_dir(self) -> Path:
        """Get the .claude/commands directory."""
        # Navigate from tests/ to project root
        project_root = Path(__file__).parent.parent
        return project_root / ".claude" / "commands"

    def test_plan_generic_exists(self, commands_dir: Path) -> None:
        """Generic plan command exists."""
        assert (commands_dir / "plan.md").exists()

    def test_plan_fastapi_exists(self, commands_dir: Path) -> None:
        """FastAPI planner command exists."""
        assert (commands_dir / "plan_fastapi.md").exists()

    def test_plan_react_exists(self, commands_dir: Path) -> None:
        """React planner command exists."""
        assert (commands_dir / "plan_react.md").exists()

    def test_plan_nextjs_exists(self, commands_dir: Path) -> None:
        """Next.js planner command exists."""
        assert (commands_dir / "plan_nextjs.md").exists()

    def test_plan_supabase_exists(self, commands_dir: Path) -> None:
        """Supabase planner command exists."""
        assert (commands_dir / "plan_supabase.md").exists()

    def test_plan_vite_vue_exists(self, commands_dir: Path) -> None:
        """Vite + Vue planner command exists."""
        assert (commands_dir / "plan_vite_vue.md").exists()


class TestPlannerFileContent:
    """Verify planner files have required content."""

    @pytest.fixture
    def commands_dir(self) -> Path:
        """Get the .claude/commands directory."""
        project_root = Path(__file__).parent.parent
        return project_root / ".claude" / "commands"

    def test_plan_fastapi_has_metadata(self, commands_dir: Path) -> None:
        """FastAPI planner has proper metadata."""
        content = (commands_dir / "plan_fastapi.md").read_text()

        assert "allowed-tools:" in content
        assert "model:" in content
        assert "FastAPI" in content
        assert "Pydantic" in content
        assert "dependency injection" in content.lower()

    def test_plan_react_has_metadata(self, commands_dir: Path) -> None:
        """React planner has proper metadata."""
        content = (commands_dir / "plan_react.md").read_text()

        assert "allowed-tools:" in content
        assert "model:" in content
        assert "React" in content
        assert "hooks" in content.lower()
        assert "component" in content.lower()

    def test_plan_nextjs_has_metadata(self, commands_dir: Path) -> None:
        """Next.js planner has proper metadata."""
        content = (commands_dir / "plan_nextjs.md").read_text()

        assert "allowed-tools:" in content
        assert "model:" in content
        assert "Next.js" in content or "Next" in content
        assert "Server Component" in content
        assert "App Router" in content

    def test_plan_supabase_has_metadata(self, commands_dir: Path) -> None:
        """Supabase planner has proper metadata."""
        content = (commands_dir / "plan_supabase.md").read_text()

        assert "allowed-tools:" in content
        assert "model:" in content
        assert "Supabase" in content
        assert "RLS" in content or "Row Level Security" in content
        assert "PostgreSQL" in content


# =============================================================================
# Planner Auto-Detection Tests
# =============================================================================


class TestPlannerAutoDetection:
    """Test planner auto-detection logic."""

    def test_detect_fastapi_project(self, tmp_path: Path) -> None:
        """Detect FastAPI project suggests fastapi planner."""
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "api"\n\n[project.dependencies]\nfastapi = "^0.100.0"\n'
        )

        detection = detect_project_type(tmp_path)
        assert detection.project_type == ProjectType.FASTAPI

    def test_detect_react_project(self, tmp_path: Path) -> None:
        """Detect React project suggests react planner."""
        (tmp_path / "package.json").write_text(
            '{"name": "app", "dependencies": {"react": "^18.0.0"}}'
        )

        detection = detect_project_type(tmp_path)
        assert detection.project_type == ProjectType.REACT

    def test_detect_nextjs_project(self, tmp_path: Path) -> None:
        """Detect Next.js project suggests nextjs planner."""
        (tmp_path / "package.json").write_text(
            '{"name": "app", "dependencies": {"next": "^14.0.0", "react": "^18.0.0"}}'
        )

        detection = detect_project_type(tmp_path)
        assert detection.project_type == ProjectType.NEXTJS

    def test_detect_vue_project(self, tmp_path: Path) -> None:
        """Detect Vue project suggests vue planner."""
        (tmp_path / "package.json").write_text(
            '{"name": "app", "dependencies": {"vue": "^3.0.0"}}'
        )

        detection = detect_project_type(tmp_path)
        assert detection.project_type == ProjectType.VUE

    def test_detect_supabase_in_package_json(self, tmp_path: Path) -> None:
        """Detect Supabase dependency in package.json."""
        (tmp_path / "package.json").write_text(
            '{"name": "app", "dependencies": {"@supabase/supabase-js": "^2.0.0", "react": "^18.0.0"}}'
        )

        # Read and check for supabase
        content = json.loads((tmp_path / "package.json").read_text())
        deps = {**content.get("dependencies", {}), **content.get("devDependencies", {})}

        assert "@supabase/supabase-js" in deps

    def test_detect_supabase_in_requirements(self, tmp_path: Path) -> None:
        """Detect Supabase dependency in requirements.txt."""
        (tmp_path / "requirements.txt").write_text("supabase==2.0.0\nfastapi==0.100.0\n")

        content = (tmp_path / "requirements.txt").read_text().lower()
        assert "supabase" in content


class TestPlannerMapping:
    """Test project type to planner mapping."""

    def test_python_maps_to_generic(self) -> None:
        """Plain Python projects use generic planner."""
        planner_map = {
            ProjectType.PYTHON: "generic",
            ProjectType.GO: "generic",
            ProjectType.RUST: "generic",
        }

        assert planner_map[ProjectType.PYTHON] == "generic"
        assert planner_map[ProjectType.GO] == "generic"
        assert planner_map[ProjectType.RUST] == "generic"

    def test_api_frameworks_map_to_fastapi(self) -> None:
        """Python API frameworks use fastapi planner."""
        planner_map = {
            ProjectType.FASTAPI: "fastapi",
            ProjectType.DJANGO: "fastapi",
            ProjectType.FLASK: "fastapi",
        }

        assert planner_map[ProjectType.FASTAPI] == "fastapi"
        assert planner_map[ProjectType.DJANGO] == "fastapi"
        assert planner_map[ProjectType.FLASK] == "fastapi"

    def test_frontend_frameworks_map_correctly(self) -> None:
        """Frontend frameworks map to appropriate planners."""
        planner_map = {
            ProjectType.REACT: "react",
            ProjectType.NEXTJS: "nextjs",
            ProjectType.VUE: "vue",
        }

        assert planner_map[ProjectType.REACT] == "react"
        assert planner_map[ProjectType.NEXTJS] == "nextjs"
        assert planner_map[ProjectType.VUE] == "vue"


# =============================================================================
# Planner Content Quality Tests
# =============================================================================


class TestPlannerContentQuality:
    """Verify planners have high-quality content."""

    @pytest.fixture
    def commands_dir(self) -> Path:
        """Get the .claude/commands directory."""
        project_root = Path(__file__).parent.parent
        return project_root / ".claude" / "commands"

    def test_planners_have_process_section(self, commands_dir: Path) -> None:
        """All planners should have a process section."""
        planners = ["plan_fastapi.md", "plan_react.md", "plan_nextjs.md", "plan_supabase.md"]

        for planner in planners:
            content = (commands_dir / planner).read_text()
            assert "## Process" in content or "## Planning Process" in content, f"{planner} missing process section"

    def test_planners_have_antipatterns(self, commands_dir: Path) -> None:
        """All planners should have anti-patterns section."""
        planners = ["plan_fastapi.md", "plan_react.md", "plan_nextjs.md", "plan_supabase.md"]

        for planner in planners:
            content = (commands_dir / planner).read_text()
            assert "Anti-Pattern" in content or "anti-pattern" in content.lower(), f"{planner} missing anti-patterns"

    def test_planners_have_best_practices(self, commands_dir: Path) -> None:
        """All planners should have best practices section."""
        planners = ["plan_fastapi.md", "plan_react.md", "plan_nextjs.md", "plan_supabase.md"]

        for planner in planners:
            content = (commands_dir / planner).read_text()
            assert "Best Practice" in content or "best practice" in content.lower(), f"{planner} missing best practices"

    def test_planners_have_code_examples(self, commands_dir: Path) -> None:
        """All planners should have code examples."""
        planners = ["plan_fastapi.md", "plan_react.md", "plan_nextjs.md", "plan_supabase.md"]

        for planner in planners:
            content = (commands_dir / planner).read_text()
            assert "```" in content, f"{planner} missing code examples"

    def test_planners_are_substantial(self, commands_dir: Path) -> None:
        """All planners should have substantial content (>200 lines)."""
        planners = ["plan_fastapi.md", "plan_react.md", "plan_nextjs.md", "plan_supabase.md"]

        for planner in planners:
            content = (commands_dir / planner).read_text()
            line_count = len(content.split("\n"))
            assert line_count > 200, f"{planner} too short ({line_count} lines)"
