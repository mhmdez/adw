#!/usr/bin/env uv run
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""User prompt logging for observability.

Called when user submits a prompt. Logs to .adw/prompts.jsonl.
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


def log_prompt(session_id: str, prompt_data: dict) -> None:
    """Log user prompt to .adw/prompts.jsonl.

    Args:
        session_id: Current session ID.
        prompt_data: Prompt data from hook input.
    """
    prompts_file = get_adw_dir() / "prompts.jsonl"

    # Extract prompt info, being careful not to log full content if too long
    prompt_text = prompt_data.get("prompt", "")
    prompt_length = len(prompt_text) if isinstance(prompt_text, str) else 0

    entry = {
        "timestamp": datetime.now().isoformat(),
        "session_id": session_id,
        "prompt_length": prompt_length,
        # Log first 200 chars as preview, or full if short
        "prompt_preview": prompt_text[:200] if prompt_length > 200 else prompt_text,
    }

    with open(prompts_file, "a") as f:
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

    # Log the prompt
    log_prompt(session_id, hook_input)

    # Always allow prompt submission
    sys.exit(0)


if __name__ == "__main__":
    main()
