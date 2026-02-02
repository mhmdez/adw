#!/usr/bin/env uv run
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Session completion logging.

Called when a Claude session ends. Logs session summary to .adw/sessions.jsonl.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path


def get_adw_dir() -> Path:
    """Get .adw directory, creating if needed."""
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
    adw_dir = Path(project_dir) / ".adw"
    adw_dir.mkdir(parents=True, exist_ok=True)
    return adw_dir


def count_tool_usage(session_id: str) -> int:
    """Count tool calls for this session from tool_usage.jsonl.

    Args:
        session_id: Session ID to count for.

    Returns:
        Number of tool calls in this session.
    """
    tool_usage_file = get_adw_dir() / "tool_usage.jsonl"
    if not tool_usage_file.exists():
        return 0

    count = 0
    try:
        with open(tool_usage_file, "r") as f:
            for line in f:
                if line.strip():
                    try:
                        entry = json.loads(line)
                        if entry.get("session_id") == session_id:
                            count += 1
                    except json.JSONDecodeError:
                        continue
    except Exception:
        pass

    return count


def get_files_modified(session_id: str) -> list[str]:
    """Get list of files modified in this session.

    Args:
        session_id: Session ID to check.

    Returns:
        List of file paths that were modified.
    """
    tool_usage_file = get_adw_dir() / "tool_usage.jsonl"
    if not tool_usage_file.exists():
        return []

    modified_files: set[str] = set()
    try:
        with open(tool_usage_file, "r") as f:
            for line in f:
                if line.strip():
                    try:
                        entry = json.loads(line)
                        if entry.get("session_id") != session_id:
                            continue
                        if entry.get("tool_name") in ("Write", "Edit"):
                            params = entry.get("parameters", {})
                            file_path = params.get("file_path")
                            if file_path:
                                modified_files.add(file_path)
                    except json.JSONDecodeError:
                        continue
    except Exception:
        pass

    return list(modified_files)


def get_session_start_time(session_id: str) -> str | None:
    """Get session start time from tool_usage.jsonl.

    Args:
        session_id: Session ID to find.

    Returns:
        ISO timestamp of first tool call in session, or None.
    """
    tool_usage_file = get_adw_dir() / "tool_usage.jsonl"
    if not tool_usage_file.exists():
        return None

    try:
        with open(tool_usage_file, "r") as f:
            for line in f:
                if line.strip():
                    try:
                        entry = json.loads(line)
                        if entry.get("session_id") == session_id:
                            return entry.get("timestamp")
                    except json.JSONDecodeError:
                        continue
    except Exception:
        pass

    return None


def calculate_duration(start_time: str | None, end_time: str) -> float:
    """Calculate session duration in seconds.

    Args:
        start_time: ISO timestamp of session start.
        end_time: ISO timestamp of session end.

    Returns:
        Duration in seconds, or 0 if start_time is None.
    """
    if not start_time:
        return 0.0

    try:
        start = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        end = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
        return (end - start).total_seconds()
    except (ValueError, TypeError):
        return 0.0


def log_session_completion(session_id: str, stop_reason: str | None) -> None:
    """Log session completion to .adw/sessions.jsonl.

    Args:
        session_id: The session ID.
        stop_reason: Reason for stopping (if provided by Claude).
    """
    sessions_file = get_adw_dir() / "sessions.jsonl"

    end_time = datetime.now().isoformat()
    start_time = get_session_start_time(session_id)
    duration = calculate_duration(start_time, end_time)
    tools_used_count = count_tool_usage(session_id)
    files_modified = get_files_modified(session_id)

    entry = {
        "session_id": session_id,
        "start_time": start_time,
        "end_time": end_time,
        "duration_seconds": duration,
        "tools_used_count": tools_used_count,
        "files_modified": files_modified,
        "files_modified_count": len(files_modified),
        "stop_reason": stop_reason,
    }

    with open(sessions_file, "a") as f:
        f.write(json.dumps(entry) + "\n")


def main() -> None:
    """Main hook handler."""
    # Read hook input from stdin
    try:
        stdin_data = sys.stdin.read()
        hook_input = json.loads(stdin_data) if stdin_data else {}
    except json.JSONDecodeError:
        hook_input = {}

    session_id = os.environ.get("CLAUDE_SESSION_ID", "unknown")
    stop_reason = hook_input.get("stop_reason")

    # Log session completion
    log_session_completion(session_id, stop_reason)

    sys.exit(0)


if __name__ == "__main__":
    main()
