"""ADW CLI - AI Developer Workflow CLI.

Main entry point for the adw command.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import click
from rich.console import Console

from . import __version__
from .dashboard import run_dashboard
from .detect import detect_project, get_project_summary, is_monorepo
from .init import init_project, print_init_summary
from .specs import get_pending_specs, load_all_specs
from .tasks import TaskStatus, get_tasks_summary, load_tasks
from .update import check_for_update, run_update

console = Console()


@click.group(invoke_without_command=True)
@click.option("--version", "-v", is_flag=True, help="Show version and exit")
@click.pass_context
def main(ctx: click.Context, version: bool) -> None:
    """ADW - AI Developer Workflow CLI.

    Orchestrate Claude Code for any project.

    Run without arguments to open the interactive dashboard.
    """
    if version:
        console.print(f"adw version {__version__}")
        return

    if ctx.invoked_subcommand is None:
        # Default: run dashboard
        run_dashboard()


@main.command()
@click.option("--force", "-f", is_flag=True, help="Overwrite existing files")
@click.argument("path", required=False, type=click.Path(exists=True, path_type=Path))
def init(force: bool, path: Path | None) -> None:
    """Initialize ADW in the current project.

    Creates .claude/ directory with commands and agents,
    tasks.md for task tracking, and specs/ for feature specs.

    If CLAUDE.md exists, appends orchestration section.
    Otherwise, generates a new one based on detected project type.
    """
    project_path = path or Path.cwd()

    console.print(f"[bold cyan]Initializing ADW in {project_path.name}[/bold cyan]")
    console.print()

    result = init_project(project_path, force=force)
    print_init_summary(result)


@main.command()
@click.argument("description", nargs=-1)
def new(description: tuple[str, ...]) -> None:
    """Start a new task discussion.

    Opens Claude Code with the /discuss command to plan a new feature.

    \b
    Examples:
        adw new add user authentication
        adw new "implement dark mode"
    """
    desc_str = " ".join(description) if description else ""

    if not desc_str:
        desc_str = click.prompt("Task description")

    if not desc_str:
        console.print("[red]No description provided[/red]")
        return

    console.print(f"[dim]Starting discussion: {desc_str}[/dim]")

    try:
        subprocess.run(["claude", f"/discuss {desc_str}"], check=False)
    except FileNotFoundError:
        console.print("[red]Error: 'claude' command not found.[/red]")
        console.print("Is Claude Code installed? Visit: https://claude.ai/code")


@main.command()
def status() -> None:
    """Show task and spec status overview.

    Displays:
    - Task counts by status
    - Actionable tasks (pending/in_progress)
    - Specs pending approval
    """
    console.print("[bold cyan]ADW Status[/bold cyan]")
    console.print()

    # Project detection
    detections = detect_project()
    if detections:
        project_summary = get_project_summary(detections)
        console.print(f"[dim]Project: {project_summary}[/dim]")
        if is_monorepo():
            console.print("[dim]Type: Monorepo[/dim]")
        console.print()

    # Task summary
    tasks = load_tasks()

    if tasks:
        task_summary = get_tasks_summary(tasks)
        console.print("[bold]Tasks:[/bold]")

        status_display = [
            ("pending", "yellow", task_summary["pending"]),
            ("in_progress", "blue", task_summary["in_progress"]),
            ("done", "green", task_summary["done"]),
            ("blocked", "red", task_summary["blocked"]),
            ("failed", "red bold", task_summary["failed"]),
        ]

        for status_name, style, count in status_display:
            if count > 0:
                label = status_name.replace("_", " ").title()
                console.print(f"  [{style}]{label}: {count}[/{style}]")

        console.print()

        # Actionable tasks
        actionable = [t for t in tasks if t.is_actionable]
        if actionable:
            console.print("[bold]Actionable:[/bold]")
            for task in actionable[:10]:
                icon = "🔵" if task.status == TaskStatus.IN_PROGRESS else "⚪"
                console.print(f"  {icon} {task.id}: {task.title}")
            if len(actionable) > 10:
                console.print(f"  [dim]... and {len(actionable) - 10} more[/dim]")
            console.print()

        # Failed tasks
        failed = [t for t in tasks if t.status == TaskStatus.FAILED]
        if failed:
            console.print("[bold red]Failed:[/bold red]")
            for task in failed:
                console.print(f"  ❌ {task.id}: {task.title}")
            console.print()
    else:
        console.print("[dim]No tasks found. Run 'adw new' to create one.[/dim]")
        console.print()

    # Spec summary
    specs = load_all_specs()
    pending = get_pending_specs()

    if pending:
        console.print(f"[yellow bold]⚠ {len(pending)} spec(s) pending approval:[/yellow bold]")
        for spec in pending:
            console.print(f"  • {spec.name}: {spec.title}")
        console.print()
        console.print("[dim]Run 'adw approve <spec-name>' to approve[/dim]")
    elif specs:
        console.print(f"[dim]{len(specs)} spec(s), none pending approval[/dim]")


@main.command()
@click.argument("task_id", required=False)
def verify(task_id: str | None) -> None:
    """Verify a completed task.

    Opens Claude Code with the /verify command to review
    implementation before committing.

    If no task ID provided, shows list of tasks to verify.
    """
    tasks = load_tasks()
    in_progress = [t for t in tasks if t.status == TaskStatus.IN_PROGRESS]

    if not in_progress:
        console.print("[yellow]No tasks in progress to verify.[/yellow]")
        console.print("[dim]Run 'adw status' to see all tasks.[/dim]")
        return

    if task_id is None:
        console.print("[bold]Tasks to verify:[/bold]")
        for i, task in enumerate(in_progress, 1):
            console.print(f"  {i}. {task.id}: {task.title}")
        console.print()

        choice = click.prompt("Task number", type=int, default=1)
        if 1 <= choice <= len(in_progress):
            task_id = in_progress[choice - 1].id
        else:
            console.print("[red]Invalid choice[/red]")
            return

    console.print(f"[dim]Verifying task: {task_id}[/dim]")

    try:
        subprocess.run(["claude", f"/verify {task_id}"], check=False)
    except FileNotFoundError:
        console.print("[red]Error: 'claude' command not found.[/red]")


@main.command()
@click.argument("spec_name", required=False)
def approve(spec_name: str | None) -> None:
    """Approve a pending spec.

    Opens Claude Code with the /approve_spec command to
    approve the spec and decompose it into tasks.

    If no spec name provided, shows list of pending specs.
    """
    pending = get_pending_specs()

    if not pending:
        console.print("[yellow]No specs pending approval.[/yellow]")
        console.print("[dim]Specs are created during /discuss sessions.[/dim]")
        return

    if spec_name is None:
        console.print("[bold]Specs pending approval:[/bold]")
        for i, spec in enumerate(pending, 1):
            console.print(f"  {i}. {spec.name}: {spec.title}")
        console.print()

        choice = click.prompt("Spec number", type=int, default=1)
        if 1 <= choice <= len(pending):
            spec_name = pending[choice - 1].name
        else:
            console.print("[red]Invalid choice[/red]")
            return

    console.print(f"[dim]Approving spec: {spec_name}[/dim]")

    try:
        subprocess.run(["claude", f"/approve_spec {spec_name}"], check=False)
    except FileNotFoundError:
        console.print("[red]Error: 'claude' command not found.[/red]")


@main.command()
def update() -> None:
    """Update ADW to the latest version.

    Checks PyPI and GitHub for the latest release
    and updates using uv, pipx, or pip.
    """
    run_update()


@main.command()
def doctor() -> None:
    """Check ADW installation health.

    Verifies:
    - ADW version
    - Claude Code availability
    - Project configuration
    - Required directories
    """
    console.print("[bold cyan]ADW Doctor[/bold cyan]")
    console.print()

    # Version
    console.print(f"[green]✓[/green] ADW version: {__version__}")

    # Check for updates
    current, latest = check_for_update()
    if latest and latest > current:
        console.print(f"[yellow]![/yellow] Update available: {current} → {latest}")
    elif latest:
        console.print("[green]✓[/green] Up to date")
    else:
        console.print("[yellow]![/yellow] Could not check for updates")

    # Claude Code
    try:
        result = subprocess.run(
            ["claude", "--version"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            version = result.stdout.strip() or "installed"
            console.print(f"[green]✓[/green] Claude Code: {version}")
        else:
            console.print("[red]✗[/red] Claude Code: not working")
    except FileNotFoundError:
        console.print("[red]✗[/red] Claude Code: not found")
        console.print("  [dim]Install from: https://claude.ai/code[/dim]")

    console.print()

    # Project configuration
    cwd = Path.cwd()
    console.print(f"[bold]Project: {cwd.name}[/bold]")

    # Check directories
    dirs_to_check = [
        (".claude", ".claude/"),
        (".claude/commands", ".claude/commands/"),
        ("specs", "specs/"),
    ]

    for name, path in dirs_to_check:
        full_path = cwd / name
        if full_path.is_dir():
            console.print(f"[green]✓[/green] {path}")
        else:
            console.print(f"[red]✗[/red] {path} [dim](run 'adw init')[/dim]")

    # Check files
    files_to_check = [
        ("tasks.md", "tasks.md"),
        ("CLAUDE.md", "CLAUDE.md"),
    ]

    for name, path in files_to_check:
        full_path = cwd / name
        if full_path.is_file():
            console.print(f"[green]✓[/green] {path}")
        else:
            console.print(f"[red]✗[/red] {path} [dim](run 'adw init')[/dim]")

    # Project detection
    console.print()
    detections = detect_project()
    if detections:
        summary = get_project_summary(detections)
        console.print(f"[green]✓[/green] Detected: {summary}")
    else:
        console.print("[yellow]![/yellow] Could not detect project type")


@main.command("version")
def version_cmd() -> None:
    """Show version information."""
    console.print(f"adw version {__version__}")

    # Also show Python version
    v = sys.version_info
    console.print(f"Python {v.major}.{v.minor}.{v.micro}")


if __name__ == "__main__":
    main()
