"""Tests for spec parsing and loading."""

from datetime import datetime
from pathlib import Path

import pytest

from adw.specs import (
    Spec,
    SpecLoader,
    SpecStatus,
    get_pending_specs,
    load_all_specs,
    load_spec,
    parse_spec,
)


class TestSpecLoader:
    """Tests for SpecLoader class."""

    def test_load_spec_from_file(self, tmp_path: Path) -> None:
        """Test loading a spec from a file."""
        specs_dir = tmp_path / "specs"
        specs_dir.mkdir()

        spec_file = specs_dir / "P1-1.md"
        spec_file.write_text("""# Task P1-1: Feature Title

Status: pending

## Objective

This is a feature description.
""")

        loader = SpecLoader(specs_dir=specs_dir)
        specs = loader.load_all()

        assert len(specs) == 1
        assert specs[0].id == "P1-1"
        assert specs[0].title == "Feature Title"
        assert specs[0].status == SpecStatus.PENDING

    def test_load_approved_spec(self, tmp_path: Path) -> None:
        """Test loading an approved spec."""
        specs_dir = tmp_path / "specs"
        specs_dir.mkdir()

        spec_file = specs_dir / "P1-2.md"
        spec_file.write_text("""# Task P1-2: Another Feature

Status: approved

## Objective

Implementation details.
""")

        loader = SpecLoader(specs_dir=specs_dir)
        specs = loader.load_all()

        assert len(specs) == 1
        assert specs[0].status == SpecStatus.APPROVED

    def test_load_draft_spec(self, tmp_path: Path) -> None:
        """Test loading a draft spec (no status or explicit draft)."""
        specs_dir = tmp_path / "specs"
        specs_dir.mkdir()

        spec_file = specs_dir / "P1-3.md"
        spec_file.write_text("""# Task P1-3: Draft Feature

Just some content without explicit status.
""")

        loader = SpecLoader(specs_dir=specs_dir)
        specs = loader.load_all()

        assert len(specs) == 1
        assert specs[0].status == SpecStatus.DRAFT

    def test_load_multiple_specs(self, tmp_path: Path) -> None:
        """Test loading multiple specs."""
        specs_dir = tmp_path / "specs"
        specs_dir.mkdir()

        (specs_dir / "P1-1.md").write_text("# Feature A\nStatus: approved")
        (specs_dir / "P1-2.md").write_text("# Feature B\nStatus: pending")
        (specs_dir / "P2-1.md").write_text("# Feature C\nStatus: draft")

        loader = SpecLoader(specs_dir=specs_dir)
        specs = loader.load_all()

        assert len(specs) == 3

    def test_load_empty_dir(self, tmp_path: Path) -> None:
        """Test loading from empty directory."""
        specs_dir = tmp_path / "specs"
        specs_dir.mkdir()

        loader = SpecLoader(specs_dir=specs_dir)
        specs = loader.load_all()

        assert len(specs) == 0

    def test_load_nonexistent_dir(self, tmp_path: Path) -> None:
        """Test loading from nonexistent directory."""
        loader = SpecLoader(specs_dir=tmp_path / "nonexistent")
        specs = loader.load_all()

        assert len(specs) == 0

    def test_get_spec_by_id(self, tmp_path: Path) -> None:
        """Test getting a specific spec by ID."""
        specs_dir = tmp_path / "specs"
        specs_dir.mkdir()

        (specs_dir / "P1-1.md").write_text("# Test Spec\nStatus: pending")

        loader = SpecLoader(specs_dir=specs_dir)
        spec = loader.get_spec("P1-1")

        assert spec is not None
        assert spec.id == "P1-1"

    def test_get_nonexistent_spec(self, tmp_path: Path) -> None:
        """Test getting a nonexistent spec."""
        specs_dir = tmp_path / "specs"
        specs_dir.mkdir()

        loader = SpecLoader(specs_dir=specs_dir)
        spec = loader.get_spec("P99-99")

        assert spec is None


class TestLoadSpec:
    """Tests for load_spec function."""

    def test_load_existing_spec(self, tmp_path: Path) -> None:
        """Test loading an existing spec file."""
        specs_dir = tmp_path / "specs"
        specs_dir.mkdir()

        spec_file = specs_dir / "P1-1.md"
        spec_file.write_text("""# Feature

Status: pending
""")

        spec = load_spec(spec_file)
        assert spec is not None
        assert spec.status == SpecStatus.PENDING

    def test_load_nonexistent_spec(self, tmp_path: Path) -> None:
        """Test loading a nonexistent spec file."""
        spec = load_spec(tmp_path / "nonexistent.md")
        assert spec is None


class TestParseSpec:
    """Tests for parse_spec function (alias for load_spec)."""

    def test_parse_spec_file(self, tmp_path: Path) -> None:
        """Test parsing a spec file."""
        specs_dir = tmp_path / "specs"
        specs_dir.mkdir()

        spec_file = specs_dir / "P1-1.md"
        spec_file.write_text("""# Test Feature

Status: approved

## Objective

Test objective.
""")

        spec = parse_spec(spec_file)
        assert spec is not None
        assert spec.status == SpecStatus.APPROVED


class TestSpecModel:
    """Tests for Spec model."""

    def test_spec_is_actionable(self) -> None:
        """Test is_actionable property."""
        approved_spec = Spec(
            id="P1-1",
            title="Test",
            status=SpecStatus.APPROVED,
            file_path=Path("test.md"),
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        assert approved_spec.is_actionable is True

        pending_spec = Spec(
            id="P1-2",
            title="Test",
            status=SpecStatus.PENDING,
            file_path=Path("test.md"),
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        assert pending_spec.is_actionable is False

    def test_spec_display_status(self) -> None:
        """Test display_status property."""
        spec = Spec(
            id="P1-1",
            title="Test",
            status=SpecStatus.PENDING,
            file_path=Path("test.md"),
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        assert "pending" in spec.display_status


class TestSpecStatus:
    """Tests for SpecStatus enum."""

    def test_status_values(self) -> None:
        """Test all status values exist."""
        assert SpecStatus.DRAFT.value == "draft"
        assert SpecStatus.PENDING.value == "pending"
        assert SpecStatus.APPROVED.value == "approved"
        assert SpecStatus.REJECTED.value == "rejected"
        assert SpecStatus.IMPLEMENTED.value == "implemented"
