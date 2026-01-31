"""Full SDLC workflow: Plan → Implement → Test → Review → Document → Release."""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable

import click

from ..agent.executor import prompt_with_retry, AgentPromptRequest
from ..agent.state import ADWState
from ..agent.utils import generate_adw_id
from ..agent.task_updater import mark_done, mark_failed, mark_in_progress


class SDLCPhase(Enum):
    """SDLC workflow phases."""
    PLAN = "plan"
    IMPLEMENT = "implement"
    TEST = "test"
    REVIEW = "review"
    DOCUMENT = "document"
    RELEASE = "release"


@dataclass
class PhaseConfig:
    """Configuration for an SDLC phase."""
    name: SDLCPhase
    prompt_template: str
    model: str = "sonnet"
    required: bool = True
    max_retries: int = 2
    timeout_seconds: int = 600


@dataclass
class SDLCConfig:
    """Full SDLC workflow configuration."""
    phases: list[PhaseConfig] = field(default_factory=list)

    @classmethod
    def default(cls) -> "SDLCConfig":
        """Create default SDLC configuration."""
        return cls(phases=[
            PhaseConfig(
                name=SDLCPhase.PLAN,
                prompt_template="/plan {task}",
                model="opus",
                timeout_seconds=900,
            ),
            PhaseConfig(
                name=SDLCPhase.IMPLEMENT,
                prompt_template="/implement {task}",
                model="sonnet",
                timeout_seconds=1200,
            ),
            PhaseConfig(
                name=SDLCPhase.TEST,
                prompt_template="/test {task}",
                model="sonnet",
                timeout_seconds=600,
            ),
            PhaseConfig(
                name=SDLCPhase.REVIEW,
                prompt_template="/review {task}",
                model="opus",
                timeout_seconds=600,
            ),
            PhaseConfig(
                name=SDLCPhase.DOCUMENT,
                prompt_template="/document {task}",
                model="haiku",
                required=False,
                timeout_seconds=300,
            ),
            PhaseConfig(
                name=SDLCPhase.RELEASE,
                prompt_template="/release {task}",
                model="sonnet",
                required=False,
                timeout_seconds=300,
            ),
        ])

    @classmethod
    def quick(cls) -> "SDLCConfig":
        """Quick SDLC config (skip optional phases)."""
        config = cls.default()
        config.phases = [p for p in config.phases if p.required]
        return config


@dataclass
class PhaseResult:
    """Result of executing a single phase."""
    phase: SDLCPhase
    success: bool
    output: str = ""
    error: str | None = None
    duration_seconds: float = 0.0


def get_current_commit() -> str | None:
    """Get current git commit hash."""
    result = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        capture_output=True, text=True
    )
    return result.stdout.strip() if result.returncode == 0 else None


def execute_phase(
    phase_config: PhaseConfig,
    task_description: str,
    adw_id: str,
    state: ADWState,
    on_progress: Callable[[str], None] | None = None,
) -> PhaseResult:
    """Execute a single SDLC phase."""
    import time
    start_time = time.time()

    phase_name = phase_config.name.value
    prompt = phase_config.prompt_template.format(task=task_description)

    if on_progress:
        on_progress(f"Starting {phase_name} phase...")

    state.save(f"phase:{phase_name}:start")

    try:
        response = prompt_with_retry(AgentPromptRequest(
            prompt=prompt,
            adw_id=adw_id,
            agent_name=f"{phase_name}-{adw_id}",
            model=phase_config.model,
            timeout_seconds=phase_config.timeout_seconds,
            max_retries=phase_config.max_retries,
        ))

        duration = time.time() - start_time

        if response.success:
            state.save(f"phase:{phase_name}:complete")
            return PhaseResult(
                phase=phase_config.name,
                success=True,
                output=response.output or "",
                duration_seconds=duration,
            )
        else:
            error = response.error_message or "Unknown error"
            state.add_error(phase_name, error)
            return PhaseResult(
                phase=phase_config.name,
                success=False,
                error=error,
                duration_seconds=duration,
            )

    except Exception as e:
        duration = time.time() - start_time
        error = str(e)
        state.add_error(phase_name, error)
        return PhaseResult(
            phase=phase_config.name,
            success=False,
            error=error,
            duration_seconds=duration,
        )


def run_sdlc_workflow(
    task_description: str,
    worktree_name: str,
    adw_id: str | None = None,
    config: SDLCConfig | None = None,
    on_progress: Callable[[str], None] | None = None,
    skip_optional: bool = False,
) -> tuple[bool, list[PhaseResult]]:
    """Execute full SDLC workflow.

    Args:
        task_description: What to build/implement
        worktree_name: Git worktree to work in
        adw_id: Optional ADW ID (generated if not provided)
        config: SDLC configuration (uses default if not provided)
        on_progress: Optional callback for progress updates
        skip_optional: If True, skip non-required phases

    Returns:
        Tuple of (overall_success, list of phase results)
    """
    adw_id = adw_id or generate_adw_id()
    config = config or SDLCConfig.default()
    tasks_file = Path("tasks.md")

    # Filter phases if skipping optional
    phases = config.phases
    if skip_optional:
        phases = [p for p in phases if p.required]

    # Initialize state
    state = ADWState(
        adw_id=adw_id,
        task_description=task_description,
        worktree_name=worktree_name,
        workflow_type="sdlc",
    )
    state.save("init")

    # Mark task as in progress
    mark_in_progress(tasks_file, task_description, adw_id)

    results: list[PhaseResult] = []
    overall_success = True

    for phase_config in phases:
        if on_progress:
            on_progress(f"Phase: {phase_config.name.value}")

        result = execute_phase(
            phase_config=phase_config,
            task_description=task_description,
            adw_id=adw_id,
            state=state,
            on_progress=on_progress,
        )
        results.append(result)

        if not result.success:
            if phase_config.required:
                overall_success = False
                if on_progress:
                    on_progress(f"Required phase {phase_config.name.value} failed: {result.error}")
                break
            else:
                if on_progress:
                    on_progress(f"Optional phase {phase_config.name.value} failed, continuing...")

    # Get final commit
    commit_hash = get_current_commit()
    state.commit_hash = commit_hash

    # Update task status
    if overall_success:
        mark_done(tasks_file, task_description, adw_id, commit_hash)
        state.save("complete")
    else:
        failed_phase = next((r for r in results if not r.success), None)
        error_msg = failed_phase.error if failed_phase else "Unknown error"
        mark_failed(tasks_file, task_description, adw_id, error_msg)
        state.save("failed")

    return overall_success, results


def format_results_summary(results: list[PhaseResult]) -> str:
    """Format phase results as a summary string."""
    lines = ["SDLC Workflow Results:", "=" * 40]

    for result in results:
        status = "✅" if result.success else "❌"
        line = f"{status} {result.phase.value}: {result.duration_seconds:.1f}s"
        if result.error:
            line += f" - {result.error}"
        lines.append(line)

    total_time = sum(r.duration_seconds for r in results)
    success_count = sum(1 for r in results if r.success)
    lines.append("=" * 40)
    lines.append(f"Total: {success_count}/{len(results)} phases, {total_time:.1f}s")

    return "\n".join(lines)


@click.command()
@click.option("--adw-id", help="ADW tracking ID")
@click.option("--worktree-name", required=True, help="Git worktree name")
@click.option("--task", required=True, help="Task description")
@click.option("--quick", is_flag=True, help="Skip optional phases")
@click.option("--verbose", is_flag=True, help="Show progress")
def main(adw_id: str | None, worktree_name: str, task: str, quick: bool, verbose: bool):
    """Run full SDLC workflow."""
    config = SDLCConfig.quick() if quick else SDLCConfig.default()

    def on_progress(msg: str):
        if verbose:
            click.echo(msg)

    success, results = run_sdlc_workflow(
        task_description=task,
        worktree_name=worktree_name,
        adw_id=adw_id,
        config=config,
        on_progress=on_progress if verbose else None,
        skip_optional=quick,
    )

    if verbose:
        click.echo(format_results_summary(results))

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
