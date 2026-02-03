"""ADW CLI - AI Developer Workflow CLI.

Main entry point for the adw command.
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import click
from rich.console import Console

from . import __version__
from .commands.completion import STATUS_CHOICES, TASK_ID, setup_completion
from .commands.monitor_commands import view_logs, watch_daemon
from .commands.task_commands import add_task, cancel_task, list_tasks, retry_task
from .dashboard import run_dashboard
from .detect import detect_project, get_project_summary, is_monorepo
from .init import init_project, print_init_summary
from .specs import get_pending_specs, load_all_specs
from .tasks import TaskStatus, get_tasks_summary, load_tasks
from .triggers.cron import run_daemon
from .tui import run_tui
from .update import check_for_update, run_update

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
            generate_architecture_md,
            generate_claude_md_from_analysis,
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
        generate_architecture_md,
        generate_claude_md_from_analysis,
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
    from .daemon_state import DaemonStatus, read_state, request_pause
    
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
    from .daemon_state import DaemonStatus, read_state, request_resume
    
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
    from .daemon_state import DaemonStatus, read_state
    
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
    from .integrations.github import add_issue_comment, get_issue
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


@github.command("watch-pr")
@click.argument("pr_number", type=int)
@click.option(
    "--interval",
    "-i",
    type=int,
    default=60,
    help="Seconds between checks (default: 60)",
)
@click.option(
    "--auto-fix",
    "-a",
    is_flag=True,
    help="Automatically fix actionable comments",
)
@click.option(
    "--dry-run",
    "-d",
    is_flag=True,
    help="Show comments without fixing",
)
def github_watch_pr(pr_number: int, interval: int, auto_fix: bool, dry_run: bool) -> None:
    """Watch a PR for review comments.

    Monitors a pull request for new review comments and can
    automatically implement requested changes.

    \\b
    Examples:
        adw github watch-pr 123              # Watch PR #123
        adw github watch-pr 123 --auto-fix   # Auto-fix comments
        adw github watch-pr 123 --dry-run    # Show without fixing
    """
    from .github import PRReviewWatcher, CommentParser, apply_review_fixes
    from .agent.executor import generate_adw_id

    console.print(f"[bold cyan]Watching PR #{pr_number}[/bold cyan]")
    console.print()
    console.print(f"[dim]Check interval: {interval}s[/dim]")
    if auto_fix:
        console.print("[yellow]Auto-fix enabled[/yellow]")
    if dry_run:
        console.print("[yellow]DRY RUN MODE[/yellow]")
    console.print()
    console.print("[yellow]Press Ctrl+C to stop[/yellow]")
    console.print()

    # Create watcher with state file
    state_file = Path.cwd() / ".adw" / "pr_watchers" / f"pr-{pr_number}.json"
    watcher = PRReviewWatcher(
        pr_number=pr_number,
        state_file=state_file,
    )

    try:
        import time

        while True:
            # Check PR status
            info = watcher.get_pr_info()
            if not info:
                console.print(f"[red]Could not get PR info[/red]")
                time.sleep(interval)
                continue

            if info.state.value in ("closed", "merged"):
                console.print(f"[yellow]PR is {info.state.value}, stopping watcher[/yellow]")
                break

            # Get new comments
            new_comments = watcher.get_new_comments()

            if new_comments:
                console.print(f"[cyan]Found {len(new_comments)} new comment(s)[/cyan]")

                # Parse comments
                parser = CommentParser(comments=new_comments)
                actionable = parser.get_actionable()

                if actionable:
                    console.print(f"[bold]{len(actionable)} actionable comment(s):[/bold]")
                    for c in actionable:
                        console.print(f"  • {c.action_description[:60]}...")

                    if auto_fix and not dry_run:
                        adw_id = generate_adw_id()
                        console.print(f"[dim]Applying fixes (ADW ID: {adw_id})...[/dim]")

                        results = apply_review_fixes(
                            pr_number=pr_number,
                            comments=actionable,
                            working_dir=Path.cwd(),
                            adw_id=adw_id,
                        )

                        for result in results:
                            if result.success:
                                console.print(f"[green]✓ Fixed comment {result.comment_id}[/green]")
                            else:
                                console.print(f"[red]✗ Failed: {result.error_message}[/red]")

            time.sleep(interval)

    except KeyboardInterrupt:
        console.print()
        console.print("[yellow]Watcher stopped[/yellow]")


@github.command("fix-comments")
@click.argument("pr_number", type=int)
@click.option(
    "--all",
    "-a",
    "fix_all",
    is_flag=True,
    help="Fix all pending comments (default: only new)",
)
@click.option(
    "--dry-run",
    "-d",
    is_flag=True,
    help="Show what would be fixed without making changes",
)
def github_fix_comments(pr_number: int, fix_all: bool, dry_run: bool) -> None:
    """Fix review comments on a PR.

    Processes actionable review comments and applies fixes.

    \\b
    Examples:
        adw github fix-comments 123           # Fix new comments
        adw github fix-comments 123 --all     # Fix all comments
        adw github fix-comments 123 --dry-run # Show without fixing
    """
    from .github import get_pr_review_comments, CommentParser, apply_review_fixes
    from .agent.executor import generate_adw_id

    console.print(f"[bold cyan]Processing PR #{pr_number} review comments[/bold cyan]")
    console.print()

    # Get comments
    comments = get_pr_review_comments(pr_number)

    if not comments:
        console.print("[yellow]No review comments found[/yellow]")
        return

    # Parse comments
    parser = CommentParser(comments=comments)
    console.print(parser.summary())
    console.print()

    actionable = parser.get_actionable()

    if not actionable:
        console.print("[green]No actionable comments to fix[/green]")
        return

    console.print(f"[bold]Actionable comments ({len(actionable)}):[/bold]")
    for c in actionable:
        priority = f"[{'red' if c.priority.value == 'high' else 'yellow'}]{c.priority.value}[/]"
        console.print(f"  {priority} {c.action_description[:60]}...")
        if c.file_path:
            console.print(f"       [dim]{c.file_path}:{c.line_number or '?'}[/dim]")
    console.print()

    if dry_run:
        console.print("[yellow]DRY RUN: No changes made[/yellow]")
        return

    if not click.confirm("Apply fixes?"):
        return

    adw_id = generate_adw_id()
    console.print(f"[dim]ADW ID: {adw_id}[/dim]")

    results = apply_review_fixes(
        pr_number=pr_number,
        comments=actionable,
        working_dir=Path.cwd(),
        adw_id=adw_id,
    )

    console.print()
    success_count = sum(1 for r in results if r.success)
    console.print(f"[bold]Results: {success_count}/{len(results)} fixed[/bold]")

    for result in results:
        if result.success:
            console.print(f"[green]✓ Fixed (commit {result.commit_hash})[/green]")
        else:
            console.print(f"[red]✗ Failed: {result.error_message}[/red]")


# ============== Human-in-the-Loop Approval Commands ==============


@main.command("approve-task")
@click.argument("task_id")
def approve_task_cmd(task_id: str) -> None:
    """Approve a task awaiting review.

    Approves a task that is waiting for human approval
    before proceeding with implementation.

    \\b
    Examples:
        adw approve-task abc12345
    """
    from .github.approval_gate import approve_task, load_approval_request

    request = load_approval_request(task_id)

    if not request:
        console.print(f"[red]No approval request found for task {task_id}[/red]")
        console.print("[dim]Use 'adw pending-approvals' to see pending requests[/dim]")
        return

    if not request.is_pending:
        console.print(f"[yellow]Task {task_id} is not pending approval[/yellow]")
        console.print(f"[dim]Current status: {request.status.value}[/dim]")
        return

    # Show request details
    console.print(f"[bold]Approving: {request.title}[/bold]")
    console.print()
    console.print(f"[dim]{request.description[:200]}...[/dim]" if len(request.description) > 200 else f"[dim]{request.description}[/dim]")
    console.print()

    if not click.confirm("Approve this task?"):
        return

    result = approve_task(task_id)

    if result:
        console.print()
        console.print(f"[green]✓ Task {task_id} approved[/green]")
    else:
        console.print(f"[red]Failed to approve task[/red]")


@main.command("reject-task")
@click.argument("task_id")
@click.option(
    "--reason",
    "-r",
    required=True,
    help="Reason for rejection",
)
def reject_task_cmd(task_id: str, reason: str) -> None:
    """Reject a task awaiting review.

    Rejects a task with a reason, sending it back to the
    planning phase with the feedback included.

    \\b
    Examples:
        adw reject-task abc12345 -r "Wrong approach"
        adw reject-task abc12345 --reason "Need more error handling"
    """
    from .github.approval_gate import reject_task, load_approval_request

    request = load_approval_request(task_id)

    if not request:
        console.print(f"[red]No approval request found for task {task_id}[/red]")
        return

    if not request.is_pending:
        console.print(f"[yellow]Task {task_id} is not pending approval[/yellow]")
        console.print(f"[dim]Current status: {request.status.value}[/dim]")
        return

    console.print(f"[bold]Rejecting: {request.title}[/bold]")
    console.print(f"[dim]Reason: {reason}[/dim]")
    console.print()

    result = reject_task(task_id, reason)

    if result:
        console.print(f"[yellow]✗ Task {task_id} rejected[/yellow]")
        console.print("[dim]Task will return to planning phase with feedback[/dim]")
    else:
        console.print(f"[red]Failed to reject task[/red]")


@main.command("continue-task")
@click.argument("task_id")
@click.argument("feedback", nargs=-1, required=True)
def continue_task_cmd(task_id: str, feedback: tuple[str, ...]) -> None:
    """Add feedback to a task.

    Adds iterative feedback to a task, which will be included
    in the context when the task is re-run.

    \\b
    Examples:
        adw continue-task abc12345 "Add input validation"
        adw continue-task abc12345 Add more error handling
    """
    from .github.approval_gate import add_continue_prompt, load_approval_request

    feedback_str = " ".join(feedback)

    request = load_approval_request(task_id)

    if not request:
        console.print(f"[red]No approval request found for task {task_id}[/red]")
        return

    result = add_continue_prompt(task_id, feedback_str)

    if result:
        console.print(f"[green]✓ Feedback added to task {task_id}[/green]")
        console.print(f"[dim]Total feedback items: {len(result.continue_prompts)}[/dim]")
    else:
        console.print(f"[red]Failed to add feedback[/red]")


@main.command("pending-approvals")
def pending_approvals_cmd() -> None:
    """List tasks awaiting approval.

    Shows all tasks that are waiting for human review and approval.

    \\b
    Examples:
        adw pending-approvals
    """
    from .github.approval_gate import list_pending_approvals

    pending = list_pending_approvals()

    if not pending:
        console.print("[green]No pending approvals[/green]")
        return

    console.print(f"[bold cyan]Pending Approvals ({len(pending)})[/bold cyan]")
    console.print()

    for request in pending:
        console.print(f"[bold]{request.task_id}[/bold]: {request.title}")
        console.print(f"  [dim]Created: {request.created_at.strftime('%Y-%m-%d %H:%M')}[/dim]")
        if request.expires_at:
            console.print(f"  [dim]Expires: {request.expires_at.strftime('%Y-%m-%d %H:%M')}[/dim]")
        if request.files_to_modify:
            console.print(f"  [dim]Files: {len(request.files_to_modify)}[/dim]")
        console.print()

    console.print("[dim]Use 'adw approve-task <id>' or 'adw reject-task <id> -r <reason>'[/dim]")


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
    from .notifications import NotificationSound, is_macos, send_notification
    
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
# Recovery Commands (Phase 8)
# =============================================================================


@main.command("rollback")
@click.argument("task_id", type=TASK_ID)
@click.option(
    "--checkpoint",
    "-c",
    help="Specific checkpoint ID to rollback to (default: last successful)",
)
@click.option(
    "--all",
    "-a",
    "rollback_all",
    is_flag=True,
    help="Rollback ALL changes made by this task",
)
@click.confirmation_option(prompt="Are you sure you want to rollback? This will discard changes.")
def rollback_cmd(task_id: str, checkpoint: str | None, rollback_all: bool) -> None:
    """Rollback a task to a previous checkpoint.

    Undoes changes made by a task by resetting to a checkpoint.
    By default, rolls back to the last successful checkpoint.

    \\b
    Examples:
        adw rollback abc12345                  # Rollback to last checkpoint
        adw rollback abc12345 -c 20260202T103045  # Rollback to specific checkpoint
        adw rollback abc12345 --all            # Undo ALL task changes
    """
    from .agent.state import ADWState
    from .agent.task_updater import update_task_status
    from .recovery.checkpoints import (
        get_last_successful_checkpoint,
        list_checkpoints,
        load_checkpoint,
        rollback_all_changes,
        rollback_to_checkpoint,
    )

    # Load task state to get worktree path
    state = ADWState.load(task_id)
    worktree_path = Path(state.worktree_path) if state and state.worktree_path else None

    if rollback_all:
        console.print(f"[yellow]Rolling back ALL changes for task {task_id}...[/yellow]")
        success = rollback_all_changes(task_id, worktree_path)
    elif checkpoint:
        cp = load_checkpoint(task_id, checkpoint)
        if not cp:
            console.print(f"[red]Checkpoint '{checkpoint}' not found[/red]")
            console.print("[dim]Use 'adw checkpoints <task_id>' to see available checkpoints[/dim]")
            return
        console.print(f"[yellow]Rolling back to checkpoint {checkpoint}...[/yellow]")
        success = rollback_to_checkpoint(task_id, checkpoint, worktree_path)
    else:
        cp = get_last_successful_checkpoint(task_id)
        if not cp:
            console.print("[red]No successful checkpoints found for this task[/red]")
            console.print("[dim]Use 'adw checkpoints <task_id>' to see available checkpoints[/dim]")
            return
        console.print(f"[yellow]Rolling back to last checkpoint ({cp.checkpoint_id})...[/yellow]")
        success = rollback_to_checkpoint(task_id, cp.checkpoint_id, worktree_path)

    if success:
        console.print("[green]✓ Rollback successful[/green]")
        # Mark task as failed
        try:
            update_task_status(task_id, "failed")
            console.print("[dim]Task marked as failed[/dim]")
        except Exception:
            pass
    else:
        console.print("[red]✗ Rollback failed[/red]")
        console.print("[dim]Check if the task has checkpoints with git commits[/dim]")


@main.command("checkpoints")
@click.argument("task_id", type=TASK_ID)
@click.option("--json", "-j", "as_json", is_flag=True, help="Output as JSON")
def checkpoints_cmd(task_id: str, as_json: bool) -> None:
    """List checkpoints for a task.

    Shows all saved checkpoints, their phases, and status.

    \\b
    Examples:
        adw checkpoints abc12345
        adw checkpoints abc12345 --json
    """
    from .recovery.checkpoints import list_checkpoints

    checkpoints = list_checkpoints(task_id)

    if not checkpoints:
        console.print(f"[yellow]No checkpoints found for task {task_id}[/yellow]")
        return

    if as_json:
        import json
        output = [cp.to_dict() for cp in checkpoints]
        click.echo(json.dumps(output, indent=2))
        return

    console.print(f"[bold cyan]Checkpoints for {task_id}[/bold cyan]")
    console.print()

    for cp in checkpoints:
        status_icon = "[green]✓[/green]" if cp.success else "[red]✗[/red]"
        console.print(f"{status_icon} [bold]{cp.checkpoint_id}[/bold]")
        console.print(f"   Phase: {cp.phase}")
        console.print(f"   Step: {cp.step}")
        console.print(f"   Time: {cp.timestamp}")
        if cp.git_commit:
            console.print(f"   Commit: {cp.git_commit}")
        if cp.files_modified:
            console.print(f"   Files: {len(cp.files_modified)} modified")
        console.print()


@main.command("resume-task")
@click.argument("task_id", type=TASK_ID)
@click.option(
    "--checkpoint",
    "-c",
    help="Resume from specific checkpoint ID (default: last successful)",
)
@click.option(
    "--workflow",
    "-w",
    type=click.Choice(["simple", "standard", "sdlc"]),
    default="standard",
    help="Workflow to use for resumption (default: standard)",
)
def resume_task_cmd(task_id: str, checkpoint: str | None, workflow: str) -> None:
    """Resume a failed task from its last checkpoint.

    Loads the checkpoint state and continues the workflow
    from where it left off.

    \\b
    Examples:
        adw resume-task abc12345              # Resume from last checkpoint
        adw resume-task abc12345 -c 20260202T103045  # Resume from specific checkpoint
        adw resume-task abc12345 -w sdlc      # Resume with SDLC workflow
    """
    from .agent.state import ADWState
    from .agent.task_updater import update_task_status
    from .recovery.checkpoints import (
        CheckpointManager,
        get_last_successful_checkpoint,
        load_checkpoint,
    )

    # Get checkpoint
    if checkpoint:
        cp = load_checkpoint(task_id, checkpoint)
        if not cp:
            console.print(f"[red]Checkpoint '{checkpoint}' not found[/red]")
            return
    else:
        cp = get_last_successful_checkpoint(task_id)
        if not cp:
            console.print(f"[red]No successful checkpoints found for task {task_id}[/red]")
            console.print("[dim]Cannot resume without a checkpoint[/dim]")
            return

    # Load task state
    state = ADWState.load(task_id)
    if not state:
        console.print(f"[red]Task state not found for {task_id}[/red]")
        return

    console.print(f"[bold cyan]Resuming task {task_id}[/bold cyan]")
    console.print()
    console.print(f"[dim]Checkpoint: {cp.checkpoint_id}[/dim]")
    console.print(f"[dim]Phase: {cp.phase}[/dim]")
    console.print(f"[dim]Step: {cp.step}[/dim]")
    console.print()

    # Get resume context
    manager = CheckpointManager(task_id)
    resume_prompt = manager.format_resume_prompt()

    if resume_prompt:
        console.print("[bold]Resume Context:[/bold]")
        console.print(resume_prompt)
        console.print()

    # Mark task as in progress
    try:
        update_task_status(task_id, "in_progress")
    except Exception:
        pass

    # Run the appropriate workflow
    worktree_path = state.worktree_path
    description = state.task_description

    # Add resume context to description
    if resume_prompt:
        description = f"{description}\n\n{resume_prompt}"

    console.print(f"[dim]Starting {workflow} workflow...[/dim]")
    console.print()

    if workflow == "simple":
        from .workflows.simple import run_simple_workflow
        success = run_simple_workflow(
            task_description=description,
            worktree_name=worktree_path,
            adw_id=task_id,
        )
    elif workflow == "sdlc":
        from .workflows.sdlc import run_sdlc_workflow
        success = run_sdlc_workflow(
            task_description=description,
            worktree_name=worktree_path,
            adw_id=task_id,
        )
    else:
        from .workflows.standard import run_standard_workflow
        success = run_standard_workflow(
            task_description=description,
            worktree_name=worktree_path,
            adw_id=task_id,
        )

    if success:
        console.print()
        console.print("[green]✓ Task resumed and completed successfully[/green]")
    else:
        console.print()
        console.print("[red]✗ Task failed again[/red]")
        console.print(f"[dim]Check logs in agents/{task_id}/[/dim]")


@main.command("escalation")
@click.argument("task_id", type=TASK_ID)
def escalation_cmd(task_id: str) -> None:
    """View escalation report for a failed task.

    Shows the generated escalation report with error details
    and suggested actions.

    \\b
    Examples:
        adw escalation abc12345
    """
    report_path = Path("agents") / task_id / "escalation.md"

    if not report_path.exists():
        console.print(f"[yellow]No escalation report found for task {task_id}[/yellow]")
        console.print("[dim]Escalation reports are generated when retries are exhausted[/dim]")
        return

    content = report_path.read_text()
    console.print(content)


# =============================================================================
# Screenshot Commands
# =============================================================================


@main.command("screenshot")
@click.option("--port", "-p", type=int, default=3000, help="Port of dev server to capture")
@click.option("--delay", "-d", type=float, default=2.0, help="Delay in seconds before capture")
@click.option("--output", "-o", type=click.Path(), help="Output file path")
@click.option("--browser", "-b", is_flag=True, help="Use browser capture (requires Playwright)")
@click.option("--list", "-l", "list_screenshots", is_flag=True, help="List recent screenshots")
@click.option("--task", "-t", type=str, help="Task ID for screenshot organization")
def screenshot_cmd(
    port: int,
    delay: float,
    output: str | None,
    browser: bool,
    list_screenshots: bool,
    task: str | None,
) -> None:
    """Capture screenshots of running dev servers.

    Takes a screenshot of a dev server running on the specified port.
    Can use either macOS screencapture or browser-based capture (Playwright).

    \\b
    Examples:
        adw screenshot                    # Capture from default port 3000
        adw screenshot --port 5173        # Capture from Vite dev server
        adw screenshot --browser          # Use Playwright for browser capture
        adw screenshot --list             # List recent screenshots
        adw screenshot -o preview.png     # Save to specific file
    """
    from .utils.screenshot import (
        capture_browser_screenshot,
        capture_screenshot,
        get_dev_server_url,
        get_screenshots_dir,
        is_dev_server_running,
    )
    from .utils.screenshot import (
        list_screenshots as list_shots,
    )

    # List mode
    if list_screenshots:
        screenshots = list_shots(task)
        if not screenshots:
            console.print("[yellow]No screenshots found[/yellow]")
            return

        console.print(f"[bold]Recent screenshots ({len(screenshots)}):[/bold]")
        for shot in screenshots[:10]:
            mtime = datetime.fromtimestamp(shot.stat().st_mtime)
            size_kb = shot.stat().st_size // 1024
            console.print(f"  {shot.name} - {mtime:%Y-%m-%d %H:%M} ({size_kb}KB)")
        return

    # Check if server is running
    if not is_dev_server_running(port):
        console.print(f"[yellow]No server detected on port {port}[/yellow]")
        console.print(
            "[dim]Start a dev server first, or specify a different port with --port[/dim]"
        )
        return

    # Determine output path
    if output:
        output_path = Path(output)
    else:
        screenshots_dir = get_screenshots_dir(task)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = screenshots_dir / f"screenshot-{timestamp}.png"

    console.print(f"[dim]Waiting {delay}s for page to settle...[/dim]")
    import time
    time.sleep(delay)

    try:
        if browser:
            url = get_dev_server_url(port)
            console.print(f"[dim]Capturing browser screenshot of {url}...[/dim]")
            result_path = capture_browser_screenshot(
                url=url,
                output_path=output_path,
                wait_time=1.0,
            )
        else:
            console.print("[dim]Capturing desktop screenshot...[/dim]")
            result_path = capture_screenshot(output_path=output_path)

        console.print(f"[green]✓[/green] Screenshot saved: {result_path}")

    except ImportError as e:
        console.print(f"[red]✗[/red] {e}")
        console.print(
            "[dim]Install with: pip install playwright && playwright install chromium[/dim]"
        )
    except RuntimeError as e:
        console.print(f"[red]✗[/red] Screenshot failed: {e}")
    except OSError as e:
        console.print(f"[red]✗[/red] Screenshot failed: {e}")


# =============================================================================
# Event Observability Commands
# =============================================================================


@main.command("events")
@click.option(
    "--type",
    "-t",
    "event_type",
    help="Filter by event type (e.g., tool_start, task_completed, error)",
)
@click.option(
    "--session",
    "-s",
    "session_id",
    help="Filter by session ID",
)
@click.option(
    "--task",
    "-k",
    "task_id",
    type=TASK_ID,
    help="Filter by task/ADW ID",
)
@click.option(
    "--since",
    help="Only events since this time (e.g., 1h, 30m, 7d)",
)
@click.option(
    "--limit",
    "-n",
    default=50,
    help="Maximum number of events to show (default: 50)",
)
@click.option(
    "--follow",
    "-f",
    is_flag=True,
    help="Follow events in real-time",
)
@click.option(
    "--json",
    "-j",
    "as_json",
    is_flag=True,
    help="Output as JSON",
)
@click.option(
    "--summary",
    is_flag=True,
    help="Show event type summary instead of listing events",
)
def events_cmd(
    event_type: str | None,
    session_id: str | None,
    task_id: str | None,
    since: str | None,
    limit: int,
    follow: bool,
    as_json: bool,
    summary: bool,
) -> None:
    """View and filter observability events.

    Query the event database for tool executions, task status changes,
    errors, and other observable events.

    \\b
    Examples:
        adw events                      # Show recent events
        adw events --type error         # Show only errors
        adw events --task abc12345      # Events for specific task
        adw events --since 1h           # Events from last hour
        adw events --follow             # Watch events in real-time
        adw events --summary            # Show event type counts
    """
    import json as json_lib
    import time

    from .observability import EventFilter, EventType, get_db

    db = get_db()

    # Parse event type filter
    event_types = None
    if event_type:
        try:
            event_types = [EventType(event_type)]
        except ValueError:
            # Try partial match
            matches = [t for t in EventType if event_type.lower() in t.value.lower()]
            if matches:
                event_types = matches
            else:
                console.print(f"[red]Unknown event type: {event_type}[/red]")
                console.print("[dim]Available types:[/dim]")
                for t in EventType:
                    console.print(f"  {t.value}")
                return

    # Parse since filter
    since_dt = None
    if since:
        try:
            since_dt = EventFilter.from_time_string(since)
        except ValueError as e:
            console.print(f"[red]Invalid time format: {e}[/red]")
            console.print("[dim]Use format like: 1h, 30m, 7d, 2w[/dim]")
            return

    # Summary mode
    if summary:
        summary_data = db.get_event_summary(since=since_dt)
        if not summary_data:
            console.print("[yellow]No events found[/yellow]")
            return

        if as_json:
            click.echo(json_lib.dumps(summary_data, indent=2))
            return

        console.print("[bold cyan]Event Summary[/bold cyan]")
        if since:
            console.print(f"[dim]Since: {since}[/dim]")
        console.print()

        total = sum(summary_data.values())
        for etype, count in sorted(summary_data.items(), key=lambda x: -x[1]):
            pct = (count / total) * 100
            bar = "█" * int(pct / 5)
            console.print(f"  {etype:<20} {count:>5}  {bar} ({pct:.1f}%)")

        console.print()
        console.print(f"[dim]Total: {total} events[/dim]")
        return

    # Build filter
    filter_ = EventFilter(
        event_types=event_types,
        session_id=session_id,
        task_id=task_id,
        since=since_dt,
        limit=limit,
    )

    # Follow mode - watch for new events
    if follow:
        console.print("[bold cyan]Watching events (Ctrl+C to stop)...[/bold cyan]")
        console.print()
        last_id = 0
        try:
            while True:
                events = db.get_events(filter_)
                for event in reversed(events):
                    if event.id and event.id > last_id:
                        _print_event(event, as_json)
                        last_id = event.id
                time.sleep(1)
        except KeyboardInterrupt:
            console.print()
            console.print("[dim]Stopped watching[/dim]")
        return

    # Regular query
    events = db.get_events(filter_)

    if not events:
        console.print("[yellow]No events found[/yellow]")
        if event_type or session_id or task_id or since:
            console.print("[dim]Try removing filters or adjusting time range[/dim]")
        return

    if as_json:
        output = [e.to_dict() for e in events]
        click.echo(json_lib.dumps(output, indent=2, default=str))
        return

    console.print(f"[bold cyan]Recent Events[/bold cyan] [dim]({len(events)} shown)[/dim]")
    console.print()

    for event in reversed(events):  # Show oldest first
        _print_event(event, as_json=False)


def _print_event(event, as_json: bool = False) -> None:
    """Print a single event to console."""
    import json as json_lib

    if as_json:
        click.echo(json_lib.dumps(event.to_dict(), default=str))
        return

    # Color-code by event type
    color = "white"
    icon = "•"

    event_type = event.event_type.value
    if "error" in event_type or "failed" in event_type:
        color = "red"
        icon = "✗"
    elif "completed" in event_type or "success" in event_type or "end" in event_type:
        color = "green"
        icon = "✓"
    elif "tool" in event_type:
        color = "cyan"
        icon = "⚙"
    elif "start" in event_type:
        color = "blue"
        icon = "▶"
    elif "warning" in event_type:
        color = "yellow"
        icon = "⚠"
    elif "block" in event_type:
        color = "red"
        icon = "🛑"

    # Format timestamp
    ts = event.timestamp.strftime("%H:%M:%S")

    # Task ID prefix
    task_str = f"[dim][{event.task_id[:8]}][/dim] " if event.task_id else ""

    # Event details
    details = ""
    if event.data:
        if "tool_name" in event.data:
            details = f" → {event.data['tool_name']}"
        elif "message" in event.data:
            msg = event.data["message"]
            if len(msg) > 50:
                msg = msg[:50] + "..."
            details = f" → {msg}"
        elif "status" in event.data:
            details = f" → {event.data['status']}"

    console.print(f"[dim]{ts}[/dim] {task_str}[{color}]{icon} {event_type}[/{color}]{details}")


@main.command("sessions")
@click.option(
    "--task",
    "-k",
    "task_id",
    type=TASK_ID,
    help="Filter by task/ADW ID",
)
@click.option(
    "--status",
    "-s",
    type=click.Choice(["running", "completed", "failed", "cancelled"]),
    help="Filter by session status",
)
@click.option(
    "--limit",
    "-n",
    default=20,
    help="Maximum number of sessions to show (default: 20)",
)
@click.option(
    "--json",
    "-j",
    "as_json",
    is_flag=True,
    help="Output as JSON",
)
def sessions_cmd(
    task_id: str | None,
    status: str | None,
    limit: int,
    as_json: bool,
) -> None:
    """View agent sessions.

    List sessions from the observability database.

    \\b
    Examples:
        adw sessions                    # Show recent sessions
        adw sessions --status running   # Show running sessions
        adw sessions --task abc12345    # Sessions for specific task
    """
    import json as json_lib

    from .observability import SessionStatus, get_db

    db = get_db()

    status_filter = SessionStatus(status) if status else None
    sessions = db.get_sessions(task_id=task_id, status=status_filter, limit=limit)

    if not sessions:
        console.print("[yellow]No sessions found[/yellow]")
        return

    if as_json:
        output = [s.to_dict() for s in sessions]
        click.echo(json_lib.dumps(output, indent=2, default=str))
        return

    console.print(f"[bold cyan]Sessions[/bold cyan] [dim]({len(sessions)} shown)[/dim]")
    console.print()

    for session in sessions:
        status_color = {
            SessionStatus.RUNNING: "blue",
            SessionStatus.COMPLETED: "green",
            SessionStatus.FAILED: "red",
            SessionStatus.CANCELLED: "yellow",
        }.get(session.status, "white")

        status_icon = {
            SessionStatus.RUNNING: "▶",
            SessionStatus.COMPLETED: "✓",
            SessionStatus.FAILED: "✗",
            SessionStatus.CANCELLED: "⊘",
        }.get(session.status, "•")

        task_str = f"[dim][{session.task_id[:8]}][/dim] " if session.task_id else ""
        start_time = session.start_time.strftime("%Y-%m-%d %H:%M:%S")

        console.print(
            f"[bold]{session.id[:12]}[/bold] {task_str}"
            f"[{status_color}]{status_icon} {session.status.value}[/{status_color}] "
            f"[dim]({session.duration_str})[/dim]"
        )
        console.print(f"  [dim]Started: {start_time}[/dim]")
        if session.end_time:
            end_time = session.end_time.strftime("%Y-%m-%d %H:%M:%S")
            console.print(f"  [dim]Ended: {end_time}[/dim]")
        console.print()


# =============================================================================
# Context Engineering Commands (Phase 3)
# =============================================================================


@main.group()
def prime() -> None:
    """Context priming commands.

    Generate and manage context priming commands for the project.
    Priming commands load relevant context at session start.
    """
    pass


@prime.command("generate")
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    help="Output directory (default: .claude/commands/)",
)
@click.option(
    "--force",
    "-f",
    is_flag=True,
    help="Overwrite existing auto-generated commands",
)
def prime_generate(output: Path | None, force: bool) -> None:
    """Generate priming commands based on project type.

    Detects project type (Python, Node.js, Go, Rust, etc.) and
    generates tailored priming commands.

    \\b
    Examples:
        adw prime generate              # Generate to default location
        adw prime generate -o ./cmds    # Custom output directory
        adw prime generate --force      # Overwrite existing
    """
    from .context import detect_project_type, generate_all_prime_commands

    detection = detect_project_type(Path.cwd())

    if detection.project_type.value == "unknown":
        console.print("[yellow]Could not detect project type[/yellow]")
        console.print("[dim]Generating generic priming commands[/dim]")
    else:
        console.print(f"[green]Detected: {detection.project_type.value}[/green]")
        if detection.framework:
            console.print(f"[dim]Framework: {detection.framework}[/dim]")

    output_dir = output or (Path.cwd() / ".claude" / "commands")

    # Check for existing auto-generated files
    if not force:
        existing = list(output_dir.glob("*_auto.md"))
        if existing:
            console.print()
            console.print("[yellow]Found existing auto-generated commands:[/yellow]")
            for f in existing:
                console.print(f"  {f.name}")
            console.print()
            if not click.confirm("Overwrite?"):
                return

    generated = generate_all_prime_commands(Path.cwd(), output_dir)

    if generated:
        console.print()
        console.print("[green]Generated priming commands:[/green]")
        for path in generated:
            console.print(f"  {path.name}")
        console.print()
        console.print("[dim]Use /prime_auto, /prime_test_auto, etc. in Claude Code[/dim]")
    else:
        console.print("[red]No commands generated[/red]")


@prime.command("show")
def prime_show() -> None:
    """Show detected project information.

    Displays what project type was detected and available priming commands.
    """
    from .context import PRIME_TEMPLATES, detect_project_type

    detection = detect_project_type(Path.cwd())

    console.print("[bold cyan]Project Detection[/bold cyan]")
    console.print()
    console.print(f"[bold]Type:[/bold] {detection.project_type.value}")

    if detection.framework:
        console.print(f"[bold]Framework:[/bold] {detection.framework}")

    if detection.test_framework:
        console.print(f"[bold]Test Framework:[/bold] {detection.test_framework}")

    if detection.config_files:
        console.print(f"[bold]Config Files:[/bold] {', '.join(detection.config_files)}")

    # Show patterns
    template = PRIME_TEMPLATES.get(detection.project_type, {})
    patterns = template.get("patterns", [])

    if patterns:
        console.print()
        console.print("[bold]Patterns:[/bold]")
        for p in patterns:
            console.print(f"  • {p}")

    # Show available commands
    console.print()
    console.print("[bold]Available Commands:[/bold]")

    commands_dir = Path.cwd() / ".claude" / "commands"
    if commands_dir.exists():
        prime_cmds = list(commands_dir.glob("prime*.md"))
        if prime_cmds:
            for cmd in sorted(prime_cmds):
                name = cmd.stem
                auto = " [dim](auto)[/dim]" if "_auto" in name else ""
                console.print(f"  /{name}{auto}")
        else:
            console.print("  [dim]None found[/dim]")
    else:
        console.print("  [dim].claude/commands not found - run 'adw init' first[/dim]")


@prime.command("refresh")
@click.option(
    "--deep",
    is_flag=True,
    help="Use Claude Code for deep analysis (slower but more accurate)",
)
def prime_refresh(deep: bool) -> None:
    """Refresh priming commands.

    Regenerates all auto-generated priming commands.
    Use after major codebase changes.

    \\b
    Examples:
        adw prime refresh          # Quick refresh
        adw prime refresh --deep   # Deep analysis with Claude
    """
    from .context import generate_all_prime_commands

    console.print("[dim]Refreshing priming commands...[/dim]")

    if deep:
        # TODO: Integrate with Claude Code analysis
        console.print("[yellow]Deep analysis not yet implemented[/yellow]")
        console.print("[dim]Using standard detection[/dim]")

    output_dir = Path.cwd() / ".claude" / "commands"

    generated = generate_all_prime_commands(Path.cwd(), output_dir)

    if generated:
        console.print(f"[green]✓ Refreshed {len(generated)} priming commands[/green]")
    else:
        console.print("[yellow]No commands generated[/yellow]")


@main.group()
def bundle() -> None:
    """Context bundle commands.

    Manage context bundles - snapshots of files accessed during sessions.
    Use bundles to quickly restore context for similar tasks.
    """
    pass


@bundle.command("list")
@click.option("--limit", "-n", type=int, default=10, help="Maximum bundles to show")
@click.option("--json", "-j", "as_json", is_flag=True, help="Output as JSON")
def bundle_list(limit: int, as_json: bool) -> None:
    """List saved context bundles.

    \\b
    Examples:
        adw bundle list              # Show recent bundles
        adw bundle list -n 20        # Show more bundles
        adw bundle list --json       # JSON output
    """
    import json as json_lib

    from .context import list_bundles

    bundles = list_bundles(limit=limit)

    if not bundles:
        console.print("[yellow]No bundles found[/yellow]")
        console.print("[dim]Bundles are saved when tasks complete[/dim]")
        return

    if as_json:
        output = [b.to_dict() for b in bundles]
        click.echo(json_lib.dumps(output, indent=2, default=str))
        return

    console.print(f"[bold cyan]Context Bundles[/bold cyan] [dim]({len(bundles)} shown)[/dim]")
    console.print()

    for bundle in bundles:
        created = bundle.created_at.strftime("%Y-%m-%d %H:%M")
        tags = f" [dim][{', '.join(bundle.tags)}][/dim]" if bundle.tags else ""

        console.print(f"[bold]{bundle.task_id}[/bold]{tags}")
        console.print(f"  {bundle.file_count} files, {bundle.total_lines} lines")
        console.print(f"  [dim]Created: {created}[/dim]")
        if bundle.description:
            desc = bundle.description[:60]
            if len(bundle.description) > 60:
                desc += "..."
            console.print(f"  [dim]{desc}[/dim]")
        console.print()


@bundle.command("show")
@click.argument("task_id")
@click.option("--files", "-f", is_flag=True, help="List all files in bundle")
def bundle_show(task_id: str, files: bool) -> None:
    """Show details of a specific bundle.

    \\b
    Examples:
        adw bundle show abc12345
        adw bundle show abc12345 --files
    """
    from .context import load_bundle

    bundle = load_bundle(task_id)

    if not bundle:
        console.print(f"[red]Bundle not found: {task_id}[/red]")
        return

    console.print(f"[bold cyan]Bundle: {bundle.task_id}[/bold cyan]")
    console.print()
    console.print(f"[bold]Created:[/bold] {bundle.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
    console.print(f"[bold]Files:[/bold] {bundle.file_count}")
    console.print(f"[bold]Lines:[/bold] {bundle.total_lines}")

    if bundle.tags:
        console.print(f"[bold]Tags:[/bold] {', '.join(bundle.tags)}")

    if bundle.description:
        console.print(f"[bold]Description:[/bold] {bundle.description}")

    if files:
        console.print()
        console.print("[bold]Files:[/bold]")
        for bf in bundle.files:
            lines = f":{bf.lines_start}-{bf.lines_end}" if bf.lines_end else ""
            console.print(f"  {bf.path}{lines}")


@bundle.command("diff")
@click.argument("task_id1")
@click.argument("task_id2")
def bundle_diff_cmd(task_id1: str, task_id2: str) -> None:
    """Show differences between two bundles.

    \\b
    Examples:
        adw bundle diff abc12345 def67890
    """
    from .context import diff_bundles

    diff = diff_bundles(task_id1, task_id2)

    if not diff:
        console.print("[red]Could not compare bundles[/red]")
        console.print("[dim]Ensure both bundle IDs exist[/dim]")
        return

    console.print(f"[bold cyan]Bundle Diff: {task_id1} → {task_id2}[/bold cyan]")
    console.print()

    if diff.added:
        console.print(f"[green]Added ({len(diff.added)}):[/green]")
        for f in diff.added[:10]:
            console.print(f"  + {f}")
        if len(diff.added) > 10:
            console.print(f"  [dim]...and {len(diff.added) - 10} more[/dim]")
        console.print()

    if diff.removed:
        console.print(f"[red]Removed ({len(diff.removed)}):[/red]")
        for f in diff.removed[:10]:
            console.print(f"  - {f}")
        if len(diff.removed) > 10:
            console.print(f"  [dim]...and {len(diff.removed) - 10} more[/dim]")
        console.print()

    console.print(f"[dim]Common: {len(diff.common)} files[/dim]")


@bundle.command("suggest")
@click.argument("description")
@click.option("--top", "-n", type=int, default=3, help="Number of suggestions")
def bundle_suggest(description: str, top: int) -> None:
    """Suggest bundles similar to a description.

    Finds bundles with similar files or tags.

    \\b
    Examples:
        adw bundle suggest "implement authentication"
        adw bundle suggest "fix api bug" --top 5
    """
    from .context import suggest_bundles

    suggestions = suggest_bundles(description, top_n=top)

    if not suggestions:
        console.print("[yellow]No matching bundles found[/yellow]")
        return

    console.print(f"[bold cyan]Suggested Bundles for:[/bold cyan] {description}")
    console.print()

    for bundle, score in suggestions:
        console.print(f"[bold]{bundle.task_id}[/bold] [dim](score: {score:.1f})[/dim]")
        console.print(f"  {bundle.file_count} files, {bundle.total_lines} lines")
        if bundle.description:
            desc = bundle.description[:50]
            if len(bundle.description) > 50:
                desc += "..."
            console.print(f"  [dim]{desc}[/dim]")
        console.print()

    console.print("[dim]Use 'adw bundle load <task_id>' to restore context[/dim]")


@bundle.command("load")
@click.argument("task_id")
@click.option("--list-only", "-l", is_flag=True, help="Just list files, don't load")
def bundle_load(task_id: str, list_only: bool) -> None:
    """Load a context bundle.

    Displays files from the bundle for context restoration.

    \\b
    Examples:
        adw bundle load abc12345
        adw bundle load abc12345 --list-only
    """
    from .context import get_bundle_file_contents, load_bundle

    bundle = load_bundle(task_id)

    if not bundle:
        console.print(f"[red]Bundle not found: {task_id}[/red]")
        return

    console.print(f"[bold cyan]Loading Bundle: {bundle.task_id}[/bold cyan]")
    console.print(f"[dim]{bundle.file_count} files, {bundle.total_lines} lines[/dim]")
    console.print()

    if list_only:
        console.print("[bold]Files in bundle:[/bold]")
        for bf in bundle.files:
            console.print(f"  {bf.path}")
        return

    # Load file contents
    contents = get_bundle_file_contents(bundle)

    if not contents:
        console.print("[yellow]Could not load any files (may have been moved/deleted)[/yellow]")
        return

    console.print(f"[green]Loaded {len(contents)} files[/green]")
    console.print()

    for path, content in contents.items():
        line_count = content.count("\n") + 1
        console.print(f"[bold]{path}[/bold] [dim]({line_count} lines)[/dim]")


@bundle.command("save")
@click.argument("task_id")
@click.argument("files", nargs=-1, required=True)
@click.option("--description", "-d", help="Bundle description")
@click.option("--tag", "-t", "tags", multiple=True, help="Add tags")
def bundle_save(task_id: str, files: tuple, description: str | None, tags: tuple) -> None:
    """Manually save a context bundle.

    \\b
    Examples:
        adw bundle save mytask src/main.py src/utils.py
        adw bundle save auth-work src/**/*.py -d "Auth implementation"
        adw bundle save feature-x src/ -t auth -t api
    """
    from .context import save_bundle

    # Expand globs
    expanded_files = []
    for pattern in files:
        if "*" in pattern:
            matches = list(Path.cwd().glob(pattern))
            expanded_files.extend([str(m.relative_to(Path.cwd())) for m in matches if m.is_file()])
        else:
            expanded_files.append(pattern)

    if not expanded_files:
        console.print("[red]No files matched[/red]")
        return

    bundle = save_bundle(
        task_id=task_id,
        files=expanded_files,
        description=description or "",
        tags=list(tags) if tags else None,
    )

    console.print(f"[green]✓ Saved bundle: {bundle.task_id}[/green]")
    console.print(f"[dim]{bundle.file_count} files, {bundle.total_lines} lines[/dim]")


@bundle.command("delete")
@click.argument("task_id")
@click.confirmation_option(prompt="Delete this bundle?")
def bundle_delete(task_id: str) -> None:
    """Delete a context bundle.

    \\b
    Examples:
        adw bundle delete abc12345
    """
    from .context import delete_bundle

    if delete_bundle(task_id):
        console.print(f"[green]✓ Deleted bundle: {task_id}[/green]")
    else:
        console.print(f"[red]Bundle not found: {task_id}[/red]")


@bundle.command("compress")
@click.option("--days", "-d", type=int, default=7, help="Compress bundles older than N days")
def bundle_compress(days: int) -> None:
    """Compress old bundles to save space.

    \\b
    Examples:
        adw bundle compress              # Compress bundles > 7 days old
        adw bundle compress --days 30    # Compress bundles > 30 days old
    """
    from .context.bundles import compress_old_bundles

    console.print(f"[dim]Compressing bundles older than {days} days...[/dim]")

    count = compress_old_bundles(days=days)

    if count > 0:
        console.print(f"[green]✓ Compressed {count} bundle(s)[/green]")
    else:
        console.print("[dim]No bundles to compress[/dim]")


# =============================================================================
# Learning Commands (Phase 5 - Self-Improving Agents)
# =============================================================================


@main.group()
def learn() -> None:
    """View and manage learned patterns.

    ADW learns from successful task completions to improve future performance.
    Use these commands to view, export, and manage learnings.
    """
    pass


@learn.command("show")
@click.option("--domain", "-d", help="Filter by domain (frontend, backend, ai)")
@click.option("--type", "-t", "learning_type", help="Filter by type (pattern, issue, mistake, best_practice)")
@click.option("--limit", "-n", type=int, default=20, help="Maximum learnings to show")
@click.option("--json", "-j", "as_json", is_flag=True, help="Output as JSON")
def learn_show(domain: str | None, learning_type: str | None, limit: int, as_json: bool) -> None:
    """Show accumulated learnings.

    Displays patterns, issues, best practices, and mistakes that ADW
    has learned from previous task completions.

    \\b
    Examples:
        adw learn show                     # Show all learnings
        adw learn show -d frontend         # Frontend learnings only
        adw learn show -t pattern -n 10    # Top 10 patterns
        adw learn show --json              # JSON output
    """
    import json as json_lib

    from .learning import LearningType, get_default_pattern_store

    store = get_default_pattern_store()
    learnings = store.learnings

    # Filter by domain
    if domain:
        learnings = [l for l in learnings if l.domain == domain or l.domain == "general"]

    # Filter by type
    if learning_type:
        try:
            lt = LearningType(learning_type)
            learnings = [l for l in learnings if l.type == lt]
        except ValueError:
            console.print(f"[red]Unknown learning type: {learning_type}[/red]")
            console.print("[dim]Valid types: pattern, issue, mistake, best_practice[/dim]")
            return

    # Limit
    learnings = learnings[:limit]

    if not learnings:
        console.print("[yellow]No learnings found[/yellow]")
        console.print("[dim]Complete some tasks to start learning![/dim]")
        console.print("[dim]Use '/improve' after tasks to record learnings.[/dim]")
        return

    if as_json:
        output = [l.to_dict() for l in learnings]
        click.echo(json_lib.dumps(output, indent=2, default=str))
        return

    # Display learnings grouped by type
    console.print(f"[bold cyan]Learnings[/bold cyan] [dim]({len(learnings)} shown)[/dim]")
    console.print()

    # Group by type
    by_type: dict[str, list] = {}
    for l in learnings:
        type_name = l.type.value
        if type_name not in by_type:
            by_type[type_name] = []
        by_type[type_name].append(l)

    type_icons = {
        "pattern": "✨",
        "issue": "⚠️",
        "best_practice": "✅",
        "mistake": "❌",
    }

    for type_name, type_learnings in by_type.items():
        icon = type_icons.get(type_name, "•")
        console.print(f"[bold]{icon} {type_name.replace('_', ' ').title()}s ({len(type_learnings)})[/bold]")
        for l in type_learnings:
            domain_tag = f" [dim][{l.domain}][/dim]" if l.domain != "general" else ""
            console.print(f"  - {l.content}{domain_tag}")
        console.print()


@learn.command("stats")
def learn_stats() -> None:
    """Show learning statistics.

    \\b
    Examples:
        adw learn stats
    """
    from .learning import get_default_pattern_store

    store = get_default_pattern_store()
    stats = store.get_statistics()

    console.print("[bold cyan]Learning Statistics[/bold cyan]")
    console.print()
    console.print(f"[bold]Total Learnings:[/bold] {stats['total_learnings']}")
    console.print()
    console.print("[bold]By Type:[/bold]")
    console.print(f"  Patterns:       {stats['patterns']}")
    console.print(f"  Issues:         {stats['issues']}")
    console.print(f"  Best Practices: {stats['best_practices']}")
    console.print(f"  Mistakes:       {stats['mistakes']}")
    console.print()
    console.print(f"[bold]Domains:[/bold] {', '.join(stats['domains']) if stats['domains'] else 'none'}")


@learn.command("export")
@click.option("--output", "-o", type=click.Path(), help="Output file (default: stdout)")
def learn_export(output: str | None) -> None:
    """Export learnings for sharing.

    Exports all learnings to a JSON file that can be imported elsewhere.

    \\b
    Examples:
        adw learn export                    # Print to stdout
        adw learn export -o learnings.json  # Save to file
    """
    import json as json_lib

    from .learning import get_default_pattern_store

    store = get_default_pattern_store()
    data = store.export()

    json_output = json_lib.dumps(data, indent=2, default=str)

    if output:
        Path(output).write_text(json_output)
        console.print(f"[green]✓ Exported {data['statistics']['total_learnings']} learnings to {output}[/green]")
    else:
        click.echo(json_output)


@learn.command("import")
@click.argument("file", type=click.Path(exists=True))
def learn_import(file: str) -> None:
    """Import learnings from a file.

    Imports learnings from an exported JSON file.

    \\b
    Examples:
        adw learn import learnings.json
    """
    import json as json_lib

    from .learning import get_default_pattern_store

    try:
        data = json_lib.loads(Path(file).read_text())
    except json_lib.JSONDecodeError as e:
        console.print(f"[red]Invalid JSON: {e}[/red]")
        return

    store = get_default_pattern_store()
    count = store.import_learnings(data)

    console.print(f"[green]✓ Imported {count} learnings[/green]")


@learn.command("clear")
@click.option("--domain", "-d", help="Clear only specific domain")
@click.confirmation_option(prompt="Clear all learnings? This cannot be undone.")
def learn_clear(domain: str | None) -> None:
    """Clear all learnings.

    \\b
    Examples:
        adw learn clear              # Clear all
        adw learn clear -d frontend  # Clear frontend only
    """
    from .learning import get_default_pattern_store

    store = get_default_pattern_store()

    if domain:
        store._learnings = [l for l in store.learnings if l.domain != domain]
        store.save()
        console.print(f"[green]✓ Cleared learnings for domain: {domain}[/green]")
    else:
        store._learnings = []
        store.save()
        console.print("[green]✓ Cleared all learnings[/green]")


@learn.command("report")
@click.option("--output", "-o", type=click.Path(), help="Save report to file")
def learn_report(output: str | None) -> None:
    """Generate a full expertise report.

    Creates a comprehensive markdown report of all learnings.

    \\b
    Examples:
        adw learn report                    # Print to stdout
        adw learn report -o expertise.md    # Save to file
    """
    from .learning.expertise import generate_expertise_report

    report = generate_expertise_report()

    if output:
        Path(output).write_text(report)
        console.print(f"[green]✓ Saved report to {output}[/green]")
    else:
        console.print(report)


@learn.command("add")
@click.argument("content")
@click.option("--type", "-t", "learning_type", default="pattern", help="Type: pattern, issue, best_practice, mistake")
@click.option("--domain", "-d", default="general", help="Domain: frontend, backend, ai, general")
@click.option("--context", "-c", help="Additional context")
def learn_add(content: str, learning_type: str, domain: str, context: str | None) -> None:
    """Manually add a learning.

    \\b
    Examples:
        adw learn add "Use compound components for forms" -d frontend
        adw learn add "Memory leak in X" -t issue -c "Use WeakRef"
        adw learn add "Don't use any type" -t mistake -d backend
    """
    from .learning import Learning, LearningType, get_default_pattern_store

    try:
        lt = LearningType(learning_type)
    except ValueError:
        console.print(f"[red]Unknown type: {learning_type}[/red]")
        console.print("[dim]Valid: pattern, issue, best_practice, mistake[/dim]")
        return

    store = get_default_pattern_store()
    learning = Learning(
        type=lt,
        content=content,
        context=context or "",
        domain=domain,
    )
    store.add_learning(learning)
    store.save()

    type_icons = {
        "pattern": "✨",
        "issue": "⚠️",
        "best_practice": "✅",
        "mistake": "❌",
    }
    icon = type_icons.get(learning_type, "•")

    console.print(f"[green]✓ Added {icon} {learning_type}: {content}[/green]")


# =============================================================================
# Planning Commands (Phase 5)
# =============================================================================


@main.command("plan")
@click.argument("description", required=False)
@click.option(
    "--planner",
    "-p",
    type=click.Choice(["auto", "generic", "fastapi", "react", "nextjs", "supabase", "vue"]),
    default="auto",
    help="Planner to use (default: auto-detect)",
)
@click.option("--show", "-s", is_flag=True, help="Show detected planner without running")
def plan_cmd(description: str | None, planner: str, show: bool) -> None:
    """Create an implementation plan with auto-detected planner.

    Auto-detects the project type and suggests the appropriate specialized
    planner command. Can also run planning directly with detected context.

    \\b
    Examples:
        adw plan                              # Show detected planner
        adw plan "Add user auth"              # Auto-detect and plan
        adw plan --planner fastapi "Add API"  # Force FastAPI planner
        adw plan --show                       # Show detection only
    """
    from .context import detect_project_type
    from .context.priming import ProjectType

    detection = detect_project_type()

    # Map project types to planners
    planner_map = {
        ProjectType.FASTAPI: "fastapi",
        ProjectType.DJANGO: "fastapi",  # Use FastAPI planner for Python APIs
        ProjectType.FLASK: "fastapi",
        ProjectType.REACT: "react",
        ProjectType.NEXTJS: "nextjs",
        ProjectType.VUE: "vue",
        ProjectType.PYTHON: "generic",
        ProjectType.NODEJS: "generic",
        ProjectType.TYPESCRIPT: "react",  # TypeScript often React
        ProjectType.GO: "generic",
        ProjectType.RUST: "generic",
        ProjectType.UNKNOWN: "generic",
    }

    # Detect Supabase usage
    supabase_detected = False
    try:
        # Check for Supabase in package.json or requirements
        package_json = Path("package.json")
        if package_json.exists():
            import json
            pkg = json.loads(package_json.read_text())
            deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
            if "@supabase/supabase-js" in deps:
                supabase_detected = True

        pyproject = Path("pyproject.toml")
        if pyproject.exists() and "supabase" in pyproject.read_text().lower():
            supabase_detected = True

        requirements = Path("requirements.txt")
        if requirements.exists() and "supabase" in requirements.read_text().lower():
            supabase_detected = True
    except Exception:
        pass

    # Determine suggested planner
    if planner == "auto":
        if supabase_detected:
            suggested_planner = "supabase"
        else:
            suggested_planner = planner_map.get(detection.project_type, "generic")
    else:
        suggested_planner = planner

    # Planner command map
    planner_commands = {
        "fastapi": "/plan_fastapi",
        "react": "/plan_react",
        "nextjs": "/plan_nextjs",
        "supabase": "/plan_supabase",
        "vue": "/plan_vite_vue",
        "generic": "/plan",
    }

    planner_descriptions = {
        "fastapi": "FastAPI API-first planner (routers, Pydantic, DI)",
        "react": "React component-first planner (hooks, state, RTL)",
        "nextjs": "Next.js full-stack planner (SSR/SSG, App Router)",
        "supabase": "Supabase database-first planner (RLS, Edge Functions)",
        "vue": "Vue 3 planner (Composition API, Pinia)",
        "generic": "Generic planner (framework-agnostic)",
    }

    if show or not description:
        # Show detection results
        console.print("[bold cyan]Project Analysis[/bold cyan]")
        console.print()
        console.print(f"[bold]Project Type:[/bold] {detection.project_type.value}")
        if detection.framework:
            console.print(f"[bold]Framework:[/bold] {detection.framework}")
        if detection.test_framework:
            console.print(f"[bold]Test Framework:[/bold] {detection.test_framework}")
        if supabase_detected:
            console.print("[bold]Database:[/bold] Supabase detected")
        console.print()

        console.print(f"[bold]Suggested Planner:[/bold] {suggested_planner}")
        console.print(f"[dim]{planner_descriptions.get(suggested_planner, '')}[/dim]")
        console.print()

        console.print("[bold]Available Planners:[/bold]")
        for key, desc in planner_descriptions.items():
            marker = " [green]← suggested[/green]" if key == suggested_planner else ""
            console.print(f"  [cyan]{planner_commands[key]}[/cyan]{marker}")
            console.print(f"    [dim]{desc}[/dim]")
        console.print()

        if not description:
            console.print("[dim]Usage: adw plan \"<description>\" to run planning[/dim]")
            cmd = planner_commands[suggested_planner]
            console.print(f"[dim]  or use: {cmd} <description> in Claude Code[/dim]")
        return

    # Provide guidance for running the planner
    cmd = planner_commands[suggested_planner]
    console.print(f"[bold cyan]Planning: {description}[/bold cyan]")
    console.print()
    console.print(f"[bold]Detected Planner:[/bold] {suggested_planner}")
    console.print(f"[dim]{planner_descriptions.get(suggested_planner, '')}[/dim]")
    console.print()
    console.print("[bold]To create the plan, run in Claude Code:[/bold]")
    console.print()
    console.print(f"  [cyan]{cmd} {description}[/cyan]")
    console.print()
    console.print("[dim]The planner will:[/dim]")
    console.print("  [dim]1. Analyze codebase structure[/dim]")
    console.print("  [dim]2. Design implementation approach[/dim]")
    console.print("  [dim]3. Create spec file in specs/[/dim]")
    console.print()
    console.print("[dim]Then use /implement <spec-file> to execute[/dim]")


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
