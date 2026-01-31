"""Task phase and workflow models."""

from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime


class TaskPhase(str, Enum):
    """Phases a task goes through in ADW workflow."""
    
    IDEA = "idea"
    DISCUSSING = "discussing"
    SPEC_DRAFT = "spec_draft"
    SPEC_REVIEW = "spec_review"
    SPEC_APPROVED = "spec_approved"
    IMPLEMENTING = "implementing"
    BLOCKED = "blocked"
    IMPLEMENTED = "implemented"
    VERIFYING = "verifying"
    VERIFICATION_FAILED = "verification_failed"
    DONE = "done"
    ABANDONED = "abandoned"
    
    @property
    def is_active(self) -> bool:
        return self not in (TaskPhase.DONE, TaskPhase.ABANDONED)
    
    @property
    def needs_human(self) -> bool:
        return self in (
            TaskPhase.SPEC_REVIEW,
            TaskPhase.BLOCKED,
            TaskPhase.VERIFICATION_FAILED,
        )
    
    @property
    def display_name(self) -> str:
        names = {
            TaskPhase.IDEA: "💡 Idea",
            TaskPhase.DISCUSSING: "💬 Discussing",
            TaskPhase.SPEC_DRAFT: "📝 Drafting Spec",
            TaskPhase.SPEC_REVIEW: "👀 Spec Review",
            TaskPhase.SPEC_APPROVED: "✅ Approved",
            TaskPhase.IMPLEMENTING: "⚙️  Implementing",
            TaskPhase.BLOCKED: "🔴 Blocked",
            TaskPhase.IMPLEMENTED: "🔧 Implemented",
            TaskPhase.VERIFYING: "🧪 Verifying",
            TaskPhase.VERIFICATION_FAILED: "❌ Verify Failed",
            TaskPhase.DONE: "🎉 Done",
            TaskPhase.ABANDONED: "🗑️  Abandoned",
        }
        return names.get(self, self.value)


@dataclass
class PhaseTransition:
    """Record of a phase transition."""
    from_phase: TaskPhase | None
    to_phase: TaskPhase
    timestamp: datetime
    reason: str | None = None
    actor: str = "system"


@dataclass
class TaskWorkflow:
    """Workflow state for a task."""
    task_id: str
    current_phase: TaskPhase = TaskPhase.IDEA
    history: list[PhaseTransition] = field(default_factory=list)
    
    spec_id: str | None = None
    spec_file: str | None = None
    discussion_file: str | None = None
    implementation_branch: str | None = None
    verification_result: str | None = None
    
    depends_on: list[str] = field(default_factory=list)
    blocks: list[str] = field(default_factory=list)
    
    def transition_to(self, phase: TaskPhase, reason: str | None = None, actor: str = "system") -> bool:
        if not self._can_transition(phase):
            return False
        
        transition = PhaseTransition(
            from_phase=self.current_phase,
            to_phase=phase,
            timestamp=datetime.now(),
            reason=reason,
            actor=actor,
        )
        self.history.append(transition)
        self.current_phase = phase
        return True
    
    def _can_transition(self, phase: TaskPhase) -> bool:
        valid_transitions = {
            TaskPhase.IDEA: [TaskPhase.DISCUSSING, TaskPhase.ABANDONED],
            TaskPhase.DISCUSSING: [TaskPhase.SPEC_DRAFT, TaskPhase.IDEA, TaskPhase.ABANDONED],
            TaskPhase.SPEC_DRAFT: [TaskPhase.SPEC_REVIEW, TaskPhase.DISCUSSING, TaskPhase.ABANDONED],
            TaskPhase.SPEC_REVIEW: [TaskPhase.SPEC_APPROVED, TaskPhase.SPEC_DRAFT, TaskPhase.ABANDONED],
            TaskPhase.SPEC_APPROVED: [TaskPhase.IMPLEMENTING, TaskPhase.SPEC_REVIEW, TaskPhase.ABANDONED],
            TaskPhase.IMPLEMENTING: [TaskPhase.IMPLEMENTED, TaskPhase.BLOCKED, TaskPhase.ABANDONED],
            TaskPhase.BLOCKED: [TaskPhase.IMPLEMENTING, TaskPhase.ABANDONED],
            TaskPhase.IMPLEMENTED: [TaskPhase.VERIFYING, TaskPhase.IMPLEMENTING, TaskPhase.ABANDONED],
            TaskPhase.VERIFYING: [TaskPhase.DONE, TaskPhase.VERIFICATION_FAILED],
            TaskPhase.VERIFICATION_FAILED: [TaskPhase.IMPLEMENTING, TaskPhase.ABANDONED],
            TaskPhase.DONE: [],
            TaskPhase.ABANDONED: [],
        }
        return phase in valid_transitions.get(self.current_phase, [])
    
    @property
    def time_in_phase(self) -> float:
        if not self.history:
            return 0
        return (datetime.now() - self.history[-1].timestamp).total_seconds()
    
    @property
    def total_time(self) -> float:
        if not self.history:
            return 0
        return (datetime.now() - self.history[0].timestamp).total_seconds()
