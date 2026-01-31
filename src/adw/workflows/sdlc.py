"""Full SDLC workflow: Plan → Build → Test → Review → Document → Ship."""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel

from ..agent.utils import generate_adw_id
from ..agent.worktree import create_worktree, get_worktree_path
from ..agent.task_updater import mark_done, mark_failed


console = Console()


SDLC_PHASES = [
    ("plan", "/plan", "Creating implementation plan"),
    ("implement", "/implement", "Implementing solution"),
    ("test", "/test", "Running tests"),
    ("review", "/review", "Reviewing implementation"),
    ("document", "/document", "Generating documentation"),
]


def run_sdlc_workflow(
    task_description: str,
    adw_id: str,
    worktree_name: str | None = None,
    model: str = "sonnet",
) -> int:
    """Run full SDLC workflow: Plan → Implement → Test → Review → Document.

    Args:
        task_description: Task description from tasks.md
        adw_id: ADW ID for this task
        worktree_name: Git worktree name (optional)
        model: Model to use (haiku, sonnet, opus)

    Returns:
        Exit code: 0 on success, 1 on failure
    """
    console.print(Panel(
        f"[bold cyan]SDLC Workflow[/bold cyan]\n"
        f"Task: {task_description}\n"
        f"ADW ID: {adw_id}\n"
        f"Model: {model}",
        title="Starting Full SDLC",
    ))

    # Initialize paths
    tasks_md = Path("tasks.md")
    agent_dir = Path("agents") / adw_id / "sdlc"
    agent_dir.mkdir(parents=True, exist_ok=True)

    # Create worktree if specified
    worktree_path = None
    if worktree_name:
        console.print(f"\n[dim]Creating worktree: {worktree_name}[/dim]")
        worktree_path = create_worktree(worktree_name)
        if not worktree_path:
            console.print("[red]Failed to create worktree[/red]")
            mark_failed(tasks_md, task_description, adw_id, "Failed to create worktree")
            return 1

    # Set working directory
    working_dir = worktree_path if worktree_path else Path.cwd()

    # Execute each SDLC phase
    for phase_name, command, description in SDLC_PHASES:
        console.print(f"\n[bold yellow]Phase: {phase_name.upper()}[/bold yellow]")
        console.print(f"[dim]{description}...[/dim]")

        # Build Claude Code command
        phase_prompt = f"""Execute SDLC phase: {phase_name}

Task: {task_description}
ADW ID: {adw_id}

Use the {command} command to {description.lower()}.
"""

        # Execute phase using Claude Code CLI
        cmd = [
            "claude",
            "--model", model,
            "--output-format", "stream-json",
            "-p", phase_prompt,
        ]

        # Write output to phase-specific file
        output_file = agent_dir / f"{phase_name}_output.jsonl"

        try:
            with open(output_file, "w") as f:
                result = subprocess.run(
                    cmd,
                    cwd=working_dir,
                    stdout=f,
                    stderr=subprocess.PIPE,
                    text=True,
                )

            if result.returncode != 0:
                error_msg = result.stderr or f"Phase {phase_name} failed with exit code {result.returncode}"
                console.print(f"[red]✗ Phase {phase_name} failed: {error_msg}[/red]")
                mark_failed(tasks_md, task_description, adw_id, error_msg)
                return 1

            console.print(f"[green]✓ Phase {phase_name} completed[/green]")

        except Exception as e:
            console.print(f"[red]✗ Phase {phase_name} exception: {e}[/red]")
            mark_failed(tasks_md, task_description, adw_id, str(e))
            return 1

    # All phases completed successfully
    console.print("\n[bold green]✓ All SDLC phases completed successfully![/bold green]")

    # Mark task as done (commit hash will be added by git hook if applicable)
    mark_done(tasks_md, task_description, adw_id)

    return 0


@click.command()
@click.option("--adw-id", required=True, help="ADW ID for this task")
@click.option("--worktree-name", help="Git worktree name")
@click.option("--task", required=True, help="Task description")
@click.option("--model", default="sonnet", help="Model to use (haiku, sonnet, opus)")
def main(adw_id: str, worktree_name: str | None, task: str, model: str) -> None:
    """Run full SDLC workflow from CLI."""
    exit_code = run_sdlc_workflow(
        task_description=task,
        adw_id=adw_id,
        worktree_name=worktree_name,
        model=model,
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
