"""Tests for project detection."""

import json
import tempfile
from pathlib import Path

import pytest

from adw.detect import detect_project, get_project_summary, is_monorepo


class TestDetectProject:
    """Tests for detect_project function."""

    def test_detect_react(self, tmp_path: Path) -> None:
        """Test React project detection."""
        package_json = tmp_path / "package.json"
        package_json.write_text(json.dumps({
            "dependencies": {"react": "^18.0.0"}
        }))

        detections = detect_project(tmp_path)
        assert len(detections) == 1
        assert detections[0].category == "frontend"
        assert detections[0].stack == "react"

    def test_detect_vue(self, tmp_path: Path) -> None:
        """Test Vue project detection."""
        package_json = tmp_path / "package.json"
        package_json.write_text(json.dumps({
            "dependencies": {"vue": "^3.0.0"}
        }))

        detections = detect_project(tmp_path)
        assert len(detections) == 1
        assert detections[0].category == "frontend"
        assert detections[0].stack == "vue"

    def test_detect_nextjs(self, tmp_path: Path) -> None:
        """Test Next.js project detection."""
        package_json = tmp_path / "package.json"
        package_json.write_text(json.dumps({
            "dependencies": {"next": "^14.0.0", "react": "^18.0.0"}
        }))

        detections = detect_project(tmp_path)
        assert len(detections) == 1
        assert detections[0].category == "fullstack"
        assert detections[0].stack == "nextjs"

    def test_detect_fastapi(self, tmp_path: Path) -> None:
        """Test FastAPI project detection."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[project]
dependencies = ["fastapi>=0.100.0", "uvicorn"]
""")

        detections = detect_project(tmp_path)
        assert len(detections) == 1
        assert detections[0].category == "backend"
        assert detections[0].stack == "fastapi"

    def test_detect_go(self, tmp_path: Path) -> None:
        """Test Go project detection."""
        go_mod = tmp_path / "go.mod"
        go_mod.write_text("module example.com/myapp\n\ngo 1.21")

        detections = detect_project(tmp_path)
        assert len(detections) == 1
        assert detections[0].category == "backend"
        assert detections[0].stack == "go"

    def test_detect_multiple(self, tmp_path: Path) -> None:
        """Test detecting multiple project types."""
        # Frontend
        package_json = tmp_path / "package.json"
        package_json.write_text(json.dumps({
            "dependencies": {"react": "^18.0.0"}
        }))

        # Backend
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[project]
dependencies = ["fastapi>=0.100.0"]
""")

        detections = detect_project(tmp_path)
        categories = {d.category for d in detections}
        assert "frontend" in categories
        assert "backend" in categories

    def test_detect_empty(self, tmp_path: Path) -> None:
        """Test detection on empty directory."""
        detections = detect_project(tmp_path)
        assert len(detections) == 0


class TestGetProjectSummary:
    """Tests for get_project_summary function."""

    def test_single_detection(self, tmp_path: Path) -> None:
        """Test summary with single detection."""
        package_json = tmp_path / "package.json"
        package_json.write_text(json.dumps({
            "dependencies": {"react": "^18.0.0"}
        }))

        detections = detect_project(tmp_path)
        summary = get_project_summary(detections)
        assert "React" in summary
        assert "frontend" in summary

    def test_no_detections(self) -> None:
        """Test summary with no detections."""
        summary = get_project_summary([])
        assert summary == "Unknown project type"


class TestIsMonorepo:
    """Tests for is_monorepo function."""

    def test_pnpm_workspace(self, tmp_path: Path) -> None:
        """Test pnpm workspace detection."""
        workspace = tmp_path / "pnpm-workspace.yaml"
        workspace.write_text("packages:\n  - 'packages/*'")

        assert is_monorepo(tmp_path) is True

    def test_npm_workspaces(self, tmp_path: Path) -> None:
        """Test npm workspaces detection."""
        package_json = tmp_path / "package.json"
        package_json.write_text(json.dumps({
            "workspaces": ["packages/*"]
        }))

        assert is_monorepo(tmp_path) is True

    def test_packages_dir(self, tmp_path: Path) -> None:
        """Test packages directory detection."""
        packages = tmp_path / "packages"
        packages.mkdir()

        assert is_monorepo(tmp_path) is True

    def test_not_monorepo(self, tmp_path: Path) -> None:
        """Test non-monorepo detection."""
        assert is_monorepo(tmp_path) is False
