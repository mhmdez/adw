"""Git worktree management for isolated parallel execution."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from rich.console import Console


console = Console()


def get_worktree_base() -> Path:
    """Get base directory for worktrees."""
    return Path("trees")


def get_worktree_path(worktree_name: str) -> Path:
    """Get full path to a worktree."""
    return get_worktree_base() / worktree_name


def worktree_exists(worktree_name: str) -> bool:
    """Check if a worktree exists."""
    worktree_path = get_worktree_path(worktree_name)
    return worktree_path.exists() and (worktree_path / ".git").exists()


def list_worktrees() -> list[dict]:
    """List all git worktrees.

    Returns:
        List of worktree info dicts with 'path', 'branch', 'commit' keys.
    """
    try:
        result = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            return []

        worktrees = []
        current: dict = {}

        for line in result.stdout.split("\n"):
            if line.startswith("worktree "):
                if current:
                    worktrees.append(current)
                current = {"path": line[9:]}
            elif line.startswith("HEAD "):
                current["commit"] = line[5:]
            elif line.startswith("branch "):
                current["branch"] = line[7:]

        if current:
            worktrees.append(current)

        return worktrees

    except Exception:
        return []


def create_worktree(
    worktree_name: str,
    branch_name: str | None = None,
    sparse_paths: list[str] | None = None,
) -> Path | None:
    """Create an isolated git worktree.

    Args:
        worktree_name: Name for the worktree directory.
        branch_name: Git branch name. Defaults to worktree_name.
        sparse_paths: Paths to include in sparse checkout. If None, full checkout.

    Returns:
        Path to created worktree, or None on failure.
    """
    worktree_path = get_worktree_path(worktree_name)
    branch = branch_name or f"adw-{worktree_name}"

    # Check if already exists
    if worktree_exists(worktree_name):
        console.print(f"[yellow]Worktree already exists: {worktree_name}[/yellow]")
        return worktree_path

    # Ensure base directory exists
    get_worktree_base().mkdir(parents=True, exist_ok=True)

    try:
        # Create worktree with new branch
        result = subprocess.run(
            ["git", "worktree", "add", "-b", branch, str(worktree_path)],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            # Branch might already exist, try without -b
            result = subprocess.run(
                ["git", "worktree", "add", str(worktree_path), branch],
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                console.print(f"[red]Failed to create worktree: {result.stderr}[/red]")
                return None

        # Configure sparse checkout if requested
        if sparse_paths:
            _configure_sparse_checkout(worktree_path, sparse_paths)

        # Copy .env file if it exists
        env_file = Path(".env")
        if env_file.exists():
            shutil.copy(env_file, worktree_path / ".env")

        console.print(f"[green]Created worktree: {worktree_path}[/green]")
        return worktree_path

    except Exception as e:
        console.print(f"[red]Error creating worktree: {e}[/red]")
        return None


def _configure_sparse_checkout(worktree_path: Path, sparse_paths: list[str]) -> None:
    """Configure sparse checkout for a worktree."""
    try:
        # Initialize sparse checkout
        subprocess.run(
            ["git", "sparse-checkout", "init", "--cone"],
            cwd=worktree_path,
            capture_output=True,
        )

        # Set sparse paths
        subprocess.run(
            ["git", "sparse-checkout", "set"] + sparse_paths,
            cwd=worktree_path,
            capture_output=True,
        )

    except Exception as e:
        console.print(f"[yellow]Sparse checkout failed: {e}[/yellow]")


def remove_worktree(worktree_name: str, force: bool = False) -> bool:
    """Remove a git worktree.

    Args:
        worktree_name: Name of the worktree to remove.
        force: Force removal even if there are changes.

    Returns:
        True if successfully removed.
    """
    worktree_path = get_worktree_path(worktree_name)

    if not worktree_exists(worktree_name):
        console.print(f"[yellow]Worktree doesn't exist: {worktree_name}[/yellow]")
        return True

    try:
        # Remove via git worktree command
        cmd = ["git", "worktree", "remove"]
        if force:
            cmd.append("--force")
        cmd.append(str(worktree_path))

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            console.print(f"[red]Failed to remove worktree: {result.stderr}[/red]")
            return False

        # Clean up the directory if it still exists
        if worktree_path.exists():
            shutil.rmtree(worktree_path)

        # Prune worktree list
        subprocess.run(["git", "worktree", "prune"], capture_output=True)

        console.print(f"[green]Removed worktree: {worktree_name}[/green]")
        return True

    except Exception as e:
        console.print(f"[red]Error removing worktree: {e}[/red]")
        return False


def get_worktree_branch(worktree_name: str) -> str | None:
    """Get the branch name for a worktree."""
    worktree_path = get_worktree_path(worktree_name)

    if not worktree_exists(worktree_name):
        return None

    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=worktree_path,
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            return result.stdout.strip()

    except Exception:
        pass

    return None
