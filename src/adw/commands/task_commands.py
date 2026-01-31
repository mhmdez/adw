"""Task management commands for ADW CLI."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.table import Table

from ..agent.task_parser import load_tasks, get_all_tasks, get_eligible_tasks
from ..agent.models import TaskStatus


console = Console()


def get_next_task_id(tasks_file: Path) -> str:
    """Generate next task ID based on existing tasks."""
    tasks = get_all_tasks(tasks_file)
    
    max_num = 0
    for task in tasks:
        # Extract number from description like "TASK-006" or "**TASK-006**"
        match = re.search(r"TASK-(\d+)", task.description)
        if match:
            num = int(match.group(1))
            max_num = max(max_num, num)
    
    return f"TASK-{max_num + 1:03d}"


def add_task(
    description: str,
    tasks_file: Path | None = None,
    priority: str | None = None,
    tags: list[str] | None = None,
) -> bool:
    """Add a new task to tasks.md.
    
    Args:
        description: Task description
        tasks_file: Path to tasks.md (default: ./tasks.md)
        priority: Optional priority tag (high, medium, low)
        tags: Optional list of tags
    
    Returns:
        True if task was added successfully
    """
    tasks_file = tasks_file or Path("tasks.md")
    
    # Ensure file exists
    if not tasks_file.exists():
        console.print(f"[red]Error: {tasks_file} not found[/red]")
        console.print("[dim]Run 'adw init' to create project structure[/dim]")
        return False
    
    # Generate task ID
    task_id = get_next_task_id(tasks_file)
    
    # Build task line
    task_line = f"[ ] **{task_id}**: {description}"
    
    # Add tags if provided
    if tags or priority:
        all_tags = list(tags or [])
        if priority:
            all_tags.append(priority)
        if all_tags:
            task_line += f" {{{', '.join(all_tags)}}}"
    
    # Read current content
    content = tasks_file.read_text()
    
    # Find "Active Tasks" section or create it
    if "## Active Tasks" in content:
        # Insert after "## Active Tasks" header
        parts = content.split("## Active Tasks", 1)
        if len(parts) == 2:
            header, rest = parts
            # Find first non-empty line after header
            lines = rest.split("\n")
            insert_idx = 0
            for i, line in enumerate(lines):
                if line.strip() and not line.strip().startswith("<!--"):
                    insert_idx = i
                    break
                insert_idx = i + 1
            
            lines.insert(insert_idx, task_line)
            content = header + "## Active Tasks" + "\n".join(lines)
    else:
        # Append to end
        content = content.rstrip() + f"\n\n## Active Tasks\n\n{task_line}\n"
    
    # Write back
    tasks_file.write_text(content)
    
    console.print(f"[green]✓[/green] Added task: [bold]{task_id}[/bold]")
    console.print(f"  {description}")
    
    return True


def list_tasks(
    tasks_file: Path | None = None,
    status_filter: str | None = None,
    show_all: bool = False,
) -> None:
    """List all tasks from tasks.md.
    
    Args:
        tasks_file: Path to tasks.md
        status_filter: Filter by status (pending, running, done, failed)
        show_all: Show completed tasks too
    """
    tasks_file = tasks_file or Path("tasks.md")
    
    if not tasks_file.exists():
        console.print(f"[yellow]No tasks file found at {tasks_file}[/yellow]")
        console.print("[dim]Run 'adw init' to create project structure[/dim]")
        return
    
    tasks = get_all_tasks(tasks_file)
    
    if not tasks:
        console.print("[yellow]No tasks found.[/yellow]")
        console.print("[dim]Run 'adw add \"task description\"' to create one[/dim]")
        return
    
    # Filter by status
    if status_filter:
        status_map = {
            "pending": TaskStatus.PENDING,
            "running": TaskStatus.IN_PROGRESS,
            "in_progress": TaskStatus.IN_PROGRESS,
            "done": TaskStatus.DONE,
            "failed": TaskStatus.FAILED,
            "blocked": TaskStatus.BLOCKED,
        }
        filter_status = status_map.get(status_filter.lower())
        if filter_status:
            tasks = [t for t in tasks if t.status == filter_status]
    elif not show_all:
        # By default, don't show completed tasks
        tasks = [t for t in tasks if t.status != TaskStatus.DONE]
    
    # Create table
    table = Table(title="Tasks", show_header=True, header_style="bold cyan")
    table.add_column("Status", width=8)
    table.add_column("ID", width=10)
    table.add_column("Description", min_width=30)
    table.add_column("Tags", width=15)
    
    status_icons = {
        TaskStatus.PENDING: "⚪",
        TaskStatus.IN_PROGRESS: "🔵",
        TaskStatus.DONE: "✅",
        TaskStatus.FAILED: "❌",
        TaskStatus.BLOCKED: "⏸️",
    }
    
    status_styles = {
        TaskStatus.PENDING: "white",
        TaskStatus.IN_PROGRESS: "blue",
        TaskStatus.DONE: "green",
        TaskStatus.FAILED: "red",
        TaskStatus.BLOCKED: "yellow",
    }
    
    for task in tasks:
        icon = status_icons.get(task.status, "❓")
        style = status_styles.get(task.status, "white")
        
        # Extract task ID from description
        task_id = "—"
        desc = task.description
        match = re.search(r"\*?\*?(TASK-\d+)\*?\*?:?\s*", desc)
        if match:
            task_id = match.group(1)
            desc = desc[match.end():].strip()
        
        # Show ADW ID if running
        if task.adw_id:
            task_id = f"{task_id}\n[dim]{task.adw_id[:8]}[/dim]"
        
        tags = ", ".join(task.tags) if task.tags else "—"
        
        table.add_row(
            f"[{style}]{icon}[/{style}]",
            task_id,
            desc[:50] + ("..." if len(desc) > 50 else ""),
            tags,
        )
    
    console.print(table)
    
    # Summary
    pending = sum(1 for t in tasks if t.status == TaskStatus.PENDING)
    running = sum(1 for t in tasks if t.status == TaskStatus.IN_PROGRESS)
    failed = sum(1 for t in tasks if t.status == TaskStatus.FAILED)
    
    summary_parts = []
    if pending:
        summary_parts.append(f"[white]{pending} pending[/white]")
    if running:
        summary_parts.append(f"[blue]{running} running[/blue]")
    if failed:
        summary_parts.append(f"[red]{failed} failed[/red]")
    
    if summary_parts:
        console.print()
        console.print(" • ".join(summary_parts))


def cancel_task(
    task_id: str,
    tasks_file: Path | None = None,
) -> bool:
    """Cancel a task (mark as failed with 'Cancelled' reason).
    
    Args:
        task_id: Task ID or ADW ID to cancel
        tasks_file: Path to tasks.md
    
    Returns:
        True if task was cancelled
    """
    tasks_file = tasks_file or Path("tasks.md")
    
    if not tasks_file.exists():
        console.print(f"[red]Error: {tasks_file} not found[/red]")
        return False
    
    from ..agent.task_updater import mark_failed
    
    # Find task by ID
    tasks = get_all_tasks(tasks_file)
    target_task = None
    
    for task in tasks:
        # Match by ADW ID
        if task.adw_id and task.adw_id.startswith(task_id):
            target_task = task
            break
        # Match by task ID in description
        if task_id.upper() in task.description.upper():
            target_task = task
            break
    
    if not target_task:
        console.print(f"[red]Task not found: {task_id}[/red]")
        return False
    
    # Mark as failed
    mark_failed(tasks_file, target_task.description, target_task.adw_id or "", "Cancelled by user")
    
    console.print(f"[yellow]Cancelled:[/yellow] {target_task.description[:50]}")
    return True


def retry_task(
    task_id: str,
    tasks_file: Path | None = None,
) -> bool:
    """Retry a failed task (reset to pending).
    
    Args:
        task_id: Task ID or ADW ID to retry
        tasks_file: Path to tasks.md
    
    Returns:
        True if task was reset
    """
    tasks_file = tasks_file or Path("tasks.md")
    
    if not tasks_file.exists():
        console.print(f"[red]Error: {tasks_file} not found[/red]")
        return False
    
    # Read content
    content = tasks_file.read_text()
    
    # Find and reset the task
    # Pattern: [❌, adw_id] description // Failed: reason
    pattern = re.compile(
        rf"\[❌,?\s*([a-f0-9]{{8}})?\]\s*(.+?)\s*//\s*Failed:.*$",
        re.MULTILINE
    )
    
    found = False
    def replacer(match):
        nonlocal found
        adw_id = match.group(1) or ""
        desc = match.group(2).strip()
        
        # Check if this is the task we want
        if task_id.upper() in desc.upper() or (adw_id and adw_id.startswith(task_id)):
            found = True
            return f"[ ] {desc}"
        return match.group(0)
    
    new_content = pattern.sub(replacer, content)
    
    if not found:
        console.print(f"[red]Failed task not found: {task_id}[/red]")
        return False
    
    tasks_file.write_text(new_content)
    console.print(f"[green]✓[/green] Task reset to pending: {task_id}")
    
    return True
