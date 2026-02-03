"""Pattern learning and storage for self-improving agents.

Tracks successful patterns, discovered issues, and learnings from task execution.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Default path for learning storage
DEFAULT_LEARNING_DIR = Path.home() / ".adw" / "learning"


class LearningType(Enum):
    """Types of learnings that can be recorded."""

    PATTERN = "pattern"  # Successful code patterns
    ISSUE = "issue"  # Problems and workarounds
    BEST_PRACTICE = "best_practice"  # Proven approaches
    MISTAKE = "mistake"  # Common errors to avoid


@dataclass
class Learning:
    """A single learning record.

    Attributes:
        type: Type of learning (pattern, issue, best_practice, mistake).
        content: The actual learning content.
        context: Additional context (task description, files, etc.).
        project: Project this was learned from (or "global").
        domain: Expert domain this applies to (frontend, backend, ai, general).
        success_count: How often this pattern led to success.
        created_at: When this was first learned.
        last_used: When this was last applied.
        source_task_id: The task that generated this learning.
    """

    type: LearningType
    content: str
    context: str = ""
    project: str = "global"
    domain: str = "general"
    success_count: int = 1
    created_at: datetime = field(default_factory=datetime.now)
    last_used: datetime | None = None
    source_task_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "type": self.type.value,
            "content": self.content,
            "context": self.context,
            "project": self.project,
            "domain": self.domain,
            "success_count": self.success_count,
            "created_at": self.created_at.isoformat(),
            "last_used": self.last_used.isoformat() if self.last_used else None,
            "source_task_id": self.source_task_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Learning:
        """Create from dictionary."""
        created_at = datetime.now()
        if data.get("created_at"):
            try:
                created_at = datetime.fromisoformat(data["created_at"])
            except (ValueError, TypeError):
                pass

        last_used = None
        if data.get("last_used"):
            try:
                last_used = datetime.fromisoformat(data["last_used"])
            except (ValueError, TypeError):
                pass

        return cls(
            type=LearningType(data.get("type", "pattern")),
            content=data.get("content", ""),
            context=data.get("context", ""),
            project=data.get("project", "global"),
            domain=data.get("domain", "general"),
            success_count=data.get("success_count", 1),
            created_at=created_at,
            last_used=last_used,
            source_task_id=data.get("source_task_id"),
        )

    def mark_used(self, success: bool = True) -> None:
        """Mark this learning as used."""
        self.last_used = datetime.now()
        if success:
            self.success_count += 1


@dataclass
class TaskOutcome:
    """Outcome of a task execution.

    Attributes:
        task_id: ADW task ID.
        task_description: What the task was about.
        success: Whether the task succeeded.
        phases_completed: Which workflow phases completed.
        retry_count: Number of retries needed.
        files_modified: Files changed during the task.
        test_passed_first_try: Whether tests passed on first attempt.
        feedback: Any feedback received (review comments, etc.).
        duration_seconds: How long the task took.
    """

    task_id: str
    task_description: str
    success: bool
    phases_completed: list[str] = field(default_factory=list)
    retry_count: int = 0
    files_modified: list[str] = field(default_factory=list)
    test_passed_first_try: bool = False
    feedback: str = ""
    duration_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "task_id": self.task_id,
            "task_description": self.task_description,
            "success": self.success,
            "phases_completed": self.phases_completed,
            "retry_count": self.retry_count,
            "files_modified": self.files_modified,
            "test_passed_first_try": self.test_passed_first_try,
            "feedback": self.feedback,
            "duration_seconds": self.duration_seconds,
            "timestamp": datetime.now().isoformat(),
        }


class PatternStore:
    """Store for accumulated learnings.

    Manages persistence and retrieval of learned patterns, issues,
    and best practices. Supports project-level and global learnings.
    """

    def __init__(self, learning_dir: Path | None = None, project: str = "global"):
        """Initialize the pattern store.

        Args:
            learning_dir: Directory for storing learning data.
            project: Project identifier for project-specific learnings.
        """
        self._learning_dir = learning_dir or DEFAULT_LEARNING_DIR
        self._project = project
        self._learnings: list[Learning] = []
        self._outcomes: list[TaskOutcome] = []
        self._loaded = False

    @property
    def learnings(self) -> list[Learning]:
        """Get all learnings."""
        if not self._loaded:
            self._load()
        return self._learnings

    def _get_patterns_path(self) -> Path:
        """Get path to patterns file."""
        if self._project == "global":
            return self._learning_dir / "global" / "patterns.json"
        return self._learning_dir / self._project / "patterns.json"

    def _get_outcomes_path(self) -> Path:
        """Get path to outcomes file."""
        if self._project == "global":
            return self._learning_dir / "global" / "outcomes.jsonl"
        return self._learning_dir / self._project / "outcomes.jsonl"

    def _load(self) -> None:
        """Load learnings from storage."""
        patterns_path = self._get_patterns_path()

        if patterns_path.exists():
            try:
                data = json.loads(patterns_path.read_text())
                self._learnings = [Learning.from_dict(d) for d in data.get("learnings", [])]
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning("Failed to load patterns: %s", e)
                self._learnings = []
        else:
            self._learnings = []

        self._loaded = True

    def save(self) -> None:
        """Persist learnings to storage."""
        patterns_path = self._get_patterns_path()
        patterns_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "learnings": [item.to_dict() for item in self._learnings],
            "updated_at": datetime.now().isoformat(),
            "project": self._project,
        }

        patterns_path.write_text(json.dumps(data, indent=2))
        logger.debug("Saved %d learnings to %s", len(self._learnings), patterns_path)

    def add_learning(self, learning: Learning) -> None:
        """Add a new learning.

        Deduplicates based on content similarity.
        """
        if not self._loaded:
            self._load()

        # Check for duplicate
        for existing in self._learnings:
            if existing.type == learning.type and existing.content.lower() == learning.content.lower():
                # Update existing instead of adding duplicate
                existing.success_count += 1
                existing.last_used = datetime.now()
                return

        self._learnings.append(learning)

    def record_outcome(self, outcome: TaskOutcome) -> None:
        """Record a task outcome for analysis."""
        outcomes_path = self._get_outcomes_path()
        outcomes_path.parent.mkdir(parents=True, exist_ok=True)

        # Append to JSONL file
        with outcomes_path.open("a") as f:
            f.write(json.dumps(outcome.to_dict()) + "\n")

        self._outcomes.append(outcome)

    def get_learnings_by_type(self, learning_type: LearningType) -> list[Learning]:
        """Get learnings of a specific type."""
        return [item for item in self.learnings if item.type == learning_type]

    def get_learnings_by_domain(self, domain: str) -> list[Learning]:
        """Get learnings for a specific domain."""
        return [item for item in self.learnings if item.domain == domain or item.domain == "general"]

    def get_top_patterns(self, limit: int = 10, domain: str | None = None) -> list[Learning]:
        """Get the most successful patterns.

        Args:
            limit: Maximum patterns to return.
            domain: Filter by domain (optional).

        Returns:
            List of learnings sorted by success count.
        """
        learnings = self.learnings
        if domain:
            learnings = self.get_learnings_by_domain(domain)

        patterns = [item for item in learnings if item.type == LearningType.PATTERN]
        return sorted(patterns, key=lambda x: x.success_count, reverse=True)[:limit]

    def get_known_issues(self, domain: str | None = None) -> list[Learning]:
        """Get known issues and their workarounds.

        Args:
            domain: Filter by domain (optional).

        Returns:
            List of issue learnings.
        """
        learnings = self.learnings
        if domain:
            learnings = self.get_learnings_by_domain(domain)

        return [item for item in learnings if item.type == LearningType.ISSUE]

    def get_mistakes_to_avoid(self, domain: str | None = None) -> list[Learning]:
        """Get common mistakes to avoid.

        Args:
            domain: Filter by domain (optional).

        Returns:
            List of mistake learnings.
        """
        learnings = self.learnings
        if domain:
            learnings = self.get_learnings_by_domain(domain)

        return [item for item in learnings if item.type == LearningType.MISTAKE]

    def get_statistics(self) -> dict[str, Any]:
        """Get statistics about learnings."""
        learnings = self.learnings

        return {
            "total_learnings": len(learnings),
            "patterns": len(self.get_learnings_by_type(LearningType.PATTERN)),
            "issues": len(self.get_learnings_by_type(LearningType.ISSUE)),
            "best_practices": len(self.get_learnings_by_type(LearningType.BEST_PRACTICE)),
            "mistakes": len(self.get_learnings_by_type(LearningType.MISTAKE)),
            "domains": list(set(item.domain for item in learnings)),
        }

    def export(self) -> dict[str, Any]:
        """Export all learnings for sharing."""
        return {
            "project": self._project,
            "learnings": [item.to_dict() for item in self.learnings],
            "statistics": self.get_statistics(),
            "exported_at": datetime.now().isoformat(),
        }

    def import_learnings(self, data: dict[str, Any]) -> int:
        """Import learnings from exported data.

        Args:
            data: Exported learning data.

        Returns:
            Number of learnings imported.
        """
        imported = 0
        for learning_data in data.get("learnings", []):
            learning = Learning.from_dict(learning_data)
            self.add_learning(learning)
            imported += 1

        self.save()
        return imported


# Patterns for extracting learnings from feedback text
LEARNING_PATTERNS = {
    LearningType.PATTERN: [
        r"pattern:?\s*(.+)",
        r"approach:?\s*(.+)",
        r"worked well:?\s*(.+)",
        r"success:?\s*(.+)",
        r"\+\s*(.+)",  # + bullet points
    ],
    LearningType.ISSUE: [
        r"issue:?\s*(.+)",
        r"problem:?\s*(.+)",
        r"workaround:?\s*(.+)",
        r"fix(?:ed)?:?\s*(.+)",
    ],
    LearningType.MISTAKE: [
        r"mistake:?\s*(.+)",
        r"avoid:?\s*(.+)",
        r"don't:?\s*(.+)",
        r"never:?\s*(.+)",
        r"-\s*(.+)",  # - bullet points (often issues/mistakes)
    ],
    LearningType.BEST_PRACTICE: [
        r"best practice:?\s*(.+)",
        r"always:?\s*(.+)",
        r"recommend:?\s*(.+)",
        r"should:?\s*(.+)",
    ],
}


def extract_learnings_from_feedback(
    feedback: str,
    domain: str = "general",
    source_task_id: str | None = None,
) -> list[Learning]:
    """Extract structured learnings from feedback text.

    Parses feedback text to identify patterns, issues, and best practices.

    Args:
        feedback: Raw feedback text from task completion.
        domain: Domain this learning applies to.
        source_task_id: Task ID that generated this feedback.

    Returns:
        List of extracted Learning objects.
    """
    learnings = []

    for learning_type, patterns in LEARNING_PATTERNS.items():
        for pattern in patterns:
            matches = re.finditer(pattern, feedback, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                content = match.group(1).strip()
                # Skip very short content
                if len(content) < 10:
                    continue

                # Skip common false positives
                if content.lower() in ("none", "n/a", "nothing"):
                    continue

                learnings.append(
                    Learning(
                        type=learning_type,
                        content=content,
                        domain=domain,
                        source_task_id=source_task_id,
                    )
                )

    return learnings


def record_task_outcome(
    store: PatternStore,
    outcome: TaskOutcome,
    auto_learn: bool = True,
) -> list[Learning]:
    """Record a task outcome and optionally extract learnings.

    Args:
        store: PatternStore to record to.
        outcome: Task outcome to record.
        auto_learn: Whether to auto-extract learnings from successful tasks.

    Returns:
        List of learnings extracted (empty if auto_learn is False).
    """
    store.record_outcome(outcome)
    learnings = []

    if auto_learn and outcome.success:
        # Detect domain from files
        domain = _detect_domain_from_files(outcome.files_modified)

        # Learn from successful patterns
        if outcome.test_passed_first_try:
            # Tests passed first try - record file patterns as successful
            for file_path in outcome.files_modified[:5]:  # Limit to avoid noise
                learning = Learning(
                    type=LearningType.PATTERN,
                    content=f"File structure: {file_path}",
                    context=outcome.task_description,
                    domain=domain,
                    source_task_id=outcome.task_id,
                )
                store.add_learning(learning)
                learnings.append(learning)

        # Extract learnings from feedback
        if outcome.feedback:
            extracted = extract_learnings_from_feedback(
                outcome.feedback,
                domain=domain,
                source_task_id=outcome.task_id,
            )
            for learning in extracted:
                store.add_learning(learning)
                learnings.append(learning)

    store.save()
    return learnings


def _detect_domain_from_files(files: list[str]) -> str:
    """Detect domain from file list."""
    # Frontend indicators
    frontend_patterns = [".tsx", ".jsx", ".vue", ".css", ".scss", "component", "hook"]
    # Backend indicators
    backend_patterns = ["router", "endpoint", "api", "model", "schema", ".py"]
    # AI indicators
    ai_patterns = ["prompt", "agent", "llm", "embed", "rag"]

    frontend_score = sum(1 for f in files for p in frontend_patterns if p in f.lower())
    backend_score = sum(1 for f in files for p in backend_patterns if p in f.lower())
    ai_score = sum(1 for f in files for p in ai_patterns if p in f.lower())

    if ai_score > frontend_score and ai_score > backend_score:
        return "ai"
    if frontend_score > backend_score:
        return "frontend"
    if backend_score > 0:
        return "backend"

    return "general"


# Global store instance
_default_store: PatternStore | None = None


def get_default_pattern_store(project: str | None = None) -> PatternStore:
    """Get the default pattern store.

    Args:
        project: Project name (uses current git repo name if None).

    Returns:
        PatternStore instance.
    """
    global _default_store

    if project is None:
        # Try to detect project from git
        import subprocess

        try:
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                project = Path(result.stdout.strip()).name
        except Exception:
            pass

    project = project or "global"

    if _default_store is None or _default_store._project != project:
        _default_store = PatternStore(project=project)

    return _default_store
