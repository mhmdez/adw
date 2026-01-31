from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.screen import ModalScreen
from textual.widgets import Static, Input, Button
from textual.binding import Binding

from ...protocol.messages import AgentQuestion


class QuestionModal(ModalScreen[str | None]):
    """Modal for agent questions requiring user input."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("enter", "submit", "Submit", show=False),
    ]

    CSS = """
    QuestionModal {
        align: center middle;
    }

    #question-container {
        width: 60;
        max-width: 80%;
        height: auto;
        max-height: 80%;
        border: solid $primary;
        background: $surface;
        padding: 1 2;
    }

    #question-title {
        text-style: bold;
        color: $primary;
        margin-bottom: 1;
    }

    #question-text {
        margin-bottom: 1;
    }

    #question-context {
        color: $text-muted;
        margin-bottom: 1;
    }

    #question-options {
        margin-bottom: 1;
    }

    #question-input {
        margin-bottom: 1;
    }

    #button-row {
        layout: horizontal;
        height: auto;
    }

    Button {
        margin-right: 1;
    }
    """

    def __init__(self, question: AgentQuestion, agent_id: str):
        super().__init__()
        self.question = question
        self.agent_id = agent_id

    def compose(self) -> ComposeResult:
        with Container(id="question-container"):
            yield Static(f"❓ Question from agent {self.agent_id[:8]}", id="question-title")
            yield Static(self.question.question, id="question-text")

            if self.question.context:
                yield Static(f"Context: {self.question.context}", id="question-context")

            if self.question.options:
                options_text = "\n".join(f"  {i+1}. {opt}" for i, opt in enumerate(self.question.options))
                yield Static(f"Options:\n{options_text}", id="question-options")

            yield Input(
                placeholder="Type your answer...",
                id="question-input",
                value=self.question.default or "",
            )

            with Container(id="button-row"):
                yield Button("Submit", variant="primary", id="submit-btn")
                if not self.question.required:
                    yield Button("Skip", variant="default", id="skip-btn")
                yield Button("Cancel", variant="error", id="cancel-btn")

    def on_mount(self) -> None:
        self.query_one("#question-input", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "submit-btn":
            self.action_submit()
        elif event.button.id == "skip-btn":
            self.dismiss(None)  # Skip returns None
        elif event.button.id == "cancel-btn":
            self.action_cancel()

    def action_submit(self) -> None:
        answer = self.query_one("#question-input", Input).value
        if answer or not self.question.required:
            self.dismiss(answer)
        else:
            self.notify("Answer is required", severity="warning")

    def action_cancel(self) -> None:
        self.dismiss(None)
