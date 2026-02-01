"""ADW CLI - AI Developer Workflow CLI.

Main entry point for the adw command.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import click
from rich.console import Console

import asyncio

from . import __version__
from .dashboard import run_dashboard
from .detect import detect_project, get_project_summary, is_monorepo
from .init import init_project, print_init_summary
from .specs import get_pending_specs, load_all_specs
from .tasks import TaskStatus, get_tasks_summary, load_tasks
from .triggers.cron import run_daemon
from .tui import run_tui
from .update import check_for_update, run_update
from .commands.task_commands import add_task, list_tasks, cancel_task, retry_task
from .commands.monitor_commands import watch_daemon, view_logs
from .commands.completion import setup_completion, TASK_ID, STATUS_CHOICES

console = Console()


def check_for_update_notice() -> None:
    """Check for updates and display notice if available (non-blocking)."""
    try:
        current, latest = check_for_update()
        if latest and latest > current:
            console.print()
            console.print(f"[yellow]⚡ Update available:[/yellow] [dim]{current}[/dim] → [bold cyan]{latest}[/bold cyan]")
            console.print(f"[dim]   Run [/dim][cyan]adw update[/cyan][dim] to upgrade[/dim]")
            console.print()
    except Exception:
        # Silently ignore update check errors
        pass


@click.group(invoke_without_command=True)
@click.option("--version", "-v", is_flag=True, help="Show version and exit")
@click.option("--no-update-check", is_flag=True, help="Skip update check", hidden=True)
@click.pass_context
def main(ctx: click.Context, version: bool, no_update_check: bool) -> None:
    """ADW - AI Developer Workflow CLI.

    Orchestrate Claude Code for any project.

    Run without arguments to open the interactive dashboard.
    """
    if version:
        console.print(f"adw version {__version__}")
        return

    # Check for updates on startup (unless disabled)
    if not no_update_check and ctx.invoked_subcommand not in ("update", "version"):
        check_for_update_notice()

    if ctx.invoked_subcommand is None:
        # Default: run TUI dashboard
        run_tui()


@main.command()
def dashboard() -> None:
    """Open the interactive TUI dashboard."""
    run_tui()


@main.command()
@click.option("--force", "-f", is_flag=True, help="Overwrite existing files")
@click.option("--smart", "-s", is_flag=True, help="Use Claude Code to analyze project (slower but better)")
@click.option("--quick", "-q", is_flag=True, help="Skip analysis, use templates only")
@click.option("--qmd/--no-qmd", default=None, help="Enable/disable qmd semantic search (default: auto-detect)")
@click.argument("path", required=False, type=click.Path(exists=True, path_type=Path))
def init(force: bool, smart: bool, quick: bool, qmd: bool | None, path: Path | None) -> None:
    """Initialize ADW in the current project.

    Creates .claude/ directory with commands and agents,
    tasks.md for task tracking, and specs/ for feature specs.

    Use --smart for Claude Code to analyze your project and generate
    tailored documentation (takes ~30-60 seconds).

    \\b
    Examples:
        adw init              # Standard init with detection
        adw init --smart      # Deep analysis with Claude Code
        adw init --quick      # Fast init, templates only
    """
    project_path = path or Path.cwd()

    console.print(f"[bold cyan]Initializing ADW in {project_path.name}[/bold cyan]")
    console.print()

    if smart and not quick:
        # Smart init with Claude Code analysis
        from .analyze import (
            analyze_project,
            generate_claude_md_from_analysis,
            generate_architecture_md,
        )
        
        console.print("[dim]🔍 Analyzing project with Claude Code...[/dim]")
        console.print("[dim]   This may take 30-60 seconds[/dim]")
        console.print()
        
        with console.status("[cyan]Analyzing...[/cyan]"):
            analysis = analyze_project(project_path, verbose=True)
        
        if analysis:
            console.print(f"[green]✓ Detected: {analysis.name}[/green]")
            console.print(f"[dim]  Stack: {', '.join(analysis.stack)}[/dim]")
            console.print(f"[dim]  {len(analysis.structure)} folders, {len(analysis.key_files)} key files[/dim]")
            console.print()
            
            # Generate docs from analysis
            claude_md = generate_claude_md_from_analysis(
                analysis.__dict__, project_path
            )
            architecture_md = generate_architecture_md(
                analysis.__dict__, project_path
            )
            
            # Write generated files
            claude_path = project_path / "CLAUDE.md"
            arch_path = project_path / "ARCHITECTURE.md"
            
            if force or not claude_path.exists():
                claude_path.write_text(claude_md)
                console.print("[green]✓ Generated CLAUDE.md[/green]")
            
            if force or not arch_path.exists():
                arch_path.write_text(architecture_md)
                console.print("[green]✓ Generated ARCHITECTURE.md[/green]")
            
            console.print()
        else:
            console.print("[yellow]⚠ Analysis failed, falling back to detection[/yellow]")
            console.print()

    result = init_project(project_path, force=force, qmd=qmd)
    print_init_summary(result)


@main.command()
@click.option("--full", "-f", is_flag=True, help="Full Claude Code analysis")
@click.argument("path", required=False, type=click.Path(exists=True, path_type=Path))
def refresh(full: bool, path: Path | None) -> None:
    """Refresh project context.

    Re-analyzes the project and updates CLAUDE.md with current state.
    Useful after major changes or when context feels stale.

    \\b
    Examples:
        adw refresh           # Quick detection refresh
        adw refresh --full    # Deep Claude Code analysis
    """
    from .analyze import (
        analyze_project,
        generate_claude_md_from_analysis,
        generate_architecture_md,
    )
    from .detect import detect_project, get_project_summary
    
    project_path = path or Path.cwd()
    claude_md_path = project_path / "CLAUDE.md"
    
    console.print(f"[bold cyan]Refreshing context for {project_path.name}[/bold cyan]")
    console.print()
    
    if full:
        # Deep analysis with Claude Code
        console.print("[dim]🔍 Running deep analysis with Claude Code...[/dim]")
        
        with console.status("[cyan]Analyzing...[/cyan]"):
            analysis = analyze_project(project_path, verbose=True)
        
        if analysis:
            console.print(f"[green]✓ Analysis complete[/green]")
            console.print(f"[dim]  Stack: {', '.join(analysis.stack)}[/dim]")
            
            # Generate and write updated docs
            claude_md = generate_claude_md_from_analysis(
                analysis.__dict__, project_path
            )
            claude_md_path.write_text(claude_md)
            console.print("[green]✓ Updated CLAUDE.md[/green]")
            
            # Also update ARCHITECTURE.md
            arch_md = generate_architecture_md(analysis.__dict__, project_path)
            (project_path / "ARCHITECTURE.md").write_text(arch_md)
            console.print("[green]✓ Updated ARCHITECTURE.md[/green]")
        else:
            console.print("[red]✗ Analysis failed[/red]")
    else:
        # Quick detection refresh
        console.print("[dim]🔍 Quick detection...[/dim]")
        
        detections = detect_project(project_path)
        
        if detections:
            summary = get_project_summary(detections)
            console.print(f"[green]✓ Detected: {summary}[/green]")
            
            # Update CLAUDE.md with new detection
            from .init import generate_claude_md
            content = generate_claude_md(detections, project_path)
            claude_md_path.write_text(content)
            console.print("[green]✓ Updated CLAUDE.md[/green]")
        else:
            console.print("[yellow]No stack detected — try 'adw refresh --full' for deep analysis[/yellow]")
    
    console.print()
    console.print("[dim]Tip: Run 'adw refresh --full' for comprehensive analysis[/dim]")


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


# ============== New Task Management Commands ==============


@main.command("add")
@click.argument("description", nargs=-1, required=True)
@click.option("--priority", "-p", type=click.Choice(["high", "medium", "low"]), help="Task priority")
@click.option("--tag", "-t", "tags", multiple=True, help="Add tags (can use multiple times)")
def add_cmd(description: tuple[str, ...], priority: str | None, tags: tuple[str, ...]) -> None:
    """Add a new task to tasks.md.

    Quick way to add a task without starting a discussion.

    \\b
    Examples:
        adw add "implement user auth"
        adw add fix login bug --priority high
        adw add refactor api -t backend -t urgent
    """
    desc_str = " ".join(description)
    add_task(desc_str, priority=priority, tags=list(tags) if tags else None)


@main.command("list")
@click.option("--status", "-s", type=STATUS_CHOICES, help="Filter by status")
@click.option("--all", "-a", "show_all", is_flag=True, help="Show completed tasks too")
def list_cmd(status: str | None, show_all: bool) -> None:
    """List all tasks from tasks.md.

    Shows pending and running tasks by default.
    Use --all to include completed tasks.

    \\b
    Examples:
        adw list                 # Show pending & running
        adw list --all           # Show all including done
        adw list -s failed       # Show only failed tasks
        adw list -s running      # Show only running tasks
    """
    list_tasks(status_filter=status, show_all=show_all)


@main.command("cancel")
@click.argument("task_id", type=TASK_ID)
@click.confirmation_option(prompt="Are you sure you want to cancel this task?")
def cancel_cmd(task_id: str) -> None:
    """Cancel a task.

    Marks the task as failed with 'Cancelled by user' reason.
    Use task ID (TASK-001) or ADW ID (abc12345).

    \\b
    Examples:
        adw cancel TASK-001
        adw cancel abc12345
    """
    cancel_task(task_id)


@main.command("retry")
@click.argument("task_id", type=TASK_ID)
def retry_cmd(task_id: str) -> None:
    """Retry a failed task.

    Resets the task status to pending so it can be picked up again.

    \\b
    Examples:
        adw retry TASK-001
        adw retry abc12345
    """
    retry_task(task_id)


# ============== Monitoring Commands ==============


@main.command("watch")
@click.option("--once", is_flag=True, help="Show status once and exit")
def watch_cmd(once: bool) -> None:
    """Watch daemon activity in real-time.

    Shows running tasks and their status, updating live.
    Press Ctrl+C to stop.

    \\b
    Examples:
        adw watch              # Live watch
        adw watch --once       # Show status and exit
    """
    watch_daemon(follow=not once)


@main.command("logs")
@click.argument("task_id", type=TASK_ID)
@click.option("--follow", "-f", is_flag=True, help="Follow logs (like tail -f)")
@click.option("--lines", "-n", type=int, default=50, help="Number of lines to show")
def logs_cmd(task_id: str, follow: bool, lines: int) -> None:
    """View logs for a specific task.

    Shows agent output and state for the given task.

    \\b
    Examples:
        adw logs TASK-001
        adw logs abc12345 -f      # Follow logs
        adw logs TASK-001 -n 100  # Show last 100 lines
    """
    view_logs(task_id, follow=follow, lines=lines)


# ============== Daemon Control ==============


@main.command("pause")
def pause_cmd() -> None:
    """Pause the running daemon.

    Stops spawning new tasks while letting running tasks complete.
    Use 'adw resume' to continue.

    \\b
    Examples:
        adw pause    # Pause task spawning
    """
    from .daemon_state import read_state, request_pause, DaemonStatus
    
    state = read_state()
    
    if state.status == DaemonStatus.STOPPED:
        console.print("[yellow]Daemon is not running[/yellow]")
        console.print("[dim]Start it with 'adw run'[/dim]")
        return
    
    if state.status == DaemonStatus.PAUSED:
        console.print("[yellow]Daemon is already paused[/yellow]")
        return
    
    if request_pause():
        console.print("[green]⏸️  Daemon paused[/green]")
        console.print("[dim]Running tasks will continue. No new tasks will start.[/dim]")
        console.print("[dim]Use 'adw resume' to continue.[/dim]")
    else:
        console.print("[red]Failed to pause daemon[/red]")


@main.command("resume")
def resume_cmd() -> None:
    """Resume a paused daemon.

    Continues spawning new tasks after a pause.

    \\b
    Examples:
        adw resume    # Resume task spawning
    """
    from .daemon_state import read_state, request_resume, DaemonStatus
    
    state = read_state()
    
    if state.status == DaemonStatus.STOPPED:
        console.print("[yellow]Daemon is not running[/yellow]")
        console.print("[dim]Start it with 'adw run'[/dim]")
        return
    
    if state.status == DaemonStatus.RUNNING:
        console.print("[yellow]Daemon is already running[/yellow]")
        return
    
    if request_resume():
        console.print("[green]▶️  Daemon resumed[/green]")
    else:
        console.print("[red]Failed to resume daemon[/red]")


@main.command("status")
def status_cmd() -> None:
    """Show daemon status.

    Displays whether the daemon is running, paused, or stopped,
    along with task statistics.

    \\b
    Examples:
        adw status
    """
    from .daemon_state import read_state, DaemonStatus
    
    state = read_state()
    
    # Status indicator
    if state.status == DaemonStatus.RUNNING:
        status_text = "[green]● Running[/green]"
    elif state.status == DaemonStatus.PAUSED:
        status_text = "[yellow]⏸ Paused[/yellow]"
    else:
        status_text = "[dim]○ Stopped[/dim]"
    
    console.print(f"[bold]Daemon Status:[/bold] {status_text}")
    
    if state.pid:
        console.print(f"[dim]PID: {state.pid}[/dim]")
    
    if state.started_at:
        console.print(f"[dim]Started: {state.started_at}[/dim]")
    
    if state.paused_at:
        console.print(f"[dim]Paused: {state.paused_at}[/dim]")
    
    console.print()
    
    # Task stats
    console.print("[bold]Tasks:[/bold]")
    console.print(f"  Running:   {len(state.running_tasks)}")
    console.print(f"  Pending:   {state.pending_count}")
    console.print(f"  Completed: {state.completed_count}")
    console.print(f"  Failed:    {state.failed_count}")
    
    # Show running tasks
    if state.running_tasks:
        console.print()
        console.print("[bold]Currently Running:[/bold]")
        for task in state.running_tasks:
            adw_id = task.get("adw_id", "?")[:8]
            desc = task.get("description", "Unknown")[:50]
            console.print(f"  [{adw_id}] {desc}")


@main.command("history")
@click.option("--days", "-d", type=int, default=7, help="Number of days to show")
@click.option("--failed", "-f", is_flag=True, help="Show only failed tasks")
@click.option("--all", "-a", "show_all", is_flag=True, help="Show all history")
def history_cmd(days: int, failed: bool, show_all: bool) -> None:
    """View task history.

    Shows completed and failed tasks from history.md.

    \\b
    Examples:
        adw history           # Last 7 days
        adw history -d 30     # Last 30 days
        adw history -f        # Failed tasks only
        adw history -a        # All history
    """
    from datetime import datetime, timedelta
    from pathlib import Path
    
    history_path = Path.cwd() / "history.md"
    
    if not history_path.exists():
        console.print("[yellow]No history found[/yellow]")
        console.print("[dim]Complete some tasks first![/dim]")
        return
    
    content = history_path.read_text()
    lines = content.split("\n")
    
    # Parse history
    current_date = None
    cutoff = datetime.now() - timedelta(days=days) if not show_all else None
    
    completed_count = 0
    failed_count = 0
    displayed = []
    
    for line in lines:
        # Check for date header
        if line.startswith("## "):
            date_str = line[3:].strip()
            try:
                current_date = datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                current_date = None
            continue
        
        if not line.startswith("- "):
            continue
        
        # Check date cutoff
        if cutoff and current_date and current_date < cutoff:
            continue
        
        # Count and filter
        is_failed = "❌" in line
        is_completed = "✅" in line
        
        if is_failed:
            failed_count += 1
        elif is_completed:
            completed_count += 1
        
        if failed and not is_failed:
            continue
        
        displayed.append((current_date, line))
    
    # Display
    console.print(f"[bold]Task History[/bold]")
    if not show_all:
        console.print(f"[dim]Last {days} days — {completed_count} completed, {failed_count} failed[/dim]")
    else:
        console.print(f"[dim]All time — {completed_count} completed, {failed_count} failed[/dim]")
    console.print()
    
    if not displayed:
        console.print("[dim]No tasks found matching criteria[/dim]")
        return
    
    # Group by date
    current_header = None
    for date, line in displayed:
        date_str = date.strftime("%Y-%m-%d") if date else "Unknown"
        if date_str != current_header:
            current_header = date_str
            console.print(f"\n[bold]{date_str}[/bold]")
        
        # Format line nicely
        if "✅" in line:
            console.print(f"  [green]{line[2:]}[/green]")
        elif "❌" in line:
            console.print(f"  [red]{line[2:]}[/red]")
        else:
            console.print(f"  {line[2:]}")


# ============== Shell Completion ==============


@main.command("completion")
@click.argument("shell", type=click.Choice(["bash", "zsh", "fish"]), required=False)
def completion_cmd(shell: str | None) -> None:
    """Generate shell completion script.

    Outputs a script that enables tab completion for adw commands.
    Add to your shell config to enable.

    \\b
    Examples:
        # Bash (add to ~/.bashrc)
        eval "$(adw completion bash)"

        # Zsh (add to ~/.zshrc)
        eval "$(adw completion zsh)"

        # Fish (save to completions)
        adw completion fish > ~/.config/fish/completions/adw.fish
    """
    script = setup_completion(shell)
    click.echo(script)


@main.group()
def worktree() -> None:
    """Manage git worktrees for parallel task execution.

    Worktrees allow multiple branches to be checked out simultaneously,
    enabling agents to work in isolated environments.
    """
    pass


@worktree.command("list")
def worktree_list() -> None:
    """List all git worktrees."""
    from .agent.worktree import list_worktrees

    worktrees = list_worktrees()

    if not worktrees:
        console.print("[yellow]No worktrees found.[/yellow]")
        console.print("[dim]Run 'adw worktree create <name>' to create one.[/dim]")
        return

    console.print("[bold cyan]Git Worktrees:[/bold cyan]")
    console.print()

    for wt in worktrees:
        path = wt.get("path", "")
        branch = wt.get("branch", "detached HEAD")
        commit = wt.get("commit", "unknown")[:8]

        # Mark main worktree
        is_main = Path(path) == Path.cwd()
        marker = "[bold yellow](main)[/bold yellow]" if is_main else ""

        console.print(f"[bold]{path}[/bold] {marker}")
        console.print(f"  Branch: {branch}")
        console.print(f"  Commit: {commit}")
        console.print()


@worktree.command("create")
@click.argument("name")
@click.option("--branch", "-b", help="Branch name (default: adw-<name>)")
def worktree_create(name: str, branch: str | None) -> None:
    """Create a new git worktree.

    Creates a worktree in the trees/ directory with an isolated
    branch for parallel task execution.

    \b
    Examples:
        adw worktree create phase-01
        adw worktree create bugfix --branch fix-login
    """
    from .agent.worktree import create_worktree

    console.print(f"[dim]Creating worktree: {name}[/dim]")

    worktree_path = create_worktree(name, branch_name=branch)

    if worktree_path:
        console.print()
        console.print(f"[green]✓[/green] Worktree created at: {worktree_path}")
        console.print()
        console.print(f"[dim]To work in this worktree:[/dim]")
        console.print(f"[dim]  cd {worktree_path}[/dim]")
    else:
        console.print("[red]Failed to create worktree[/red]")


@worktree.command("remove")
@click.argument("name")
@click.option("--force", "-f", is_flag=True, help="Force removal even if there are changes")
def worktree_remove(name: str, force: bool) -> None:
    """Remove a git worktree.

    Removes the specified worktree and cleans up git references.

    \b
    Examples:
        adw worktree remove phase-01
        adw worktree remove bugfix --force
    """
    from .agent.worktree import remove_worktree

    console.print(f"[dim]Removing worktree: {name}[/dim]")

    success = remove_worktree(name, force=force)

    if not success:
        console.print()
        console.print("[yellow]Tip: Use --force to remove worktree with uncommitted changes[/yellow]")


@main.group()
def github() -> None:
    """GitHub integration commands.

    Trigger workflows from GitHub issues, watch repositories,
    and create pull requests automatically.
    """
    pass


@github.command("watch")
@click.option(
    "--label",
    "-l",
    default="adw",
    help="GitHub issue label to watch (default: adw)",
)
@click.option(
    "--interval",
    "-i",
    type=int,
    default=300,
    help="Seconds between checks (default: 300)",
)
@click.option(
    "--dry-run",
    "-d",
    is_flag=True,
    help="Show what would be processed without executing",
)
def github_watch(label: str, interval: int, dry_run: bool) -> None:
    """Watch GitHub issues and trigger workflows.

    Continuously polls GitHub for open issues with the specified label
    and spawns agents to work on them using the standard workflow.

    \b
    Examples:
        adw github watch                    # Watch for 'adw' label
        adw github watch -l feature         # Watch for 'feature' label
        adw github watch -i 60              # Check every 60 seconds
        adw github watch --dry-run          # See what would run

    Press Ctrl+C to stop watching.
    """
    from .triggers.github import run_github_cron

    console.print("[bold cyan]Starting GitHub issue watcher[/bold cyan]")
    console.print()
    console.print(f"[dim]Label: {label}[/dim]")
    console.print(f"[dim]Check interval: {interval}s[/dim]")
    if dry_run:
        console.print("[yellow]DRY RUN MODE[/yellow]")
    console.print()
    console.print("[yellow]Press Ctrl+C to stop[/yellow]")
    console.print()

    try:
        run_github_cron(label=label, interval=interval, dry_run=dry_run)
    except KeyboardInterrupt:
        console.print()
        console.print("[yellow]Watcher stopped by user[/yellow]")


@github.command("process")
@click.argument("issue_number", type=int)
@click.option(
    "--dry-run",
    "-d",
    is_flag=True,
    help="Show what would be processed without executing",
)
def github_process(issue_number: int, dry_run: bool) -> None:
    """Process a specific GitHub issue.

    Fetches the issue details and spawns an agent to work on it
    using the standard workflow (plan, implement, update).

    \b
    Examples:
        adw github process 123              # Process issue #123
        adw github process 456 --dry-run    # See details without running
    """
    from .agent.executor import generate_adw_id
    from .integrations.github import get_issue, add_issue_comment
    from .workflows.standard import run_standard_workflow

    console.print(f"[bold cyan]Processing GitHub issue #{issue_number}[/bold cyan]")
    console.print()

    # Fetch issue
    console.print("[dim]Fetching issue details...[/dim]")
    issue = get_issue(issue_number)

    if not issue:
        console.print(f"[red]Error: Issue #{issue_number} not found[/red]")
        console.print("[dim]Make sure you're in a GitHub repository with 'gh' CLI configured[/dim]")
        return

    console.print(f"[bold]Title:[/bold] {issue.title}")
    console.print(f"[bold]State:[/bold] {issue.state}")
    console.print(f"[bold]Labels:[/bold] {', '.join(issue.labels) if issue.labels else 'none'}")
    console.print()

    if issue.state != "OPEN":
        console.print(f"[yellow]Warning: Issue is {issue.state.lower()}[/yellow]")
        if not click.confirm("Continue anyway?"):
            return

    adw_id = generate_adw_id()

    if dry_run:
        console.print(f"[yellow]DRY RUN: Would process with ADW ID {adw_id}[/yellow]")
        console.print(f"[dim]Worktree: issue-{issue_number}-{adw_id}[/dim]")
        return

    console.print(f"[dim]ADW ID: {adw_id}[/dim]")
    console.print()

    # Add comment to issue
    add_issue_comment(
        issue_number,
        f"🤖 ADW is working on this issue.\n\n**ADW ID**: `{adw_id}`",
        adw_id,
    )

    # Run workflow
    worktree_name = f"issue-{issue_number}-{adw_id}"
    console.print(f"[dim]Running standard workflow in worktree: {worktree_name}[/dim]")
    console.print()

    success = run_standard_workflow(
        task_description=f"{issue.title}\n\n{issue.body}",
        worktree_name=worktree_name,
        adw_id=adw_id,
    )

    # Update issue with result
    if success:
        console.print()
        console.print("[green]✓ Workflow completed successfully[/green]")
        add_issue_comment(
            issue_number,
            f"✅ Implementation complete!\n\nADW ID: `{adw_id}`\n\nPlease review the PR.",
            adw_id,
        )
    else:
        console.print()
        console.print("[red]✗ Workflow failed[/red]")
        console.print(f"[dim]Check logs in agents/{adw_id}/[/dim]")
        add_issue_comment(
            issue_number,
            f"❌ Implementation failed.\n\nADW ID: `{adw_id}`\n\nCheck logs in `agents/{adw_id}/`",
            adw_id,
        )


@main.command()
@click.option(
    "--poll-interval",
    "-p",
    type=float,
    default=5.0,
    help="Seconds between task checks (default: 5.0)",
)
@click.option(
    "--max-concurrent",
    "-m",
    type=int,
    default=3,
    help="Maximum simultaneous agents (default: 3)",
)
@click.option(
    "--tasks-file",
    "-f",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Path to tasks.md (default: ./tasks.md)",
)
@click.option(
    "--dry-run",
    "-d",
    is_flag=True,
    help="Show eligible tasks without executing them",
)
@click.option(
    "--no-notifications",
    is_flag=True,
    help="Disable desktop notifications",
)
def run(
    poll_interval: float,
    max_concurrent: int,
    tasks_file: Path | None,
    dry_run: bool,
    no_notifications: bool,
) -> None:
    """Start autonomous task execution daemon.

    Monitors tasks.md for eligible tasks and spawns agents
    to execute them automatically. Tasks are picked up based on:

    - Status (pending tasks only)
    - Dependencies (blocked tasks wait for dependencies)
    - Concurrency limits (max-concurrent setting)

    \b
    Examples:
        adw run                    # Start with defaults
        adw run -m 5              # Allow 5 concurrent agents
        adw run -p 10             # Poll every 10 seconds
        adw run --dry-run         # See what would run

    Press Ctrl+C to stop the daemon gracefully.
    """
    tasks_path = tasks_file or Path.cwd() / "tasks.md"

    if dry_run:
        # Import here to avoid loading heavy deps for simple commands
        from .agent.task_parser import get_eligible_tasks

        console.print("[bold cyan]Dry run - eligible tasks:[/bold cyan]")
        console.print()

        eligible = get_eligible_tasks(tasks_path)

        if not eligible:
            console.print("[yellow]No eligible tasks found.[/yellow]")
            console.print("[dim]Tasks must be pending and not blocked by dependencies.[/dim]")
            return

        console.print(f"[bold]Found {len(eligible)} eligible task(s):[/bold]")
        for i, task in enumerate(eligible[:max_concurrent], 1):
            model = task.model or "sonnet"
            console.print(f"  {i}. {task.description}")
            console.print(f"     [dim]Model: {model}[/dim]")
            if task.worktree_name:
                console.print(f"     [dim]Worktree: {task.worktree_name}[/dim]")

        if len(eligible) > max_concurrent:
            console.print()
            console.print(f"[dim]... and {len(eligible) - max_concurrent} more (would queue)[/dim]")

        return

    # Run the daemon
    console.print("[bold cyan]Starting ADW autonomous execution daemon[/bold cyan]")
    console.print()
    console.print(f"[dim]Tasks file: {tasks_path}[/dim]")
    console.print(f"[dim]Poll interval: {poll_interval}s[/dim]")
    console.print(f"[dim]Max concurrent: {max_concurrent}[/dim]")
    console.print()
    console.print("[yellow]Press Ctrl+C to stop[/yellow]")
    console.print()

    try:
        asyncio.run(
            run_daemon(
                tasks_file=tasks_path,
                poll_interval=poll_interval,
                max_concurrent=max_concurrent,
                notifications=not no_notifications,
            )
        )
    except KeyboardInterrupt:
        console.print()
        console.print("[yellow]Daemon stopped by user[/yellow]")


@main.group()
def webhook() -> None:
    """Webhook management commands.
    
    Configure webhooks to get Slack/Discord/HTTP notifications
    when tasks complete or fail.
    """
    pass


@webhook.command("test")
@click.argument("url")
@click.option(
    "--event",
    "-e",
    type=click.Choice(["completed", "failed", "started"]),
    default="completed",
    help="Event type to simulate",
)
def webhook_test(url: str, event: str) -> None:
    """Test a webhook URL.
    
    Sends a test event to verify your webhook is working.
    
    \b
    Examples:
        adw webhook test https://hooks.slack.com/services/...
        adw webhook test https://discord.com/api/webhooks/... -e failed
    """
    from .webhooks import WebhookConfig, detect_webhook_type, send_webhook
    
    webhook_type = detect_webhook_type(url)
    config = WebhookConfig(
        url=url,
        type=webhook_type,
        events=["task_started", "task_completed", "task_failed"],
    )
    
    event_name = f"task_{event}"
    test_data = {
        "adw_id": "test1234",
        "description": "This is a test event from ADW CLI",
        "error": "Simulated failure" if event == "failed" else None,
        "return_code": 1 if event == "failed" else 0,
    }
    
    console.print(f"[dim]Detected type: {webhook_type.value}[/dim]")
    console.print(f"[dim]Sending {event_name} event...[/dim]")
    
    success = send_webhook(config, event_name, test_data)
    
    if success:
        console.print(f"[green]✓ Webhook sent successfully[/green]")
    else:
        console.print(f"[red]✗ Failed to send webhook[/red]")
        console.print("[dim]Check the URL and try again[/dim]")


@webhook.command("show")
def webhook_show() -> None:
    """Show current webhook configuration.
    
    Displays webhook URL from environment variable (ADW_WEBHOOK_URL).
    """
    import os
    
    url = os.environ.get("ADW_WEBHOOK_URL")
    events = os.environ.get("ADW_WEBHOOK_EVENTS", "task_completed,task_failed")
    
    if not url:
        console.print("[yellow]No webhook configured[/yellow]")
        console.print()
        console.print("[dim]To configure, set environment variables:[/dim]")
        console.print("  [cyan]export ADW_WEBHOOK_URL='https://...'[/cyan]")
        console.print("  [cyan]export ADW_WEBHOOK_EVENTS='task_completed,task_failed'[/cyan]")
        return
    
    from .webhooks import detect_webhook_type
    
    webhook_type = detect_webhook_type(url)
    
    # Mask URL for security
    masked = url[:30] + "..." if len(url) > 35 else url
    
    console.print(f"[bold]URL:[/bold] {masked}")
    console.print(f"[bold]Type:[/bold] {webhook_type.value}")
    console.print(f"[bold]Events:[/bold] {events}")


@main.command()
@click.option(
    "--sound",
    "-s",
    type=click.Choice(["glass", "basso", "ping", "pop", "hero", "none"]),
    default="glass",
    help="Notification sound (default: glass)",
)
@click.argument("message", required=False, default="Test notification from ADW")
def notify(sound: str, message: str) -> None:
    """Test desktop notifications.
    
    Sends a test notification to verify macOS notifications are working.
    
    \b
    Examples:
        adw notify                          # Default test
        adw notify "Task completed!"        # Custom message
        adw notify -s basso "Failed!"       # With error sound
    """
    from .notifications import send_notification, NotificationSound, is_macos
    
    if not is_macos():
        console.print("[red]Desktop notifications are only supported on macOS[/red]")
        return
    
    sound_map = {
        "glass": NotificationSound.GLASS,
        "basso": NotificationSound.BASSO,
        "ping": NotificationSound.PING,
        "pop": NotificationSound.POP,
        "hero": NotificationSound.HERO,
        "none": NotificationSound.NONE,
    }
    
    console.print(f"[dim]Sending notification: {message}[/dim]")
    
    success = send_notification(
        title="🔔 ADW Notification",
        message=message,
        sound=sound_map.get(sound, NotificationSound.GLASS),
    )
    
    if success:
        console.print("[green]✓ Notification sent[/green]")
    else:
        console.print("[red]✗ Failed to send notification[/red]")
        console.print("[dim]Check System Preferences > Notifications[/dim]")


# =============================================================================
# Plugin System
# =============================================================================


@main.group()
def plugin() -> None:
    """Manage ADW plugins.

    Plugins extend ADW with additional features like semantic search,
    GitHub integration, notifications, and more.

    \\b
    Examples:
        adw plugin list                  # Show installed plugins
        adw plugin install qmd           # Install a plugin
        adw plugin remove qmd            # Uninstall
    """
    pass


@plugin.command("list")
def plugin_list() -> None:
    """List installed plugins."""
    from .plugins import get_plugin_manager
    
    manager = get_plugin_manager()
    plugins = manager.all
    
    if not plugins:
        console.print("[yellow]No plugins installed[/yellow]")
        console.print()
        console.print("[dim]Available plugins:[/dim]")
        console.print("  • qmd - Semantic search and context injection")
        console.print()
        console.print("[dim]Install with: adw plugin install <name>[/dim]")
        return
    
    console.print("[bold cyan]Installed Plugins:[/bold cyan]")
    console.print()
    
    for p in plugins:
        status_icon = "[green]✓[/green]" if p.enabled else "[yellow]○[/yellow]"
        console.print(f"{status_icon} [bold]{p.name}[/bold] v{p.version}")
        if p.description:
            console.print(f"   [dim]{p.description}[/dim]")


@plugin.command("install")
@click.argument("name")
def plugin_install(name: str) -> None:
    """Install a plugin.

    \\b
    Examples:
        adw plugin install qmd           # Built-in plugin
        adw plugin install ./my-plugin   # From local path
        adw plugin install gh:user/repo  # From GitHub
    """
    from .plugins import get_plugin_manager
    
    manager = get_plugin_manager()
    
    console.print(f"[dim]Installing {name}...[/dim]")
    
    success, message = manager.install(name)
    
    if success:
        console.print(f"[green]✓ {message}[/green]")
    else:
        console.print(f"[red]✗ {message}[/red]")


@plugin.command("remove")
@click.argument("name")
def plugin_remove(name: str) -> None:
    """Remove a plugin."""
    from .plugins import get_plugin_manager
    
    manager = get_plugin_manager()
    
    success, message = manager.uninstall(name)
    
    if success:
        console.print(f"[green]✓ {message}[/green]")
    else:
        console.print(f"[red]✗ {message}[/red]")


@plugin.command("status")
@click.argument("name", required=False)
def plugin_status(name: str | None) -> None:
    """Show plugin status."""
    from .plugins import get_plugin_manager
    
    manager = get_plugin_manager()
    
    if name:
        p = manager.get(name)
        if not p:
            console.print(f"[red]Plugin '{name}' not found[/red]")
            return
        
        status = p.status()
        console.print(f"[bold]{status['name']}[/bold] v{status['version']}")
        console.print()
        for key, value in status.items():
            if key not in ("name", "version"):
                console.print(f"  {key}: {value}")
    else:
        plugins = manager.all
        for p in plugins:
            status = p.status()
            enabled = "[green]enabled[/green]" if status.get("enabled") else "[yellow]disabled[/yellow]"
            console.print(f"[bold]{p.name}[/bold]: {enabled}")


# =============================================================================
# QMD Commands (via plugin, kept for backward compatibility)
# =============================================================================

def _register_plugin_commands():
    """Register commands from enabled plugins."""
    try:
        from .plugins import get_plugin_manager
        manager = get_plugin_manager()
        
        for plugin in manager.enabled:
            for cmd in plugin.get_commands():
                main.add_command(cmd)
    except Exception:
        # Don't crash if plugin loading fails
        pass


# Register plugin commands at import time
_register_plugin_commands()


if __name__ == "__main__":
    main()
