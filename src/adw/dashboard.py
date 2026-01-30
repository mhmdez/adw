"""Interactive TUI dashboard for ADW."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .specs import SpecStatus, get_pending_specs, load_all_specs
from .tasks import TaskStatus, get_tasks_summary, load_tasks

console = Console()


def clear_screen() -> None:
    """Clear the terminal screen."""
    console.clear()


def print_header() -> None:
    """Print the dashboard header."""
    header = Text()
    header.append("ADW", style="bold cyan")
    header.append(" - AI Developer Workflow", style="dim")
    console.print(Panel(header, border_style="cyan"))
    console.print()


def print_task_summary(tasks_path: Path | None = None) -> None:
    """Print a summary of tasks.

    Args:
        tasks_path: Path to tasks.md file.
    """
    tasks = load_tasks(tasks_path)

    if not tasks:
        console.print("[dim]No tasks found. Run 'adw new' to create one.[/dim]")
        console.print()
        return

    summary = get_tasks_summary(tasks)

    table = Table(title="Tasks", show_header=True, header_style="bold")
    table.add_column("Status", style="dim")
    table.add_column("Count", justify="right")

    status_styles = {
        "pending": "yellow",
        "in_progress": "blue",
        "done": "green",
        "blocked": "red",
        "failed": "red bold",
    }

    for status in ["pending", "in_progress", "done", "blocked", "failed"]:
        count = summary[status]
        if count > 0:
            style = status_styles[status]
            table.add_row(status.replace("_", " ").title(), f"[{style}]{count}[/{style}]")

    console.print(table)
    console.print()

    # Show actionable tasks
    actionable = [t for t in tasks if t.is_actionable]
    if actionable:
        console.print("[bold]Actionable Tasks:[/bold]")
        for task in actionable[:5]:
            status_icon = "🔵" if task.status == TaskStatus.IN_PROGRESS else "⚪"
            console.print(f"  {status_icon} {task.id}: {task.title}")
        if len(actionable) > 5:
            console.print(f"  [dim]... and {len(actionable) - 5} more[/dim]")
        console.print()


def print_spec_summary(specs_dir: Path | None = None) -> None:
    """Print a summary of specs.

    Args:
        specs_dir: Path to specs directory.
    """
    specs = load_all_specs(specs_dir)

    if not specs:
        return

    pending = [s for s in specs if s.status == SpecStatus.PENDING_APPROVAL]

    if pending:
        console.print(f"[yellow bold]⚠ {len(pending)} spec(s) pending approval[/yellow bold]")
        for spec in pending:
            console.print(f"  • {spec.name}: {spec.title}")
        console.print()


def print_menu() -> None:
    """Print the interactive menu."""
    console.print("[bold]Commands:[/bold]")
    console.print("  [cyan]n[/cyan]  New task (start /discuss)")
    console.print("  [cyan]s[/cyan]  Status overview")
    console.print("  [cyan]v[/cyan]  Verify completed task")
    console.print("  [cyan]a[/cyan]  Approve pending spec")
    console.print("  [cyan]q[/cyan]  Quit")
    console.print()


def run_claude_command(command: str, args: str = "") -> None:
    """Run a Claude Code command.

    Args:
        command: The slash command to run (without /).
        args: Optional arguments.
    """
    full_command = f"/{command}"
    if args:
        full_command = f"{full_command} {args}"

    console.print(f"[dim]Running: claude {full_command}[/dim]")

    try:
        subprocess.run(["claude", full_command], check=False)
    except FileNotFoundError:
        console.print("[red]Error: 'claude' command not found. Is Claude Code installed?[/red]")


def get_input(prompt: str) -> str:
    """Get input from user.

    Args:
        prompt: The prompt to display.

    Returns:
        User input string.
    """
    try:
        return input(prompt).strip()
    except (KeyboardInterrupt, EOFError):
        return "q"


def run_dashboard() -> None:
    """Run the interactive dashboard."""
    while True:
        clear_screen()
        print_header()
        print_task_summary()
        print_spec_summary()
        print_menu()

        choice = get_input("Choice: ").lower()

        if choice == "q":
            console.print("[dim]Goodbye![/dim]")
            sys.exit(0)

        elif choice == "n":
            description = get_input("Task description: ")
            if description:
                run_claude_command("discuss", description)
            input("\nPress Enter to continue...")

        elif choice == "s":
            clear_screen()
            print_header()
            print_task_summary()

            tasks = load_tasks()
            if tasks:
                console.print("[bold]All Tasks:[/bold]")
                for task in tasks:
                    status_icons = {
                        TaskStatus.PENDING: "⚪",
                        TaskStatus.IN_PROGRESS: "🔵",
                        TaskStatus.DONE: "✅",
                        TaskStatus.BLOCKED: "🔴",
                        TaskStatus.FAILED: "❌",
                    }
                    icon = status_icons.get(task.status, "⚪")
                    console.print(f"  {icon} {task.id}: {task.title}")
                console.print()

            input("\nPress Enter to continue...")

        elif choice == "v":
            tasks = load_tasks()
            in_progress = [t for t in tasks if t.status == TaskStatus.IN_PROGRESS]

            if not in_progress:
                console.print("[yellow]No tasks in progress to verify.[/yellow]")
            else:
                console.print("[bold]Tasks to verify:[/bold]")
                for i, task in enumerate(in_progress, 1):
                    console.print(f"  {i}. {task.id}: {task.title}")

                task_choice = get_input("Task number (or Enter to cancel): ")
                if task_choice.isdigit():
                    idx = int(task_choice) - 1
                    if 0 <= idx < len(in_progress):
                        task = in_progress[idx]
                        run_claude_command("verify", task.id)

            input("\nPress Enter to continue...")

        elif choice == "a":
            pending = get_pending_specs()

            if not pending:
                console.print("[yellow]No specs pending approval.[/yellow]")
            else:
                console.print("[bold]Specs to approve:[/bold]")
                for i, spec in enumerate(pending, 1):
                    console.print(f"  {i}. {spec.name}: {spec.title}")

                spec_choice = get_input("Spec number (or Enter to cancel): ")
                if spec_choice.isdigit():
                    idx = int(spec_choice) - 1
                    if 0 <= idx < len(pending):
                        spec = pending[idx]
                        run_claude_command("approve_spec", spec.name)

            input("\nPress Enter to continue...")

        else:
            console.print(f"[red]Unknown command: {choice}[/red]")
            input("\nPress Enter to continue...")
