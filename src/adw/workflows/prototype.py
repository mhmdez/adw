"""Prototype workflows for rapid application generation.

This module provides both configuration for prototype types and
execution logic to scaffold new applications using Claude Code.

Example usage:
    from adw.workflows.prototype import run_prototype_workflow

    success, result = run_prototype_workflow(
        prototype_type="vite_vue",
        app_name="my-app",
        description="A task management app",
    )
"""

from __future__ import annotations

import logging
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import click

from ..agent.executor import prompt_with_retry
from ..agent.models import AgentPromptRequest
from ..agent.state import ADWState
from ..agent.task_updater import mark_done, mark_failed, mark_in_progress
from ..agent.utils import generate_adw_id

logger = logging.getLogger(__name__)


@dataclass
class PrototypeConfig:
    """Configuration for a prototype type."""

    name: str
    plan_command: str
    description: str
    output_dir: str
    file_patterns: list[str]


@dataclass
class PrototypeResult:
    """Result of running a prototype workflow."""

    success: bool
    output_dir: Path | None = None
    error: str | None = None
    files_created: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0


# Available prototype types
PROTOTYPES: dict[str, PrototypeConfig] = {
    "vite_vue": PrototypeConfig(
        name="Vite + Vue",
        plan_command="/plan_vite_vue",
        description="Modern Vue 3 application with TypeScript and Vite",
        output_dir="apps/{app_name}",
        file_patterns=[
            "package.json",
            "vite.config.ts",
            "tsconfig.json",
            "src/App.vue",
            "src/main.ts",
            "src/components/*.vue",
            "index.html",
        ],
    ),
    "uv_script": PrototypeConfig(
        name="UV Script",
        plan_command="/plan_uv_script",
        description="Single-file Python CLI with inline dependencies",
        output_dir="apps/{app_name}",
        file_patterns=[
            "main.py",  # With /// script header
        ],
    ),
    "bun_scripts": PrototypeConfig(
        name="Bun TypeScript",
        plan_command="/plan_bun_scripts",
        description="TypeScript application with Bun runtime",
        output_dir="apps/{app_name}",
        file_patterns=[
            "package.json",
            "tsconfig.json",
            "src/index.ts",
            "src/**/*.ts",
        ],
    ),
    "uv_mcp": PrototypeConfig(
        name="MCP Server",
        plan_command="/plan_uv_mcp",
        description="Model Context Protocol server for Claude",
        output_dir="apps/{app_name}",
        file_patterns=[
            "server.py",
            "pyproject.toml",
        ],
    ),
    "fastapi": PrototypeConfig(
        name="FastAPI",
        plan_command="/plan_fastapi",
        description="FastAPI backend with async support",
        output_dir="apps/{app_name}",
        file_patterns=[
            "pyproject.toml",
            "app/main.py",
            "app/routes/*.py",
            "app/models/*.py",
        ],
    ),
}


def get_prototype_config(prototype_type: str) -> PrototypeConfig | None:
    """Get configuration for a prototype type."""
    return PROTOTYPES.get(prototype_type)


def list_prototypes() -> list[PrototypeConfig]:
    """List all available prototype types."""
    return list(PROTOTYPES.values())


def build_scaffold_prompt(
    config: PrototypeConfig,
    app_name: str,
    description: str,
    output_dir: Path,
) -> str:
    """Build the prompt for scaffolding a prototype.

    Args:
        config: Prototype configuration.
        app_name: Name of the application to create.
        description: Description of what the app should do.
        output_dir: Directory where files should be created.

    Returns:
        Formatted prompt string.
    """
    file_list = "\n".join(f"  - {p}" for p in config.file_patterns)

    return f"""Create a new {config.name} application.

**Application Name:** {app_name}
**Description:** {description}
**Output Directory:** {output_dir}

## Requirements

1. Create all files in the output directory: {output_dir}
2. Follow {config.name} best practices and conventions
3. Use modern patterns and TypeScript/type hints where applicable
4. Include proper configuration files

## Expected Files

{file_list}

## Instructions

1. First, create the directory structure
2. Create each file with proper content
3. Ensure the project is immediately runnable
4. Add any necessary dependencies in package.json/pyproject.toml

Focus on speed over perfection - this is a prototype for rapid iteration.
"""


def build_verify_prompt(
    config: PrototypeConfig,
    app_name: str,
    output_dir: Path,
) -> str:
    """Build the prompt for verifying a prototype.

    Args:
        config: Prototype configuration.
        app_name: Name of the application.
        output_dir: Directory where files were created.

    Returns:
        Formatted prompt string.
    """
    return f"""Verify that the {config.name} prototype '{app_name}' was created correctly.

**Output Directory:** {output_dir}

## Verification Steps

1. Check that all expected files exist
2. Verify the project structure is correct
3. If possible, run a quick syntax check or lint
4. Report any missing files or issues

## Expected Files

{', '.join(config.file_patterns)}

Report your findings. If everything looks good, confirm success.
If there are issues, list them clearly.
"""


def run_prototype_workflow(
    prototype_type: str,
    app_name: str,
    description: str = "",
    worktree_name: str | None = None,
    adw_id: str | None = None,
    model: Literal["haiku", "sonnet", "opus"] = "sonnet",
    skip_verify: bool = False,
    on_progress: Callable[[str], None] | None = None,
) -> tuple[bool, PrototypeResult]:
    """Execute a prototype scaffolding workflow.

    This workflow creates a new application using the specified prototype
    template and optionally verifies the result.

    Args:
        prototype_type: Type of prototype (e.g., "vite_vue", "fastapi").
        app_name: Name of the application to create.
        description: Description of what the app should do.
        worktree_name: Optional git worktree name.
        adw_id: Optional ADW tracking ID.
        model: Claude model to use.
        skip_verify: Skip the verification phase.
        on_progress: Optional callback for progress updates.

    Returns:
        Tuple of (success, PrototypeResult).
    """
    start_time = time.time()

    # Get prototype config
    config = get_prototype_config(prototype_type)
    if config is None:
        available = ", ".join(PROTOTYPES.keys())
        return False, PrototypeResult(
            success=False,
            error=f"Unknown prototype type: {prototype_type}. Available: {available}",
        )

    adw_id = adw_id or generate_adw_id()
    worktree_name = worktree_name or f"prototype-{app_name}"
    tasks_file = Path("tasks.md")

    # Calculate output directory
    output_dir = Path(config.output_dir.format(app_name=app_name))

    # Initialize state
    state = ADWState(
        adw_id=adw_id,
        task_description=f"Create {config.name} prototype: {app_name}",
        worktree_name=worktree_name,
        workflow_type="prototype",
    )
    state.save("init")

    task_description = f"Create {config.name} prototype: {app_name}"
    if description:
        task_description += f" - {description}"

    # Mark task as in progress
    mark_in_progress(tasks_file, task_description, adw_id)

    files_created: list[str] = []

    # Phase 1: Scaffold
    if on_progress:
        on_progress(f"Scaffolding {config.name} application: {app_name}")

    scaffold_prompt = build_scaffold_prompt(config, app_name, description, output_dir)

    try:
        scaffold_response = prompt_with_retry(
            AgentPromptRequest(
                prompt=scaffold_prompt,
                adw_id=adw_id,
                agent_name=f"scaffold-{adw_id}",
                model=model,
                timeout=600,
            ),
            max_retries=2,
        )

        if not scaffold_response.success:
            error = scaffold_response.error_message or "Scaffold phase failed"
            mark_failed(tasks_file, task_description, adw_id, error)
            state.add_error("scaffold", error)
            return False, PrototypeResult(
                success=False,
                error=error,
                duration_seconds=time.time() - start_time,
            )

        state.save("phase:scaffold:complete")

    except Exception as e:
        error = str(e)
        mark_failed(tasks_file, task_description, adw_id, error)
        state.add_error("scaffold", error)
        return False, PrototypeResult(
            success=False,
            error=error,
            duration_seconds=time.time() - start_time,
        )

    # Collect created files
    if output_dir.exists():
        for pattern in config.file_patterns:
            if "*" in pattern:
                # Glob pattern
                for f in output_dir.glob(pattern):
                    if f.is_file():
                        files_created.append(str(f.relative_to(output_dir)))
            else:
                # Exact file
                if (output_dir / pattern).exists():
                    files_created.append(pattern)

    # Phase 2: Verify (optional)
    if not skip_verify:
        if on_progress:
            on_progress(f"Verifying {config.name} prototype...")

        verify_prompt = build_verify_prompt(config, app_name, output_dir)

        try:
            verify_response = prompt_with_retry(
                AgentPromptRequest(
                    prompt=verify_prompt,
                    adw_id=adw_id,
                    agent_name=f"verify-{adw_id}",
                    model="haiku",  # Use cheaper model for verification
                    timeout=300,
                ),
                max_retries=1,
            )

            if not verify_response.success:
                if on_progress:
                    on_progress("Verification had issues, but prototype was created")
                # Don't fail the whole workflow for verification issues
                state.save("phase:verify:warning")
            else:
                state.save("phase:verify:complete")

        except Exception as e:
            if on_progress:
                on_progress(f"Verification error: {e}, continuing anyway")
            state.save("phase:verify:error")

    # Mark complete
    duration = time.time() - start_time
    mark_done(tasks_file, task_description, adw_id)
    state.save("complete")

    if on_progress:
        on_progress(f"Prototype created: {output_dir}")
        if files_created:
            on_progress(f"Files: {', '.join(files_created[:5])}")
            if len(files_created) > 5:
                on_progress(f"  ... and {len(files_created) - 5} more")

    return True, PrototypeResult(
        success=True,
        output_dir=output_dir,
        files_created=files_created,
        duration_seconds=duration,
    )


def format_prototype_result(result: PrototypeResult) -> str:
    """Format prototype result as a summary string."""
    lines = ["Prototype Result:", "=" * 40]

    if result.success:
        lines.append("✅ Success")
        if result.output_dir:
            lines.append(f"   Output: {result.output_dir}")
        if result.files_created:
            lines.append(f"   Files created: {len(result.files_created)}")
            for f in result.files_created[:10]:
                lines.append(f"     - {f}")
            if len(result.files_created) > 10:
                lines.append(f"     ... and {len(result.files_created) - 10} more")
    else:
        lines.append("❌ Failed")
        if result.error:
            lines.append(f"   Error: {result.error}")

    lines.append(f"   Duration: {result.duration_seconds:.1f}s")
    lines.append("=" * 40)

    return "\n".join(lines)


@click.command()
@click.option(
    "--type",
    "-t",
    "prototype_type",
    required=True,
    type=click.Choice(list(PROTOTYPES.keys())),
    help="Prototype type to create",
)
@click.option("--name", "-n", required=True, help="Application name")
@click.option("--description", "-d", default="", help="Application description")
@click.option("--adw-id", help="ADW tracking ID")
@click.option("--worktree-name", help="Git worktree name")
@click.option(
    "--model",
    default="sonnet",
    type=click.Choice(["haiku", "sonnet", "opus"]),
    help="Claude model to use",
)
@click.option("--skip-verify", is_flag=True, help="Skip verification phase")
@click.option("--verbose", "-v", is_flag=True, help="Show progress")
def main(
    prototype_type: str,
    name: str,
    description: str,
    adw_id: str | None,
    worktree_name: str | None,
    model: Literal["haiku", "sonnet", "opus"],
    skip_verify: bool,
    verbose: bool,
) -> None:
    """Create a new application from a prototype template."""

    def on_progress(msg: str) -> None:
        if verbose:
            click.echo(msg)

    success, result = run_prototype_workflow(
        prototype_type=prototype_type,
        app_name=name,
        description=description,
        worktree_name=worktree_name,
        adw_id=adw_id,
        model=model,
        skip_verify=skip_verify,
        on_progress=on_progress if verbose else None,
    )

    if verbose:
        click.echo(format_prototype_result(result))

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
