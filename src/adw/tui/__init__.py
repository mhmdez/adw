"""ADW TUI module."""

import subprocess
import sys
from pathlib import Path

from .app import ADWApp, run_tui as run_textual_tui


def run_tui() -> None:
    """Run the TUI - beautiful Ink-based dashboard (like Claude Code)."""
    run_ink_tui()


def run_ink_tui() -> None:
    """Run the Ink-based TUI (Node.js) - like Claude Code."""
    # Find the bundled Ink dist
    ink_dist = Path(__file__).parent / "ink_dist"
    cli_path = ink_dist / "cli.mjs"

    if not cli_path.exists():
        print("Ink TUI not found, falling back to Textual TUI...")
        run_textual_tui()
        return

    try:
        subprocess.run(["node", str(cli_path)], check=False)
    except FileNotFoundError:
        print("Node.js not found. Install Node.js or run with --textual flag.")
        print("Falling back to Textual TUI...")
        run_textual_tui()
    except KeyboardInterrupt:
        pass


__all__ = ["ADWApp", "run_tui", "run_ink_tui", "run_textual_tui"]
