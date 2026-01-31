"""Simple workflow: Build → Update."""

from __future__ import annotations

import sys
import time
from pathlib import Path

import click

from ..agent.executor import prompt_with_retry, AgentPromptRequest
from ..agent.state import ADWState
from ..agent.utils import generate_adw_id
from ..agent.task_updater import mark_done, mark_failed
from ..agent.worktree import create_worktree, get_worktree_path
from ..agent.ports import find_available_ports, write_ports_env
from ..agent.environment import write_env_file


def run_simple_workflow(
    task_description: str,
    worktree_name: str,
    adw_id: str | None = None,
    model: str = "sonnet",
) -> bool:
    """Execute simple build workflow."""
    adw_id = adw_id or generate_adw_id()
    tasks_file = Path("tasks.md")

    # Create worktree
    worktree_path = create_worktree(worktree_name)
    if not worktree_path:
        return False

    # Allocate ports and setup environment
    backend_port, frontend_port = find_available_ports(adw_id)
    write_ports_env(str(worktree_path), backend_port, frontend_port)
    write_env_file(
        worktree_path,
        {
            "ADW_ID": adw_id,
            "ADW_WORKTREE": worktree_name,
        },
        filename=".adw.env",
    )

    # Create state
    state = ADWState(
        adw_id=adw_id,
        task_description=task_description,
        worktree_name=worktree_name,
        workflow_type="simple",
    )
    state.save("init")

    success = True
    error_message = None
    commit_hash = None

    try:
        # Build phase
        state.save("build")

        response = prompt_with_retry(AgentPromptRequest(
            prompt=f"/build {task_description}",
            adw_id=adw_id,
            agent_name=f"builder-{adw_id}",
            model=model,
            working_dir=str(worktree_path),
        ))

        if not response.success:
            raise Exception(response.error_message or "Build failed")

        # Get commit hash
        import subprocess
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(worktree_path),
            capture_output=True, text=True
        )
        if result.returncode == 0:
            commit_hash = result.stdout.strip()

        state.commit_hash = commit_hash
        state.save("build")

    except Exception as e:
        success = False
        error_message = str(e)
        state.add_error("build", error_message)

    # Update task
    if success:
        mark_done(tasks_file, task_description, adw_id, commit_hash)
    else:
        mark_failed(tasks_file, task_description, adw_id, error_message or "Unknown")

    state.save("complete" if success else "failed")
    return success


@click.command()
@click.option("--adw-id")
@click.option("--worktree-name", required=True)
@click.option("--task", required=True)
@click.option("--model", default="sonnet")
def main(adw_id, worktree_name, task, model):
    success = run_simple_workflow(task, worktree_name, adw_id, model)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
