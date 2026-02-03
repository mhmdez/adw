"""Adaptive SDLC Workflow.

This module provides a single, unified workflow that automatically adapts to
task complexity. It replaces the separate simple/standard/sdlc workflows with
one configurable workflow.

Task Complexity Detection:
- MINIMAL: Well-defined, small tasks (docs, typos, simple fixes)
- STANDARD: Tasks requiring planning (features, refactors)
- FULL: Complex tasks requiring full SDLC (critical bugs, new systems)

The workflow analyzes the task description, priority, tags, and optional
explicit overrides to determine the appropriate execution phases.
"""

from __future__ import annotations

import logging
import re
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Literal

import click

from ..agent.environment import write_env_file
from ..agent.executor import prompt_with_retry
from ..agent.models import AgentPromptRequest
from ..agent.ports import find_available_ports, write_ports_env
from ..agent.state import ADWState
from ..agent.task_updater import mark_done, mark_failed, mark_in_progress
from ..agent.utils import generate_adw_id
from ..agent.worktree import create_worktree
from ..retry.context import format_test_failure_context, select_retry_strategy
from ..retry.escalation import AttemptRecord, generate_escalation_report
from ..testing.detector import detect_test_framework
from ..testing.validation import ValidationConfig, ValidationResult, validate_tests

logger = logging.getLogger(__name__)

# Type alias for model names
ModelType = Literal["haiku", "sonnet", "opus"]


class TaskComplexity(str, Enum):
    """Task complexity levels determining workflow behavior."""

    MINIMAL = "minimal"  # Direct implementation, no planning
    STANDARD = "standard"  # Plan + Implement
    FULL = "full"  # Full SDLC with test validation


class AdaptivePhase(str, Enum):
    """Phases available in the adaptive workflow."""

    PLAN = "plan"
    IMPLEMENT = "implement"
    TEST = "test"
    REVIEW = "review"
    DOCUMENT = "document"


@dataclass
class PhaseConfig:
    """Configuration for a workflow phase."""

    name: AdaptivePhase
    prompt_template: str
    model: ModelType = "sonnet"
    required: bool = True
    max_retries: int = 2
    timeout_seconds: int = 600


@dataclass
class AdaptiveConfig:
    """Configuration for the adaptive workflow.

    This configuration determines which phases run based on task complexity.
    """

    complexity: TaskComplexity = TaskComplexity.STANDARD
    phases: list[PhaseConfig] = field(default_factory=list)
    test_validation_enabled: bool = True
    max_test_retries: int = 3
    test_timeout_seconds: int = 300
    skip_if_no_tests: bool = True
    inject_expertise: bool = True

    @classmethod
    def for_complexity(cls, complexity: TaskComplexity) -> AdaptiveConfig:
        """Create configuration for a specific complexity level."""
        if complexity == TaskComplexity.MINIMAL:
            return cls._minimal()
        elif complexity == TaskComplexity.STANDARD:
            return cls._standard()
        else:
            return cls._full()

    @classmethod
    def _minimal(cls) -> AdaptiveConfig:
        """Minimal workflow: just implement (like simple workflow)."""
        return cls(
            complexity=TaskComplexity.MINIMAL,
            phases=[
                PhaseConfig(
                    name=AdaptivePhase.IMPLEMENT,
                    prompt_template="/build {task}",
                    model="sonnet",
                    timeout_seconds=900,
                ),
            ],
            test_validation_enabled=False,
            inject_expertise=False,
        )

    @classmethod
    def _standard(cls) -> AdaptiveConfig:
        """Standard workflow: plan + implement (like standard workflow)."""
        return cls(
            complexity=TaskComplexity.STANDARD,
            phases=[
                PhaseConfig(
                    name=AdaptivePhase.PLAN,
                    prompt_template="/plan {task}",
                    model="sonnet",
                    timeout_seconds=600,
                ),
                PhaseConfig(
                    name=AdaptivePhase.IMPLEMENT,
                    prompt_template="/implement {task}",
                    model="sonnet",
                    timeout_seconds=1200,
                ),
            ],
            test_validation_enabled=True,
            inject_expertise=True,
        )

    @classmethod
    def _full(cls) -> AdaptiveConfig:
        """Full SDLC workflow (like sdlc workflow)."""
        return cls(
            complexity=TaskComplexity.FULL,
            phases=[
                PhaseConfig(
                    name=AdaptivePhase.PLAN,
                    prompt_template="/plan {task}",
                    model="opus",
                    timeout_seconds=900,
                ),
                PhaseConfig(
                    name=AdaptivePhase.IMPLEMENT,
                    prompt_template="/implement {task}",
                    model="sonnet",
                    timeout_seconds=1200,
                ),
                PhaseConfig(
                    name=AdaptivePhase.TEST,
                    prompt_template="/test {task}",
                    model="sonnet",
                    timeout_seconds=600,
                ),
                PhaseConfig(
                    name=AdaptivePhase.REVIEW,
                    prompt_template="/review {task}",
                    model="opus",
                    timeout_seconds=600,
                ),
                PhaseConfig(
                    name=AdaptivePhase.DOCUMENT,
                    prompt_template="/document {task}",
                    model="haiku",
                    required=False,
                    timeout_seconds=300,
                ),
            ],
            test_validation_enabled=True,
            max_test_retries=3,
            inject_expertise=True,
        )


@dataclass
class PhaseResult:
    """Result from executing a single phase."""

    phase: AdaptivePhase
    success: bool
    output: str = ""
    error: str | None = None
    duration_seconds: float = 0.0
    test_result: ValidationResult | None = None


# Patterns for detecting task complexity from description
MINIMAL_PATTERNS = [
    r"\b(typo|spelling|grammar|comment|readme|doc(s|umentation)?)\b",
    r"\b(minor|tiny|small|quick)\s+(fix|change|update)\b",
    r"\b(remove|delete)\s+(unused|dead)\b",
    r"\bchore\b",
    r"\bupdate\s+(dependency|dependencies|version)\b",
]

FULL_PATTERNS = [
    r"\b(critical|urgent|p0|priority\s*0|blocker)\b",
    r"\b(security|vulnerability|auth(entication)?|authz|authorization)\b",
    r"\b(new\s+)?system\b",
    r"\b(architect(ure)?|design|redesign)\b",
    r"\b(refactor|rewrite|overhaul)\b",
    r"\b(performance|optimization|scale|scalability)\b",
    r"\b(api|endpoint).*\b(add|create|implement)\b",
    r"\b(database|schema|migration)\b",
]


def detect_complexity(
    description: str,
    priority: str | None = None,
    tags: list[str] | None = None,
    explicit_workflow: str | None = None,
) -> TaskComplexity:
    """Detect task complexity from description and metadata.

    Args:
        description: Task description text.
        priority: Optional priority level (p0, p1, p2, p3).
        tags: Optional list of task tags.
        explicit_workflow: Optional explicit workflow override.

    Returns:
        Detected TaskComplexity level.
    """
    tags = tags or []
    desc_lower = description.lower()

    # Explicit workflow overrides
    if explicit_workflow:
        mapping = {
            "simple": TaskComplexity.MINIMAL,
            "standard": TaskComplexity.STANDARD,
            "sdlc": TaskComplexity.FULL,
            "full": TaskComplexity.FULL,
            "minimal": TaskComplexity.MINIMAL,
        }
        if explicit_workflow in mapping:
            return mapping[explicit_workflow]

    # Check tags for explicit complexity
    if "simple" in tags or "minimal" in tags:
        return TaskComplexity.MINIMAL
    if "sdlc" in tags or "full" in tags:
        return TaskComplexity.FULL

    # Priority-based detection
    if priority == "p0":
        return TaskComplexity.FULL
    if priority == "p3":
        return TaskComplexity.MINIMAL

    # Pattern-based detection
    for pattern in FULL_PATTERNS:
        if re.search(pattern, desc_lower, re.IGNORECASE):
            return TaskComplexity.FULL

    for pattern in MINIMAL_PATTERNS:
        if re.search(pattern, desc_lower, re.IGNORECASE):
            return TaskComplexity.MINIMAL

    # Default to standard
    return TaskComplexity.STANDARD


def get_current_commit(cwd: Path | str | None = None) -> str | None:
    """Get current git commit hash."""
    result = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        capture_output=True,
        text=True,
        cwd=cwd,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def run_test_validation(
    worktree_path: Path,
    adw_id: str,
    task_description: str,
    config: AdaptiveConfig,
    on_progress: Callable[[str], None] | None = None,
) -> ValidationResult:
    """Run test validation.

    Args:
        worktree_path: Path to the working directory.
        adw_id: ADW task ID.
        task_description: Task description.
        config: Workflow configuration.
        on_progress: Progress callback.

    Returns:
        ValidationResult with test outcomes.
    """
    if not config.test_validation_enabled:
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
        timeout_seconds=config.test_timeout_seconds,
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


def execute_phase(
    phase_config: PhaseConfig,
    task_description: str,
    adw_id: str,
    state: ADWState,
    worktree_path: Path | None = None,
    retry_context: str | None = None,
    on_progress: Callable[[str], None] | None = None,
    inject_expertise: bool = True,
) -> PhaseResult:
    """Execute a single workflow phase.

    Args:
        phase_config: Phase configuration.
        task_description: Task description.
        adw_id: ADW tracking ID.
        state: Workflow state.
        worktree_path: Working directory path.
        retry_context: Optional retry context from previous failure.
        on_progress: Progress callback.
        inject_expertise: Whether to inject expertise section.

    Returns:
        PhaseResult with execution outcome.
    """
    start_time = time.time()
    phase_name = phase_config.name.value

    # Build prompt
    prompt = phase_config.prompt_template.format(task=task_description)

    # Inject expertise for PLAN and IMPLEMENT phases
    if inject_expertise and phase_name in ("plan", "implement"):
        try:
            from ..learning.expertise import inject_expertise_into_prompt

            prompt = inject_expertise_into_prompt(prompt=prompt, position="end")
        except Exception as e:
            logger.debug("Could not inject expertise: %s", e)

    # Add retry context if provided
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
                dangerously_skip_permissions=True,
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


def run_adaptive_workflow(
    task_description: str,
    worktree_name: str,
    adw_id: str | None = None,
    config: AdaptiveConfig | None = None,
    complexity: TaskComplexity | None = None,
    priority: str | None = None,
    tags: list[str] | None = None,
    explicit_workflow: str | None = None,
    model_override: ModelType | None = None,
    on_progress: Callable[[str], None] | None = None,
) -> tuple[bool, list[PhaseResult]]:
    """Execute the adaptive workflow.

    This is the main entry point for task execution. It automatically detects
    task complexity and runs the appropriate phases.

    Args:
        task_description: What to build/implement.
        worktree_name: Git worktree to work in.
        adw_id: Optional ADW ID (generated if not provided).
        config: Optional explicit configuration.
        complexity: Optional explicit complexity level.
        priority: Optional task priority (p0-p3).
        tags: Optional task tags.
        explicit_workflow: Optional explicit workflow name.
        model_override: Optional model to use for all phases.
        on_progress: Progress callback.

    Returns:
        Tuple of (overall_success, list of phase results).
    """
    adw_id = adw_id or generate_adw_id()
    tasks_file = Path("tasks.md")
    tags = tags or []

    # Detect complexity if not provided
    if complexity is None:
        complexity = detect_complexity(
            description=task_description,
            priority=priority,
            tags=tags,
            explicit_workflow=explicit_workflow,
        )

    if on_progress:
        on_progress(f"Detected complexity: {complexity.value}")

    # Get configuration
    if config is None:
        config = AdaptiveConfig.for_complexity(complexity)

    # Apply model override if provided
    if model_override:
        for phase in config.phases:
            phase.model = model_override

    # Create worktree
    worktree_path = create_worktree(worktree_name)
    if not worktree_path:
        return False, []

    # Allocate ports and setup environment
    backend_port, frontend_port = find_available_ports(adw_id)
    write_ports_env(str(worktree_path), backend_port, frontend_port)
    write_env_file(
        worktree_path,
        {
            "ADW_ID": adw_id,
            "ADW_WORKTREE": worktree_name,
            "ADW_COMPLEXITY": complexity.value,
        },
        filename=".adw.env",
    )

    # Initialize state
    state = ADWState(
        adw_id=adw_id,
        task_description=task_description,
        worktree_name=worktree_name,
        workflow_type=f"adaptive:{complexity.value}",
    )
    state.save("init")

    # Mark task as in progress
    mark_in_progress(tasks_file, task_description, adw_id)

    results: list[PhaseResult] = []
    overall_success = True
    attempt_records: list[AttemptRecord] = []

    # Track test retry cycles
    test_retry_count = 0
    current_retry_context: str | None = None

    i = 0
    while i < len(config.phases):
        phase_config = config.phases[i]
        phase_name = phase_config.name

        if on_progress:
            on_progress(f"Phase: {phase_name.value}")

        # Execute phase with optional retry context
        result = execute_phase(
            phase_config=phase_config,
            task_description=task_description,
            adw_id=adw_id,
            state=state,
            worktree_path=worktree_path,
            retry_context=current_retry_context if phase_name == AdaptivePhase.IMPLEMENT else None,
            on_progress=on_progress,
            inject_expertise=config.inject_expertise,
        )
        current_retry_context = None  # Clear after use
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
        if phase_name == AdaptivePhase.TEST and config.test_validation_enabled:
            if on_progress:
                on_progress("Running test validation...")

            start_time = time.time()
            validation_result = run_test_validation(
                worktree_path=worktree_path,
                adw_id=adw_id,
                task_description=task_description,
                config=config,
                on_progress=on_progress,
            )
            duration = time.time() - start_time

            result.test_result = validation_result

            if not validation_result.success:
                test_retry_count += 1

                # Record the attempt
                strategy = select_retry_strategy(test_retry_count, config.max_test_retries + 1)
                attempt_records.append(
                    AttemptRecord(
                        attempt_number=test_retry_count,
                        phase="test_validation",
                        error_message=validation_result.retry_context or "Tests failed",
                        strategy=strategy.value,
                        duration_seconds=duration,
                    )
                )

                if test_retry_count < config.max_test_retries:
                    if on_progress:
                        on_progress(
                            f"Tests failed (attempt {test_retry_count}/{config.max_test_retries}), "
                            "re-running implement phase with error context..."
                        )

                    # Generate retry context
                    if validation_result.final_test_result:
                        current_retry_context = format_test_failure_context(
                            test_result=validation_result.final_test_result,
                            phase="implement",
                            attempt_number=test_retry_count,
                            max_attempts=config.max_test_retries,
                        )
                    else:
                        current_retry_context = validation_result.retry_context

                    # Jump back to IMPLEMENT phase
                    implement_idx = next(
                        (idx for idx, p in enumerate(config.phases) if p.name == AdaptivePhase.IMPLEMENT),
                        None,
                    )
                    if implement_idx is not None:
                        i = implement_idx
                        continue
                else:
                    # All retries exhausted
                    if on_progress:
                        on_progress("All test retries exhausted, generating escalation report...")

                    generate_escalation_report(
                        task_id=adw_id,
                        task_description=task_description,
                        workflow_type=f"adaptive:{complexity.value}",
                        attempts=attempt_records,
                        output_dir=Path(f"agents/{adw_id}"),
                    )
                    logger.warning("Generated escalation report for task %s", adw_id)

                    overall_success = False
                    result.error = f"Tests failed after {test_retry_count} retries"
                    result.success = False
                    break

        # After IMPLEMENT phase, run test validation for STANDARD complexity
        # (when there's no explicit TEST phase)
        if (
            phase_name == AdaptivePhase.IMPLEMENT
            and config.test_validation_enabled
            and config.complexity == TaskComplexity.STANDARD
            and not any(p.name == AdaptivePhase.TEST for p in config.phases)
        ):
            if on_progress:
                on_progress("Running test validation after implement...")

            validation_result = run_test_validation(
                worktree_path=worktree_path,
                adw_id=adw_id,
                task_description=task_description,
                config=config,
                on_progress=on_progress,
            )

            if not validation_result.success:
                test_retry_count += 1

                if test_retry_count < config.max_test_retries:
                    if on_progress:
                        on_progress(
                            f"Tests failed (attempt {test_retry_count}/{config.max_test_retries}), "
                            "retrying implement phase..."
                        )

                    if validation_result.final_test_result:
                        current_retry_context = format_test_failure_context(
                            test_result=validation_result.final_test_result,
                            phase="implement",
                            attempt_number=test_retry_count,
                            max_attempts=config.max_test_retries,
                        )
                    else:
                        current_retry_context = validation_result.retry_context

                    # Stay at IMPLEMENT phase (don't increment i)
                    continue

        i += 1

    # Get final commit
    commit_hash = get_current_commit(worktree_path)
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


def format_results_summary(results: list[PhaseResult], complexity: TaskComplexity | None = None) -> str:
    """Format phase results as a summary string."""
    lines = [f"Adaptive Workflow Results ({complexity.value if complexity else 'unknown'}):", "=" * 50]

    for result in results:
        status = "✅" if result.success else "❌"
        line = f"{status} {result.phase.value}: {result.duration_seconds:.1f}s"
        if result.error:
            line += f" - {result.error}"
        lines.append(line)

    total_time = sum(r.duration_seconds for r in results)
    success_count = sum(1 for r in results if r.success)
    lines.append("=" * 50)
    lines.append(f"Total: {success_count}/{len(results)} phases, {total_time:.1f}s")

    return "\n".join(lines)


# Backward compatibility aliases
def run_simple_workflow(
    task_description: str,
    worktree_name: str,
    adw_id: str | None = None,
    model: str = "sonnet",
) -> bool:
    """Run minimal complexity workflow (backward compatible)."""
    success, _ = run_adaptive_workflow(
        task_description=task_description,
        worktree_name=worktree_name,
        adw_id=adw_id,
        complexity=TaskComplexity.MINIMAL,
        model_override=model,  # type: ignore
    )
    return success


def run_standard_workflow(
    task_description: str,
    worktree_name: str,
    adw_id: str | None = None,
    model: str = "sonnet",
) -> bool:
    """Run standard complexity workflow (backward compatible)."""
    success, _ = run_adaptive_workflow(
        task_description=task_description,
        worktree_name=worktree_name,
        adw_id=adw_id,
        complexity=TaskComplexity.STANDARD,
        model_override=model,  # type: ignore
    )
    return success


def run_sdlc_workflow(
    task_description: str,
    worktree_name: str,
    adw_id: str | None = None,
    on_progress: Callable[[str], None] | None = None,
) -> tuple[bool, list[PhaseResult]]:
    """Run full complexity workflow (backward compatible)."""
    return run_adaptive_workflow(
        task_description=task_description,
        worktree_name=worktree_name,
        adw_id=adw_id,
        complexity=TaskComplexity.FULL,
        on_progress=on_progress,
    )


@click.command()
@click.option("--adw-id", help="ADW tracking ID")
@click.option("--worktree-name", required=True, help="Git worktree name")
@click.option("--task", required=True, help="Task description")
@click.option(
    "--complexity",
    type=click.Choice(["minimal", "standard", "full", "auto"]),
    default="auto",
    help="Task complexity (auto-detects if not specified)",
)
@click.option(
    "--model",
    type=click.Choice(["haiku", "sonnet", "opus"]),
    help="Override model for all phases",
)
@click.option("--priority", type=click.Choice(["p0", "p1", "p2", "p3"]), help="Task priority")
@click.option("--verbose", is_flag=True, help="Show progress")
@click.option("--no-test-validation", is_flag=True, help="Disable automatic test validation")
def main(
    adw_id: str | None,
    worktree_name: str,
    task: str,
    complexity: str,
    model: str | None,
    priority: str | None,
    verbose: bool,
    no_test_validation: bool,
) -> None:
    """Run the adaptive SDLC workflow.

    This workflow automatically detects task complexity and runs the
    appropriate phases. Complexity can also be specified explicitly.
    """
    # Detect or use explicit complexity
    if complexity == "auto":
        detected = detect_complexity(task, priority=priority)
    else:
        complexity_map = {
            "minimal": TaskComplexity.MINIMAL,
            "standard": TaskComplexity.STANDARD,
            "full": TaskComplexity.FULL,
        }
        detected = complexity_map[complexity]

    # Create config and optionally disable test validation
    config = AdaptiveConfig.for_complexity(detected)
    if no_test_validation:
        config.test_validation_enabled = False

    def on_progress(msg: str) -> None:
        if verbose:
            click.echo(msg)

    success, results = run_adaptive_workflow(
        task_description=task,
        worktree_name=worktree_name,
        adw_id=adw_id,
        config=config,
        complexity=detected,
        priority=priority,
        model_override=model,  # type: ignore
        on_progress=on_progress if verbose else None,
    )

    if verbose:
        click.echo(format_results_summary(results, detected))

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
