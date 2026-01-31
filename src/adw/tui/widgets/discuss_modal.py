"""Discussion modal for interactive task planning."""

from textual.app import ComposeResult
from textual.containers import Container, Vertical, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Static, Input, Button
from textual.binding import Binding
from rich.text import Text
import asyncio


class DiscussModal(ModalScreen[dict | None]):
    """Modal for interactive task discussion."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    CSS = """
    DiscussModal {
        align: center middle;
    }

    #discuss-container {
        width: 80%;
        height: 80%;
        border: solid $primary;
        background: $surface;
        padding: 1 2;
    }

    #discuss-header {
        height: 1;
        text-style: bold;
        color: $primary;
        margin-bottom: 1;
    }

    #discuss-log {
        height: 1fr;
        border: solid $primary-darken-2;
        padding: 1;
        overflow-y: auto;
    }

    #discuss-input {
        margin-top: 1;
    }

    #button-row {
        height: 3;
        margin-top: 1;
    }

    Button {
        margin-right: 1;
    }
    """

    def __init__(self, initial_idea: str):
        super().__init__()
        self.initial_idea = initial_idea
        self.messages: list[dict] = []
        self.spec_generated = False
        self.spec_content: str | None = None

    def compose(self) -> ComposeResult:
        with Container(id="discuss-container"):
            yield Static("💬 Task Discussion", id="discuss-header")
            yield Static("", id="discuss-log")
            
            yield Input(
                placeholder="Type your message... (Enter to send)",
                id="discuss-input"
            )
            
            with Horizontal(id="button-row"):
                yield Button("Send", variant="primary", id="send-btn")
                yield Button("Generate Spec", variant="success", id="spec-btn", disabled=True)
                yield Button("Approve & Start", variant="warning", id="approve-btn", disabled=True)
                yield Button("Cancel", variant="error", id="cancel-btn")

    async def on_mount(self) -> None:
        """Initialize discussion."""
        self._add_system_message(f"Starting discussion about: {self.initial_idea}")
        self._add_system_message("Discuss the task. When ready, click 'Generate Spec'.")
        
        self.query_one("#discuss-input", Input).focus()
        await self._get_ai_response(f"I want to work on: {self.initial_idea}\n\nHelp me think through this.")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "send-btn":
            self._send_message()
        elif event.button.id == "spec-btn":
            asyncio.create_task(self._generate_spec())
        elif event.button.id == "approve-btn":
            self._approve_and_start()
        elif event.button.id == "cancel-btn":
            self.action_cancel()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "discuss-input":
            self._send_message()

    def _send_message(self) -> None:
        """Send user message."""
        input_widget = self.query_one("#discuss-input", Input)
        message = input_widget.value.strip()
        
        if not message:
            return
        
        input_widget.value = ""
        self._add_user_message(message)
        asyncio.create_task(self._get_ai_response(message))

    async def _get_ai_response(self, user_message: str) -> None:
        """Get AI response."""
        self._add_system_message("Thinking...")
        
        try:
            process = await asyncio.create_subprocess_exec(
                "claude", "--print",
                f"You are helping plan a task. Be concise.\n\nUser: {user_message}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=60.0)
            
            self.messages = [m for m in self.messages if m.get("content") != "Thinking..."]
            
            if process.returncode == 0 and stdout:
                response = stdout.decode().strip()
                self._add_ai_message(response)
                self.query_one("#spec-btn", Button).disabled = False
            else:
                self._add_system_message(f"Error: {stderr.decode()[:100]}")
        
        except asyncio.TimeoutError:
            self._add_system_message("Response timed out")
        except Exception as e:
            self._add_system_message(f"Error: {e}")
        
        self._update_log()

    async def _generate_spec(self) -> None:
        """Generate spec from discussion."""
        self._add_system_message("Generating spec...")
        
        conversation = "\n".join([
            f"{'User' if m['role'] == 'user' else 'AI'}: {m['content']}"
            for m in self.messages
            if m['role'] in ('user', 'assistant')
        ])
        
        prompt = f"""Based on this discussion, generate a task spec in markdown:

{conversation}

Generate:
1. Title
2. Objective (1-2 sentences)
3. Requirements (bullet list)
4. Validation (how to verify done)

Keep it concise."""

        try:
            process = await asyncio.create_subprocess_exec(
                "claude", "--print", prompt,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=90.0)
            
            if process.returncode == 0 and stdout:
                self.spec_content = stdout.decode().strip()
                self.spec_generated = True
                
                self._add_system_message("Spec generated! Review below:")
                self._add_ai_message(self.spec_content)
                self.query_one("#approve-btn", Button).disabled = False
            else:
                self._add_system_message(f"Failed: {stderr.decode()[:100]}")
        
        except Exception as e:
            self._add_system_message(f"Error: {e}")
        
        self._update_log()

    def _approve_and_start(self) -> None:
        """Approve spec and start task."""
        if not self.spec_content:
            return
        
        self.dismiss({
            "action": "approve",
            "idea": self.initial_idea,
            "spec": self.spec_content,
            "messages": self.messages,
        })

    def action_cancel(self) -> None:
        self.dismiss(None)

    def _add_user_message(self, content: str) -> None:
        self.messages.append({"role": "user", "content": content})
        self._update_log()

    def _add_ai_message(self, content: str) -> None:
        self.messages.append({"role": "assistant", "content": content})
        self._update_log()

    def _add_system_message(self, content: str) -> None:
        self.messages.append({"role": "system", "content": content})
        self._update_log()

    def _update_log(self) -> None:
        """Update the discussion log."""
        log = self.query_one("#discuss-log", Static)
        
        text = Text()
        for msg in self.messages[-15:]:
            if msg["role"] == "user":
                text.append("You: ", style="bold #4ec9b0")
                text.append(f"{msg['content']}\n\n")
            elif msg["role"] == "assistant":
                text.append("AI: ", style="bold #569cd6")
                text.append(f"{msg['content']}\n\n")
            else:
                text.append(f"[{msg['content']}]\n", style="italic dim")
        
        log.update(text)
