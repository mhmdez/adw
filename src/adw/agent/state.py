"""Persistent state management."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class ADWState(BaseModel):
    """Persistent workflow state."""

    adw_id: str
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())

    # Task info
    task_description: str = ""
    task_id: str | None = None
    task_tags: list[str] = Field(default_factory=list)

    # Workflow
    workflow_type: str = "standard"
    current_phase: str = "init"
    phases_completed: list[str] = Field(default_factory=list)

    # Git
    worktree_name: str | None = None
    worktree_path: str | None = None
    branch_name: str | None = None
    commit_hash: str | None = None

    # Artifacts
    plan_file: str | None = None

    # Errors
    errors: list[dict] = Field(default_factory=list)

    @classmethod
    def get_path(cls, adw_id: str) -> Path:
        return Path("agents") / adw_id / "adw_state.json"

    @classmethod
    def load(cls, adw_id: str) -> ADWState | None:
        path = cls.get_path(adw_id)
        if not path.exists():
            return None
        try:
            return cls(**json.loads(path.read_text()))
        except Exception:
            return None

    def save(self, phase: str | None = None) -> Path:
        if phase:
            self.current_phase = phase
            if phase not in self.phases_completed:
                self.phases_completed.append(phase)

        self.updated_at = datetime.now().isoformat()
        path = self.get_path(self.adw_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=2))
        return path

    def add_error(self, phase: str, error: str) -> None:
        self.errors.append(
            {
                "phase": phase,
                "error": error,
                "timestamp": datetime.now().isoformat(),
            }
        )


def list_adw_states(limit: int = 50) -> list[ADWState]:
    """List all ADW states, sorted by most recently updated.

    Args:
        limit: Maximum number of states to return.

    Returns:
        List of ADWState objects sorted by updated_at descending.
    """
    agents_dir = Path("agents")
    if not agents_dir.exists():
        return []

    states: list[ADWState] = []
    for agent_dir in agents_dir.iterdir():
        if not agent_dir.is_dir():
            continue

        state_file = agent_dir / "adw_state.json"
        if not state_file.exists():
            continue

        try:
            state = ADWState(**json.loads(state_file.read_text()))
            states.append(state)
        except Exception:
            continue

    # Sort by updated_at descending
    states.sort(key=lambda s: s.updated_at, reverse=True)

    return states[:limit]
