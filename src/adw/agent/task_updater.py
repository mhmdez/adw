"""Atomic task status updates."""

from __future__ import annotations

import re
from pathlib import Path

from .models import TaskStatus


def update_task_status(
    path: Path,
    task_description: str,
    new_status: TaskStatus,
    adw_id: str | None = None,
    commit_hash: str | None = None,
    error_message: str | None = None,
) -> bool:
    """Update task status in tasks.md."""
    if not path.exists():
        return False

    content = path.read_text()
    lines = content.split("\n")
    desc_escaped = re.escape(task_description.strip())
    updated = False

    for i, line in enumerate(lines):
        if not re.search(rf"\]\s*.*{desc_escaped}", line, re.IGNORECASE):
            continue

        # Build status marker
        if new_status == TaskStatus.PENDING:
            marker = "[]"
        elif new_status == TaskStatus.BLOCKED:
            marker = "[⏰]"
        elif new_status == TaskStatus.IN_PROGRESS:
            marker = f"[🟡, {adw_id}]" if adw_id else "[🟡]"
        elif new_status == TaskStatus.DONE:
            parts = ["✅"]
            if commit_hash:
                parts.append(commit_hash[:9])
            if adw_id:
                parts.append(adw_id)
            marker = f"[{', '.join(parts)}]"
        elif new_status == TaskStatus.FAILED:
            marker = f"[❌, {adw_id}]" if adw_id else "[❌]"
        else:
            continue

        # Preserve tags
        tags_match = re.search(r"\{([^}]+)\}", line)
        tags = f" {{{tags_match.group(1)}}}" if tags_match else ""

        # Build new line
        new_line = f"{marker} {task_description.strip()}{tags}"
        if new_status == TaskStatus.FAILED and error_message:
            new_line += f" // Failed: {error_message}"

        lines[i] = new_line
        updated = True
        break

    if updated:
        path.write_text("\n".join(lines))

    return updated


def mark_in_progress(path: Path, description: str, adw_id: str) -> bool:
    """Mark task as in-progress."""
    return update_task_status(path, description, TaskStatus.IN_PROGRESS, adw_id=adw_id)


def mark_done(path: Path, description: str, adw_id: str, commit: str | None = None) -> bool:
    """Mark task as done."""
    return update_task_status(path, description, TaskStatus.DONE, adw_id=adw_id, commit_hash=commit)


def mark_failed(path: Path, description: str, adw_id: str, error: str) -> bool:
    """Mark task as failed."""
    return update_task_status(path, description, TaskStatus.FAILED, adw_id=adw_id, error_message=error)
