#!/usr/bin/env uv run
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Check for and surface user messages to agent."""

import json
import os
import sys
from pathlib import Path


def main():
    # Get ADW ID from environment (set by ADW when spawning)
    adw_id = os.environ.get("ADW_ID")
    if not adw_id:
        sys.exit(0)

    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
    messages_file = Path(project_dir) / "agents" / adw_id / "adw_messages.jsonl"
    processed_file = Path(project_dir) / "agents" / adw_id / "adw_messages_processed.jsonl"

    if not messages_file.exists():
        sys.exit(0)

    # Read all messages
    messages = []
    for line in messages_file.read_text().strip().split("\n"):
        if line:
            messages.append(json.loads(line))

    # Read processed messages
    processed = set()
    if processed_file.exists():
        for line in processed_file.read_text().strip().split("\n"):
            if line:
                processed.add(line)

    # Find new messages
    new_messages = []
    for msg in messages:
        msg_key = json.dumps(msg, sort_keys=True)
        if msg_key not in processed:
            new_messages.append(msg)
            # Mark as processed
            with open(processed_file, "a") as f:
                f.write(msg_key + "\n")

    if new_messages:
        # Output message for Claude to see
        print("\n" + "="*60)
        print("📨 MESSAGE FROM USER:")
        for msg in new_messages:
            print(f"  {msg['message']}")
        print("="*60 + "\n")

        # If interrupt priority, suggest stopping
        if any(m.get("priority") == "interrupt" for m in new_messages):
            print("⚠️  HIGH PRIORITY - Please address this before continuing.\n")

    sys.exit(0)


if __name__ == "__main__":
    main()
