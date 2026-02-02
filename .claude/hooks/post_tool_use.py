#!/usr/bin/env uv run
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Tool usage logging for observability with screenshot capture.

Logs all tool calls to .adw/tool_usage.jsonl with automatic rotation.
Captures screenshots when dev server start commands are detected.
"""

import json
import os
import re
import socket
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

# Maximum log file size before rotation (10MB)
MAX_LOG_SIZE = 10 * 1024 * 1024

# Dev server start command patterns
DEV_SERVER_PATTERNS = [
    r"npm\s+run\s+dev",
    r"npm\s+start",
    r"bun\s+run\s+dev",
    r"bun\s+dev",
    r"pnpm\s+dev",
    r"pnpm\s+run\s+dev",
    r"yarn\s+dev",
    r"yarn\s+run\s+dev",
    r"vite",
    r"next\s+dev",
    r"nuxt\s+dev",
    r"python\s+-m\s+http\.server",
    r"uvicorn\s+",
    r"flask\s+run",
    r"gunicorn\s+",
    r"fastapi\s+dev",
    r"php\s+-[sS]",
    r"ng\s+serve",
]

# Common dev server ports
DEV_SERVER_PORTS = [3000, 3001, 5173, 5174, 8000, 8080, 8888, 4200, 4000]


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


def is_dev_server_command(command: str) -> bool:
    """Check if a command is starting a development server."""
    if not command:
        return False
    command_lower = command.lower()
    for pattern in DEV_SERVER_PATTERNS:
        if re.search(pattern, command_lower):
            return True
    return False


def extract_port_from_command(command: str) -> Optional[int]:
    """Extract port number from a dev server command."""
    port_patterns = [
        r"--port[=\s]+(\d+)",
        r"-p[=\s]+(\d+)",
        r"-P[=\s]+(\d+)",
        r":(\d{4,5})\b",
        r"PORT=(\d+)",
        r"\.server\s+(\d+)",
    ]
    for pattern in port_patterns:
        match = re.search(pattern, command)
        if match:
            port = int(match.group(1))
            if 1024 <= port <= 65535:
                return port
    return None


def is_port_open(port: int) -> bool:
    """Check if a port is open (server listening)."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1)
    try:
        return sock.connect_ex(("127.0.0.1", port)) == 0
    finally:
        sock.close()


def detect_running_port() -> Optional[int]:
    """Find the first dev server port that's open."""
    for port in DEV_SERVER_PORTS:
        if is_port_open(port):
            return port
    return None


def capture_screenshot_async(task_id: Optional[str], port: int) -> None:
    """Capture screenshot in background after server starts."""
    def capture():
        # Wait for server to be ready
        time.sleep(3)

        # Verify port is still open
        if not is_port_open(port):
            return

        # Get screenshots directory
        project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
        if task_id:
            screenshots_dir = Path(project_dir) / "agents" / task_id / "screenshots"
        else:
            screenshots_dir = Path(project_dir) / ".adw" / "screenshots"
        screenshots_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = screenshots_dir / f"screenshot-{timestamp}.png"

        # Try to capture with screencapture (macOS)
        try:
            result = subprocess.run(
                ["screencapture", "-x", str(output_path)],
                capture_output=True,
                timeout=10,
            )
            if result.returncode == 0 and output_path.exists():
                # Log successful capture
                log_file = Path(project_dir) / ".adw" / "screenshots.jsonl"
                entry = {
                    "timestamp": datetime.now().isoformat(),
                    "task_id": task_id,
                    "port": port,
                    "path": str(output_path),
                }
                with open(log_file, "a") as f:
                    f.write(json.dumps(entry) + "\n")
        except (subprocess.SubprocessError, FileNotFoundError):
            pass

    # Run in background thread
    thread = threading.Thread(target=capture, daemon=True)
    thread.start()


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

    # Check for dev server start commands and capture screenshots
    if tool_name == "Bash":
        command = tool_input.get("command", "")
        if is_dev_server_command(command):
            # Try to extract port from command, or detect running port
            port = extract_port_from_command(command)
            if port is None:
                port = detect_running_port()
            if port is None:
                port = 3000  # Default fallback

            # Get task ID from environment if available
            task_id = os.environ.get("ADW_TASK_ID")

            # Capture screenshot asynchronously
            capture_screenshot_async(task_id, port)

    # Always allow (this is post-tool, nothing to block)
    sys.exit(0)


if __name__ == "__main__":
    main()
