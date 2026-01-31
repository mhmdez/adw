"""Environment variable isolation for parallel ADW instances."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def get_isolated_env(
    adw_id: str,
    worktree_path: str | Path | None = None,
    backend_port: int | None = None,
    frontend_port: int | None = None,
    base_env: dict[str, str] | None = None,
) -> dict[str, str]:
    """Create isolated environment variables for an ADW instance.

    Args:
        adw_id: The ADW ID for this instance.
        worktree_path: Path to the worktree (optional).
        backend_port: Backend port number (optional).
        frontend_port: Frontend port number (optional).
        base_env: Base environment to extend. Defaults to os.environ.

    Returns:
        Dictionary of environment variables.
    """
    env = dict(base_env or os.environ)

    # Core ADW environment
    env["ADW_ID"] = adw_id
    env["ADW_WORKTREE"] = str(worktree_path) if worktree_path else ""

    # Port configuration
    if backend_port is not None:
        env["BACKEND_PORT"] = str(backend_port)
        env["PORT"] = str(backend_port)  # Common alias
        env["VITE_API_URL"] = f"http://localhost:{backend_port}"

    if frontend_port is not None:
        env["FRONTEND_PORT"] = str(frontend_port)
        env["VITE_PORT"] = str(frontend_port)

    # Prevent port conflicts with main repo
    env["FORCE_COLOR"] = "1"  # Ensure color output in isolated env
    env["CI"] = "false"  # Ensure we're not detected as CI environment

    return env


def merge_env_files(
    worktree_path: str | Path,
    env: dict[str, str] | None = None,
) -> dict[str, str]:
    """Merge environment files from worktree into env dict.

    Reads .env and .ports.env files and merges them into the environment.

    Args:
        worktree_path: Path to the worktree.
        env: Existing environment to merge into. Defaults to os.environ copy.

    Returns:
        Merged environment dictionary.
    """
    result = dict(env or os.environ)
    worktree = Path(worktree_path)

    # Load .env file
    env_file = worktree / ".env"
    if env_file.exists():
        result.update(_parse_env_file(env_file))

    # Load .ports.env file (takes precedence)
    ports_file = worktree / ".ports.env"
    if ports_file.exists():
        result.update(_parse_env_file(ports_file))

    return result


def _parse_env_file(file_path: Path) -> dict[str, str]:
    """Parse a .env file into a dictionary.

    Args:
        file_path: Path to the .env file.

    Returns:
        Dictionary of environment variables.
    """
    env = {}

    try:
        content = file_path.read_text()
        for line in content.splitlines():
            line = line.strip()

            # Skip empty lines and comments
            if not line or line.startswith("#"):
                continue

            # Parse KEY=VALUE
            if "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip()

                # Remove quotes if present
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]

                env[key] = value

    except Exception:
        # Silently ignore parsing errors
        pass

    return env


def write_env_file(
    worktree_path: str | Path,
    env_vars: dict[str, Any],
    filename: str = ".env",
) -> None:
    """Write environment variables to a file in the worktree.

    Args:
        worktree_path: Path to the worktree.
        env_vars: Dictionary of environment variables to write.
        filename: Name of the env file (default: .env).
    """
    worktree = Path(worktree_path)
    env_file = worktree / filename

    lines = []
    for key, value in env_vars.items():
        # Quote values with spaces
        if " " in str(value):
            lines.append(f'{key}="{value}"')
        else:
            lines.append(f"{key}={value}")

    env_file.write_text("\n".join(lines) + "\n")


def get_agent_env(
    adw_id: str,
    worktree_path: str | Path | None = None,
    backend_port: int | None = None,
    frontend_port: int | None = None,
) -> dict[str, str]:
    """Get complete environment for an agent with all isolation and file merging.

    This is the main entry point for getting a fully configured environment
    for an ADW agent instance.

    Args:
        adw_id: The ADW ID.
        worktree_path: Path to the worktree.
        backend_port: Backend port number.
        frontend_port: Frontend port number.

    Returns:
        Complete environment dictionary.
    """
    # Start with isolated environment
    env = get_isolated_env(
        adw_id=adw_id,
        worktree_path=worktree_path,
        backend_port=backend_port,
        frontend_port=frontend_port,
    )

    # Merge in .env files from worktree
    if worktree_path:
        env = merge_env_files(worktree_path, env)

    return env
