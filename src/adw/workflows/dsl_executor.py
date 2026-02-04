"""DSL Workflow Executor - Execute YAML-defined workflows.

This module bridges DSL workflow definitions to the execution engine,
allowing custom workflows defined in YAML to be executed just like
the built-in Python workflows.

Example usage:
    from adw.workflows.dsl_executor import run_dsl_workflow
    from adw.workflows.dsl import get_workflow

    workflow = get_workflow("my-custom-workflow")
    success, results = run_dsl_workflow(
        workflow=workflow,
        task_description="Implement user authentication",
        worktree_name="auth-feature",
    )
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock

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
from .dsl import (
    LoopCondition,
    PhaseCondition,
    PhaseDefinition,
    PromptTemplate,
    WorkflowDefinition,
    get_workflow,
)

logger = logging.getLogger(__name__)


@dataclass
class DSLPhaseResult:
    """Result of executing a single DSL-defined phase."""

    phase_name: str
    success: bool
    output: str = ""
    error: str | None = None
    duration_seconds: float = 0.0
    test_result: ValidationResult | None = None
    loop_iterations: int = 1
    was_parallel: bool = False  # True if executed as part of a parallel group


@dataclass
class DSLExecutionContext:
    """Context passed between phases during workflow execution."""

    task_description: str
    adw_id: str
    worktree_path: Path
    state: ADWState
    last_test_passed: bool = True
    has_changes: bool = False
    phase_results: dict[str, DSLPhaseResult] = field(default_factory=dict)
    _lock: Lock = field(default_factory=Lock, repr=False)

    def update_result(self, phase_name: str, result: DSLPhaseResult) -> None:
        """Thread-safe update of phase results."""
        with self._lock:
            self.phase_results[phase_name] = result

    def get_result(self, phase_name: str) -> DSLPhaseResult | None:
        """Thread-safe get of phase result."""
        with self._lock:
            return self.phase_results.get(phase_name)


def check_git_changes(worktree_path: Path) -> bool:
    """Check if there are uncommitted git changes."""
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=worktree_path,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return bool(result.stdout.strip())
    except Exception as e:
        logger.debug("Error checking git status: %s", e)
        return False


def check_file_exists(worktree_path: Path, filename: str) -> bool:
    """Check if a file exists in the worktree."""
    return (worktree_path / filename).exists()


def check_env_set(env_name: str) -> bool:
    """Check if an environment variable is set."""
    return env_name in os.environ and bool(os.environ[env_name])


def evaluate_condition(
    condition: PhaseCondition,
    condition_value: str | None,
    context: DSLExecutionContext,
) -> bool:
    """Evaluate whether a phase condition is met.

    Args:
        condition: The condition type to evaluate.
        condition_value: Optional value for the condition (e.g., filename).
        context: Current execution context.

    Returns:
        True if condition is met, False otherwise.
    """
    if condition == PhaseCondition.ALWAYS:
        return True
    elif condition == PhaseCondition.HAS_CHANGES:
        return check_git_changes(context.worktree_path)
    elif condition == PhaseCondition.TESTS_PASSED:
        return context.last_test_passed
    elif condition == PhaseCondition.TESTS_FAILED:
        return not context.last_test_passed
    elif condition == PhaseCondition.FILE_EXISTS:
        if not condition_value:
            logger.warning("FILE_EXISTS condition requires a filename")
            return True  # Default to allowing execution
        return check_file_exists(context.worktree_path, condition_value)
    elif condition == PhaseCondition.ENV_SET:
        if not condition_value:
            logger.warning("ENV_SET condition requires an environment variable name")
            return True  # Default to allowing execution
        return check_env_set(condition_value)
    else:
        logger.warning("Unknown condition: %s", condition)
        return True


def run_phase_tests(
    phase: PhaseDefinition,
    context: DSLExecutionContext,
    on_progress: Callable[[str], None] | None = None,
) -> ValidationResult:
    """Run tests configured for a phase.

    Args:
        phase: Phase definition with test configuration.
        context: Execution context.
        on_progress: Optional progress callback.

    Returns:
        ValidationResult with test outcomes.
    """
    if not phase.tests:
        return ValidationResult(success=True)

    # Handle "auto" for automatic test detection
    if phase.tests == "auto":
        framework_info = detect_test_framework(context.worktree_path)
        if framework_info is None:
            if on_progress:
                on_progress("No test framework detected, skipping tests")
            return ValidationResult(success=True)
        test_command = framework_info.command
    else:
        test_command = phase.tests

    if on_progress:
        on_progress(f"Running tests: {test_command}")

    config = ValidationConfig(
        max_retries=0,  # We handle retries at the loop level
        timeout_seconds=phase.test_timeout,
        test_command=test_command,
    )

    return validate_tests(
        path=context.worktree_path,
        config=config,
        on_progress=on_progress,
        task_id=context.adw_id,
        task_description=context.task_description,
    )


def execute_dsl_phase(
    phase: PhaseDefinition,
    context: DSLExecutionContext,
    retry_context: str | None = None,
    on_progress: Callable[[str], None] | None = None,
) -> DSLPhaseResult:
    """Execute a single DSL-defined phase.

    Args:
        phase: Phase definition from workflow DSL.
        context: Execution context.
        retry_context: Optional context from previous failure.
        on_progress: Optional progress callback.

    Returns:
        DSLPhaseResult with execution outcome.
    """
    start_time = time.time()

    # Render prompt template
    template = PromptTemplate(phase.prompt, base_path=context.worktree_path)
    prompt = template.render(
        task_description=context.task_description,
        task=context.task_description,  # Alias for convenience
        adw_id=context.adw_id,
        worktree=str(context.worktree_path),
    )

    # Inject expertise for plan/implement phases
    if phase.name in ("plan", "implement"):
        try:
            from ..learning.expertise import inject_expertise_into_prompt

            prompt = inject_expertise_into_prompt(prompt=prompt, position="end")
        except Exception as e:
            logger.debug("Could not inject expertise: %s", e)

    # Add retry context if provided
    if retry_context:
        prompt = f"{prompt}\n\n{retry_context}"
        if on_progress:
            on_progress(f"Retrying {phase.name} with error context...")

    if on_progress:
        on_progress(f"Starting phase: {phase.name}")

    context.state.save(f"phase:{phase.name}:start")

    try:
        response = prompt_with_retry(
            AgentPromptRequest(
                prompt=prompt,
                adw_id=context.adw_id,
                agent_name=f"{phase.name}-{context.adw_id}",
                model=phase.model,
                timeout=phase.timeout_seconds,
                working_dir=str(context.worktree_path),
            ),
            max_retries=phase.max_retries,
        )

        duration = time.time() - start_time

        if response.success:
            context.state.save(f"phase:{phase.name}:complete")
            return DSLPhaseResult(
                phase_name=phase.name,
                success=True,
                output=response.output or "",
                duration_seconds=duration,
            )
        else:
            error = response.error_message or "Unknown error"
            context.state.add_error(phase.name, error)
            return DSLPhaseResult(
                phase_name=phase.name,
                success=False,
                error=error,
                duration_seconds=duration,
            )

    except Exception as e:
        duration = time.time() - start_time
        error = str(e)
        context.state.add_error(phase.name, error)
        return DSLPhaseResult(
            phase_name=phase.name,
            success=False,
            error=error,
            duration_seconds=duration,
        )


def execute_phase_with_loop(
    phase: PhaseDefinition,
    context: DSLExecutionContext,
    on_progress: Callable[[str], None] | None = None,
) -> tuple[DSLPhaseResult, list[AttemptRecord]]:
    """Execute a phase with loop handling.

    Args:
        phase: Phase definition with loop configuration.
        context: Execution context.
        on_progress: Optional progress callback.

    Returns:
        Tuple of (final result, list of attempt records).
    """
    attempt_records: list[AttemptRecord] = []
    iterations = 0
    max_iterations = phase.loop_max if phase.loop != LoopCondition.NONE else 1
    current_retry_context: str | None = None
    final_result: DSLPhaseResult | None = None

    while iterations < max_iterations:
        iterations += 1

        if on_progress and phase.loop != LoopCondition.NONE:
            on_progress(f"Phase {phase.name} iteration {iterations}/{max_iterations}")

        # Execute the phase
        result = execute_dsl_phase(
            phase=phase,
            context=context,
            retry_context=current_retry_context,
            on_progress=on_progress,
        )
        result.loop_iterations = iterations
        final_result = result

        # If phase failed, handle based on loop condition
        if not result.success:
            if phase.loop == LoopCondition.UNTIL_SUCCESS:
                if iterations < max_iterations:
                    attempt_records.append(
                        AttemptRecord(
                            attempt_number=iterations,
                            phase=phase.name,
                            error_message=result.error or "Unknown error",
                            strategy="retry",
                            duration_seconds=result.duration_seconds,
                        )
                    )
                    continue
            break

        # Run tests if configured
        if phase.tests:
            test_result = run_phase_tests(phase, context, on_progress)
            result.test_result = test_result
            context.last_test_passed = test_result.success

            if not test_result.success:
                if phase.loop == LoopCondition.UNTIL_TESTS_PASS:
                    if iterations < max_iterations:
                        # Generate retry context
                        if test_result.final_test_result:
                            current_retry_context = format_test_failure_context(
                                test_result=test_result.final_test_result,
                                phase=phase.name,
                                attempt_number=iterations,
                                max_attempts=max_iterations,
                            )
                        else:
                            current_retry_context = test_result.retry_context

                        attempt_records.append(
                            AttemptRecord(
                                attempt_number=iterations,
                                phase=f"{phase.name}_tests",
                                error_message=test_result.retry_context or "Tests failed",
                                strategy=select_retry_strategy(iterations, max_iterations).value,
                                duration_seconds=result.duration_seconds,
                            )
                        )
                        continue

                # Tests failed without retry loop
                result.success = False
                result.error = test_result.retry_context or "Tests failed"
                break

        # Handle fixed count loop
        if phase.loop == LoopCondition.FIXED_COUNT:
            if iterations < max_iterations:
                continue

        # Success - exit loop
        break

    return final_result or result, attempt_records


# ============================================================================
# Parallel Execution Support
# ============================================================================


def build_parallel_groups(
    phases: list[PhaseDefinition],
) -> list[list[PhaseDefinition]]:
    """Build groups of phases that can be executed together.

    Phases with `parallel_with` references are grouped together.
    Phases without parallel references are in their own single-phase group.

    Args:
        phases: List of phase definitions.

    Returns:
        List of phase groups (each group executes in parallel).
    """
    groups: list[list[PhaseDefinition]] = []
    processed_names: set[str] = set()

    for phase in phases:
        if phase.name in processed_names:
            continue

        if phase.parallel_with:
            # Build a group with this phase and all its parallel partners
            group = [phase]
            processed_names.add(phase.name)

            for ref_name in phase.parallel_with:
                # Find the referenced phase
                ref_phase = next((p for p in phases if p.name == ref_name), None)
                if ref_phase and ref_name not in processed_names:
                    group.append(ref_phase)
                    processed_names.add(ref_name)

            groups.append(group)
        else:
            # Single phase group
            groups.append([phase])
            processed_names.add(phase.name)

    return groups


def execute_parallel_phases(
    phases: list[PhaseDefinition],
    context: DSLExecutionContext,
    on_progress: Callable[[str], None] | None = None,
    max_workers: int = 4,
) -> tuple[list[DSLPhaseResult], list[AttemptRecord]]:
    """Execute multiple phases in parallel.

    Args:
        phases: List of phases to execute in parallel.
        context: Execution context shared by all phases.
        on_progress: Optional progress callback (called thread-safely).
        max_workers: Maximum number of concurrent phase executions.

    Returns:
        Tuple of (list of results, list of attempt records).
    """
    results: list[DSLPhaseResult] = []
    all_attempt_records: list[AttemptRecord] = []
    results_lock = Lock()

    if len(phases) == 1:
        # Single phase, no need for threading
        result, attempt_records = execute_phase_with_loop(
            phase=phases[0],
            context=context,
            on_progress=on_progress,
        )
        return [result], attempt_records

    if on_progress:
        phase_names = ", ".join(p.name for p in phases)
        on_progress(f"Executing phases in parallel: {phase_names}")

    def execute_single(phase: PhaseDefinition) -> tuple[DSLPhaseResult, list[AttemptRecord]]:
        """Execute a single phase in a thread."""

        # Create thread-safe progress callback
        def thread_progress(msg: str) -> None:
            if on_progress:
                on_progress(f"[{phase.name}] {msg}")

        result, attempt_records = execute_phase_with_loop(
            phase=phase,
            context=context,
            on_progress=thread_progress,
        )
        result.was_parallel = True
        return result, attempt_records

    # Execute phases in parallel using ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=min(max_workers, len(phases))) as executor:
        # Submit all phases
        future_to_phase = {executor.submit(execute_single, phase): phase for phase in phases}

        # Collect results as they complete
        for future in as_completed(future_to_phase):
            phase = future_to_phase[future]
            try:
                result, attempt_records = future.result()
                with results_lock:
                    results.append(result)
                    all_attempt_records.extend(attempt_records)
                    # Update context with result
                    context.update_result(phase.name, result)
            except Exception as e:
                # Handle unexpected exceptions during parallel execution
                logger.error("Phase %s failed with exception: %s", phase.name, e)
                error_result = DSLPhaseResult(
                    phase_name=phase.name,
                    success=False,
                    error=str(e),
                    was_parallel=True,
                )
                with results_lock:
                    results.append(error_result)
                    context.update_result(phase.name, error_result)

    # Sort results to match original phase order
    phase_order = {p.name: i for i, p in enumerate(phases)}
    results.sort(key=lambda r: phase_order.get(r.phase_name, 999))

    return results, all_attempt_records


def get_current_commit() -> str | None:
    """Get current git commit hash."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except Exception:
        return None


def run_dsl_workflow(
    workflow: WorkflowDefinition,
    task_description: str,
    worktree_name: str,
    adw_id: str | None = None,
    on_progress: Callable[[str], None] | None = None,
    skip_optional: bool = False,
) -> tuple[bool, list[DSLPhaseResult]]:
    """Execute a DSL-defined workflow.

    This is the main entry point for executing custom workflows defined
    in YAML. It handles all phase execution, conditions, loops, and
    test validation.

    Args:
        workflow: WorkflowDefinition loaded from YAML.
        task_description: Description of the task to execute.
        worktree_name: Git worktree name for the execution.
        adw_id: Optional ADW ID (generated if not provided).
        on_progress: Optional callback for progress updates.
        skip_optional: If True, skip non-required phases.

    Returns:
        Tuple of (overall_success, list of phase results).
    """
    adw_id = adw_id or generate_adw_id()
    tasks_file = Path("tasks.md")
    worktree_path = Path.cwd()  # TODO: Resolve actual worktree path

    # Initialize context
    context = DSLExecutionContext(
        task_description=task_description,
        adw_id=adw_id,
        worktree_path=worktree_path,
        state=ADWState(
            adw_id=adw_id,
            task_description=task_description,
            worktree_name=worktree_name,
            workflow_type=f"dsl:{workflow.name}",
        ),
    )
    context.state.save("init")

    # Mark task as in progress
    mark_in_progress(tasks_file, task_description, adw_id)

    # Filter phases if skipping optional
    phases = workflow.phases
    if skip_optional:
        phases = [p for p in phases if p.required]

    results: list[DSLPhaseResult] = []
    all_attempt_records: list[AttemptRecord] = []
    overall_success = True
    required_failed = False

    if on_progress:
        on_progress(f"Starting workflow: {workflow.name} ({len(phases)} phases)")

    # Build phase groups for parallel execution
    phase_groups = build_parallel_groups(phases)

    for group in phase_groups:
        # Filter out phases that don't meet conditions or should be skipped
        eligible_phases: list[PhaseDefinition] = []
        for phase in group:
            # Check condition
            if not evaluate_condition(phase.condition, phase.condition_value, context):
                if on_progress:
                    on_progress(f"Skipping phase {phase.name}: condition not met ({phase.condition.value})")
                continue

            # Skip optional phases if a required phase has failed
            if not phase.required and required_failed and workflow.skip_optional_on_failure:
                if on_progress:
                    on_progress(f"Skipping optional phase {phase.name}: previous required phase failed")
                continue

            eligible_phases.append(phase)

        if not eligible_phases:
            continue

        # Execute phases (parallel if multiple, sequential if single)
        if len(eligible_phases) > 1:
            # Parallel execution
            group_results, attempt_records = execute_parallel_phases(
                phases=eligible_phases,
                context=context,
                on_progress=on_progress,
            )
        else:
            # Single phase execution
            phase = eligible_phases[0]
            if on_progress:
                on_progress(f"Phase: {phase.name}")

            result, attempt_records = execute_phase_with_loop(
                phase=phase,
                context=context,
                on_progress=on_progress,
            )
            group_results = [result]

        # Process results
        results.extend(group_results)
        all_attempt_records.extend(attempt_records)

        for result in group_results:
            context.update_result(result.phase_name, result)

        # Update context state
        context.has_changes = check_git_changes(worktree_path)

        # Check for failures
        fail_fast_triggered = False
        for result in group_results:
            if not result.success:
                failed_phase = next((p for p in eligible_phases if p.name == result.phase_name), None)
                if failed_phase and failed_phase.required:
                    overall_success = False
                    required_failed = True

                    if on_progress:
                        on_progress(f"Required phase {result.phase_name} failed: {result.error}")

                    # Generate escalation report if there were retries
                    if attempt_records:
                        generate_escalation_report(
                            task_id=adw_id,
                            task_description=task_description,
                            workflow_type=f"dsl:{workflow.name}",
                            attempts=all_attempt_records,
                            output_dir=Path(f"agents/{adw_id}"),
                        )
                        logger.warning("Generated escalation report for task %s", adw_id)

                    if workflow.fail_fast:
                        fail_fast_triggered = True
                else:
                    if on_progress:
                        on_progress(f"Optional phase {result.phase_name} failed, continuing...")

        if fail_fast_triggered:
            break

    # Get final commit
    commit_hash = get_current_commit()
    context.state.commit_hash = commit_hash

    # Update task status
    if overall_success:
        mark_done(tasks_file, task_description, adw_id, commit_hash)
        context.state.save("complete")
        if on_progress:
            on_progress("Workflow completed successfully")
    else:
        failed_result = next((r for r in results if not r.success), None)
        error_msg = failed_result.error if failed_result and failed_result.error else "Unknown error"
        mark_failed(tasks_file, task_description, adw_id, error_msg)
        context.state.save("failed")

    return overall_success, results


def format_dsl_results_summary(workflow_name: str, results: list[DSLPhaseResult]) -> str:
    """Format DSL phase results as a summary string."""
    lines = [f"Workflow '{workflow_name}' Results:", "=" * 40]

    for result in results:
        status = "✅" if result.success else "❌"
        parallel_indicator = " ⚡" if result.was_parallel else ""
        line = f"{status} {result.phase_name}{parallel_indicator}: {result.duration_seconds:.1f}s"
        if result.loop_iterations > 1:
            line += f" ({result.loop_iterations} iterations)"
        if result.error:
            line += f" - {result.error}"
        lines.append(line)

    total_time = sum(r.duration_seconds for r in results)
    success_count = sum(1 for r in results if r.success)
    parallel_count = sum(1 for r in results if r.was_parallel)
    lines.append("=" * 40)
    summary = f"Total: {success_count}/{len(results)} phases, {total_time:.1f}s"
    if parallel_count > 0:
        summary += f" ({parallel_count} parallel)"
    lines.append(summary)

    return "\n".join(lines)


def run_workflow_by_name(
    workflow_name: str,
    task_description: str,
    worktree_name: str,
    adw_id: str | None = None,
    on_progress: Callable[[str], None] | None = None,
    skip_optional: bool = False,
) -> tuple[bool, list[DSLPhaseResult]]:
    """Execute a workflow by name (loads from DSL library).

    This is a convenience function that loads a workflow by name
    from the DSL library and executes it.

    Args:
        workflow_name: Name of the workflow to execute.
        task_description: Description of the task.
        worktree_name: Git worktree name.
        adw_id: Optional ADW ID.
        on_progress: Optional progress callback.
        skip_optional: Skip optional phases.

    Returns:
        Tuple of (success, results).

    Raises:
        ValueError: If workflow not found.
    """
    workflow = get_workflow(workflow_name)
    if workflow is None:
        raise ValueError(f"Workflow '{workflow_name}' not found")

    return run_dsl_workflow(
        workflow=workflow,
        task_description=task_description,
        worktree_name=worktree_name,
        adw_id=adw_id,
        on_progress=on_progress,
        skip_optional=skip_optional,
    )


@click.command()
@click.option("--workflow", "-w", required=True, help="Workflow name to execute")
@click.option("--adw-id", help="ADW tracking ID")
@click.option("--worktree-name", required=True, help="Git worktree name")
@click.option("--task", required=True, help="Task description")
@click.option("--skip-optional", is_flag=True, help="Skip optional phases")
@click.option("--verbose", "-v", is_flag=True, help="Show progress")
def main(
    workflow: str,
    adw_id: str | None,
    worktree_name: str,
    task: str,
    skip_optional: bool,
    verbose: bool,
) -> None:
    """Execute a DSL-defined workflow."""

    def on_progress(msg: str) -> None:
        if verbose:
            click.echo(msg)

    try:
        success, results = run_workflow_by_name(
            workflow_name=workflow,
            task_description=task,
            worktree_name=worktree_name,
            adw_id=adw_id,
            on_progress=on_progress if verbose else None,
            skip_optional=skip_optional,
        )

        if verbose:
            click.echo(format_dsl_results_summary(workflow, results))

        sys.exit(0 if success else 1)

    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
