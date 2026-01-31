"""ADW TUI module."""

import subprocess
import sys
from pathlib import Path

from .app import ADWApp, run_tui as run_textual_tui


def run_tui() -> None:
    """Run the TUI - beautiful Textual-based dashboard."""
    run_textual_tui()


def run_ink_tui() -> None:
    """Run the Ink-based TUI (Node.js) - deprecated."""
    # Find the bundled Ink dist
    ink_dist = Path(__file__).parent / "ink_dist"
    cli_path = ink_dist / "cli.mjs"

    if not cli_path.exists():
        print("Ink TUI not found, using Textual TUI...")
        run_textual_tui()
        return

    try:
        subprocess.run(["node", str(cli_path)], check=False)
    except FileNotFoundError:
        print("Node.js not found, using Textual TUI...")
        run_textual_tui()
    except KeyboardInterrupt:
        pass


__all__ = ["ADWApp", "run_tui", "run_ink_tui", "run_textual_tui"]
