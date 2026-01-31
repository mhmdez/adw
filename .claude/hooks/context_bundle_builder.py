#!/usr/bin/env uv run
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Track file operations into context bundles for session restoration."""

import json
import os
import sys
from datetime import datetime
from pathlib import Path


def get_bundle_path() -> Path:
    """Get path to current session's context bundle."""
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
    session_id = os.environ.get("CLAUDE_SESSION_ID", "unknown")

    # Create bundle directory
    bundle_dir = Path(project_dir) / ".claude" / "agents" / "context_bundles"
    bundle_dir.mkdir(parents=True, exist_ok=True)

    # Use date + session for filename
    date_str = datetime.now().strftime("%Y%m%d_%H")
    return bundle_dir / f"{date_str}_{session_id[:8]}.jsonl"


def main():
    # Read hook input from stdin
    try:
        hook_input = json.loads(sys.stdin.read())
    except json.JSONDecodeError:
        sys.exit(0)  # Silent fail - don't disrupt Claude

    tool_name = hook_input.get("tool_name", "")
    tool_input = hook_input.get("tool_input", {})
    tool_result = hook_input.get("tool_result", {})

    # Only track file operations
    if tool_name not in ("Read", "Write", "Edit"):
        sys.exit(0)

    # Build context entry
    entry = {
        "timestamp": datetime.now().isoformat(),
        "session_id": os.environ.get("CLAUDE_SESSION_ID", "unknown"),
        "tool": tool_name,
    }

    if tool_name == "Read":
        entry["file_path"] = tool_input.get("file_path")
        entry["offset"] = tool_input.get("offset")
        entry["limit"] = tool_input.get("limit")
    elif tool_name == "Write":
        entry["file_path"] = tool_input.get("file_path")
        entry["content_length"] = len(tool_input.get("content", ""))
    elif tool_name == "Edit":
        entry["file_path"] = tool_input.get("file_path")
        entry["old_string_length"] = len(tool_input.get("old_string", ""))
        entry["new_string_length"] = len(tool_input.get("new_string", ""))

    # Append to bundle
    bundle_path = get_bundle_path()
    with open(bundle_path, "a") as f:
        f.write(json.dumps(entry) + "\n")

    sys.exit(0)


if __name__ == "__main__":
    main()
