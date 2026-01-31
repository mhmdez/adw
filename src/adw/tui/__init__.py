"""ADW TUI module."""

import subprocess
import sys
from pathlib import Path

from .app import ADWApp, run_tui as run_textual_tui


def run_tui() -> None:
    """Run the TUI - uses Ink (Node.js) for native terminal look."""
    run_ink_tui()


def run_ink_tui() -> None:
    """Run the Ink-based TUI (Node.js)."""
    # Find the bundled Ink dist
    ink_dist = Path(__file__).parent / "ink_dist"
    cli_path = ink_dist / "cli.mjs"

    if not cli_path.exists():
        # Fallback to textual TUI if Ink not built
        print("Ink TUI not found, falling back to Textual TUI...")
        run_textual_tui()
        return

    try:
        subprocess.run(["node", str(cli_path)], check=False)
    except FileNotFoundError:
        print("Node.js not found. Install Node.js or use 'adw dashboard' for Textual TUI.")
        sys.exit(1)
    except KeyboardInterrupt:
        pass


__all__ = ["ADWApp", "run_tui", "run_ink_tui", "run_textual_tui"]
