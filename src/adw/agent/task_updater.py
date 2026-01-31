"""Atomic task status updates."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from .models import TaskStatus


HISTORY_HEADER = """# ADW Task History

*Archived completed and failed tasks*

---

"""


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


def archive_to_history(
    tasks_path: Path,
    description: str,
    status: str,
    adw_id: str,
    duration: str | None = None,
    error: str | None = None,
) -> bool:
    """Archive a completed/failed task to history.md.
    
    Args:
        tasks_path: Path to tasks.md (history.md will be in same dir)
        description: Task description
        status: "completed" or "failed"
        adw_id: ADW ID
        duration: Duration string (e.g., "2m 34s")
        error: Error message for failed tasks
        
    Returns:
        True if archived successfully
    """
    history_path = tasks_path.parent / "history.md"
    
    # Create history file if doesn't exist
    if not history_path.exists():
        history_path.write_text(HISTORY_HEADER)
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    if status == "completed":
        emoji = "✅"
        line = f"- {emoji} [{adw_id[:8]}] {description[:60]}"
        if duration:
            line += f" ({duration})"
        line += f" — {timestamp}"
    else:
        emoji = "❌"
        line = f"- {emoji} [{adw_id[:8]}] {description[:60]}"
        if error:
            line += f" — {error[:50]}"
        line += f" — {timestamp}"
    
    # Append to history
    content = history_path.read_text()
    
    # Find today's section or create it
    today = datetime.now().strftime("%Y-%m-%d")
    today_header = f"\n## {today}\n"
    
    if today_header.strip() not in content:
        content = content.rstrip() + f"\n{today_header}\n"
    
    # Insert after today's header
    parts = content.split(today_header)
    if len(parts) == 2:
        parts[1] = line + "\n" + parts[1]
        content = today_header.join(parts)
    else:
        content = content.rstrip() + "\n" + line + "\n"
    
    history_path.write_text(content)
    return True


def remove_from_tasks(path: Path, description: str) -> bool:
    """Remove a task line from tasks.md.
    
    Used after archiving to keep tasks.md clean.
    """
    if not path.exists():
        return False
    
    content = path.read_text()
    lines = content.split("\n")
    desc_escaped = re.escape(description.strip())
    
    new_lines = []
    removed = False
    
    for line in lines:
        if re.search(rf"\]\s*.*{desc_escaped}", line, re.IGNORECASE):
            removed = True
            continue  # Skip this line
        new_lines.append(line)
    
    if removed:
        path.write_text("\n".join(new_lines))
    
    return removed


def mark_in_progress(path: Path, description: str, adw_id: str) -> bool:
    """Mark task as in-progress."""
    return update_task_status(path, description, TaskStatus.IN_PROGRESS, adw_id=adw_id)


def mark_done(
    path: Path,
    description: str,
    adw_id: str,
    commit: str | None = None,
    duration: str | None = None,
    archive: bool = True,
    update_context: bool = True,
) -> bool:
    """Mark task as done and optionally archive to history."""
    result = update_task_status(
        path, description, TaskStatus.DONE, adw_id=adw_id, commit_hash=commit
    )
    
    if result and archive:
        archive_to_history(path, description, "completed", adw_id, duration=duration)
        # Optionally remove from tasks.md to keep it clean
        # remove_from_tasks(path, description)
    
    if result and update_context:
        # Update CLAUDE.md progress log
        try:
            from ..context import update_progress_log
            update_progress_log(path.parent, description, success=True)
        except Exception:
            pass  # Don't fail task completion on context update failure
    
    return result


def mark_failed(
    path: Path,
    description: str,
    adw_id: str,
    error: str,
    archive: bool = True,
) -> bool:
    """Mark task as failed and optionally archive to history."""
    result = update_task_status(
        path, description, TaskStatus.FAILED, adw_id=adw_id, error_message=error
    )
    
    if result and archive:
        archive_to_history(path, description, "failed", adw_id, error=error)
    
    return result
