#!/usr/bin/env uv run
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Session completion alias - delegates to stop.py.

This file exists for backward compatibility with settings.json
that references session_complete.py instead of stop.py.
"""

import subprocess
import sys
from pathlib import Path


def main() -> None:
    """Delegate to stop.py."""
    stop_script = Path(__file__).parent / "stop.py"

    if not stop_script.exists():
        # If stop.py doesn't exist, just exit successfully
        sys.exit(0)

    # Pass stdin through to stop.py
    result = subprocess.run(
        ["uv", "run", str(stop_script)],
        stdin=sys.stdin,
        capture_output=False,
    )

    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
