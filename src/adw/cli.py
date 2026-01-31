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
def run(
    poll_interval: float,
    max_concurrent: int,
    tasks_file: Path | None,
    dry_run: bool,
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
            )
        )
    except KeyboardInterrupt:
        console.print()
        console.print("[yellow]Daemon stopped by user[/yellow]")


if __name__ == "__main__":
    main()
