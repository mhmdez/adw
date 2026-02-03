"""Base expert class and knowledge persistence.

Experts are domain-specific agents that accumulate knowledge over time.
Knowledge is stored in ~/.adw/experts/<name>/knowledge.json.
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Default path for expert knowledge storage
DEFAULT_EXPERTS_DIR = Path.home() / ".adw" / "experts"

# Registry of available experts
_expert_registry: dict[str, type[Expert]] = {}


@dataclass
class ExpertKnowledge:
    """Accumulated knowledge for an expert.

    Attributes:
        patterns: Discovered code patterns that work well.
        best_practices: Proven approaches and conventions.
        known_issues: Problems and their workarounds.
        learnings: Insights discovered from real usage.
        last_updated: Timestamp of last knowledge update.
        task_count: Number of tasks this expert has handled.
        success_rate: Percentage of tasks completed successfully.
    """

    patterns: list[str] = field(default_factory=list)
    best_practices: list[str] = field(default_factory=list)
    known_issues: dict[str, str] = field(default_factory=dict)  # issue -> workaround
    learnings: list[str] = field(default_factory=list)
    last_updated: datetime | None = None
    task_count: int = 0
    success_rate: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "patterns": self.patterns,
            "best_practices": self.best_practices,
            "known_issues": self.known_issues,
            "learnings": self.learnings,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
            "task_count": self.task_count,
            "success_rate": self.success_rate,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExpertKnowledge:
        """Create from dictionary."""
        last_updated = None
        if data.get("last_updated"):
            try:
                last_updated = datetime.fromisoformat(data["last_updated"])
            except (ValueError, TypeError):
                pass

        return cls(
            patterns=data.get("patterns", []),
            best_practices=data.get("best_practices", []),
            known_issues=data.get("known_issues", {}),
            learnings=data.get("learnings", []),
            last_updated=last_updated,
            task_count=data.get("task_count", 0),
            success_rate=data.get("success_rate", 0.0),
        )

    def add_pattern(self, pattern: str) -> None:
        """Add a new pattern if not already known."""
        if pattern and pattern not in self.patterns:
            self.patterns.append(pattern)
            self.last_updated = datetime.now()

    def add_best_practice(self, practice: str) -> None:
        """Add a new best practice if not already known."""
        if practice and practice not in self.best_practices:
            self.best_practices.append(practice)
            self.last_updated = datetime.now()

    def add_issue(self, issue: str, workaround: str) -> None:
        """Add a known issue and its workaround."""
        if issue:
            self.known_issues[issue] = workaround
            self.last_updated = datetime.now()

    def add_learning(self, learning: str) -> None:
        """Add a new learning if not already known."""
        if learning and learning not in self.learnings:
            self.learnings.append(learning)
            self.last_updated = datetime.now()

    def record_task(self, success: bool) -> None:
        """Record a completed task."""
        self.task_count += 1
        # Update running success rate
        old_successes = int(self.success_rate * (self.task_count - 1))
        new_successes = old_successes + (1 if success else 0)
        self.success_rate = new_successes / self.task_count
        self.last_updated = datetime.now()


class Expert(ABC):
    """Base class for domain-specific experts.

    An expert has specialized knowledge in a particular domain and can:
    - Plan tasks using domain expertise
    - Build/implement solutions with best practices
    - Learn from outcomes to improve over time

    Subclasses must implement:
    - domain: The area of expertise (e.g., "frontend", "backend")
    - specializations: Specific technologies (e.g., ["React", "Vue"])
    - plan(): Create a specialized plan for a task
    - get_context(): Get context string for prompts
    """

    # Class-level defaults (override in subclasses)
    domain: str = "general"
    specializations: list[str] = []
    description: str = "General-purpose expert"

    def __init__(self, experts_dir: Path | None = None):
        """Initialize expert with knowledge storage path.

        Args:
            experts_dir: Directory for storing expert knowledge.
                        Defaults to ~/.adw/experts/
        """
        self._experts_dir = experts_dir or DEFAULT_EXPERTS_DIR
        self._knowledge_path = self._experts_dir / self.domain / "knowledge.json"
        self._knowledge: ExpertKnowledge | None = None

    @property
    def knowledge(self) -> ExpertKnowledge:
        """Get or load expert knowledge."""
        if self._knowledge is None:
            self._knowledge = self._load_knowledge()
        return self._knowledge

    def _load_knowledge(self) -> ExpertKnowledge:
        """Load knowledge from persistent storage."""
        if self._knowledge_path.exists():
            try:
                data = json.loads(self._knowledge_path.read_text())
                return ExpertKnowledge.from_dict(data)
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Failed to load {self.domain} knowledge: {e}")

        return ExpertKnowledge()

    def save_knowledge(self) -> None:
        """Persist knowledge to storage."""
        self._knowledge_path.parent.mkdir(parents=True, exist_ok=True)
        self._knowledge_path.write_text(json.dumps(self.knowledge.to_dict(), indent=2))
        logger.debug(f"Saved {self.domain} expert knowledge")

    @abstractmethod
    def plan(self, task: str, context: dict[str, Any] | None = None) -> str:
        """Create a specialized plan for a task.

        Args:
            task: Task description.
            context: Additional context (files, project info, etc.)

        Returns:
            Markdown-formatted plan with domain expertise.
        """
        pass

    @abstractmethod
    def get_context(self) -> str:
        """Get expertise context for prompts.

        Returns:
            Markdown-formatted expertise section to inject into prompts.
        """
        pass

    def build(self, spec: str, context: dict[str, Any] | None = None) -> str:
        """Generate implementation guidance based on a spec.

        Args:
            spec: Implementation specification.
            context: Additional context.

        Returns:
            Implementation guidance with best practices.
        """
        return f"""## Implementation Guidance ({self.domain})

Based on expertise in: {", ".join(self.specializations)}

### Approach

{spec}

### Best Practices to Apply

{self._format_best_practices()}

### Patterns to Use

{self._format_patterns()}

### Known Issues to Avoid

{self._format_known_issues()}
"""

    def improve(self, feedback: str, success: bool = True) -> None:
        """Learn from task outcome.

        Args:
            feedback: What happened during the task.
            success: Whether the task succeeded.
        """
        self.knowledge.record_task(success)

        # Extract learnings from feedback
        if feedback:
            # Simple heuristic: lines starting with "- " or "* " are likely learnings
            for line in feedback.split("\n"):
                line = line.strip()
                if line.startswith(("- ", "* ")):
                    learning = line.lstrip("-* ").strip()
                    if learning:
                        self.knowledge.add_learning(learning)

        self.save_knowledge()
        logger.info(f"{self.domain} expert updated with feedback")

    def _format_best_practices(self) -> str:
        """Format best practices as markdown list."""
        if not self.knowledge.best_practices:
            return "_No specific best practices recorded yet._"
        return "\n".join(f"- {p}" for p in self.knowledge.best_practices)

    def _format_patterns(self) -> str:
        """Format patterns as markdown list."""
        if not self.knowledge.patterns:
            return "_No specific patterns recorded yet._"
        return "\n".join(f"- {p}" for p in self.knowledge.patterns)

    def _format_known_issues(self) -> str:
        """Format known issues as markdown list."""
        if not self.knowledge.known_issues:
            return "_No known issues recorded._"
        items = []
        for issue, workaround in self.knowledge.known_issues.items():
            items.append(f"- **{issue}**: {workaround}")
        return "\n".join(items)

    def get_stats(self) -> dict[str, Any]:
        """Get expert statistics."""
        return {
            "domain": self.domain,
            "specializations": self.specializations,
            "task_count": self.knowledge.task_count,
            "success_rate": f"{self.knowledge.success_rate:.1%}",
            "patterns_count": len(self.knowledge.patterns),
            "best_practices_count": len(self.knowledge.best_practices),
            "known_issues_count": len(self.knowledge.known_issues),
            "learnings_count": len(self.knowledge.learnings),
            "last_updated": (self.knowledge.last_updated.isoformat() if self.knowledge.last_updated else None),
        }


def register_expert(expert_class: type[Expert]) -> type[Expert]:
    """Register an expert class in the global registry.

    Use as a decorator:
        @register_expert
        class MyExpert(Expert):
            domain = "my_domain"
    """
    _expert_registry[expert_class.domain] = expert_class
    return expert_class


def get_expert(domain: str, experts_dir: Path | None = None) -> Expert | None:
    """Get an expert instance by domain name.

    Args:
        domain: Expert domain (e.g., "frontend", "backend").
        experts_dir: Optional custom directory for knowledge storage.

    Returns:
        Expert instance or None if not found.
    """
    expert_class = _expert_registry.get(domain)
    if expert_class:
        return expert_class(experts_dir=experts_dir)
    return None


def list_experts() -> list[dict[str, Any]]:
    """List all registered experts with their info.

    Returns:
        List of expert info dicts with domain, specializations, description.
    """
    experts = []
    for domain, expert_class in _expert_registry.items():
        experts.append(
            {
                "domain": domain,
                "specializations": expert_class.specializations,
                "description": expert_class.description,
            }
        )
    return experts
