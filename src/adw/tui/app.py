"""Main ADW TUI application - Claude Code style interface."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from datetime import datetime

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical, Horizontal
from textual.widgets import Static, Input, RichLog
from rich.text import Text

from .commands import execute_command, TUI_COMMANDS
from .state import AppState
from .log_watcher import LogWatcher, LogEvent
from ..agent.manager import AgentManager
from ..agent.task_updater import mark_in_progress
from ..agent.utils import generate_adw_id
from ..protocol.messages import write_message, MessagePriority
from .. import __version__


# Simple header
LOGO = "[bold cyan]❯❯[/bold cyan] [bold]ADW[/bold] [dim]v{version}[/dim]"


class ADWApp(App):
    """ADW - Claude Code style chat interface."""

    CSS = """
    Screen {
        background: #1a1a2e;
    }

    #header {
        dock: top;
        height: 1;
        padding: 0 1;
        background: #1a1a2e;
        color: #4fc3f7;
    }

    #chat-container {
        height: 1fr;
        padding: 0 1;
        background: #1a1a2e;
    }

    #chat-log {
        height: 1fr;
        background: #1a1a2e;
        scrollbar-size: 1 1;
    }

    #input-container {
        dock: bottom;
        height: 1;
        padding: 0 1;
        background: #1a1a2e;
    }

    #prompt-symbol {
        width: 3;
        color: #4fc3f7;
        background: #1a1a2e;
    }

    #user-input {
        width: 1fr;
        background: #1a1a2e;
        border: none;
        padding: 0;
    }

    #user-input:focus {
        border: none;
    }

    #user-input > .input--placeholder {
        color: #666;
    }
    """

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", show=False),
        Binding("ctrl+l", "clear", "Clear", show=False),
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(self):
        super().__init__()
        self.state = AppState()
        self.agent_manager = AgentManager()
        self.log_watcher = LogWatcher()
        self._new_task_mode = False
        self._daemon_running = False

        self.state.subscribe(self._on_state_change)
        self.agent_manager.subscribe(self._on_agent_event)
        self.log_watcher.subscribe_all(self._on_log_event)

    def compose(self) -> ComposeResult:
        """Create the UI layout."""
        # Header with logo
        yield Static(LOGO.format(version=__version__), id="header")

        # Main chat area
        with Container(id="chat-container"):
            yield RichLog(id="chat-log", highlight=True, markup=True)

        # Input area - clean like Claude Code
        with Horizontal(id="input-container"):
            yield Static("❯", id="prompt-symbol")
            yield Input(placeholder="", id="user-input")

    async def on_mount(self) -> None:
        """Initialize on mount."""
        self.state.load_from_tasks_md()
        self.set_interval(2.0, self._poll_agents)
        self.run_worker(self.log_watcher.watch())

        # Welcome message
        self._log_system("Welcome to ADW - AI Developer Workflow")
        self._log_system("Type [bold]/help[/bold] for available commands")
        self._log_system("")

        # Show current tasks
        self._show_tasks()

        # Focus input
        self.query_one("#user-input", Input).focus()

    def _log_system(self, message: str) -> None:
        """Log a system message."""
        log = self.query_one("#chat-log", RichLog)
        log.write(Text.from_markup(f"[dim]{message}[/dim]"))

    def _log_user(self, message: str) -> None:
        """Log a user message."""
        log = self.query_one("#chat-log", RichLog)
        log.write(Text.from_markup(f"[bold green]>[/bold green] {message}"))

    def _log_response(self, message: str) -> None:
        """Log a response message."""
        log = self.query_one("#chat-log", RichLog)
        log.write(Text.from_markup(message))

    def _log_error(self, message: str) -> None:
        """Log an error message."""
        log = self.query_one("#chat-log", RichLog)
        log.write(Text.from_markup(f"[bold red]Error:[/bold red] {message}"))

    def _show_tasks(self) -> None:
        """Show current tasks."""
        if not self.state.tasks:
            self._log_system("No tasks. Create one with [bold]/new <description>[/bold]")
            return

        self._log_system(f"[bold]Tasks ({len(self.state.tasks)}):[/bold]")
        for key, task in self.state.tasks.items():
            status_icon = {
                "pending": "⏳",
                "in_progress": "🟡",
                "done": "✅",
                "blocked": "⏰",
                "failed": "❌",
            }.get(task.status.value, "○")
            self._log_system(f"  {status_icon} [{task.display_id}] {task.description[:50]}")

    def _on_state_change(self, state: AppState) -> None:
        """Handle state changes."""
        pass  # We update UI reactively via commands

    def _on_agent_event(self, event: str, adw_id: str, data: dict) -> None:
        """Handle agent events."""
        if event == "spawned":
            self._log_response(f"[cyan]Agent {adw_id[:8]} started[/cyan]")
        elif event == "completed":
            self._log_response(f"[green]Agent {adw_id[:8]} completed[/green]")
            self.state.load_from_tasks_md()
        elif event == "failed":
            return_code = data.get("return_code", "?")
            stderr = data.get("stderr", "")
            self._log_error(f"Agent {adw_id[:8]} failed (exit code: {return_code})")
            if stderr:
                for line in stderr.strip().split("\n")[:5]:
                    self._log_error(f"  {line}")
            self.state.load_from_tasks_md()
        elif event == "killed":
            self._log_response(f"[yellow]Agent {adw_id[:8]} killed[/yellow]")

    def _on_log_event(self, event: LogEvent) -> None:
        """Handle log event from agents."""
        icon = {
            "assistant": "💬",
            "tool": "🔧",
            "tool_result": "✓",
            "result": "✅",
            "error": "❌",
        }.get(event.event_type, "•")

        msg = event.message[:80] if event.message else ""
        self._log_response(f"[dim]{icon} [{event.adw_id[:8]}] {msg}[/dim]")

    def _poll_agents(self) -> None:
        """Poll for agent completion."""
        completed = self.agent_manager.poll()
        if completed:
            self.state.load_from_tasks_md()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission."""
        if event.input.id != "user-input":
            return

        message = event.value.strip()
        if not message:
            return

        event.input.value = ""
        self._log_user(message)

        # Handle slash commands
        if message.startswith("/"):
            self._handle_command(message)
            return

        # Detect if it's a question or a task
        # Questions typically start with question words or end with ?
        question_starters = ("what", "how", "why", "where", "when", "who", "which", "can", "could", "would", "is", "are", "do", "does", "explain", "describe", "tell", "show")
        is_question = (
            message.endswith("?") or
            message.lower().startswith(question_starters)
        )

        if is_question:
            self._ask_question(message)
        else:
            self._log_response("Creating task and spawning agent...")
            self._log_response("[dim]Tip: Use /ask for questions, or /do to explicitly create a task[/dim]")
            self._spawn_task(message)

    def _handle_command(self, text: str) -> None:
        """Handle a slash command."""
        parts = text[1:].split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        # Core commands
        if cmd == "help":
            self._show_help()
        elif cmd == "init":
            self._run_init()
        elif cmd == "tasks" or cmd == "list":
            self.state.load_from_tasks_md()
            self._show_tasks()
        elif cmd == "new":
            if args:
                self._spawn_task(args)
            else:
                self._log_error("Usage: /new <task description>")
        elif cmd == "status":
            self._show_status()
        elif cmd == "clear":
            self.query_one("#chat-log", RichLog).clear()
        elif cmd == "version":
            self._log_response(f"ADW version {__version__}")
        elif cmd == "update":
            self._run_update()
        elif cmd == "quit" or cmd == "exit":
            self.exit()
        # New commands
        elif cmd == "doctor":
            self._run_doctor()
        elif cmd == "verify":
            self._run_verify(args)
        elif cmd == "approve":
            self._run_approve(args)
        elif cmd == "run":
            self._run_daemon(args)
        elif cmd == "stop":
            self._stop_daemon()
        elif cmd == "worktree":
            self._run_worktree(args)
        elif cmd == "github":
            self._run_github(args)
        elif cmd == "ask":
            if args:
                self._ask_question(args)
            else:
                self._log_error("Usage: /ask <question>")
        elif cmd == "do" or cmd == "task":
            if args:
                self._spawn_task(args)
            else:
                self._log_error("Usage: /do <task description>")
        else:
            self._log_error(f"Unknown command: /{cmd}. Type /help for commands.")

    def _show_help(self) -> None:
        """Show help message."""
        self._log_response("[bold]Commands:[/bold]")
        self._log_response("")
        self._log_response("[cyan]Setup & Info:[/cyan]")
        self._log_response("  /init          - Initialize ADW in current project")
        self._log_response("  /doctor        - Check installation health")
        self._log_response("  /status        - Show system status")
        self._log_response("  /version       - Show version")
        self._log_response("  /update        - Check for updates")
        self._log_response("")
        self._log_response("[cyan]Chat:[/cyan]")
        self._log_response("  /ask <question>- Ask Claude a question")
        self._log_response("")
        self._log_response("[cyan]Tasks:[/cyan]")
        self._log_response("  /do <desc>     - Create task and spawn agent")
        self._log_response("  /new <desc>    - Same as /do")
        self._log_response("  /tasks         - List all tasks")
        self._log_response("  /verify [id]   - Verify completed task")
        self._log_response("  /approve [spec]- Approve spec, create tasks")
        self._log_response("")
        self._log_response("[cyan]Automation:[/cyan]")
        self._log_response("  /run           - Start autonomous daemon")
        self._log_response("  /stop          - Stop daemon")
        self._log_response("")
        self._log_response("[cyan]Worktrees:[/cyan]")
        self._log_response("  /worktree list          - List worktrees")
        self._log_response("  /worktree create <name> - Create worktree")
        self._log_response("  /worktree remove <name> - Remove worktree")
        self._log_response("")
        self._log_response("[cyan]GitHub:[/cyan]")
        self._log_response("  /github watch           - Watch issues")
        self._log_response("  /github process <num>   - Process issue")
        self._log_response("")
        self._log_response("[cyan]Other:[/cyan]")
        self._log_response("  /clear         - Clear screen")
        self._log_response("  /quit          - Exit ADW")
        self._log_response("")
        self._log_response("[dim]Or just type: questions get answered, tasks get executed[/dim]")

    def _show_status(self) -> None:
        """Show status."""
        total = len(self.state.tasks)
        running = self.state.running_count
        pending = sum(1 for t in self.state.tasks.values() if t.status.value == "pending")
        done = sum(1 for t in self.state.tasks.values() if t.status.value == "done")

        self._log_response("[bold]Status:[/bold]")
        self._log_response(f"  Version: {__version__}")
        self._log_response(f"  Tasks: {total} total")
        self._log_response(f"    ⏳ Pending: {pending}")
        self._log_response(f"    🟡 Running: {running}")
        self._log_response(f"    ✅ Done: {done}")
        self._log_response(f"  Daemon: {'[green]running[/green]' if self._daemon_running else '[dim]stopped[/dim]'}")

    def _run_update(self) -> None:
        """Check for updates."""
        from ..update import check_for_update

        self._log_response("Checking for updates...")
        current, latest = check_for_update()

        if latest is None:
            self._log_error("Could not check for updates")
            return

        if latest <= current:
            self._log_response(f"Already at latest version ({current})")
        else:
            self._log_response(f"Update available: {current} → {latest}")
            self._log_response("Run: uv tool upgrade adw")

    def _run_init(self) -> None:
        """Initialize ADW in current project."""
        from ..init import init_project

        self._log_response("Initializing ADW in current project...")

        try:
            result = init_project(Path.cwd(), force=False)

            if result["created"]:
                self._log_response("[green]Created:[/green]")
                for path in result["created"]:
                    self._log_response(f"  + {path}")

            if result["updated"]:
                self._log_response("[cyan]Updated:[/cyan]")
                for path in result["updated"]:
                    self._log_response(f"  ~ {path}")

            if result["skipped"]:
                self._log_response("[dim]Skipped (already exist):[/dim]")
                for path in result["skipped"]:
                    self._log_response(f"  - {path}")

            self._log_response("")
            self._log_response("[green]ADW initialized![/green] Run /new <task> to get started.")

            # Reload tasks
            self.state.load_from_tasks_md()

        except Exception as e:
            self._log_error(f"Init failed: {e}")

    def _run_doctor(self) -> None:
        """Check installation health."""
        self._log_response("[bold]ADW Health Check[/bold]")
        self._log_response("")

        # Check ADW version
        self._log_response(f"[green]✓[/green] ADW version: {__version__}")

        # Check Claude Code
        try:
            result = subprocess.run(
                ["claude", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                version = result.stdout.strip() or "installed"
                self._log_response(f"[green]✓[/green] Claude Code: {version}")
            else:
                self._log_response("[red]✗[/red] Claude Code: not working")
        except FileNotFoundError:
            self._log_response("[red]✗[/red] Claude Code: not installed")
            self._log_response("  Install: npm install -g @anthropic-ai/claude-code")
        except Exception as e:
            self._log_response(f"[yellow]?[/yellow] Claude Code: {e}")

        # Check project files
        cwd = Path.cwd()

        if (cwd / "CLAUDE.md").exists():
            self._log_response("[green]✓[/green] CLAUDE.md exists")
        else:
            self._log_response("[yellow]![/yellow] CLAUDE.md missing (run /init)")

        if (cwd / "tasks.md").exists():
            self._log_response("[green]✓[/green] tasks.md exists")
        else:
            self._log_response("[yellow]![/yellow] tasks.md missing (run /init)")

        if (cwd / ".claude" / "commands").exists():
            self._log_response("[green]✓[/green] .claude/commands/ exists")
        else:
            self._log_response("[yellow]![/yellow] .claude/commands/ missing (run /init)")

        # Check git
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                self._log_response("[green]✓[/green] Git repository detected")
            else:
                self._log_response("[yellow]![/yellow] Not a git repository")
        except Exception:
            self._log_response("[yellow]?[/yellow] Could not check git")

    def _run_verify(self, args: str) -> None:
        """Verify a completed task."""
        task_id = args.strip() if args else None

        # Find tasks to verify (done status)
        done_tasks = [
            t for t in self.state.tasks.values()
            if t.status.value == "done"
        ]

        if not done_tasks:
            self._log_response("No completed tasks to verify.")
            return

        if task_id:
            # Find specific task
            task = None
            for t in done_tasks:
                if t.adw_id and t.adw_id.startswith(task_id):
                    task = t
                    break
            if not task:
                self._log_error(f"Task {task_id} not found or not completed")
                return
            self._log_response(f"Opening Claude Code to verify task {task.display_id}...")
            self._log_response(f"  {task.description[:60]}")
        else:
            # Show list
            self._log_response("[bold]Completed tasks to verify:[/bold]")
            for t in done_tasks:
                self._log_response(f"  ✅ [{t.display_id}] {t.description[:50]}")
            self._log_response("")
            self._log_response("Run /verify <task_id> to verify a specific task")

    def _run_approve(self, args: str) -> None:
        """Approve a pending spec."""
        spec_name = args.strip() if args else None
        specs_dir = Path.cwd() / "specs"

        if not specs_dir.exists():
            self._log_response("No specs/ directory found. Run /init first.")
            return

        # Find pending specs
        specs = list(specs_dir.glob("*.md"))
        if not specs:
            self._log_response("No specs found in specs/ directory.")
            return

        if spec_name:
            # Find specific spec
            spec_path = specs_dir / f"{spec_name}.md"
            if not spec_path.exists():
                spec_path = specs_dir / spec_name
            if not spec_path.exists():
                self._log_error(f"Spec '{spec_name}' not found")
                return
            self._log_response(f"Opening Claude Code to approve spec: {spec_path.name}")
        else:
            # Show list
            self._log_response("[bold]Available specs:[/bold]")
            for spec in specs:
                self._log_response(f"  📄 {spec.name}")
            self._log_response("")
            self._log_response("Run /approve <spec_name> to approve a specific spec")

    def _run_daemon(self, args: str) -> None:
        """Start autonomous daemon."""
        if self._daemon_running:
            self._log_response("Daemon is already running. Use /stop to stop it.")
            return

        self._log_response("[cyan]Starting autonomous daemon...[/cyan]")
        self._log_response("  Monitoring tasks.md for eligible tasks")
        self._log_response("  Press /stop to stop the daemon")
        self._log_response("")

        # Parse args for options
        max_concurrent = 3
        poll_interval = 5.0

        if args:
            parts = args.split()
            for i, part in enumerate(parts):
                if part in ("-m", "--max") and i + 1 < len(parts):
                    try:
                        max_concurrent = int(parts[i + 1])
                    except ValueError:
                        pass
                elif part in ("-p", "--poll") and i + 1 < len(parts):
                    try:
                        poll_interval = float(parts[i + 1])
                    except ValueError:
                        pass

        self._log_response(f"  Max concurrent: {max_concurrent}")
        self._log_response(f"  Poll interval: {poll_interval}s")

        self._daemon_running = True

        # Start daemon polling
        self.set_interval(poll_interval, self._daemon_tick)
        self._log_response("[green]Daemon started[/green]")

    def _daemon_tick(self) -> None:
        """Daemon tick - check for eligible tasks."""
        if not self._daemon_running:
            return

        self.state.load_from_tasks_md()

        # Find eligible tasks (pending, not blocked)
        eligible = [
            t for t in self.state.tasks.values()
            if t.status.value == "pending"
        ]

        if eligible and self.state.running_count < 3:
            task = eligible[0]
            self._log_response(f"[cyan]Daemon: spawning agent for {task.display_id}[/cyan]")
            self._spawn_task(task.description)

    def _stop_daemon(self) -> None:
        """Stop the daemon."""
        if not self._daemon_running:
            self._log_response("Daemon is not running.")
            return

        self._daemon_running = False
        self._log_response("[yellow]Daemon stopped[/yellow]")

    def _run_worktree(self, args: str) -> None:
        """Manage git worktrees."""
        parts = args.strip().split(maxsplit=1) if args else []
        subcmd = parts[0].lower() if parts else "list"
        subargs = parts[1] if len(parts) > 1 else ""

        if subcmd == "list":
            self._worktree_list()
        elif subcmd == "create":
            if subargs:
                self._worktree_create(subargs)
            else:
                self._log_error("Usage: /worktree create <name>")
        elif subcmd == "remove" or subcmd == "rm":
            if subargs:
                self._worktree_remove(subargs)
            else:
                self._log_error("Usage: /worktree remove <name>")
        else:
            self._log_error(f"Unknown worktree command: {subcmd}")
            self._log_response("Usage: /worktree [list|create|remove] [name]")

    def _worktree_list(self) -> None:
        """List git worktrees."""
        try:
            result = subprocess.run(
                ["git", "worktree", "list"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                self._log_response("[bold]Git Worktrees:[/bold]")
                for line in result.stdout.strip().split("\n"):
                    if line:
                        self._log_response(f"  {line}")
            else:
                self._log_error("Failed to list worktrees")
        except Exception as e:
            self._log_error(f"Failed to list worktrees: {e}")

    def _worktree_create(self, name: str) -> None:
        """Create a git worktree."""
        worktree_path = Path.cwd().parent / f"worktrees/{name}"

        try:
            # Create branch and worktree
            result = subprocess.run(
                ["git", "worktree", "add", str(worktree_path), "-b", name],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                self._log_response(f"[green]Created worktree:[/green] {worktree_path}")
            else:
                # Try without -b if branch exists
                result = subprocess.run(
                    ["git", "worktree", "add", str(worktree_path), name],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if result.returncode == 0:
                    self._log_response(f"[green]Created worktree:[/green] {worktree_path}")
                else:
                    self._log_error(f"Failed: {result.stderr}")
        except Exception as e:
            self._log_error(f"Failed to create worktree: {e}")

    def _worktree_remove(self, name: str) -> None:
        """Remove a git worktree."""
        try:
            result = subprocess.run(
                ["git", "worktree", "remove", name, "--force"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                self._log_response(f"[green]Removed worktree:[/green] {name}")
            else:
                self._log_error(f"Failed: {result.stderr}")
        except Exception as e:
            self._log_error(f"Failed to remove worktree: {e}")

    def _run_github(self, args: str) -> None:
        """GitHub integration commands."""
        parts = args.strip().split(maxsplit=1) if args else []
        subcmd = parts[0].lower() if parts else ""
        subargs = parts[1] if len(parts) > 1 else ""

        if subcmd == "watch":
            self._github_watch()
        elif subcmd == "process":
            if subargs:
                self._github_process(subargs)
            else:
                self._log_error("Usage: /github process <issue_number>")
        else:
            self._log_response("[bold]GitHub Commands:[/bold]")
            self._log_response("  /github watch          - Watch for new issues")
            self._log_response("  /github process <num>  - Process specific issue")

    def _github_watch(self) -> None:
        """Watch GitHub issues."""
        self._log_response("[cyan]Starting GitHub issue watcher...[/cyan]")
        self._log_response("  This will poll for new issues and create tasks")
        self._log_response("")
        self._log_response("[yellow]Note:[/yellow] GitHub watching runs in background.")
        self._log_response("Configure with GITHUB_TOKEN environment variable.")

    def _ask_question(self, question: str) -> None:
        """Ask Claude a question and display the response."""
        self._log_response("[dim]Thinking... (this may take a moment)[/dim]")
        # Run in background worker to not block TUI
        self.run_worker(self._ask_question_async(question))

    async def _ask_question_async(self, question: str) -> None:
        """Async worker to ask Claude a question."""
        import asyncio

        try:
            # Use Claude CLI to answer the question
            # Include project context if CLAUDE.md exists
            context = ""
            claude_md = Path.cwd() / "CLAUDE.md"
            if claude_md.exists():
                try:
                    context = f"Project context from CLAUDE.md:\n{claude_md.read_text()[:2000]}\n\n"
                except Exception:
                    pass

            prompt = f"{context}Question: {question}\n\nProvide a concise, helpful answer."

            # Run subprocess asynchronously
            process = await asyncio.create_subprocess_exec(
                "claude", "--print", prompt,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=120.0
                )

                if process.returncode == 0 and stdout:
                    response = stdout.decode().strip()
                    for line in response.split("\n"):
                        self._log_response(line)
                else:
                    self._log_error("Failed to get response from Claude")
                    if stderr:
                        self._log_error(f"  {stderr.decode()[:200]}")

            except asyncio.TimeoutError:
                process.kill()
                self._log_error("Request timed out (120s)")

        except FileNotFoundError:
            self._log_error("Claude CLI not found. Install with: npm install -g @anthropic-ai/claude-code")
        except Exception as e:
            self._log_error(f"Error: {e}")

    def _github_process(self, issue_num: str) -> None:
        """Process a GitHub issue."""
        try:
            num = int(issue_num)
            self._log_response(f"[cyan]Processing GitHub issue #{num}...[/cyan]")

            # Try to fetch issue info
            try:
                result = subprocess.run(
                    ["gh", "issue", "view", str(num), "--json", "title,body"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode == 0:
                    import json
                    data = json.loads(result.stdout)
                    title = data.get("title", "")
                    self._log_response(f"  Title: {title}")
                    self._log_response(f"  Creating task from issue...")
                    self._spawn_task(f"[GitHub #{num}] {title}")
                else:
                    self._log_error("Failed to fetch issue. Is 'gh' CLI installed?")
            except FileNotFoundError:
                self._log_error("GitHub CLI (gh) not installed")
                self._log_response("Install: https://cli.github.com/")
        except ValueError:
            self._log_error(f"Invalid issue number: {issue_num}")

    def _spawn_task(self, description: str) -> None:
        """Spawn a new task."""
        adw_id = generate_adw_id()
        tasks_file = Path("tasks.md")

        # Add task to tasks.md
        if tasks_file.exists():
            content = tasks_file.read_text()
        else:
            content = "# Tasks\n\n## Active Tasks\n\n"

        content = content.rstrip() + f"\n[🟡, {adw_id}] {description}\n"
        tasks_file.write_text(content)

        self._log_response(f"[cyan]Task {adw_id[:8]} created[/cyan]")

        # Create agents directory for logging
        agents_dir = Path("agents") / adw_id
        agents_dir.mkdir(parents=True, exist_ok=True)

        # Spawn agent
        try:
            self.agent_manager.spawn_workflow(
                task_description=description,
                worktree_name=f"task-{adw_id}",
                workflow="standard",
                model="sonnet",
                adw_id=adw_id,
            )
            self._log_response(f"[cyan]Agent spawned for task {adw_id[:8]}[/cyan]")
            self._log_response(f"[dim]Logs: agents/{adw_id}/[/dim]")
        except Exception as e:
            self._log_error(f"Failed to spawn agent: {e}")

        self.state.load_from_tasks_md()

    def action_quit(self) -> None:
        """Quit the app."""
        self.exit()

    def action_clear(self) -> None:
        """Clear the log."""
        self.query_one("#chat-log", RichLog).clear()

    def action_cancel(self) -> None:
        """Cancel current input."""
        self.query_one("#user-input", Input).value = ""


def run_tui() -> None:
    """Run the TUI application."""
    app = ADWApp()
    app.run()
