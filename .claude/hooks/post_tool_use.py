#!/usr/bin/env uv run
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Tool usage logging for observability.

Logs all tool calls to .adw/tool_usage.jsonl with automatic rotation.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Maximum log file size before rotation (10MB)
MAX_LOG_SIZE = 10 * 1024 * 1024


def get_adw_dir() -> Path:
    """Get .adw directory, creating if needed."""
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
    adw_dir = Path(project_dir) / ".adw"
    adw_dir.mkdir(parents=True, exist_ok=True)
    return adw_dir


def rotate_log_if_needed(log_file: Path) -> None:
    """Rotate log file if it exceeds MAX_LOG_SIZE."""
    if not log_file.exists():
        return

    if log_file.stat().st_size > MAX_LOG_SIZE:
        # Rotate: rename current to timestamped backup
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = log_file.with_suffix(f".{timestamp}.jsonl")
        log_file.rename(backup_file)


def summarize_result(tool_result: dict) -> str:
    """Create a brief summary of tool result.

    Args:
        tool_result: The full tool result dict.

    Returns:
        A brief summary string.
    """
    if not tool_result:
        return "no_result"

    # Check for common result patterns
    if "error" in tool_result:
        return f"error: {str(tool_result['error'])[:100]}"

    if "content" in tool_result:
        content = tool_result["content"]
        if isinstance(content, str):
            # Truncate long content
            if len(content) > 100:
                return f"content: {len(content)} chars"
            return f"content: {content[:50]}"
        return f"content: {type(content).__name__}"

    if "output" in tool_result:
        output = tool_result["output"]
        if isinstance(output, str):
            lines = output.count("\n") + 1
            return f"output: {lines} lines"
        return f"output: {type(output).__name__}"

    # Generic summary
    return f"keys: {list(tool_result.keys())[:5]}"


def sanitize_params(params: dict) -> dict:
    """Sanitize parameters for logging (remove sensitive content).

    Args:
        params: The tool input parameters.

    Returns:
        Sanitized parameters safe for logging.
    """
    if not params:
        return {}

    sanitized = {}
    for key, value in params.items():
        if key in ("content", "new_string", "old_string"):
            # Don't log full content, just length
            if isinstance(value, str):
                sanitized[key] = f"<{len(value)} chars>"
            else:
                sanitized[key] = "<redacted>"
        elif key == "command":
            # Log command but truncate if too long
            if isinstance(value, str) and len(value) > 200:
                sanitized[key] = value[:200] + "..."
            else:
                sanitized[key] = value
        else:
            # Log other params as-is if they're not too large
            if isinstance(value, str) and len(value) > 500:
                sanitized[key] = f"<{len(value)} chars>"
            elif isinstance(value, (dict, list)) and len(str(value)) > 500:
                sanitized[key] = f"<{type(value).__name__}>"
            else:
                sanitized[key] = value

    return sanitized


def log_tool_usage(
    tool_name: str,
    tool_input: dict,
    tool_result: dict,
    session_id: str,
) -> None:
    """Log tool usage to .adw/tool_usage.jsonl.

    Args:
        tool_name: Name of the tool called.
        tool_input: Tool input parameters.
        tool_result: Tool execution result.
        session_id: Current session ID.
    """
    log_file = get_adw_dir() / "tool_usage.jsonl"

    # Rotate if needed
    rotate_log_if_needed(log_file)

    entry = {
        "timestamp": datetime.now().isoformat(),
        "session_id": session_id,
        "tool_name": tool_name,
        "parameters": sanitize_params(tool_input),
        "result_summary": summarize_result(tool_result),
    }

    with open(log_file, "a") as f:
        f.write(json.dumps(entry) + "\n")


def main() -> None:
    """Main hook handler."""
    # Read hook input from stdin
    try:
        stdin_data = sys.stdin.read()
        hook_input = json.loads(stdin_data) if stdin_data else {}
    except json.JSONDecodeError:
        hook_input = {}

    tool_name = hook_input.get("tool_name", "unknown")
    tool_input = hook_input.get("tool_input", {})
    tool_result = hook_input.get("tool_result", {})
    session_id = os.environ.get("CLAUDE_SESSION_ID", "unknown")

    # Log the tool usage
    log_tool_usage(tool_name, tool_input, tool_result, session_id)

    # Always allow (this is post-tool, nothing to block)
    sys.exit(0)


if __name__ == "__main__":
    main()
