"""Tests for PR linker module (Phase 6: Multi-Repo Orchestration)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

import pytest

from adw.github.pr_linker import (
    LinkedPR,
    LinkStatus,
    MergeResult,
    PRLinkGroup,
    _get_link_storage_path,
    _load_link_groups,
    _save_link_groups,
    parse_pr_url,
)


# ============== LinkedPR Tests ==============


class TestLinkedPR:
    """Tests for LinkedPR dataclass."""

    def test_create_linked_pr(self) -> None:
        """Test creating a LinkedPR."""
        pr = LinkedPR(
            owner="octocat",
            repo="hello-world",
            number=42,
            url="https://github.com/octocat/hello-world/pull/42",
            title="Add greeting feature",
        )
        assert pr.owner == "octocat"
        assert pr.repo == "hello-world"
        assert pr.number == 42
        assert pr.state == "open"
        assert pr.approved is False

    def test_full_name(self) -> None:
        """Test full_name property."""
        pr = LinkedPR(
            owner="owner",
            repo="repo",
            number=123,
            url="https://github.com/owner/repo/pull/123",
        )
        assert pr.full_name == "owner/repo#123"

    def test_to_dict(self) -> None:
        """Test serialization to dictionary."""
        pr = LinkedPR(
            owner="octocat",
            repo="hello-world",
            number=42,
            url="https://github.com/octocat/hello-world/pull/42",
            title="Test PR",
            state="merged",
            approved=True,
            head_sha="abc123",
            base_branch="develop",
        )
        data = pr.to_dict()

        assert data["owner"] == "octocat"
        assert data["repo"] == "hello-world"
        assert data["number"] == 42
        assert data["state"] == "merged"
        assert data["approved"] is True
        assert data["head_sha"] == "abc123"
        assert data["base_branch"] == "develop"

    def test_from_dict(self) -> None:
        """Test deserialization from dictionary."""
        data = {
            "owner": "octocat",
            "repo": "hello-world",
            "number": 42,
            "url": "https://github.com/octocat/hello-world/pull/42",
            "title": "Test",
            "state": "open",
            "approved": True,
        }
        pr = LinkedPR.from_dict(data)

        assert pr.owner == "octocat"
        assert pr.repo == "hello-world"
        assert pr.number == 42
        assert pr.approved is True


# ============== PRLinkGroup Tests ==============


class TestPRLinkGroup:
    """Tests for PRLinkGroup dataclass."""

    def test_create_link_group(self) -> None:
        """Test creating a PRLinkGroup."""
        group = PRLinkGroup(
            id="abc12345",
            description="Feature X across repos",
            atomic=True,
        )
        assert group.id == "abc12345"
        assert group.status == LinkStatus.PENDING
        assert group.atomic is True
        assert group.prs == []

    def test_add_pr(self) -> None:
        """Test adding PRs to group."""
        group = PRLinkGroup(id="test")
        pr1 = LinkedPR(owner="o", repo="r1", number=1, url="u1")
        pr2 = LinkedPR(owner="o", repo="r2", number=2, url="u2")

        group.add_pr(pr1)
        group.add_pr(pr2)

        assert len(group.prs) == 2
        assert "o/r1#1" in group.merge_order
        assert "o/r2#2" in group.merge_order

    def test_add_pr_duplicate(self) -> None:
        """Test that duplicate PRs are not added."""
        group = PRLinkGroup(id="test")
        pr1 = LinkedPR(owner="o", repo="r", number=1, url="u")

        group.add_pr(pr1)
        group.add_pr(pr1)

        assert len(group.prs) == 1

    def test_remove_pr(self) -> None:
        """Test removing PR from group."""
        group = PRLinkGroup(id="test")
        pr1 = LinkedPR(owner="o", repo="r1", number=1, url="u1")
        pr2 = LinkedPR(owner="o", repo="r2", number=2, url="u2")

        group.add_pr(pr1)
        group.add_pr(pr2)
        result = group.remove_pr("o/r1#1")

        assert result is True
        assert len(group.prs) == 1
        assert group.prs[0].full_name == "o/r2#2"

    def test_remove_pr_not_found(self) -> None:
        """Test removing non-existent PR."""
        group = PRLinkGroup(id="test")
        result = group.remove_pr("o/r#99")
        assert result is False

    def test_get_pr(self) -> None:
        """Test getting PR by full name."""
        group = PRLinkGroup(id="test")
        pr = LinkedPR(owner="o", repo="r", number=1, url="u")
        group.add_pr(pr)

        found = group.get_pr("o/r#1")
        assert found is not None
        assert found.number == 1

        not_found = group.get_pr("o/r#99")
        assert not_found is None

    def test_is_ready(self) -> None:
        """Test ready check for merge."""
        group = PRLinkGroup(id="test")

        # Empty group is not ready
        assert group.is_ready() is False

        # Add approved and mergeable PR
        pr1 = LinkedPR(
            owner="o",
            repo="r1",
            number=1,
            url="u1",
            state="open",
            approved=True,
            mergeable=True,
        )
        group.add_pr(pr1)
        assert group.is_ready() is True

        # Add non-approved PR
        pr2 = LinkedPR(
            owner="o",
            repo="r2",
            number=2,
            url="u2",
            state="open",
            approved=False,
            mergeable=True,
        )
        group.add_pr(pr2)
        assert group.is_ready() is False

    def test_is_ready_with_conflicts(self) -> None:
        """Test ready check with merge conflicts."""
        group = PRLinkGroup(id="test")
        pr = LinkedPR(
            owner="o",
            repo="r",
            number=1,
            url="u",
            state="open",
            approved=True,
            mergeable=False,
        )
        group.add_pr(pr)
        assert group.is_ready() is False

    def test_to_dict(self) -> None:
        """Test serialization to dictionary."""
        group = PRLinkGroup(
            id="abc123",
            status=LinkStatus.READY,
            description="Test group",
            atomic=True,
            created_at=datetime(2026, 2, 1, 12, 0, 0),
        )
        pr = LinkedPR(owner="o", repo="r", number=1, url="u")
        group.add_pr(pr)

        data = group.to_dict()

        assert data["id"] == "abc123"
        assert data["status"] == "ready"
        assert data["description"] == "Test group"
        assert data["atomic"] is True
        assert len(data["prs"]) == 1
        assert data["created_at"] == "2026-02-01T12:00:00"

    def test_from_dict(self) -> None:
        """Test deserialization from dictionary."""
        data = {
            "id": "xyz789",
            "prs": [
                {"owner": "o", "repo": "r", "number": 1, "url": "u"},
            ],
            "status": "merged",
            "atomic": False,
            "merge_order": ["o/r#1"],
        }
        group = PRLinkGroup.from_dict(data)

        assert group.id == "xyz789"
        assert group.status == LinkStatus.MERGED
        assert group.atomic is False
        assert len(group.prs) == 1


# ============== LinkStatus Tests ==============


class TestLinkStatus:
    """Tests for LinkStatus enum."""

    def test_status_values(self) -> None:
        """Test all status values exist."""
        assert LinkStatus.PENDING.value == "pending"
        assert LinkStatus.READY.value == "ready"
        assert LinkStatus.PARTIAL.value == "partial"
        assert LinkStatus.MERGED.value == "merged"
        assert LinkStatus.FAILED.value == "failed"
        assert LinkStatus.CANCELLED.value == "cancelled"


# ============== MergeResult Tests ==============


class TestMergeResult:
    """Tests for MergeResult dataclass."""

    def test_create_success_result(self) -> None:
        """Test creating a successful result."""
        result = MergeResult(
            success=True,
            merged_prs=["o/r1#1", "o/r2#2"],
        )
        assert result.success is True
        assert len(result.merged_prs) == 2
        assert result.failed_prs == []
        assert result.error == ""

    def test_create_failure_result(self) -> None:
        """Test creating a failure result."""
        result = MergeResult(
            success=False,
            merged_prs=["o/r1#1"],
            failed_prs=["o/r2#2"],
            error="Merge conflict",
        )
        assert result.success is False
        assert result.error == "Merge conflict"

    def test_create_rollback_result(self) -> None:
        """Test creating a rollback result."""
        result = MergeResult(
            success=False,
            merged_prs=["o/r1#1"],
            failed_prs=["o/r2#2"],
            rolled_back=True,
            error="Atomic merge failed",
        )
        assert result.rolled_back is True


# ============== parse_pr_url Tests ==============


class TestParsePrUrl:
    """Tests for parse_pr_url function."""

    def test_parse_full_url(self) -> None:
        """Test parsing full GitHub PR URL."""
        result = parse_pr_url("https://github.com/octocat/hello-world/pull/42")
        assert result == ("octocat", "hello-world", 42)

    def test_parse_short_form(self) -> None:
        """Test parsing owner/repo#number format."""
        result = parse_pr_url("octocat/hello-world#42")
        assert result == ("octocat", "hello-world", 42)

    def test_parse_local_with_mock(self) -> None:
        """Test parsing #number format with mocked current repo."""
        with patch("adw.github.pr_linker.get_current_repo") as mock:
            mock.return_value = ("owner", "repo")
            result = parse_pr_url("#123")
            assert result == ("owner", "repo", 123)

    def test_parse_local_number_only(self) -> None:
        """Test parsing number without # prefix."""
        with patch("adw.github.pr_linker.get_current_repo") as mock:
            mock.return_value = ("owner", "repo")
            result = parse_pr_url("123")
            assert result == ("owner", "repo", 123)

    def test_parse_invalid(self) -> None:
        """Test parsing invalid reference."""
        result = parse_pr_url("not-a-valid-reference")
        assert result is None


# ============== Storage Tests ==============


class TestStorage:
    """Tests for link group storage."""

    def test_save_and_load_groups(self) -> None:
        """Test saving and loading link groups."""
        with TemporaryDirectory() as tmpdir:
            with patch("adw.github.pr_linker._get_link_storage_path") as mock_path:
                mock_path.return_value = Path(tmpdir) / "pr_links.json"

                group = PRLinkGroup(
                    id="test123",
                    description="Test",
                    atomic=True,
                )
                pr = LinkedPR(owner="o", repo="r", number=1, url="u")
                group.add_pr(pr)

                _save_link_groups({"test123": group})
                loaded = _load_link_groups()

                assert "test123" in loaded
                assert loaded["test123"].description == "Test"
                assert len(loaded["test123"].prs) == 1

    def test_load_empty(self) -> None:
        """Test loading when no file exists."""
        with TemporaryDirectory() as tmpdir:
            with patch("adw.github.pr_linker._get_link_storage_path") as mock_path:
                mock_path.return_value = Path(tmpdir) / "nonexistent.json"
                loaded = _load_link_groups()
                assert loaded == {}


# ============== Integration Tests ==============


class TestIntegration:
    """Integration tests for PR linker."""

    def test_link_group_lifecycle(self) -> None:
        """Test complete link group lifecycle."""
        # Create group
        group = PRLinkGroup(
            id="lifecycle",
            description="Test lifecycle",
            atomic=True,
        )

        # Add PRs
        pr1 = LinkedPR(
            owner="org",
            repo="frontend",
            number=10,
            url="https://github.com/org/frontend/pull/10",
            title="Frontend changes",
            approved=True,
            mergeable=True,
        )
        pr2 = LinkedPR(
            owner="org",
            repo="backend",
            number=20,
            url="https://github.com/org/backend/pull/20",
            title="Backend changes",
            approved=False,
            mergeable=True,
        )

        group.add_pr(pr1)
        group.add_pr(pr2)

        # Check not ready (pr2 not approved)
        assert group.is_ready() is False
        assert group.status == LinkStatus.PENDING

        # Approve pr2
        group.prs[1].approved = True
        assert group.is_ready() is True

        # Simulate merge
        group.prs[0].state = "merged"
        group.prs[1].state = "merged"
        group.status = LinkStatus.MERGED

        assert group.status == LinkStatus.MERGED
        assert all(pr.state == "merged" for pr in group.prs)

    def test_serialization_roundtrip(self) -> None:
        """Test that groups survive serialization roundtrip."""
        original = PRLinkGroup(
            id="roundtrip",
            description="Test serialization",
            atomic=True,
            created_at=datetime(2026, 1, 15, 10, 0, 0),
            merge_order=["o/r1#1", "o/r2#2"],
        )
        pr1 = LinkedPR(
            owner="o",
            repo="r1",
            number=1,
            url="u1",
            title="PR 1",
            state="open",
            approved=True,
            mergeable=True,
        )
        pr2 = LinkedPR(
            owner="o",
            repo="r2",
            number=2,
            url="u2",
            title="PR 2",
            state="open",
            approved=False,
        )
        original.add_pr(pr1)
        original.add_pr(pr2)

        # Serialize and deserialize
        data = original.to_dict()
        restored = PRLinkGroup.from_dict(data)

        # Verify
        assert restored.id == original.id
        assert restored.description == original.description
        assert restored.atomic == original.atomic
        assert restored.created_at == original.created_at
        assert len(restored.prs) == 2
        assert restored.prs[0].title == "PR 1"
        assert restored.prs[1].approved is False
