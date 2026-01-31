"""Daemon state management for IPC.

Provides file-based communication between CLI and daemon.
Uses .adw/daemon.json for state and control signaling.
"""

from __future__ import annotations

import json
import os
import signal
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any


class DaemonStatus(str, Enum):
    """Daemon status."""
    STOPPED = "stopped"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"


@dataclass
class DaemonState:
    """Daemon state for IPC."""
    pid: int | None = None
    status: DaemonStatus = DaemonStatus.STOPPED
    started_at: str | None = None
    paused_at: str | None = None
    running_tasks: list[dict] = field(default_factory=list)
    pending_count: int = 0
    completed_count: int = 0
    failed_count: int = 0
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        d = asdict(self)
        d["status"] = self.status.value
        return d
    
    @classmethod
    def from_dict(cls, d: dict) -> "DaemonState":
        """Create from dictionary."""
        status = DaemonStatus(d.get("status", "stopped"))
        return cls(
            pid=d.get("pid"),
            status=status,
            started_at=d.get("started_at"),
            paused_at=d.get("paused_at"),
            running_tasks=d.get("running_tasks", []),
            pending_count=d.get("pending_count", 0),
            completed_count=d.get("completed_count", 0),
            failed_count=d.get("failed_count", 0),
        )


def get_state_path() -> Path:
    """Get path to daemon state file."""
    return Path.cwd() / ".adw" / "daemon.json"


def read_state() -> DaemonState:
    """Read current daemon state.
    
    Returns:
        DaemonState, or default stopped state if not found
    """
    state_path = get_state_path()
    
    if not state_path.exists():
        return DaemonState()
    
    try:
        data = json.loads(state_path.read_text())
        state = DaemonState.from_dict(data)
        
        # Check if daemon is actually running
        if state.pid and state.status != DaemonStatus.STOPPED:
            if not is_process_running(state.pid):
                # Daemon crashed or was killed
                state.status = DaemonStatus.STOPPED
                state.pid = None
        
        return state
    except (json.JSONDecodeError, KeyError):
        return DaemonState()


def write_state(state: DaemonState) -> None:
    """Write daemon state to file."""
    state_path = get_state_path()
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state.to_dict(), indent=2))


def is_process_running(pid: int) -> bool:
    """Check if a process is running."""
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def signal_daemon(sig: signal.Signals) -> bool:
    """Send signal to running daemon.
    
    Args:
        sig: Signal to send (SIGUSR1 for pause, SIGUSR2 for resume)
        
    Returns:
        True if signal was sent successfully
    """
    state = read_state()
    
    if not state.pid or state.status == DaemonStatus.STOPPED:
        return False
    
    try:
        os.kill(state.pid, sig)
        return True
    except (OSError, ProcessLookupError):
        return False


def request_pause() -> bool:
    """Request daemon to pause.
    
    Returns:
        True if request was sent
    """
    return signal_daemon(signal.SIGUSR1)


def request_resume() -> bool:
    """Request daemon to resume.
    
    Returns:
        True if request was sent
    """
    return signal_daemon(signal.SIGUSR2)


class DaemonStateManager:
    """Manager for daemon state updates.
    
    Used by the daemon to update state file as it runs.
    
    Usage:
        manager = DaemonStateManager()
        manager.start()
        manager.add_task({"id": "abc", "description": "..."})
        manager.task_completed("abc")
        manager.pause()
        manager.resume()
        manager.stop()
    """
    
    def __init__(self):
        self._state = DaemonState()
        self._paused = False
    
    @property
    def is_paused(self) -> bool:
        """Check if daemon is paused."""
        return self._paused
    
    def start(self) -> None:
        """Mark daemon as started."""
        self._state.pid = os.getpid()
        self._state.status = DaemonStatus.RUNNING
        self._state.started_at = datetime.now().isoformat()
        self._state.paused_at = None
        self._paused = False
        self._save()
    
    def stop(self) -> None:
        """Mark daemon as stopped."""
        self._state.status = DaemonStatus.STOPPED
        self._state.pid = None
        self._save()
    
    def pause(self) -> None:
        """Pause the daemon."""
        self._paused = True
        self._state.status = DaemonStatus.PAUSED
        self._state.paused_at = datetime.now().isoformat()
        self._save()
    
    def resume(self) -> None:
        """Resume the daemon."""
        self._paused = False
        self._state.status = DaemonStatus.RUNNING
        self._state.paused_at = None
        self._save()
    
    def add_task(self, task_info: dict) -> None:
        """Add a running task."""
        self._state.running_tasks.append(task_info)
        self._save()
    
    def remove_task(self, adw_id: str) -> None:
        """Remove a task from running list."""
        self._state.running_tasks = [
            t for t in self._state.running_tasks
            if t.get("adw_id") != adw_id
        ]
        self._save()
    
    def task_completed(self, adw_id: str) -> None:
        """Mark task as completed."""
        self.remove_task(adw_id)
        self._state.completed_count += 1
        self._save()
    
    def task_failed(self, adw_id: str) -> None:
        """Mark task as failed."""
        self.remove_task(adw_id)
        self._state.failed_count += 1
        self._save()
    
    def update_pending(self, count: int) -> None:
        """Update pending task count."""
        self._state.pending_count = count
        self._save()
    
    def _save(self) -> None:
        """Save state to file."""
        write_state(self._state)
