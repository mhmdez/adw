"""Agent process management."""

from __future__ import annotations

import os
import sys
import subprocess
import signal
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .utils import generate_adw_id
from .models import AgentPromptRequest
from .task_updater import mark_in_progress


@dataclass
class AgentProcess:
    """Represents a running agent."""
    adw_id: str
    pid: int
    process: subprocess.Popen
    task_description: str
    worktree: str | None = None
    model: str = "sonnet"


class AgentManager:
    """Manage running agent processes."""

    def __init__(self):
        self._agents: dict[str, AgentProcess] = {}  # adw_id -> AgentProcess
        self._callbacks: list[Callable] = []

    def subscribe(self, callback: Callable) -> None:
        """Subscribe to agent events."""
        self._callbacks.append(callback)

    def notify(self, event: str, adw_id: str, **data) -> None:
        """Notify subscribers of event."""
        for cb in self._callbacks:
            cb(event, adw_id, data)

    def spawn_workflow(
        self,
        task_description: str,
        worktree_name: str | None = None,
        workflow: str = "standard",
        model: str = "sonnet",
        adw_id: str | None = None,
    ) -> str:
        """Spawn a workflow agent.

        Args:
            task_description: What to do
            worktree_name: Git worktree name
            workflow: simple, standard, full, prototype
            model: haiku, sonnet, opus

        Returns:
            ADW ID of spawned agent
        """
        adw_id = adw_id or generate_adw_id()
        worktree = worktree_name or f"task-{adw_id}"

        # Build command
        cmd = [
            sys.executable, "-m", f"adw.workflows.{workflow}",
            "--adw-id", adw_id,
            "--worktree-name", worktree,
            "--task", task_description,
            "--model", model,
        ]

        # Spawn process
        env = os.environ.copy()
        env["ADW_ID"] = adw_id

        process = subprocess.Popen(
            cmd,
            env=env,
            start_new_session=True,  # Survives parent death
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        agent = AgentProcess(
            adw_id=adw_id,
            pid=process.pid,
            process=process,
            task_description=task_description,
            worktree=worktree,
            model=model,
        )

        self._agents[adw_id] = agent
        self.notify("spawned", adw_id, pid=process.pid, task=task_description)

        return adw_id

    def spawn_prompt(
        self,
        prompt: str,
        adw_id: str | None = None,
        model: str = "sonnet",
    ) -> str:
        """Spawn a simple prompt agent."""
        adw_id = adw_id or generate_adw_id()

        cmd = [
            "claude",
            "--model", model,
            "--output-format", "stream-json",
            "--print", prompt,
        ]

        # Create output directory
        output_dir = Path("agents") / adw_id / "prompt"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / "cc_raw_output.jsonl"

        env = os.environ.copy()
        env["ADW_ID"] = adw_id

        # Open file for stdout - DON'T close it, let subprocess own it
        stdout_file = open(output_file, "w")

        process = subprocess.Popen(
            cmd,
            env=env,
            start_new_session=True,
            stdout=stdout_file,
            stderr=subprocess.PIPE,
        )

        agent = AgentProcess(
            adw_id=adw_id,
            pid=process.pid,
            process=process,
            task_description=prompt[:50],
        )
        # Store file handle for later cleanup
        agent._stdout_file = stdout_file

        self._agents[adw_id] = agent
        self.notify("spawned", adw_id, pid=process.pid)

        return adw_id

    def kill(self, adw_id: str) -> bool:
        """Kill an agent."""
        if adw_id not in self._agents:
            return False

        agent = self._agents[adw_id]
        try:
            os.killpg(os.getpgid(agent.pid), signal.SIGTERM)
            self.notify("killed", adw_id)
            return True
        except ProcessLookupError:
            return False

    def poll(self) -> list[tuple[str, int]]:
        """Poll agents for completion.

        Returns:
            List of (adw_id, return_code) for completed agents.
        """
        completed = []

        for adw_id, agent in list(self._agents.items()):
            code = agent.process.poll()
            if code is not None:
                # Capture stderr before removing
                stderr_msg = ""
                if agent.process.stderr:
                    try:
                        stderr_msg = agent.process.stderr.read().decode()[:500]
                    except Exception:
                        pass

                # Close stdout file if it exists
                if hasattr(agent, "_stdout_file") and agent._stdout_file:
                    try:
                        agent._stdout_file.close()
                    except Exception:
                        pass

                completed.append((adw_id, code))
                del self._agents[adw_id]

                event = "completed" if code == 0 else "failed"
                self.notify(event, adw_id, return_code=code, stderr=stderr_msg)

        return completed

    def get(self, adw_id: str) -> AgentProcess | None:
        """Get agent by ID."""
        return self._agents.get(adw_id)

    @property
    def running(self) -> list[AgentProcess]:
        """Get all running agents."""
        return list(self._agents.values())

    @property
    def count(self) -> int:
        """Count of running agents."""
        return len(self._agents)
