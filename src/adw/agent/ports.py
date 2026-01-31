"""Deterministic port allocation for parallel ADW instances."""

from __future__ import annotations

import socket


# Port ranges for ADW instances
BACKEND_PORT_START = 9100
BACKEND_PORT_END = 9114
FRONTEND_PORT_START = 9200
FRONTEND_PORT_END = 9214

MAX_INSTANCES = 15


def get_ports_for_adw(adw_id: str) -> tuple[int, int]:
    """Get deterministic ports for an ADW instance.

    Uses hash of ADW ID to assign consistent ports.

    Args:
        adw_id: The 8-character ADW ID.

    Returns:
        Tuple of (backend_port, frontend_port).
    """
    # Convert first 8 chars to index
    try:
        index = int(adw_id[:8], 36) % MAX_INSTANCES
    except ValueError:
        index = hash(adw_id) % MAX_INSTANCES

    backend_port = BACKEND_PORT_START + index
    frontend_port = FRONTEND_PORT_START + index

    return backend_port, frontend_port


def is_port_available(port: int) -> bool:
    """Check if a port is available.

    Args:
        port: Port number to check.

    Returns:
        True if port is available.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", port))
            return True
    except OSError:
        return False


def find_available_ports(adw_id: str) -> tuple[int, int]:
    """Find available ports, with fallback if deterministic ports are busy.

    Args:
        adw_id: The ADW ID.

    Returns:
        Tuple of (backend_port, frontend_port).
    """
    backend, frontend = get_ports_for_adw(adw_id)

    # Try deterministic ports first
    if is_port_available(backend) and is_port_available(frontend):
        return backend, frontend

    # Fallback: find next available in range
    for i in range(MAX_INSTANCES):
        candidate_backend = BACKEND_PORT_START + i
        candidate_frontend = FRONTEND_PORT_START + i

        if is_port_available(candidate_backend) and is_port_available(candidate_frontend):
            return candidate_backend, candidate_frontend

    # Last resort: let OS assign
    raise RuntimeError("No available ports in ADW range")


def write_ports_env(worktree_path: str, backend_port: int, frontend_port: int) -> None:
    """Write .ports.env file to worktree.

    Args:
        worktree_path: Path to worktree.
        backend_port: Backend port number.
        frontend_port: Frontend port number.
    """
    from pathlib import Path

    ports_file = Path(worktree_path) / ".ports.env"
    ports_file.write_text(
        f"BACKEND_PORT={backend_port}\n"
        f"FRONTEND_PORT={frontend_port}\n"
        f"VITE_API_URL=http://localhost:{backend_port}\n"
    )
