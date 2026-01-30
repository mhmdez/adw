"""Tests for spec parsing."""

from pathlib import Path

import pytest

from adw.specs import (
    Spec,
    SpecStatus,
    get_pending_specs,
    load_all_specs,
    load_spec,
    parse_spec,
)


class TestParseSpec:
    """Tests for parse_spec function."""

    def test_parse_basic_spec(self, tmp_path: Path) -> None:
        """Test parsing a basic spec."""
        spec_path = tmp_path / "feature.md"
        content = """# Feature Title

Status: PENDING_APPROVAL

## Description

This is a feature description.

## Technical Approach

Implementation details here.
"""
        spec = parse_spec(content, spec_path)

        assert spec.title == "Feature Title"
        assert spec.status == SpecStatus.PENDING_APPROVAL
        assert "feature description" in spec.description

    def test_parse_approved_spec(self, tmp_path: Path) -> None:
        """Test parsing an approved spec."""
        spec_path = tmp_path / "feature.md"
        content = """# Feature

Status: APPROVED
"""
        spec = parse_spec(content, spec_path)
        assert spec.status == SpecStatus.APPROVED

    def test_parse_draft_spec(self, tmp_path: Path) -> None:
        """Test parsing a draft spec."""
        spec_path = tmp_path / "feature.md"
        content = """# Feature

Status: DRAFT
"""
        spec = parse_spec(content, spec_path)
        assert spec.status == SpecStatus.DRAFT

    def test_parse_no_status(self, tmp_path: Path) -> None:
        """Test parsing spec without status defaults to draft."""
        spec_path = tmp_path / "feature.md"
        content = """# Feature

Just some content.
"""
        spec = parse_spec(content, spec_path)
        assert spec.status == SpecStatus.DRAFT

    def test_parse_title_from_filename(self, tmp_path: Path) -> None:
        """Test title generation from filename."""
        spec_path = tmp_path / "user-authentication.md"
        content = "Just some content."

        spec = parse_spec(content, spec_path)
        assert spec.title == "User Authentication"


class TestLoadSpec:
    """Tests for load_spec function."""

    def test_load_existing_spec(self, tmp_path: Path) -> None:
        """Test loading an existing spec."""
        spec_path = tmp_path / "feature.md"
        spec_path.write_text("""# Feature

Status: PENDING_APPROVAL
""")

        spec = load_spec(spec_path)
        assert spec is not None
        assert spec.status == SpecStatus.PENDING_APPROVAL

    def test_load_nonexistent_spec(self, tmp_path: Path) -> None:
        """Test loading a nonexistent spec."""
        spec = load_spec(tmp_path / "nonexistent.md")
        assert spec is None


class TestLoadAllSpecs:
    """Tests for load_all_specs function."""

    def test_load_multiple_specs(self, tmp_path: Path) -> None:
        """Test loading multiple specs."""
        specs_dir = tmp_path / "specs"
        specs_dir.mkdir()

        (specs_dir / "feature-a.md").write_text("# Feature A\nStatus: APPROVED")
        (specs_dir / "feature-b.md").write_text("# Feature B\nStatus: PENDING_APPROVAL")
        (specs_dir / "feature-c.md").write_text("# Feature C\nStatus: DRAFT")

        specs = load_all_specs(specs_dir)

        assert len(specs) == 3
        # Should be sorted by name
        assert specs[0].name == "feature-a"
        assert specs[1].name == "feature-b"
        assert specs[2].name == "feature-c"

    def test_load_empty_dir(self, tmp_path: Path) -> None:
        """Test loading from empty directory."""
        specs_dir = tmp_path / "specs"
        specs_dir.mkdir()

        specs = load_all_specs(specs_dir)
        assert len(specs) == 0

    def test_load_nonexistent_dir(self, tmp_path: Path) -> None:
        """Test loading from nonexistent directory."""
        specs = load_all_specs(tmp_path / "nonexistent")
        assert len(specs) == 0


class TestGetPendingSpecs:
    """Tests for get_pending_specs function."""

    def test_get_pending(self, tmp_path: Path) -> None:
        """Test getting pending specs."""
        specs_dir = tmp_path / "specs"
        specs_dir.mkdir()

        (specs_dir / "approved.md").write_text("# Approved\nStatus: APPROVED")
        (specs_dir / "pending.md").write_text("# Pending\nStatus: PENDING_APPROVAL")
        (specs_dir / "draft.md").write_text("# Draft\nStatus: DRAFT")

        pending = get_pending_specs(specs_dir)

        assert len(pending) == 1
        assert pending[0].name == "pending"


class TestSpecNeedsApproval:
    """Tests for Spec.needs_approval property."""

    def test_pending_needs_approval(self, tmp_path: Path) -> None:
        """Test that pending spec needs approval."""
        spec = Spec(
            path=tmp_path / "test.md",
            name="test",
            title="Test",
            status=SpecStatus.PENDING_APPROVAL,
        )
        assert spec.needs_approval is True

    def test_approved_no_approval(self, tmp_path: Path) -> None:
        """Test that approved spec doesn't need approval."""
        spec = Spec(
            path=tmp_path / "test.md",
            name="test",
            title="Test",
            status=SpecStatus.APPROVED,
        )
        assert spec.needs_approval is False
