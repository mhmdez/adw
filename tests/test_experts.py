"""Tests for expert system module (Phase 5).

Tests expert base class, domain experts, knowledge persistence,
and expert auto-selection.
"""

from __future__ import annotations

import json
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from adw.experts import (
    AIExpert,
    BackendExpert,
    Expert,
    ExpertKnowledge,
    ExpertMatch,
    FrontendExpert,
    get_expert,
    list_experts,
    register_expert,
    select_experts,
)
from adw.experts.selector import (
    DOMAIN_KEYWORDS,
    FILE_PATTERNS,
    detect_domain_from_path,
    get_relevant_experts_for_files,
)


# =============================================================================
# ExpertKnowledge Tests
# =============================================================================


class TestExpertKnowledge:
    """Tests for ExpertKnowledge dataclass."""

    def test_default_values(self) -> None:
        """Test default knowledge values."""
        knowledge = ExpertKnowledge()

        assert knowledge.patterns == []
        assert knowledge.best_practices == []
        assert knowledge.known_issues == {}
        assert knowledge.learnings == []
        assert knowledge.task_count == 0
        assert knowledge.success_rate == 0.0
        assert knowledge.last_updated is None

    def test_add_pattern(self) -> None:
        """Test adding patterns."""
        knowledge = ExpertKnowledge()

        knowledge.add_pattern("Use dependency injection")
        assert "Use dependency injection" in knowledge.patterns
        assert knowledge.last_updated is not None

        # Adding same pattern should not duplicate
        knowledge.add_pattern("Use dependency injection")
        assert len(knowledge.patterns) == 1

    def test_add_best_practice(self) -> None:
        """Test adding best practices."""
        knowledge = ExpertKnowledge()

        knowledge.add_best_practice("Write tests first")
        assert "Write tests first" in knowledge.best_practices

    def test_add_issue(self) -> None:
        """Test adding known issues."""
        knowledge = ExpertKnowledge()

        knowledge.add_issue("Memory leak in X", "Use WeakRef instead")
        assert knowledge.known_issues["Memory leak in X"] == "Use WeakRef instead"

    def test_add_learning(self) -> None:
        """Test adding learnings."""
        knowledge = ExpertKnowledge()

        knowledge.add_learning("Async is faster for I/O")
        assert "Async is faster for I/O" in knowledge.learnings

    def test_record_task_success(self) -> None:
        """Test recording successful tasks."""
        knowledge = ExpertKnowledge()

        knowledge.record_task(success=True)
        assert knowledge.task_count == 1
        assert knowledge.success_rate == 1.0

        knowledge.record_task(success=True)
        assert knowledge.task_count == 2
        assert knowledge.success_rate == 1.0

    def test_record_task_failure(self) -> None:
        """Test recording failed tasks."""
        knowledge = ExpertKnowledge()

        knowledge.record_task(success=True)
        knowledge.record_task(success=False)

        assert knowledge.task_count == 2
        assert knowledge.success_rate == 0.5

    def test_to_dict(self) -> None:
        """Test serialization to dict."""
        knowledge = ExpertKnowledge(
            patterns=["Pattern 1"],
            best_practices=["Practice 1"],
            known_issues={"Issue": "Fix"},
            learnings=["Learning 1"],
            task_count=10,
            success_rate=0.9,
        )

        data = knowledge.to_dict()

        assert data["patterns"] == ["Pattern 1"]
        assert data["best_practices"] == ["Practice 1"]
        assert data["known_issues"] == {"Issue": "Fix"}
        assert data["task_count"] == 10
        assert data["success_rate"] == 0.9

    def test_from_dict(self) -> None:
        """Test deserialization from dict."""
        data = {
            "patterns": ["Pattern 1"],
            "best_practices": ["Practice 1"],
            "known_issues": {"Issue": "Fix"},
            "learnings": ["Learning 1"],
            "task_count": 5,
            "success_rate": 0.8,
            "last_updated": "2026-01-15T10:30:00",
        }

        knowledge = ExpertKnowledge.from_dict(data)

        assert knowledge.patterns == ["Pattern 1"]
        assert knowledge.task_count == 5
        assert knowledge.last_updated is not None
        assert knowledge.last_updated.year == 2026

    def test_from_dict_handles_invalid_date(self) -> None:
        """Test from_dict handles invalid date gracefully."""
        data = {"last_updated": "invalid-date"}

        knowledge = ExpertKnowledge.from_dict(data)

        assert knowledge.last_updated is None


# =============================================================================
# Expert Base Class Tests
# =============================================================================


class TestFrontendExpert:
    """Tests for FrontendExpert."""

    def test_domain_and_specializations(self) -> None:
        """Test expert domain and specializations."""
        expert = FrontendExpert()

        assert expert.domain == "frontend"
        assert "React" in expert.specializations
        assert "Vue.js" in expert.specializations
        assert "CSS" in expert.specializations

    def test_plan_react_task(self) -> None:
        """Test planning a React task."""
        expert = FrontendExpert()

        plan = expert.plan("Create a React login component")

        assert "React" in plan
        assert "Component" in plan
        assert "Accessibility" in plan or "accessibility" in plan

    def test_plan_vue_task(self) -> None:
        """Test planning a Vue task."""
        expert = FrontendExpert()

        plan = expert.plan("Create a Vue dashboard")

        assert "Vue" in plan
        assert "Composition API" in plan or "composition" in plan.lower()

    def test_get_context(self) -> None:
        """Test getting expertise context."""
        expert = FrontendExpert()

        context = expert.get_context()

        assert "Frontend Expertise" in context
        assert "Patterns" in context
        assert "Best Practices" in context

    def test_build_guidance(self) -> None:
        """Test build guidance generation."""
        expert = FrontendExpert()

        guidance = expert.build("Create a modal component")

        assert "Implementation Guidance" in guidance
        assert "Accessibility" in guidance

    def test_knowledge_persistence(self, tmp_path: Path) -> None:
        """Test knowledge persistence to disk."""
        expert = FrontendExpert(experts_dir=tmp_path)

        expert.knowledge.add_pattern("Custom pattern")
        expert.save_knowledge()

        # Create new expert to load from disk
        expert2 = FrontendExpert(experts_dir=tmp_path)
        assert "Custom pattern" in expert2.knowledge.patterns


class TestBackendExpert:
    """Tests for BackendExpert."""

    def test_domain_and_specializations(self) -> None:
        """Test expert domain and specializations."""
        expert = BackendExpert()

        assert expert.domain == "backend"
        assert "FastAPI" in expert.specializations
        assert "PostgreSQL" in expert.specializations

    def test_plan_fastapi_task(self) -> None:
        """Test planning a FastAPI task."""
        expert = BackendExpert()

        plan = expert.plan("Create a REST API endpoint")

        assert "API" in plan or "Endpoint" in plan
        assert "FastAPI" in plan

    def test_plan_django_task(self) -> None:
        """Test planning a Django task."""
        expert = BackendExpert()

        plan = expert.plan("Create a Django view for user management")

        assert "Django" in plan

    def test_get_context(self) -> None:
        """Test getting expertise context."""
        expert = BackendExpert()

        context = expert.get_context()

        assert "Backend Expertise" in context
        assert "Pydantic" in context or "validation" in context.lower()

    def test_improve_from_feedback(self, tmp_path: Path) -> None:
        """Test learning from feedback."""
        expert = BackendExpert(experts_dir=tmp_path)

        expert.improve(
            "- Always use async for database operations\n- Pydantic v2 is faster",
            success=True,
        )

        assert "Always use async for database operations" in expert.knowledge.learnings
        assert expert.knowledge.task_count == 1
        assert expert.knowledge.success_rate == 1.0


class TestAIExpert:
    """Tests for AIExpert."""

    def test_domain_and_specializations(self) -> None:
        """Test expert domain and specializations."""
        expert = AIExpert()

        assert expert.domain == "ai"
        assert "LLM integration" in expert.specializations
        assert "prompt engineering" in expert.specializations

    def test_plan_agent_task(self) -> None:
        """Test planning an agent task."""
        expert = AIExpert()

        plan = expert.plan("Build an AI agent for customer support")

        assert "Agent" in plan or "agent" in plan
        assert "Tool" in plan or "tool" in plan.lower()

    def test_plan_rag_task(self) -> None:
        """Test planning a RAG task."""
        expert = AIExpert()

        plan = expert.plan("Implement RAG for document search")

        assert "RAG" in plan
        assert "retriev" in plan.lower()

    def test_plan_chatbot_task(self) -> None:
        """Test planning a chatbot task."""
        expert = AIExpert()

        plan = expert.plan("Create a chatbot for FAQ")

        assert "Chat" in plan or "chat" in plan

    def test_get_context(self) -> None:
        """Test getting expertise context."""
        expert = AIExpert()

        context = expert.get_context()

        assert "AI/LLM Expertise" in context
        assert "prompt" in context.lower()


# =============================================================================
# Expert Registry Tests
# =============================================================================


class TestExpertRegistry:
    """Tests for expert registration and lookup."""

    def test_get_frontend_expert(self) -> None:
        """Test getting frontend expert by domain."""
        expert = get_expert("frontend")

        assert expert is not None
        assert isinstance(expert, FrontendExpert)

    def test_get_backend_expert(self) -> None:
        """Test getting backend expert by domain."""
        expert = get_expert("backend")

        assert expert is not None
        assert isinstance(expert, BackendExpert)

    def test_get_ai_expert(self) -> None:
        """Test getting AI expert by domain."""
        expert = get_expert("ai")

        assert expert is not None
        assert isinstance(expert, AIExpert)

    def test_get_nonexistent_expert(self) -> None:
        """Test getting non-existent expert returns None."""
        expert = get_expert("nonexistent")

        assert expert is None

    def test_list_experts(self) -> None:
        """Test listing all registered experts."""
        experts = list_experts()

        assert len(experts) >= 3  # At least frontend, backend, ai
        domains = [e["domain"] for e in experts]
        assert "frontend" in domains
        assert "backend" in domains
        assert "ai" in domains


# =============================================================================
# Expert Selection Tests
# =============================================================================


class TestExpertSelection:
    """Tests for expert auto-selection."""

    def test_select_frontend_from_keywords(self) -> None:
        """Test selecting frontend expert from keywords."""
        matches = select_experts("Create a React component with CSS styling")

        assert len(matches) > 0
        assert matches[0].expert.domain == "frontend"
        assert matches[0].score > 0.5

    def test_select_backend_from_keywords(self) -> None:
        """Test selecting backend expert from keywords."""
        matches = select_experts("Create a FastAPI endpoint with PostgreSQL")

        assert len(matches) > 0
        assert matches[0].expert.domain == "backend"

    def test_select_ai_from_keywords(self) -> None:
        """Test selecting AI expert from keywords."""
        matches = select_experts("Build a Claude-powered agent with tool use")

        assert len(matches) > 0
        assert matches[0].expert.domain == "ai"

    def test_select_from_files(self) -> None:
        """Test selecting expert based on files."""
        files = [
            "src/components/Button.tsx",
            "src/components/Modal.vue",
            "styles/main.css",
        ]

        matches = select_experts("Update the code", files=files)

        assert len(matches) > 0
        assert matches[0].expert.domain == "frontend"

    def test_select_backend_from_files(self) -> None:
        """Test selecting backend expert from file patterns."""
        files = [
            "app/routers/users.py",
            "app/models/user.py",
            "app/schemas/user.py",
        ]

        matches = select_experts("Update the code", files=files)

        assert len(matches) > 0
        assert matches[0].expert.domain == "backend"

    def test_select_multiple_experts(self) -> None:
        """Test selecting multiple experts for full-stack task."""
        matches = select_experts(
            "Create a React frontend with FastAPI backend",
            max_experts=3,
        )

        domains = [m.expert.domain for m in matches]
        assert "frontend" in domains
        assert "backend" in domains

    def test_threshold_filtering(self) -> None:
        """Test that low-scoring experts are filtered."""
        matches = select_experts("Hello world", threshold=0.9)

        # Generic task shouldn't match with high threshold
        assert len(matches) == 0

    def test_expert_match_reasons(self) -> None:
        """Test that match includes reasons."""
        matches = select_experts("Create a Vue component")

        assert len(matches) > 0
        assert len(matches[0].reasons) > 0
        assert any("vue" in r.lower() for r in matches[0].reasons)


class TestDomainDetection:
    """Tests for domain detection from paths."""

    def test_detect_frontend_from_tsx(self) -> None:
        """Test detecting frontend from .tsx file."""
        domain = detect_domain_from_path("src/components/Button.tsx")

        assert domain == "frontend"

    def test_detect_frontend_from_vue(self) -> None:
        """Test detecting frontend from .vue file."""
        domain = detect_domain_from_path("src/components/Modal.vue")

        assert domain == "frontend"

    def test_detect_backend_from_routers(self) -> None:
        """Test detecting backend from routers path."""
        domain = detect_domain_from_path("app/routers/users.py")

        assert domain == "backend"

    def test_detect_ai_from_prompts(self) -> None:
        """Test detecting AI from prompts path."""
        domain = detect_domain_from_path("src/prompts/system.md")

        assert domain == "ai"

    def test_no_detection_for_generic(self) -> None:
        """Test no detection for generic files."""
        domain = detect_domain_from_path("README.md")

        assert domain is None


class TestGetRelevantExperts:
    """Tests for getting experts from file list."""

    def test_get_experts_from_frontend_files(self) -> None:
        """Test getting experts from frontend files."""
        files = [
            "src/components/Button.tsx",
            "src/hooks/useAuth.ts",
        ]

        matches = get_relevant_experts_for_files(files)

        assert len(matches) > 0
        assert matches[0].expert.domain == "frontend"

    def test_get_experts_from_mixed_files(self) -> None:
        """Test getting experts from mixed files."""
        files = [
            "src/components/Button.tsx",
            "app/routers/api.py",
        ]

        matches = get_relevant_experts_for_files(files, threshold=0.2)

        domains = [m.expert.domain for m in matches]
        # Should detect both
        assert len(domains) >= 1


# =============================================================================
# Expert Stats Tests
# =============================================================================


class TestExpertStats:
    """Tests for expert statistics."""

    def test_get_stats(self, tmp_path: Path) -> None:
        """Test getting expert statistics."""
        expert = FrontendExpert(experts_dir=tmp_path)

        # Add some activity
        expert.knowledge.add_pattern("Test pattern")
        expert.knowledge.record_task(True)
        expert.knowledge.record_task(True)
        expert.knowledge.record_task(False)

        stats = expert.get_stats()

        assert stats["domain"] == "frontend"
        assert stats["task_count"] == 3
        assert stats["success_rate"] == "66.7%"
        assert stats["patterns_count"] == 1


# =============================================================================
# Integration Tests
# =============================================================================


class TestExpertIntegration:
    """Integration tests for the expert system."""

    def test_full_workflow(self, tmp_path: Path) -> None:
        """Test complete expert workflow."""
        # 1. Select expert based on task
        matches = select_experts("Build a React login form")
        assert len(matches) > 0

        # 2. Get the expert
        expert = matches[0].expert

        # Use custom path for test isolation
        expert = FrontendExpert(experts_dir=tmp_path)

        # 3. Generate a plan
        plan = expert.plan("Build a React login form")
        assert "React" in plan

        # 4. Get context for prompts
        context = expert.get_context()
        assert "Expertise" in context

        # 5. Learn from outcome
        expert.improve("- Form validation was tricky", success=True)
        assert expert.knowledge.task_count == 1

        # 6. Save and reload
        expert.save_knowledge()

        expert2 = FrontendExpert(experts_dir=tmp_path)
        assert expert2.knowledge.task_count == 1
        assert "Form validation was tricky" in expert2.knowledge.learnings

    def test_multi_expert_collaboration(self) -> None:
        """Test using multiple experts together."""
        task = "Create a full-stack feature with React frontend and FastAPI backend"

        matches = select_experts(task, max_experts=3)

        # Should get both frontend and backend
        domains = {m.expert.domain for m in matches}
        assert "frontend" in domains
        assert "backend" in domains

        # Get combined context
        combined_context = ""
        for match in matches:
            combined_context += match.expert.get_context() + "\n\n"

        assert "Frontend" in combined_context
        assert "Backend" in combined_context
