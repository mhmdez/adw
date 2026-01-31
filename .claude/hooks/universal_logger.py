#!/usr/bin/env uv run
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Universal hook logger for debugging and analysis."""

import json
import os
import sys
from datetime import datetime
from pathlib import Path


def get_log_path() -> Path:
    """Get path to hook log file."""
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
    session_id = os.environ.get("CLAUDE_SESSION_ID", "unknown")

    log_dir = Path(project_dir) / ".claude" / "agents" / "hook_logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    date_str = datetime.now().strftime("%Y%m%d")
    return log_dir / f"{date_str}_{session_id[:8]}.jsonl"


def main():
    hook_name = os.environ.get("CLAUDE_HOOK_NAME", "unknown")

    try:
        hook_input = json.loads(sys.stdin.read())
    except json.JSONDecodeError:
        hook_input = {}

    entry = {
        "timestamp": datetime.now().isoformat(),
        "hook": hook_name,
        "session_id": os.environ.get("CLAUDE_SESSION_ID"),
        "tool_name": hook_input.get("tool_name"),
        "tool_input_keys": list(hook_input.get("tool_input", {}).keys()),
    }

    log_path = get_log_path()
    with open(log_path, "a") as f:
        f.write(json.dumps(entry) + "\n")

    sys.exit(0)


if __name__ == "__main__":
    main()
