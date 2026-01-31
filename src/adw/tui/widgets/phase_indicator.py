"""Phase indicator widget."""

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Static
from rich.text import Text

from ...workflow import TaskPhase, TaskWorkflow


class PhaseIndicator(Horizontal):
    """Visual indicator of task phase progression."""

    DEFAULT_CSS = """
    PhaseIndicator {
        width: 100%;
        height: 1;
        padding: 0 1;
        background: $surface;
    }
    """

    PHASES_SEQUENCE = [
        TaskPhase.IDEA,
        TaskPhase.DISCUSSING,
        TaskPhase.SPEC_DRAFT,
        TaskPhase.SPEC_REVIEW,
        TaskPhase.SPEC_APPROVED,
        TaskPhase.IMPLEMENTING,
        TaskPhase.IMPLEMENTED,
        TaskPhase.VERIFYING,
        TaskPhase.DONE,
    ]

    def __init__(self):
        super().__init__()
        self._workflow: TaskWorkflow | None = None

    def compose(self) -> ComposeResult:
        yield Static("[dim]Select a task to see phases[/dim]", id="phase-content")

    def update_workflow(self, workflow: TaskWorkflow | None) -> None:
        """Update the displayed workflow."""
        self._workflow = workflow
        self._build_indicator()

    def _build_indicator(self) -> None:
        """Build the phase indicator."""
        content = self.query_one("#phase-content", Static)

        if not self._workflow:
            content.update("[dim]Select a task to see phases[/dim]")
            return

        current = self._workflow.current_phase
        current_idx = self._get_phase_index(current)

        text = Text()
        for i, phase in enumerate(self.PHASES_SEQUENCE):
            if phase == current:
                state = "current"
            elif i < current_idx:
                state = "completed"
            else:
                state = "pending"

            icon = self._get_icon(phase, state)
            text.append(icon)

            if i < len(self.PHASES_SEQUENCE) - 1:
                if state == "completed":
                    text.append("─", style="green")
                else:
                    text.append("─", style="dim")

        text.append(f"  {current.display_name}", style="bold cyan")
        content.update(text)

    def _get_phase_index(self, phase: TaskPhase) -> int:
        """Get index of phase in sequence."""
        try:
            return self.PHASES_SEQUENCE.index(phase)
        except ValueError:
            if phase == TaskPhase.BLOCKED:
                return self.PHASES_SEQUENCE.index(TaskPhase.IMPLEMENTING)
            elif phase == TaskPhase.VERIFICATION_FAILED:
                return self.PHASES_SEQUENCE.index(TaskPhase.VERIFYING)
            return 0

    def _get_icon(self, phase: TaskPhase, state: str) -> str:
        """Get icon for phase."""
        if state == "current":
            return "●"
        elif state == "completed":
            return "[green]●[/]"
        else:
            return "[dim]○[/]"


class PhaseTimeline(Static):
    """Timeline showing phase history."""

    DEFAULT_CSS = """
    PhaseTimeline {
        width: 100%;
        height: auto;
        max-height: 6;
        padding: 0 1;
    }
    """

    def __init__(self):
        super().__init__()
        self._workflow: TaskWorkflow | None = None

    def update_workflow(self, workflow: TaskWorkflow | None) -> None:
        """Update with workflow history."""
        self._workflow = workflow
        self._render()

    def _render(self) -> None:
        """Render the timeline."""
        if not self._workflow or not self._workflow.history:
            self.update("[dim]No history[/dim]")
            return

        text = Text()
        text.append("Timeline:\n", style="bold")

        for transition in self._workflow.history[-5:]:
            time_str = transition.timestamp.strftime("%H:%M")
            phase_name = transition.to_phase.display_name

            text.append(f"  {time_str} ", style="dim")
            text.append(f"{phase_name}", style="cyan")
            if transition.reason:
                text.append(f" - {transition.reason}", style="dim italic")
            text.append("\n")

        self.update(text)
