"""Test utilities for ADW.

This module provides helper functions for testing ADW functionality.
Created as part of the workflow validation test (ADW ID: 793a7295).
"""

from __future__ import annotations

from typing import Any


def validate_adw_id(adw_id: str) -> bool:
    """Validate that a string is a valid ADW ID format.

    ADW IDs are 8-character hexadecimal strings.

    Args:
        adw_id: The ID string to validate

    Returns:
        True if the ID is valid, False otherwise

    Examples:
        >>> validate_adw_id("793a7295")
        True
        >>> validate_adw_id("invalid")
        False
        >>> validate_adw_id("abc12345")
        True
    """
    if not isinstance(adw_id, str):
        return False

    if len(adw_id) != 8:
        return False

    try:
        int(adw_id, 16)
        return True
    except ValueError:
        return False


def format_task_status(status: str, adw_id: str | None = None) -> str:
    """Format a task status marker for tasks.md.

    Args:
        status: Status string (ready, blocked, in_progress, completed, failed)
        adw_id: Optional ADW ID for the task

    Returns:
        Formatted status marker string

    Examples:
        >>> format_task_status("ready")
        '[]'
        >>> format_task_status("in_progress", "793a7295")
        '[🟡, 793a7295]'
        >>> format_task_status("completed", "abc12345")
        '[✅, abc12345]'
    """
    status_map = {
        "ready": "[]",
        "blocked": "[⏰]",
        "in_progress": "[🟡, {}]",
        "completed": "[✅, {}]",
        "failed": "[❌, {}]",
    }

    marker = status_map.get(status)
    if marker is None:
        raise ValueError(f"Invalid status: {status}")

    if "{}" in marker:
        if adw_id is None:
            raise ValueError(f"ADW ID required for status: {status}")
        return marker.format(adw_id)

    return marker


def parse_task_line(line: str) -> dict[str, Any]:
    """Parse a task line from tasks.md.

    Args:
        line: A line from tasks.md containing a task

    Returns:
        Dictionary with task information

    Examples:
        >>> parse_task_line("[✅, 793a7295] Create test utils")
        {'status': 'completed', 'adw_id': '793a7295', 'description': 'Create test utils'}
        >>> parse_task_line("[] New task")
        {'status': 'ready', 'adw_id': None, 'description': 'New task'}
    """
    line = line.strip()

    # Match status markers
    if line.startswith("[✅,"):
        parts = line[1:].split("]", 1)
        status_part = parts[0]
        adw_id = status_part.split(",")[1].strip()
        description = parts[1].strip() if len(parts) > 1 else ""
        return {"status": "completed", "adw_id": adw_id, "description": description}
    elif line.startswith("[🟡,"):
        parts = line[1:].split("]", 1)
        status_part = parts[0]
        adw_id = status_part.split(",")[1].strip()
        description = parts[1].strip() if len(parts) > 1 else ""
        return {"status": "in_progress", "adw_id": adw_id, "description": description}
    elif line.startswith("[❌,"):
        parts = line[1:].split("]", 1)
        status_part = parts[0]
        adw_id = status_part.split(",")[1].strip()
        description = parts[1].strip() if len(parts) > 1 else ""
        return {"status": "failed", "adw_id": adw_id, "description": description}
    elif line.startswith("[⏰]"):
        description = line[3:].strip()
        return {"status": "blocked", "adw_id": None, "description": description}
    elif line.startswith("[]"):
        description = line[2:].strip()
        return {"status": "ready", "adw_id": None, "description": description}
    else:
        return {"status": "unknown", "adw_id": None, "description": line}
