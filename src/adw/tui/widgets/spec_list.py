"""Spec list widget."""

from textual.app import ComposeResult
from textual.containers import Vertical, Container
from textual.widgets import Static
from rich.text import Text

from ...specs import Spec, SpecStatus


class SpecList(Vertical):
    """List of specs with status indicators."""

    DEFAULT_CSS = """
    SpecList {
        width: 100%;
        height: auto;
        max-height: 12;
        padding: 0 1;
    }

    SpecList > #spec-header {
        height: 1;
        color: #888;
    }

    SpecList > #spec-container {
        height: auto;
        max-height: 10;
    }

    .spec-item {
        height: 1;
    }
    """

    def __init__(self):
        super().__init__()
        self._specs: list[Spec] = []
        self._selected_id: str | None = None
        self._filter_status: SpecStatus | None = None

    def compose(self) -> ComposeResult:
        yield Static("SPECS", id="spec-header")
        yield Container(id="spec-container")

    def update_specs(self, specs: list[Spec]) -> None:
        """Update the spec list."""
        self._specs = specs
        self._update_display()

    def select_spec(self, spec_id: str | None) -> None:
        """Select a spec."""
        self._selected_id = spec_id
        self._update_display()

    def filter_by_status(self, status: SpecStatus | None) -> None:
        """Filter specs by status."""
        self._filter_status = status
        self._update_display()

    def _update_display(self) -> None:
        """Refresh the spec display."""
        container = self.query_one("#spec-container", Container)
        container.remove_children()

        specs = self._specs
        if self._filter_status:
            specs = [s for s in specs if s.status == self._filter_status]

        if not specs:
            container.mount(Static("[dim]No specs found[/dim]"))
            return

        current_phase = None
        for spec in specs:
            if spec.phase != current_phase:
                current_phase = spec.phase
                if current_phase:
                    container.mount(Static(f"[bold dim]{current_phase}[/]"))

            widget = self._make_spec_widget(spec)
            container.mount(widget)

    def _make_spec_widget(self, spec: Spec) -> Static:
        """Create widget for a single spec."""
        text = Text()

        icons = {
            SpecStatus.DRAFT: ("📝", "dim"),
            SpecStatus.PENDING: ("⏳", "yellow"),
            SpecStatus.APPROVED: ("✅", "green"),
            SpecStatus.REJECTED: ("❌", "red"),
            SpecStatus.IMPLEMENTED: ("🎉", "cyan"),
        }
        icon, style = icons.get(spec.status, ("?", ""))
        text.append(f" {icon} ", style=style)
        text.append(f"{spec.id} ", style="dim")

        title = spec.title[:30]
        if len(spec.title) > 30:
            title += "…"
        text.append(title, style=style if spec.status != SpecStatus.DRAFT else "")

        widget = Static(text, classes="spec-item")
        if spec.id == self._selected_id:
            widget.add_class("-selected")

        return widget

    @property
    def pending_count(self) -> int:
        return sum(1 for s in self._specs if s.status == SpecStatus.PENDING)

    @property
    def approved_count(self) -> int:
        return sum(1 for s in self._specs if s.status == SpecStatus.APPROVED)
