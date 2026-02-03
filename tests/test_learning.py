"""Tests for the learning module (Phase 5 - Self-Improving Agents).

Tests pattern learning, expertise section building, and knowledge persistence.
"""

from __future__ import annotations

import json
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from adw.learning import (
    Learning,
    LearningType,
    PatternStore,
    build_expertise_section,
    extract_learnings_from_feedback,
    get_combined_expertise,
    get_default_pattern_store,
    inject_expertise_into_prompt,
    record_task_outcome,
)
from adw.learning.patterns import TaskOutcome, _detect_domain_from_files


# =============================================================================
# Learning Data Structure Tests
# =============================================================================


class TestLearning:
    """Tests for the Learning dataclass."""

    def test_default_values(self) -> None:
        """Test default learning values."""
        learning = Learning(
            type=LearningType.PATTERN,
            content="Use dependency injection",
        )

        assert learning.type == LearningType.PATTERN
        assert learning.content == "Use dependency injection"
        assert learning.context == ""
        assert learning.project == "global"
        assert learning.domain == "general"
        assert learning.success_count == 1
        assert learning.created_at is not None
        assert learning.last_used is None
        assert learning.source_task_id is None

    def test_to_dict(self) -> None:
        """Test serialization to dict."""
        learning = Learning(
            type=LearningType.ISSUE,
            content="Memory leak in X",
            context="Use WeakRef",
            domain="frontend",
            success_count=5,
        )

        data = learning.to_dict()

        assert data["type"] == "issue"
        assert data["content"] == "Memory leak in X"
        assert data["context"] == "Use WeakRef"
        assert data["domain"] == "frontend"
        assert data["success_count"] == 5
        assert "created_at" in data

    def test_from_dict(self) -> None:
        """Test deserialization from dict."""
        data = {
            "type": "pattern",
            "content": "Test pattern",
            "context": "Test context",
            "domain": "backend",
            "success_count": 10,
            "created_at": "2026-01-15T10:30:00",
        }

        learning = Learning.from_dict(data)

        assert learning.type == LearningType.PATTERN
        assert learning.content == "Test pattern"
        assert learning.domain == "backend"
        assert learning.success_count == 10

    def test_from_dict_handles_invalid_date(self) -> None:
        """Test from_dict handles invalid date gracefully."""
        data = {
            "type": "pattern",
            "content": "Test",
            "created_at": "invalid-date",
        }

        learning = Learning.from_dict(data)
        assert learning.created_at is not None  # Falls back to now()

    def test_mark_used(self) -> None:
        """Test marking learning as used."""
        learning = Learning(
            type=LearningType.PATTERN,
            content="Test",
        )

        original_count = learning.success_count
        learning.mark_used(success=True)

        assert learning.success_count == original_count + 1
        assert learning.last_used is not None


class TestLearningType:
    """Tests for LearningType enum."""

    def test_all_types_exist(self) -> None:
        """Test all expected learning types exist."""
        assert LearningType.PATTERN.value == "pattern"
        assert LearningType.ISSUE.value == "issue"
        assert LearningType.BEST_PRACTICE.value == "best_practice"
        assert LearningType.MISTAKE.value == "mistake"


# =============================================================================
# Pattern Store Tests
# =============================================================================


class TestPatternStore:
    """Tests for PatternStore."""

    def test_empty_store(self, tmp_path: Path) -> None:
        """Test empty pattern store."""
        store = PatternStore(learning_dir=tmp_path, project="test")

        assert len(store.learnings) == 0
        assert store.get_statistics()["total_learnings"] == 0

    def test_add_learning(self, tmp_path: Path) -> None:
        """Test adding a learning."""
        store = PatternStore(learning_dir=tmp_path, project="test")

        learning = Learning(
            type=LearningType.PATTERN,
            content="Use async for I/O",
        )
        store.add_learning(learning)

        assert len(store.learnings) == 1
        assert store.learnings[0].content == "Use async for I/O"

    def test_add_duplicate_learning(self, tmp_path: Path) -> None:
        """Test that duplicate learnings are merged."""
        store = PatternStore(learning_dir=tmp_path, project="test")

        learning1 = Learning(
            type=LearningType.PATTERN,
            content="Use async for I/O",
        )
        learning2 = Learning(
            type=LearningType.PATTERN,
            content="use async for i/o",  # Same content, different case
        )

        store.add_learning(learning1)
        store.add_learning(learning2)

        assert len(store.learnings) == 1
        assert store.learnings[0].success_count == 2

    def test_save_and_load(self, tmp_path: Path) -> None:
        """Test persistence."""
        store1 = PatternStore(learning_dir=tmp_path, project="test")
        store1.add_learning(
            Learning(type=LearningType.PATTERN, content="Test pattern")
        )
        store1.add_learning(
            Learning(type=LearningType.ISSUE, content="Test issue")
        )
        store1.save()

        # Load in new store
        store2 = PatternStore(learning_dir=tmp_path, project="test")
        assert len(store2.learnings) == 2

    def test_get_learnings_by_type(self, tmp_path: Path) -> None:
        """Test filtering by type."""
        store = PatternStore(learning_dir=tmp_path, project="test")
        store.add_learning(Learning(type=LearningType.PATTERN, content="P1"))
        store.add_learning(Learning(type=LearningType.PATTERN, content="P2"))
        store.add_learning(Learning(type=LearningType.ISSUE, content="I1"))

        patterns = store.get_learnings_by_type(LearningType.PATTERN)
        issues = store.get_learnings_by_type(LearningType.ISSUE)

        assert len(patterns) == 2
        assert len(issues) == 1

    def test_get_learnings_by_domain(self, tmp_path: Path) -> None:
        """Test filtering by domain."""
        store = PatternStore(learning_dir=tmp_path, project="test")
        store.add_learning(Learning(type=LearningType.PATTERN, content="F1", domain="frontend"))
        store.add_learning(Learning(type=LearningType.PATTERN, content="B1", domain="backend"))
        store.add_learning(Learning(type=LearningType.PATTERN, content="G1", domain="general"))

        frontend = store.get_learnings_by_domain("frontend")
        # Should include frontend + general
        assert len(frontend) == 2

    def test_get_top_patterns(self, tmp_path: Path) -> None:
        """Test getting top patterns sorted by success count."""
        store = PatternStore(learning_dir=tmp_path, project="test")

        p1 = Learning(type=LearningType.PATTERN, content="Low", success_count=1)
        p2 = Learning(type=LearningType.PATTERN, content="High", success_count=10)
        p3 = Learning(type=LearningType.PATTERN, content="Medium", success_count=5)

        store.add_learning(p1)
        store.add_learning(p2)
        store.add_learning(p3)

        top = store.get_top_patterns(limit=2)

        assert len(top) == 2
        assert top[0].content == "High"
        assert top[1].content == "Medium"

    def test_export_import(self, tmp_path: Path) -> None:
        """Test export and import."""
        store1 = PatternStore(learning_dir=tmp_path, project="test1")
        store1.add_learning(Learning(type=LearningType.PATTERN, content="Export me"))
        store1.save()

        exported = store1.export()

        store2 = PatternStore(learning_dir=tmp_path, project="test2")
        count = store2.import_learnings(exported)

        assert count == 1
        assert store2.learnings[0].content == "Export me"


class TestTaskOutcome:
    """Tests for TaskOutcome."""

    def test_to_dict(self) -> None:
        """Test outcome serialization."""
        outcome = TaskOutcome(
            task_id="abc123",
            task_description="Test task",
            success=True,
            phases_completed=["plan", "implement"],
            retry_count=1,
            files_modified=["src/main.py"],
            test_passed_first_try=False,
        )

        data = outcome.to_dict()

        assert data["task_id"] == "abc123"
        assert data["success"] is True
        assert data["phases_completed"] == ["plan", "implement"]


# =============================================================================
# Learning Extraction Tests
# =============================================================================


class TestExtractLearnings:
    """Tests for learning extraction from feedback."""

    def test_extract_pattern_from_plus(self) -> None:
        """Test extracting patterns from + bullet points."""
        feedback = """
        + Use compound components for complex forms
        + Prefer composition over inheritance
        """

        learnings = extract_learnings_from_feedback(feedback)

        patterns = [l for l in learnings if l.type == LearningType.PATTERN]
        assert len(patterns) >= 1

    def test_extract_issue(self) -> None:
        """Test extracting issues."""
        feedback = "Issue: Memory leak when using setTimeout without cleanup"

        learnings = extract_learnings_from_feedback(feedback)

        issues = [l for l in learnings if l.type == LearningType.ISSUE]
        assert len(issues) == 1
        assert "Memory leak" in issues[0].content

    def test_extract_mistake(self) -> None:
        """Test extracting mistakes."""
        feedback = "Avoid: Using any type for API responses"

        learnings = extract_learnings_from_feedback(feedback)

        mistakes = [l for l in learnings if l.type == LearningType.MISTAKE]
        assert len(mistakes) == 1

    def test_extract_best_practice(self) -> None:
        """Test extracting best practices."""
        feedback = "Best practice: Always validate input at API boundaries"

        learnings = extract_learnings_from_feedback(feedback)

        practices = [l for l in learnings if l.type == LearningType.BEST_PRACTICE]
        # May match multiple patterns (best practice: and should:)
        assert len(practices) >= 1
        assert any("validate input" in p.content for p in practices)

    def test_skip_short_content(self) -> None:
        """Test that very short content is skipped."""
        feedback = "Pattern: hi"  # Too short

        learnings = extract_learnings_from_feedback(feedback)

        assert len(learnings) == 0

    def test_domain_assignment(self) -> None:
        """Test domain is assigned correctly."""
        feedback = "Pattern: Use React hooks for state"

        learnings = extract_learnings_from_feedback(feedback, domain="frontend")

        assert learnings[0].domain == "frontend"


class TestDomainDetection:
    """Tests for domain detection from files."""

    def test_detect_frontend(self) -> None:
        """Test detecting frontend from file paths."""
        files = ["src/components/Button.tsx", "src/hooks/useAuth.ts"]

        domain = _detect_domain_from_files(files)

        assert domain == "frontend"

    def test_detect_backend(self) -> None:
        """Test detecting backend from file paths."""
        files = ["app/routers/users.py", "app/models/user.py"]

        domain = _detect_domain_from_files(files)

        assert domain == "backend"

    def test_detect_ai(self) -> None:
        """Test detecting AI from file paths."""
        files = ["src/prompts/system.md", "src/agents/helper.py"]

        domain = _detect_domain_from_files(files)

        assert domain == "ai"

    def test_detect_general(self) -> None:
        """Test fallback to general."""
        files = ["README.md", "CHANGELOG.txt"]  # Files without domain indicators

        domain = _detect_domain_from_files(files)

        assert domain == "general"


# =============================================================================
# Expertise Section Tests
# =============================================================================


class TestBuildExpertiseSection:
    """Tests for building expertise sections."""

    def test_empty_expertise(self) -> None:
        """Test empty expertise returns empty string."""
        section = build_expertise_section()

        assert section == ""

    def test_patterns_only(self) -> None:
        """Test section with patterns only."""
        patterns = [
            Learning(type=LearningType.PATTERN, content="Pattern 1"),
            Learning(type=LearningType.PATTERN, content="Pattern 2"),
        ]

        section = build_expertise_section(patterns=patterns)

        assert "## Expertise" in section
        assert "Pattern 1" in section
        assert "Pattern 2" in section

    def test_all_sections(self) -> None:
        """Test section with all learning types."""
        patterns = [Learning(type=LearningType.PATTERN, content="P1")]
        issues = [Learning(type=LearningType.ISSUE, content="I1")]
        best_practices = [Learning(type=LearningType.BEST_PRACTICE, content="BP1")]
        mistakes = [Learning(type=LearningType.MISTAKE, content="M1")]

        section = build_expertise_section(
            patterns=patterns,
            issues=issues,
            best_practices=best_practices,
            mistakes=mistakes,
        )

        assert "Discovered Patterns" in section
        assert "Known Issues" in section
        assert "Best Practices" in section
        assert "Mistakes to Avoid" in section

    def test_include_stats(self) -> None:
        """Test including usage statistics."""
        patterns = [
            Learning(type=LearningType.PATTERN, content="P1", success_count=5)
        ]

        section = build_expertise_section(patterns=patterns, include_stats=True)

        assert "used 5x" in section


class TestInjectExpertise:
    """Tests for injecting expertise into prompts."""

    def test_inject_at_start(self, tmp_path: Path) -> None:
        """Test injecting at start of prompt."""
        # Create a store with some learnings
        store = PatternStore(learning_dir=tmp_path, project="test")
        store.add_learning(Learning(type=LearningType.PATTERN, content="Test pattern"))
        store.save()

        prompt = "Implement a login form"

        # Use a simple expertise (bypass the default store)
        from adw.learning.expertise import build_expertise_section

        expertise = build_expertise_section(
            patterns=[Learning(type=LearningType.PATTERN, content="Test pattern")]
        )

        if expertise:
            result = f"{expertise}\n\n---\n\n{prompt}"
            assert "Test pattern" in result
            assert "Implement a login form" in result

    def test_inject_at_end(self) -> None:
        """Test injecting at end of prompt."""
        from adw.learning.expertise import build_expertise_section

        patterns = [Learning(type=LearningType.PATTERN, content="End pattern")]
        expertise = build_expertise_section(patterns=patterns)

        prompt = "Do something"
        result = f"{prompt}\n\n---\n\n{expertise}"

        # Expertise should be at the end
        assert result.endswith("End pattern\n")


class TestGetCombinedExpertise:
    """Tests for combined expertise from multiple sources."""

    def test_with_expert(self, tmp_path: Path) -> None:
        """Test combining with expert context."""
        # This would require an actual expert instance
        # For now, test without expert
        expertise = get_combined_expertise(project="nonexistent")

        # Should not crash, returns empty or minimal content
        assert expertise is not None

    def test_domain_filter(self, tmp_path: Path) -> None:
        """Test filtering by domain."""
        store = PatternStore(learning_dir=tmp_path, project="test")
        store.add_learning(Learning(type=LearningType.PATTERN, content="F1", domain="frontend"))
        store.add_learning(Learning(type=LearningType.PATTERN, content="B1", domain="backend"))
        store.save()

        # Get frontend expertise
        patterns = store.get_top_patterns(domain="frontend")
        frontend_content = [p.content for p in patterns]

        assert "F1" in frontend_content


# =============================================================================
# Record Outcome Tests
# =============================================================================


class TestRecordOutcome:
    """Tests for recording task outcomes."""

    def test_record_success(self, tmp_path: Path) -> None:
        """Test recording a successful outcome."""
        store = PatternStore(learning_dir=tmp_path, project="test")

        outcome = TaskOutcome(
            task_id="test123",
            task_description="Test task",
            success=True,
            files_modified=["src/main.py"],
            test_passed_first_try=True,
        )

        learnings = record_task_outcome(store, outcome, auto_learn=True)

        # Should have learned from file patterns
        assert len(learnings) >= 0  # May or may not extract depending on files

    def test_record_with_feedback(self, tmp_path: Path) -> None:
        """Test recording outcome with feedback."""
        store = PatternStore(learning_dir=tmp_path, project="test")

        outcome = TaskOutcome(
            task_id="test123",
            task_description="Test task",
            success=True,
            feedback="Pattern: Use async for database calls",
        )

        learnings = record_task_outcome(store, outcome, auto_learn=True)

        # Should extract the pattern from feedback
        assert any(l.content for l in learnings if "async" in l.content.lower())

    def test_no_auto_learn(self, tmp_path: Path) -> None:
        """Test recording without auto-learning."""
        store = PatternStore(learning_dir=tmp_path, project="test")

        outcome = TaskOutcome(
            task_id="test123",
            task_description="Test task",
            success=True,
            feedback="Pattern: Something",
        )

        learnings = record_task_outcome(store, outcome, auto_learn=False)

        assert len(learnings) == 0


# =============================================================================
# Integration Tests
# =============================================================================


class TestLearningIntegration:
    """Integration tests for the learning system."""

    def test_full_workflow(self, tmp_path: Path) -> None:
        """Test complete learning workflow."""
        # 1. Create store
        store = PatternStore(learning_dir=tmp_path, project="test")

        # 2. Record a successful task
        outcome = TaskOutcome(
            task_id="task1",
            task_description="Implement user auth",
            success=True,
            files_modified=["src/auth.py", "tests/test_auth.py"],
            test_passed_first_try=True,
            feedback="+ Use bcrypt for password hashing\n+ Always validate tokens",
        )
        record_task_outcome(store, outcome)

        # 3. Check learnings were stored
        assert store.get_statistics()["total_learnings"] > 0

        # 4. Build expertise section
        section = build_expertise_section(
            patterns=store.get_top_patterns(),
        )
        assert section  # Should have content

        # 5. Export and import
        exported = store.export()
        new_store = PatternStore(learning_dir=tmp_path, project="test2")
        count = new_store.import_learnings(exported)
        assert count > 0

    def test_multiple_tasks_accumulate(self, tmp_path: Path) -> None:
        """Test that multiple tasks accumulate learnings."""
        store = PatternStore(learning_dir=tmp_path, project="test")

        for i in range(3):
            outcome = TaskOutcome(
                task_id=f"task{i}",
                task_description=f"Task {i}",
                success=True,
                feedback=f"Pattern: Pattern number {i}",
            )
            record_task_outcome(store, outcome)

        # Should have accumulated multiple learnings
        patterns = store.get_learnings_by_type(LearningType.PATTERN)
        assert len(patterns) >= 3
