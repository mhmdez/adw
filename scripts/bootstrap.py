#!/usr/bin/env python3
"""Bootstrap script for building ADW using ADW principles.

This script handles the initial bootstrapping phase where ADW doesn't
exist yet. It manually executes tasks from tasks.md until the core
system is functional enough to take over.

Usage:
    python scripts/bootstrap.py [--phase N] [--dry-run]

Options:
    --phase N    Only run tasks up to phase N (default: run until self-sufficient)
    --dry-run    Show what would be done without executing
    --task DESC  Run a specific task by description match
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


# Task status markers
STATUS_PENDING = "[]"
STATUS_BLOCKED = "[⏰]"
STATUS_IN_PROGRESS = "[🟡"
STATUS_DONE = "[✅"
STATUS_FAILED = "[❌"


@dataclass
class Task:
    """A task from tasks.md."""
    description: str
    status: str
    adw_id: str | None
    tags: list[str]
    worktree: str
    line_number: int

    @property
    def is_pending(self) -> bool:
        return self.status == STATUS_PENDING

    @property
    def is_blocked(self) -> bool:
        return self.status == STATUS_BLOCKED

    @property
    def model(self) -> str:
        if "opus" in self.tags:
            return "opus"
        return "sonnet"


def generate_adw_id() -> str:
    """Generate 8-character ADW ID."""
    return uuid.uuid4().hex[:8]


def parse_tasks_md(content: str) -> list[Task]:
    """Parse tasks.md into Task objects."""
    tasks = []
    current_worktree = "default"

    worktree_pattern = re.compile(r"^##\s+Worktree:\s*(.+)$")
    task_pattern = re.compile(
        r"^(\[[^\]]*\])"  # Status
        r"(?:\s*,?\s*([a-f0-9]{8}))?"  # ADW ID
        r"(?:\s*,?\s*[a-f0-9]+)?"  # Commit hash
        r"\s+(.+?)"  # Description
        r"(?:\s*\{([^}]+)\})?"  # Tags
        r"\s*$"
    )

    for line_num, line in enumerate(content.split("\n"), 1):
        line = line.rstrip()

        # Check for worktree header
        wt_match = worktree_pattern.match(line)
        if wt_match:
            current_worktree = wt_match.group(1).strip()
            continue

        # Check for task
        task_match = task_pattern.match(line)
        if task_match:
            status = task_match.group(1).strip()
            adw_id = task_match.group(2)
            description = task_match.group(3).strip()
            tags_str = task_match.group(4) or ""
            tags = [t.strip().lower() for t in tags_str.split(",") if t.strip()]

            # Normalize status
            if status.startswith(STATUS_DONE):
                status = STATUS_DONE
            elif status.startswith(STATUS_FAILED):
                status = STATUS_FAILED
            elif status.startswith(STATUS_IN_PROGRESS):
                status = STATUS_IN_PROGRESS

            tasks.append(Task(
                description=description,
                status=status,
                adw_id=adw_id,
                tags=tags,
                worktree=current_worktree,
                line_number=line_num,
            ))

    return tasks


def get_eligible_tasks(tasks: list[Task], worktree: str | None = None) -> list[Task]:
    """Get tasks eligible for execution."""
    eligible = []

    # Group by worktree
    by_worktree: dict[str, list[Task]] = {}
    for task in tasks:
        if worktree and task.worktree != worktree:
            continue
        if task.worktree not in by_worktree:
            by_worktree[task.worktree] = []
        by_worktree[task.worktree].append(task)

    # Check eligibility
    for wt, wt_tasks in by_worktree.items():
        for i, task in enumerate(wt_tasks):
            if task.is_pending:
                eligible.append(task)
            elif task.is_blocked:
                # Eligible if all above are done
                above = wt_tasks[:i]
                if all(t.status == STATUS_DONE for t in above):
                    eligible.append(task)

    return eligible


def update_task_status(
    tasks_file: Path,
    description: str,
    new_status: str,
    adw_id: str | None = None,
    error: str | None = None,
) -> bool:
    """Update task status in tasks.md."""
    content = tasks_file.read_text()
    lines = content.split("\n")
    desc_escaped = re.escape(description.strip())
    updated = False

    for i, line in enumerate(lines):
        if not re.search(rf"\]\s*.*{desc_escaped}", line, re.IGNORECASE):
            continue

        # Build new status marker
        if new_status == STATUS_PENDING:
            marker = "[]"
        elif new_status == STATUS_BLOCKED:
            marker = "[⏰]"
        elif new_status == STATUS_IN_PROGRESS:
            marker = f"[🟡, {adw_id}]" if adw_id else "[🟡]"
        elif new_status == STATUS_DONE:
            marker = f"[✅, {adw_id}]" if adw_id else "[✅]"
        elif new_status == STATUS_FAILED:
            marker = f"[❌, {adw_id}]" if adw_id else "[❌]"
        else:
            continue

        # Preserve tags
        tags_match = re.search(r"\{([^}]+)\}", line)
        tags = f" {{{tags_match.group(1)}}}" if tags_match else ""

        # Build new line
        new_line = f"{marker} {description.strip()}{tags}"
        if new_status == STATUS_FAILED and error:
            new_line += f" // Failed: {error}"

        lines[i] = new_line
        updated = True
        break

    if updated:
        tasks_file.write_text("\n".join(lines))

    return updated


def execute_task(task: Task, dry_run: bool = False) -> bool:
    """Execute a single task using Claude Code.

    Args:
        task: The task to execute.
        dry_run: If True, just print what would be done.

    Returns:
        True if successful, False otherwise.
    """
    adw_id = generate_adw_id()
    tasks_file = Path("tasks.md")

    print(f"\n{'='*60}")
    print(f"Task: {task.description}")
    print(f"ADW ID: {adw_id}")
    print(f"Model: {task.model}")
    print(f"Worktree: {task.worktree}")
    print(f"{'='*60}")

    if dry_run:
        print("[DRY RUN] Would execute this task")
        return True

    # Mark as in progress
    update_task_status(tasks_file, task.description, STATUS_IN_PROGRESS, adw_id)

    # Build the prompt
    # Reference the phase spec if it exists
    phase_match = re.search(r"phase-(\d+)", task.worktree)
    spec_hint = ""
    if phase_match:
        phase_num = phase_match.group(1)
        spec_file = Path(f"specs/phase-{phase_num.zfill(2)}-*.md")
        specs = list(Path("specs").glob(f"phase-{phase_num.zfill(2)}*.md"))
        if specs:
            spec_hint = f"\n\nRefer to the spec file: {specs[0]}"

    prompt = f"""Execute this task for the ADW build:

Task: {task.description}
ADW ID: {adw_id}
{spec_hint}

Follow the spec precisely. Create the files as specified.
When done, report what was created/modified.
"""

    # Create output directory
    output_dir = Path("agents") / adw_id / "bootstrap"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Run Claude Code with permissions to write files
    cmd = [
        "claude",
        "--model", task.model,
        "--verbose",
        "--output-format", "stream-json",
        "--dangerously-skip-permissions",
        "--print", prompt,
    ]

    try:
        print(f"\nExecuting with Claude ({task.model})...")

        # Longer timeout for Opus (complex tasks)
        timeout = 1200 if task.model == "opus" else 600  # 20 min for opus, 10 for others

        with open(output_dir / "cc_raw_output.jsonl", "w") as f:
            result = subprocess.run(
                cmd,
                stdout=f,
                stderr=subprocess.PIPE,
                timeout=timeout,
            )

        if result.returncode == 0:
            print(f"✅ Task completed successfully")
            update_task_status(tasks_file, task.description, STATUS_DONE, adw_id)
            return True
        else:
            error = result.stderr.decode()[:100] if result.stderr else "Unknown error"
            print(f"❌ Task failed: {error}")
            update_task_status(tasks_file, task.description, STATUS_FAILED, adw_id, error)
            return False

    except subprocess.TimeoutExpired:
        timeout_mins = 20 if task.model == "opus" else 10
        print(f"❌ Task timed out after {timeout_mins} minutes")
        update_task_status(tasks_file, task.description, STATUS_FAILED, adw_id, "Timeout")
        return False

    except FileNotFoundError:
        print("❌ Claude Code CLI not found. Install from https://claude.ai/code")
        update_task_status(tasks_file, task.description, STATUS_FAILED, adw_id, "Claude not found")
        return False

    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        update_task_status(tasks_file, task.description, STATUS_FAILED, adw_id, str(e)[:50])
        return False


def run_bootstrap(
    max_phase: int | None = None,
    dry_run: bool = False,
    task_filter: str | None = None,
) -> None:
    """Run the bootstrap process.

    Args:
        max_phase: Stop after this phase number.
        dry_run: Just show what would be done.
        task_filter: Only run tasks matching this string.
    """
    tasks_file = Path("tasks.md")

    if not tasks_file.exists():
        print("Error: tasks.md not found")
        sys.exit(1)

    content = tasks_file.read_text()
    tasks = parse_tasks_md(content)

    print(f"Loaded {len(tasks)} tasks from tasks.md")

    # Filter by phase if specified
    if max_phase:
        phase_prefix = f"phase-{str(max_phase).zfill(2)}"
        tasks = [t for t in tasks if any(
            f"phase-{str(i).zfill(2)}" in t.worktree
            for i in range(1, max_phase + 1)
        )]
        print(f"Filtered to {len(tasks)} tasks up to phase {max_phase}")

    # Filter by task description if specified
    if task_filter:
        tasks = [t for t in tasks if task_filter.lower() in t.description.lower()]
        print(f"Filtered to {len(tasks)} tasks matching '{task_filter}'")

    # Get eligible tasks
    eligible = get_eligible_tasks(tasks)
    print(f"Found {len(eligible)} eligible tasks")

    if not eligible:
        print("\nNo eligible tasks. Either all done or dependencies not met.")
        return

    # Execute tasks one at a time
    for task in eligible:
        success = execute_task(task, dry_run)

        if not success and not dry_run:
            print(f"\n⚠️  Task failed. Stopping bootstrap.")
            print("Fix the issue and run bootstrap again to continue.")
            sys.exit(1)

        if dry_run:
            continue

        # Re-check eligibility after each task (dependencies may have changed)
        content = tasks_file.read_text()
        tasks = parse_tasks_md(content)
        eligible = get_eligible_tasks(tasks)

        if not eligible:
            print("\n✅ All eligible tasks completed!")
            break

    print("\n" + "="*60)
    print("Bootstrap complete!")
    print("="*60)


def main():
    parser = argparse.ArgumentParser(
        description="Bootstrap ADW build using Claude Code"
    )
    parser.add_argument(
        "--phase", "-p",
        type=int,
        help="Only run tasks up to this phase number"
    )
    parser.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="Show what would be done without executing"
    )
    parser.add_argument(
        "--task", "-t",
        type=str,
        help="Only run tasks matching this description"
    )

    args = parser.parse_args()

    run_bootstrap(
        max_phase=args.phase,
        dry_run=args.dry_run,
        task_filter=args.task,
    )


if __name__ == "__main__":
    main()
