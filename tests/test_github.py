"""Tests for Phase 4: Feedback Loops (GitHub integration).

Tests for:
- PR review watcher
- Comment parser
- Auto-fix functionality
- Approval gates
"""

from __future__ import annotations

import gzip
import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from adw.github.review_watcher import (
    PRInfo,
    PRReviewWatcher,
    PRStatus,
    ReviewComment,
    get_pr_review_comments,
    get_pr_status,
    reply_to_comment,
    add_pr_comment,
)
from adw.github.comment_parser import (
    ActionableComment,
    ActionPriority,
    CommentParser,
    CommentType,
    parse_review_comment,
)
from adw.github.auto_fix import (
    AutoFixer,
    FixResult,
    FixStatus,
    apply_review_fixes,
)
from adw.github.approval_gate import (
    ApprovalGate,
    ApprovalRequest,
    ApprovalStatus,
    ContinuePrompt,
    add_continue_prompt,
    approve_task,
    create_approval_request,
    get_approval_context,
    list_pending_approvals,
    load_approval_request,
    reject_task,
)


# ============== ReviewComment Tests ==============


class TestReviewComment:
    """Tests for ReviewComment data class."""

    def test_to_dict(self) -> None:
        """Test serialization to dictionary."""
        comment = ReviewComment(
            id=123,
            body="Please fix this",
            author="reviewer",
            path="src/main.py",
            line=42,
            created_at=datetime(2024, 1, 15, 10, 30),
        )

        result = comment.to_dict()

        assert result["id"] == 123
        assert result["body"] == "Please fix this"
        assert result["author"] == "reviewer"
        assert result["path"] == "src/main.py"
        assert result["line"] == 42
        assert result["created_at"] == "2024-01-15T10:30:00"

    def test_from_dict(self) -> None:
        """Test deserialization from dictionary."""
        data = {
            "id": 456,
            "body": "Add error handling",
            "author": "dev",
            "path": "src/api.py",
            "line": 100,
            "created_at": "2024-02-20T14:00:00",
        }

        comment = ReviewComment.from_dict(data)

        assert comment.id == 456
        assert comment.body == "Add error handling"
        assert comment.author == "dev"
        assert comment.path == "src/api.py"
        assert comment.line == 100
        assert comment.created_at == datetime(2024, 2, 20, 14, 0)

    def test_from_dict_minimal(self) -> None:
        """Test deserialization with minimal data."""
        data = {
            "id": 789,
            "body": "LGTM",
            "author": "reviewer",
        }

        comment = ReviewComment.from_dict(data)

        assert comment.id == 789
        assert comment.path is None
        assert comment.line is None
        assert comment.created_at is None


# ============== PRInfo Tests ==============


class TestPRInfo:
    """Tests for PRInfo data class."""

    def test_to_dict(self) -> None:
        """Test serialization."""
        info = PRInfo(
            number=123,
            title="Add feature",
            state=PRStatus.OPEN,
            head_branch="feature-branch",
            base_branch="main",
        )

        result = info.to_dict()

        assert result["number"] == 123
        assert result["title"] == "Add feature"
        assert result["state"] == "open"
        assert result["head_branch"] == "feature-branch"


# ============== PRReviewWatcher Tests ==============


class TestPRReviewWatcher:
    """Tests for PR review watcher."""

    def test_init_without_state_file(self) -> None:
        """Test initialization without state file."""
        watcher = PRReviewWatcher(pr_number=123)

        assert watcher.pr_number == 123
        assert watcher.seen_comment_ids == set()
        assert watcher.last_check is None

    def test_init_with_state_file(self, tmp_path: Path) -> None:
        """Test initialization loads existing state."""
        state_file = tmp_path / "watcher.json"
        state_data = {
            "seen_comment_ids": [1, 2, 3],
            "last_check": "2024-01-15T10:00:00",
        }
        state_file.write_text(json.dumps(state_data))

        watcher = PRReviewWatcher(pr_number=123, state_file=state_file)

        assert watcher.seen_comment_ids == {1, 2, 3}
        assert watcher.last_check == datetime(2024, 1, 15, 10, 0)

    def test_mark_comment_seen(self, tmp_path: Path) -> None:
        """Test marking comments as seen."""
        state_file = tmp_path / "watcher.json"
        watcher = PRReviewWatcher(pr_number=123, state_file=state_file)

        watcher.mark_comment_seen(456)

        assert 456 in watcher.seen_comment_ids

        # Check persistence
        saved_data = json.loads(state_file.read_text())
        assert 456 in saved_data["seen_comment_ids"]

    @patch("adw.github.review_watcher.get_pr_review_comments")
    def test_get_new_comments(self, mock_get: MagicMock, tmp_path: Path) -> None:
        """Test getting only new comments."""
        state_file = tmp_path / "watcher.json"
        watcher = PRReviewWatcher(pr_number=123, state_file=state_file)
        watcher.seen_comment_ids = {1, 2}

        mock_get.return_value = [
            ReviewComment(id=1, body="Old", author="a"),
            ReviewComment(id=2, body="Old", author="b"),
            ReviewComment(id=3, body="New", author="c"),
        ]

        new_comments = watcher.get_new_comments()

        assert len(new_comments) == 1
        assert new_comments[0].id == 3
        assert 3 in watcher.seen_comment_ids


# ============== Comment Parser Tests ==============


class TestCommentParser:
    """Tests for comment parsing."""

    def test_parse_actionable_change_request(self) -> None:
        """Test parsing actionable change request."""
        comment = ReviewComment(
            id=1,
            body="Please change the variable name to be more descriptive",
            author="reviewer",
        )

        result = parse_review_comment(comment)

        assert result.comment_type == CommentType.ACTIONABLE
        assert result.is_actionable
        assert "please change" in result.keywords[0].lower()

    def test_parse_actionable_add_request(self) -> None:
        """Test parsing add request."""
        comment = ReviewComment(
            id=2,
            body="Add error handling for the edge case",
            author="reviewer",
            path="src/api.py",
            line=50,
        )

        result = parse_review_comment(comment)

        assert result.comment_type == CommentType.ACTIONABLE
        assert result.priority == ActionPriority.HIGH
        assert result.file_path == "src/api.py"
        assert result.line_number == 50

    def test_parse_approval(self) -> None:
        """Test parsing approval comment."""
        comment = ReviewComment(
            id=3,
            body="LGTM",
            author="reviewer",
        )

        result = parse_review_comment(comment)

        assert result.comment_type == CommentType.APPROVAL
        assert not result.is_actionable

    def test_parse_approval_with_emoji(self) -> None:
        """Test parsing emoji approval."""
        comment = ReviewComment(
            id=4,
            body="👍",
            author="reviewer",
        )

        result = parse_review_comment(comment)

        assert result.comment_type == CommentType.APPROVAL

    def test_parse_question(self) -> None:
        """Test parsing question comment."""
        comment = ReviewComment(
            id=5,
            body="Why did you choose this approach?",
            author="reviewer",
        )

        result = parse_review_comment(comment)

        assert result.comment_type == CommentType.QUESTION

    def test_parse_adw_generated(self) -> None:
        """Test parsing ADW-generated comment."""
        comment = ReviewComment(
            id=6,
            body="<!-- ADW:abc12345 -->\nFixed in commit def456",
            author="bot",
        )

        result = parse_review_comment(comment)

        assert result.comment_type == CommentType.ADW_GENERATED

    def test_extract_suggestion(self) -> None:
        """Test extracting code suggestion."""
        comment = ReviewComment(
            id=7,
            body="This should be:\n```suggestion\nconst value = 42;\n```",
            author="reviewer",
        )

        result = parse_review_comment(comment)

        assert result.suggested_change == "const value = 42;"

    def test_parser_get_actionable(self) -> None:
        """Test CommentParser.get_actionable()."""
        comments = [
            ReviewComment(id=1, body="Please fix this", author="a"),
            ReviewComment(id=2, body="LGTM", author="b"),
            ReviewComment(id=3, body="Add error handling", author="c"),
        ]

        parser = CommentParser(comments=comments)
        actionable = parser.get_actionable()

        assert len(actionable) == 2
        assert all(c.is_actionable for c in actionable)

    def test_parser_get_by_file(self) -> None:
        """Test grouping comments by file."""
        comments = [
            ReviewComment(id=1, body="Fix this", author="a", path="src/a.py"),
            ReviewComment(id=2, body="Fix that", author="b", path="src/a.py"),
            ReviewComment(id=3, body="General comment", author="c"),
        ]

        parser = CommentParser(comments=comments)
        by_file = parser.get_by_file()

        assert "src/a.py" in by_file
        assert len(by_file["src/a.py"]) == 2
        assert "__general__" in by_file

    def test_parser_get_high_priority(self) -> None:
        """Test getting high priority comments."""
        comments = [
            ReviewComment(id=1, body="Add error handling for null", author="a"),
            ReviewComment(id=2, body="Consider using a better name", author="b"),
        ]

        parser = CommentParser(comments=comments)
        high = parser.get_high_priority()

        assert len(high) == 1
        assert high[0].priority == ActionPriority.HIGH

    def test_parser_summary(self) -> None:
        """Test summary generation."""
        comments = [
            ReviewComment(id=1, body="Please fix", author="a"),
            ReviewComment(id=2, body="LGTM", author="b"),
            ReviewComment(id=3, body="Why?", author="c"),
        ]

        parser = CommentParser(comments=comments)
        summary = parser.summary()

        assert "3 total" in summary
        assert "1 actionable" in summary


# ============== FixResult Tests ==============


class TestFixResult:
    """Tests for FixResult data class."""

    def test_success_property(self) -> None:
        """Test success property."""
        success_result = FixResult(
            comment_id=1,
            status=FixStatus.SUCCESS,
            commit_hash="abc123",
        )
        failed_result = FixResult(
            comment_id=2,
            status=FixStatus.FAILED,
            error_message="Error",
        )

        assert success_result.success
        assert not failed_result.success

    def test_to_dict(self) -> None:
        """Test serialization."""
        result = FixResult(
            comment_id=123,
            status=FixStatus.SUCCESS,
            commit_hash="abc123",
            changes_made=["src/main.py"],
            duration_seconds=5.5,
        )

        data = result.to_dict()

        assert data["comment_id"] == 123
        assert data["status"] == "success"
        assert data["commit_hash"] == "abc123"
        assert data["changes_made"] == ["src/main.py"]


# ============== AutoFixer Tests ==============


class TestAutoFixer:
    """Tests for AutoFixer."""

    def test_build_fix_prompt(self, tmp_path: Path) -> None:
        """Test building fix prompt."""
        fixer = AutoFixer(
            pr_number=123,
            branch="feature",
            working_dir=tmp_path,
            adw_id="abc123",
        )

        comment = ActionableComment(
            original_comment=ReviewComment(id=1, body="Fix this", author="a"),
            comment_type=CommentType.ACTIONABLE,
            action_description="Please add null check",
            priority=ActionPriority.HIGH,
            file_path="src/main.py",
            line_number=42,
        )

        prompt = fixer._build_fix_prompt(comment)

        assert "PR Review Fix Request" in prompt
        assert "Please add null check" in prompt
        assert "src/main.py" in prompt
        assert "42" in prompt
        assert "high" in prompt.lower()

    def test_fix_comment_skips_non_actionable(self, tmp_path: Path) -> None:
        """Test that non-actionable comments are skipped."""
        fixer = AutoFixer(
            pr_number=123,
            branch="feature",
            working_dir=tmp_path,
            adw_id="abc123",
        )

        comment = ActionableComment(
            original_comment=ReviewComment(id=1, body="LGTM", author="a"),
            comment_type=CommentType.APPROVAL,
            action_description="",
        )

        result = fixer.fix_comment(comment)

        assert result.status == FixStatus.SKIPPED
        assert "not actionable" in result.error_message.lower()

    def test_fix_comment_dry_run(self, tmp_path: Path) -> None:
        """Test dry run mode."""
        fixer = AutoFixer(
            pr_number=123,
            branch="feature",
            working_dir=tmp_path,
            adw_id="abc123",
            dry_run=True,
        )

        comment = ActionableComment(
            original_comment=ReviewComment(id=1, body="Fix", author="a"),
            comment_type=CommentType.ACTIONABLE,
            action_description="Fix this",
        )

        result = fixer.fix_comment(comment)

        assert result.status == FixStatus.SKIPPED
        assert "dry run" in result.error_message.lower()


# ============== Approval Gate Tests ==============


class TestApprovalRequest:
    """Tests for ApprovalRequest data class."""

    def test_to_dict(self) -> None:
        """Test serialization."""
        request = ApprovalRequest(
            task_id="abc123",
            title="Add feature",
            description="Implement user auth",
            proposed_plan="1. Add login\n2. Add logout",
            files_to_modify=["src/auth.py"],
            created_at=datetime(2024, 1, 15, 10, 0),
        )

        data = request.to_dict()

        assert data["task_id"] == "abc123"
        assert data["title"] == "Add feature"
        assert data["status"] == "pending"
        assert "src/auth.py" in data["files_to_modify"]

    def test_from_dict(self) -> None:
        """Test deserialization."""
        data = {
            "task_id": "def456",
            "title": "Fix bug",
            "description": "Fix login",
            "proposed_plan": "Update validation",
            "files_to_modify": [],
            "status": "approved",
            "created_at": "2024-02-20T14:00:00",
        }

        request = ApprovalRequest.from_dict(data)

        assert request.task_id == "def456"
        assert request.status == ApprovalStatus.APPROVED

    def test_is_pending(self) -> None:
        """Test is_pending property."""
        pending = ApprovalRequest(
            task_id="a",
            title="T",
            description="D",
            proposed_plan="P",
        )
        approved = ApprovalRequest(
            task_id="b",
            title="T",
            description="D",
            proposed_plan="P",
            status=ApprovalStatus.APPROVED,
        )

        assert pending.is_pending
        assert not approved.is_pending

    def test_is_expired(self) -> None:
        """Test expiration detection."""
        expired = ApprovalRequest(
            task_id="a",
            title="T",
            description="D",
            proposed_plan="P",
            created_at=datetime.now() - timedelta(hours=48),
            expires_at=datetime.now() - timedelta(hours=24),
        )
        not_expired = ApprovalRequest(
            task_id="b",
            title="T",
            description="D",
            proposed_plan="P",
        )

        assert expired.is_expired
        assert not not_expired.is_expired

    def test_to_markdown(self) -> None:
        """Test markdown generation."""
        request = ApprovalRequest(
            task_id="abc123",
            title="Add authentication",
            description="Implement OAuth2",
            proposed_plan="1. Add routes\n2. Add handlers",
            files_to_modify=["src/auth.py", "src/routes.py"],
            effort_estimate="2 hours",
            risk_assessment="Low risk",
        )

        md = request.to_markdown()

        assert "# Approval Request: Add authentication" in md
        assert "abc123" in md
        assert "OAuth2" in md
        assert "src/auth.py" in md
        assert "adw approve abc123" in md


# ============== Approval Functions Tests ==============


class TestApprovalFunctions:
    """Tests for approval gate functions."""

    def test_create_approval_request(self, tmp_path: Path) -> None:
        """Test creating approval request."""
        request = create_approval_request(
            task_id="test123",
            title="Test Task",
            description="Test description",
            proposed_plan="Test plan",
            files_to_modify=["file.py"],
            base_path=tmp_path,
        )

        assert request.task_id == "test123"
        assert request.status == ApprovalStatus.PENDING

        # Check files were created
        json_path = tmp_path / ".adw" / "approvals" / "test123.json"
        md_path = tmp_path / "agents" / "test123" / "APPROVAL_REQUEST.md"

        assert json_path.exists()
        assert md_path.exists()

    def test_load_approval_request(self, tmp_path: Path) -> None:
        """Test loading approval request."""
        # Create first
        create_approval_request(
            task_id="load123",
            title="Load Test",
            description="Test",
            proposed_plan="Plan",
            base_path=tmp_path,
        )

        # Load
        loaded = load_approval_request("load123", base_path=tmp_path)

        assert loaded is not None
        assert loaded.task_id == "load123"
        assert loaded.title == "Load Test"

    def test_load_approval_request_not_found(self, tmp_path: Path) -> None:
        """Test loading non-existent request."""
        loaded = load_approval_request("nonexistent", base_path=tmp_path)

        assert loaded is None

    def test_approve_task(self, tmp_path: Path) -> None:
        """Test approving a task."""
        create_approval_request(
            task_id="approve123",
            title="Approve Test",
            description="Test",
            proposed_plan="Plan",
            base_path=tmp_path,
        )

        result = approve_task("approve123", reviewer="tester", base_path=tmp_path)

        assert result is not None
        assert result.status == ApprovalStatus.APPROVED
        assert result.reviewer == "tester"
        assert result.approved_at is not None

    def test_reject_task(self, tmp_path: Path) -> None:
        """Test rejecting a task."""
        create_approval_request(
            task_id="reject123",
            title="Reject Test",
            description="Test",
            proposed_plan="Plan",
            base_path=tmp_path,
        )

        result = reject_task(
            "reject123",
            reason="Wrong approach",
            reviewer="tester",
            base_path=tmp_path,
        )

        assert result is not None
        assert result.status == ApprovalStatus.REJECTED
        assert result.rejection_reason == "Wrong approach"
        assert result.rejected_at is not None

    def test_add_continue_prompt(self, tmp_path: Path) -> None:
        """Test adding continue prompt."""
        create_approval_request(
            task_id="continue123",
            title="Continue Test",
            description="Test",
            proposed_plan="Plan",
            base_path=tmp_path,
        )

        result = add_continue_prompt(
            "continue123",
            "Add more error handling",
            phase="implement",
            base_path=tmp_path,
        )

        assert result is not None
        assert len(result.continue_prompts) == 1
        assert result.continue_prompts[0].prompt == "Add more error handling"
        assert result.continue_prompts[0].phase == "implement"

    def test_list_pending_approvals(self, tmp_path: Path) -> None:
        """Test listing pending approvals."""
        # Create multiple requests
        create_approval_request(
            task_id="pending1",
            title="Pending 1",
            description="Test",
            proposed_plan="Plan",
            base_path=tmp_path,
        )
        create_approval_request(
            task_id="pending2",
            title="Pending 2",
            description="Test",
            proposed_plan="Plan",
            base_path=tmp_path,
        )

        # Approve one
        approve_task("pending1", base_path=tmp_path)

        # List pending
        pending = list_pending_approvals(base_path=tmp_path)

        assert len(pending) == 1
        assert pending[0].task_id == "pending2"

    def test_get_approval_context(self, tmp_path: Path) -> None:
        """Test getting approval context for agent prompt."""
        create_approval_request(
            task_id="context123",
            title="Context Test",
            description="Test",
            proposed_plan="Plan",
            base_path=tmp_path,
        )
        reject_task("context123", reason="Bad approach", base_path=tmp_path)

        # Re-create as pending for continue prompt
        create_approval_request(
            task_id="context456",
            title="Context Test 2",
            description="Test",
            proposed_plan="Plan",
            base_path=tmp_path,
        )
        add_continue_prompt("context456", "Add validation", base_path=tmp_path)

        context = get_approval_context("context456", base_path=tmp_path)

        assert "Add validation" in context


# ============== ApprovalGate Tests ==============


class TestApprovalGate:
    """Tests for ApprovalGate class."""

    def test_requires_approval_default(self) -> None:
        """Test default approval requirements."""
        gate = ApprovalGate()

        assert gate.requires_approval("plan")
        assert gate.requires_approval("implement")
        assert not gate.requires_approval("test")

    def test_requires_approval_disabled(self) -> None:
        """Test with gate disabled."""
        gate = ApprovalGate(enabled=False)

        assert not gate.requires_approval("plan")
        assert not gate.requires_approval("implement")

    @patch.dict("os.environ", {"ADW_AUTO_APPROVE": "1"})
    def test_auto_approve_env(self) -> None:
        """Test auto-approve from environment variable."""
        gate = ApprovalGate()

        assert not gate.enabled

    def test_create_gate(self, tmp_path: Path) -> None:
        """Test creating approval gate."""
        gate = ApprovalGate()

        request = gate.create_gate(
            task_id="gate123",
            title="Gate Test",
            description="Test",
            proposed_plan="Plan",
            files_to_modify=["file.py"],
            risk_level="medium",
            base_path=tmp_path,
        )

        assert request.status == ApprovalStatus.PENDING
        assert "medium" in request.risk_assessment.lower()

    def test_create_gate_auto_approve_low_risk(self, tmp_path: Path) -> None:
        """Test auto-approve for low risk tasks."""
        gate = ApprovalGate(auto_approve_low_risk=True)

        gate.create_gate(
            task_id="lowrisk123",
            title="Low Risk Test",
            description="Test",
            proposed_plan="Plan",
            risk_level="low",
            base_path=tmp_path,
        )

        # Reload to get the approved status
        request = load_approval_request("lowrisk123", base_path=tmp_path)

        assert request is not None
        assert request.status == ApprovalStatus.APPROVED
        assert request.reviewer == "auto"


# ============== ContinuePrompt Tests ==============


class TestContinuePrompt:
    """Tests for ContinuePrompt data class."""

    def test_to_dict(self) -> None:
        """Test serialization."""
        prompt = ContinuePrompt(
            prompt="Add validation",
            timestamp=datetime(2024, 1, 15, 10, 30),
            phase="implement",
        )

        data = prompt.to_dict()

        assert data["prompt"] == "Add validation"
        assert data["phase"] == "implement"

    def test_from_dict(self) -> None:
        """Test deserialization."""
        data = {
            "prompt": "Fix bug",
            "timestamp": "2024-02-20T14:00:00",
            "phase": "test",
        }

        prompt = ContinuePrompt.from_dict(data)

        assert prompt.prompt == "Fix bug"
        assert prompt.phase == "test"
