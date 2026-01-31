"""Monitoring commands for ADW CLI."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.panel import Panel


console = Console()


def watch_daemon(
    tasks_file: Path | None = None,
    follow: bool = True,
) -> None:
    """Watch daemon activity in real-time.
    
    Shows running tasks and their status, updating live.
    
    Args:
        tasks_file: Path to tasks.md
        follow: Keep watching (like tail -f)
    """
    from ..agent.task_parser import get_all_tasks
    from ..agent.models import TaskStatus
    
    tasks_file = tasks_file or Path("tasks.md")
    agents_dir = Path("agents")
    
    console.print("[bold cyan]ADW Daemon Watch[/bold cyan]")
    console.print(f"[dim]Tasks: {tasks_file}[/dim]")
    console.print(f"[dim]Agents: {agents_dir}[/dim]")
    console.print()
    console.print("[yellow]Press Ctrl+C to stop[/yellow]")
    console.print()
    
    last_content = ""
    
    try:
        while True:
            # Check tasks
            tasks = get_all_tasks(tasks_file) if tasks_file.exists() else []
            
            running = [t for t in tasks if t.status == TaskStatus.IN_PROGRESS]
            pending = [t for t in tasks if t.status == TaskStatus.PENDING]
            failed = [t for t in tasks if t.status == TaskStatus.FAILED]
            done = [t for t in tasks if t.status == TaskStatus.DONE]
            
            # Build status display
            lines = []
            lines.append(f"[bold]Status:[/bold] {len(running)} running, {len(pending)} pending, {len(done)} done, {len(failed)} failed")
            lines.append("")
            
            if running:
                lines.append("[bold blue]🔵 Running:[/bold blue]")
                for task in running:
                    adw_id = task.adw_id or "unknown"
                    desc = task.description[:60]
                    
                    # Try to get current phase from agent state
                    phase = "unknown"
                    state_file = agents_dir / adw_id / "adw_state.json"
                    if state_file.exists():
                        try:
                            state = json.loads(state_file.read_text())
                            phase = state.get("current_phase", "unknown")
                        except:
                            pass
                    
                    lines.append(f"  [{adw_id[:8]}] {desc}")
                    lines.append(f"  [dim]Phase: {phase}[/dim]")
                lines.append("")
            
            if pending:
                lines.append(f"[bold white]⚪ Pending: {len(pending)}[/bold white]")
                for task in pending[:3]:
                    desc = task.description[:50]
                    lines.append(f"  • {desc}")
                if len(pending) > 3:
                    lines.append(f"  [dim]... and {len(pending) - 3} more[/dim]")
                lines.append("")
            
            if failed:
                lines.append(f"[bold red]❌ Failed: {len(failed)}[/bold red]")
                for task in failed[:3]:
                    desc = task.description[:50]
                    lines.append(f"  • {desc}")
                    if task.error_message:
                        lines.append(f"    [dim]{task.error_message[:60]}[/dim]")
                lines.append("")
            
            content = "\n".join(lines)
            
            # Only update if changed
            if content != last_content:
                # Clear and reprint
                if last_content:
                    # Move cursor up and clear
                    num_lines = last_content.count("\n") + 1
                    sys.stdout.write(f"\033[{num_lines}A\033[J")
                
                console.print(content)
                last_content = content
            
            if not follow:
                break
            
            time.sleep(2)
            
    except KeyboardInterrupt:
        console.print()
        console.print("[yellow]Watch stopped[/yellow]")


def view_logs(
    task_id: str,
    tasks_file: Path | None = None,
    follow: bool = False,
    lines: int = 50,
) -> None:
    """View logs for a specific task/agent.
    
    Args:
        task_id: Task ID or ADW ID
        tasks_file: Path to tasks.md
        follow: Keep following (like tail -f)
        lines: Number of lines to show
    """
    from ..agent.task_parser import get_all_tasks
    
    tasks_file = tasks_file or Path("tasks.md")
    agents_dir = Path("agents")
    
    # Find the task
    adw_id = None
    
    # Check if task_id is an ADW ID (8 hex chars)
    if len(task_id) == 8 and all(c in "0123456789abcdef" for c in task_id.lower()):
        adw_id = task_id.lower()
    else:
        # Search in tasks
        tasks = get_all_tasks(tasks_file) if tasks_file.exists() else []
        for task in tasks:
            if task_id.upper() in task.description.upper():
                adw_id = task.adw_id
                break
            if task.adw_id and task.adw_id.startswith(task_id):
                adw_id = task.adw_id
                break
    
    if not adw_id:
        console.print(f"[red]Task not found: {task_id}[/red]")
        console.print("[dim]Use 'adw list' to see available tasks[/dim]")
        return
    
    agent_dir = agents_dir / adw_id
    
    if not agent_dir.exists():
        console.print(f"[red]Agent directory not found: {agent_dir}[/red]")
        return
    
    console.print(f"[bold cyan]Logs for {adw_id}[/bold cyan]")
    console.print(f"[dim]Directory: {agent_dir}[/dim]")
    console.print()
    
    # Show state
    state_file = agent_dir / "adw_state.json"
    if state_file.exists():
        try:
            state = json.loads(state_file.read_text())
            console.print(f"[bold]Phase:[/bold] {state.get('current_phase', 'unknown')}")
            console.print(f"[bold]Workflow:[/bold] {state.get('workflow_type', 'unknown')}")
            console.print(f"[bold]Worktree:[/bold] {state.get('worktree_name', 'unknown')}")
            if state.get("errors"):
                console.print(f"[bold red]Errors:[/bold red]")
                for err in state["errors"]:
                    console.print(f"  • {err}")
            console.print()
        except:
            pass
    
    # Find log files
    log_files = []
    for subdir in agent_dir.iterdir():
        if subdir.is_dir():
            for log_file in ["cc_final_result.txt", "cc_raw_output.jsonl"]:
                log_path = subdir / log_file
                if log_path.exists():
                    log_files.append((subdir.name, log_path))
    
    if not log_files:
        console.print("[yellow]No log files found yet[/yellow]")
        return
    
    # Show logs
    for agent_name, log_path in log_files:
        console.print(f"[bold]{agent_name}[/bold] ({log_path.name})")
        console.print("─" * 60)
        
        content = log_path.read_text()
        
        if log_path.name.endswith(".jsonl"):
            # Parse JSONL and extract messages
            for line in content.strip().split("\n")[-lines:]:
                if not line.strip():
                    continue
                try:
                    msg = json.loads(line)
                    if msg.get("type") == "assistant":
                        text = msg.get("message", {}).get("content", [])
                        for block in text:
                            if isinstance(block, dict) and block.get("type") == "text":
                                console.print(f"[cyan]Claude:[/cyan] {block.get('text', '')[:200]}")
                    elif msg.get("type") == "result":
                        result = msg.get("result", "")
                        console.print(f"[green]Result:[/green] {result[:200]}")
                except:
                    pass
        else:
            # Plain text
            text_lines = content.strip().split("\n")
            for line in text_lines[-lines:]:
                console.print(line)
        
        console.print()
    
    if follow:
        console.print("[yellow]Following logs... Press Ctrl+C to stop[/yellow]")
        # TODO: implement tail -f style following
        console.print("[dim](Follow mode not yet implemented)[/dim]")
