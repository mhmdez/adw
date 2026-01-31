"""Utility functions for ADW."""

import uuid
from pathlib import Path


def generate_adw_id() -> str:
    """Generate unique 8-character execution identifier."""
    return uuid.uuid4().hex[:8]


def get_output_dir(adw_id: str, agent_name: str = "default") -> Path:
    """Get output directory for an agent execution."""
    output_dir = Path("agents") / adw_id / agent_name
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def truncate_string(s: str, max_length: int = 100) -> str:
    """Truncate string with ellipsis."""
    if len(s) <= max_length:
        return s
    return s[:max_length - 3] + "..."
