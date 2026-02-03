"""Full SDLC workflow: Plan → Implement → Test → Review → Document → Release.

DEPRECATED: This module is deprecated in favor of the adaptive workflow.
Use `from adw.workflows.adaptive import run_adaptive_workflow` with
`complexity=TaskComplexity.FULL` instead.

The adaptive workflow consolidates simple, standard, and sdlc workflows
into a single workflow that auto-detects task complexity.

This workflow integrates with the testing and retry modules to provide:
- Automatic test framework detection and execution
- Smart retry with context injection on test failures
- Escalation reports when all retries exhausted
"""

from __future__ import annotations

import logging
import subprocess
import sys
import warnings
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Literal

import click

from ..agent.executor import prompt_with_retry
from ..agent.models import AgentPromptRequest
from ..agent.state import ADWState
from ..agent.task_updater import mark_done, mark_failed, mark_in_progress
from ..agent.utils import generate_adw_id
from ..retry.context import format_test_failure_context, select_retry_strategy
from ..retry.escalation import AttemptRecord, generate_escalation_report
from ..testing.detector import detect_test_framework
from ..testing.validation import ValidationConfig, ValidationResult, validate_tests

logger = logging.getLogger(__name__)

# Type alias for model names
ModelType = Literal["haiku", "sonnet", "opus"]


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
    model: ModelType = "sonnet"
    required: bool = True
    max_retries: int = 2
    timeout_seconds: int = 600


@dataclass
class SDLCConfig:
    """Full SDLC workflow configuration."""

    phases: list[PhaseConfig] = field(default_factory=list)

    @classmethod
    def default(cls) -> SDLCConfig:
        """Create default SDLC configuration."""
        return cls(
            phases=[
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
            ]
        )

    @classmethod
    def quick(cls) -> SDLCConfig:
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
    test_result: ValidationResult | None = None  # Populated for TEST phase


@dataclass
class TestValidationConfig:
    """Configuration for test validation in SDLC workflow."""

    enabled: bool = True
    max_test_retries: int = 3  # Number of implement-test cycles to try
    timeout_seconds: int = 300
    skip_if_no_tests: bool = True  # Skip validation if no test framework found


def get_current_commit() -> str | None:
    """Get current git commit hash."""
    result = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else None


def run_test_validation(
    worktree_path: Path,
    adw_id: str,
    task_description: str,
    validation_config: TestValidationConfig | None = None,
    on_progress: Callable[[str], None] | None = None,
) -> ValidationResult:
    """Run test validation using the testing module.

    This function actually executes tests (rather than just prompting
    an agent to write tests) and returns structured results.

    Args:
        worktree_path: Path to the working directory.
        adw_id: ADW task ID for escalation reports.
        task_description: Description of the task being validated.
        validation_config: Test validation configuration.
        on_progress: Progress callback.

    Returns:
        ValidationResult with test outcomes.
    """

    config = validation_config or TestValidationConfig()

    if not config.enabled:
        if on_progress:
            on_progress("Test validation disabled")
        return ValidationResult(success=True)

    # Detect test framework
    framework_info = detect_test_framework(worktree_path)
    if framework_info is None:
        if config.skip_if_no_tests:
            if on_progress:
                on_progress("No test framework detected, skipping validation")
            return ValidationResult(success=True)
        else:
            return ValidationResult(
                success=False,
                retry_context="No test framework detected. Please add tests.",
            )

    if on_progress:
        on_progress(f"Detected {framework_info.framework.value}: {framework_info.command}")

    # Run validation
    val_config = ValidationConfig(
        max_retries=0,  # We handle retries at the workflow level
        timeout_seconds=config.timeout_seconds,
        test_command=framework_info.command,
    )

    result = validate_tests(
        path=worktree_path,
        config=val_config,
        on_progress=on_progress,
        task_id=adw_id,
        task_description=task_description,
    )

    return result


def execute_phase_with_retry(
    phase_config: PhaseConfig,
    task_description: str,
    adw_id: str,
    state: ADWState,
    worktree_path: Path | None = None,
    retry_context: str | None = None,
    on_progress: Callable[[str], None] | None = None,
    inject_expertise: bool = True,
) -> PhaseResult:
    """Execute a phase with optional retry context injection.

    This enhanced version can inject error context from previous
    failed attempts to help the agent fix issues.

    Args:
        phase_config: Phase configuration.
        task_description: Task description.
        adw_id: ADW tracking ID.
        state: Workflow state.
        worktree_path: Optional working directory path.
        retry_context: Optional retry context from previous failure.
        on_progress: Progress callback.
        inject_expertise: Whether to inject expertise section into prompt.

    Returns:
        PhaseResult with execution outcome.
    """
    import time

    start_time = time.time()

    phase_name = phase_config.name.value

    # Build prompt with optional retry context
    prompt = phase_config.prompt_template.format(task=task_description)

    # Inject expertise section for IMPLEMENT and PLAN phases
    if inject_expertise and phase_name in ("implement", "plan"):
        try:
            from ..learning.expertise import inject_expertise_into_prompt

            prompt = inject_expertise_into_prompt(
                prompt=prompt,
                position="end",
            )
        except Exception as e:
            logger.debug("Could not inject expertise: %s", e)

    if retry_context:
        prompt = f"{prompt}\n\n{retry_context}"
        if on_progress:
            on_progress(f"Retrying {phase_name} with error context...")

    if on_progress:
        on_progress(f"Starting {phase_name} phase...")

    state.save(f"phase:{phase_name}:start")

    try:
        response = prompt_with_retry(
            AgentPromptRequest(
                prompt=prompt,
                adw_id=adw_id,
                agent_name=f"{phase_name}-{adw_id}",
                model=phase_config.model,
                timeout=phase_config.timeout_seconds,
                working_dir=str(worktree_path) if worktree_path else None,
            ),
            max_retries=phase_config.max_retries,
        )

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


def execute_phase(
    phase_config: PhaseConfig,
    task_description: str,
    adw_id: str,
    state: ADWState,
    on_progress: Callable[[str], None] | None = None,
    inject_expertise: bool = True,
) -> PhaseResult:
    """Execute a single SDLC phase."""
    import time

    start_time = time.time()

    phase_name = phase_config.name.value
    prompt = phase_config.prompt_template.format(task=task_description)

    # Inject expertise section for IMPLEMENT and PLAN phases
    if inject_expertise and phase_name in ("implement", "plan"):
        try:
            from ..learning.expertise import inject_expertise_into_prompt

            prompt = inject_expertise_into_prompt(
                prompt=prompt,
                position="end",
            )
        except Exception as e:
            logger.debug("Could not inject expertise: %s", e)

    if on_progress:
        on_progress(f"Starting {phase_name} phase...")

    state.save(f"phase:{phase_name}:start")

    try:
        response = prompt_with_retry(
            AgentPromptRequest(
                prompt=prompt,
                adw_id=adw_id,
                agent_name=f"{phase_name}-{adw_id}",
                model=phase_config.model,
                timeout=phase_config.timeout_seconds,
            ),
            max_retries=phase_config.max_retries,
        )

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
    test_validation_config: TestValidationConfig | None = None,
    _skip_deprecation_warning: bool = False,  # Internal flag to suppress warning
) -> tuple[bool, list[PhaseResult]]:
    """Execute full SDLC workflow with test validation.

    This enhanced workflow integrates with the testing module to:
    1. Run actual tests after the TEST phase
    2. Re-run IMPLEMENT with error context if tests fail
    3. Generate escalation reports when all retries exhausted

    Args:
        task_description: What to build/implement
        worktree_name: Git worktree to work in
        adw_id: Optional ADW ID (generated if not provided)
        config: SDLC configuration (uses default if not provided)
        on_progress: Optional callback for progress updates
        skip_optional: If True, skip non-required phases
        test_validation_config: Configuration for test validation

    Returns:
        Tuple of (overall_success, list of phase results)

    DEPRECATED: Use run_adaptive_workflow with complexity=TaskComplexity.FULL instead.
    """
    import time

    if not _skip_deprecation_warning:
        warnings.warn(
            "run_sdlc_workflow is deprecated. Use run_adaptive_workflow with "
            "complexity=TaskComplexity.FULL instead.",
            DeprecationWarning,
            stacklevel=2,
        )

    adw_id = adw_id or generate_adw_id()
    config = config or SDLCConfig.default()
    test_config = test_validation_config or TestValidationConfig()
    tasks_file = Path("tasks.md")
    worktree_path = Path.cwd()  # TODO: Resolve actual worktree path

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
    attempt_records: list[AttemptRecord] = []

    # Track implement-test retry cycles
    test_retry_count = 0
    current_retry_context: str | None = None

    i = 0
    while i < len(phases):
        phase_config = phases[i]
        phase_name = phase_config.name

        if on_progress:
            on_progress(f"Phase: {phase_name.value}")

        # Use enhanced phase execution for IMPLEMENT (to inject retry context)
        if phase_name == SDLCPhase.IMPLEMENT and current_retry_context:
            result = execute_phase_with_retry(
                phase_config=phase_config,
                task_description=task_description,
                adw_id=adw_id,
                state=state,
                worktree_path=worktree_path,
                retry_context=current_retry_context,
                on_progress=on_progress,
            )
            current_retry_context = None  # Clear after use
        else:
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
                    on_progress(f"Required phase {phase_name.value} failed: {result.error}")
                break
            else:
                if on_progress:
                    on_progress(f"Optional phase {phase_name.value} failed, continuing...")
                i += 1
                continue

        # After TEST phase, run actual test validation
        if phase_name == SDLCPhase.TEST and test_config.enabled:
            if on_progress:
                on_progress("Running test validation...")

            start_time = time.time()
            validation_result = run_test_validation(
                worktree_path=worktree_path,
                adw_id=adw_id,
                task_description=task_description,
                validation_config=test_config,
                on_progress=on_progress,
            )
            duration = time.time() - start_time

            # Store test result in phase result
            result.test_result = validation_result

            if not validation_result.success:
                test_retry_count += 1

                # Record the attempt
                strategy = select_retry_strategy(test_retry_count, test_config.max_test_retries + 1)
                attempt_records.append(
                    AttemptRecord(
                        attempt_number=test_retry_count,
                        phase="test_validation",
                        error_message=validation_result.retry_context or "Tests failed",
                        strategy=strategy.value,
                        duration_seconds=duration,
                    )
                )

                if test_retry_count < test_config.max_test_retries:
                    if on_progress:
                        max_retries = test_config.max_test_retries
                        on_progress(
                            f"Tests failed (attempt {test_retry_count}/{max_retries}), "
                            "re-running implement phase with error context..."
                        )

                    # Generate retry context for the implement phase
                    if validation_result.final_test_result:
                        current_retry_context = format_test_failure_context(
                            test_result=validation_result.final_test_result,
                            phase="implement",
                            attempt_number=test_retry_count,
                            max_attempts=test_config.max_test_retries,
                        )
                    else:
                        current_retry_context = validation_result.retry_context

                    # Find IMPLEMENT phase index and jump back
                    implement_idx = next((idx for idx, p in enumerate(phases) if p.name == SDLCPhase.IMPLEMENT), None)
                    if implement_idx is not None:
                        i = implement_idx
                        continue
                else:
                    # All retries exhausted - generate escalation report
                    if on_progress:
                        on_progress("All test retries exhausted, generating escalation report...")

                    generate_escalation_report(
                        task_id=adw_id,
                        task_description=task_description,
                        workflow_type="sdlc",
                        attempts=attempt_records,
                        output_dir=Path(f"agents/{adw_id}"),
                    )
                    logger.warning("Generated escalation report for task %s", adw_id)

                    overall_success = False
                    result.error = f"Tests failed after {test_retry_count} retries"
                    result.success = False
                    break

        i += 1

    # Get final commit
    commit_hash = get_current_commit()
    state.commit_hash = commit_hash

    # Update task status
    if overall_success:
        mark_done(tasks_file, task_description, adw_id, commit_hash)
        state.save("complete")
        if on_progress:
            test_attempts_msg = ""
            if test_retry_count > 0:
                test_attempts_msg = f" (tests passed after {test_retry_count + 1} attempts)"
            on_progress(f"Workflow completed successfully{test_attempts_msg}")
    else:
        failed_phase = next((r for r in results if not r.success), None)
        error_msg = failed_phase.error if failed_phase and failed_phase.error else "Unknown error"
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
@click.option("--no-test-validation", is_flag=True, help="Disable automatic test validation")
@click.option("--test-retries", default=3, help="Max implement-test retry cycles (default: 3)")
def main(
    adw_id: str | None,
    worktree_name: str,
    task: str,
    quick: bool,
    verbose: bool,
    no_test_validation: bool,
    test_retries: int,
) -> None:
    """Run full SDLC workflow with integrated test validation."""
    config = SDLCConfig.quick() if quick else SDLCConfig.default()
    test_config = TestValidationConfig(
        enabled=not no_test_validation,
        max_test_retries=test_retries,
    )

    def on_progress(msg: str) -> None:
        if verbose:
            click.echo(msg)

    success, results = run_sdlc_workflow(
        task_description=task,
        worktree_name=worktree_name,
        adw_id=adw_id,
        config=config,
        on_progress=on_progress if verbose else None,
        skip_optional=quick,
        test_validation_config=test_config,
    )

    if verbose:
        click.echo(format_results_summary(results))

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
