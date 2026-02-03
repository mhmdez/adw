"""Agent process management."""

from __future__ import annotations

import logging
import os
import signal
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .utils import generate_adw_id

logger = logging.getLogger(__name__)

# Built-in Python workflows that can be run as modules
# Note: "adaptive" is the primary workflow that handles simple/standard/sdlc
BUILTIN_PYTHON_WORKFLOWS = {"simple", "standard", "sdlc", "adaptive"}


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
        workflow: str = "adaptive",
        model: str = "sonnet",
        adw_id: str | None = None,
        priority: str | None = None,
    ) -> str:
        """Spawn a workflow agent.

        By default, uses the adaptive workflow which automatically detects
        task complexity and runs appropriate phases. Also supports explicit
        workflow selection (simple, standard, sdlc) and DSL-defined workflows.

        Args:
            task_description: What to do
            worktree_name: Git worktree name
            workflow: Workflow name - "adaptive" (default, auto-detects complexity),
                "simple", "standard", "sdlc", or a DSL workflow name
            model: haiku, sonnet, opus
            adw_id: Optional ADW ID (generated if not provided)
            priority: Optional task priority (p0-p3) for complexity detection

        Returns:
            ADW ID of spawned agent
        """
        adw_id = adw_id or generate_adw_id()
        # Sanitize worktree name
        raw_worktree = worktree_name or f"task-{adw_id}"
        worktree = raw_worktree.replace(" ", "-").lower()

        # Map legacy workflow names to adaptive complexity levels
        complexity_mapping = {
            "simple": "minimal",
            "standard": "standard",
            "sdlc": "full",
        }

        # Determine if this is a DSL workflow or built-in Python workflow
        is_dsl_workflow = workflow not in BUILTIN_PYTHON_WORKFLOWS
        if is_dsl_workflow:
            # Check if DSL workflow exists
            try:
                from ..workflows.dsl import get_workflow

                dsl_workflow = get_workflow(workflow)
                if dsl_workflow is None:
                    logger.warning(
                        "DSL workflow '%s' not found, falling back to adaptive",
                        workflow,
                    )
                    workflow = "adaptive"
                    is_dsl_workflow = False
            except Exception as e:
                logger.warning(
                    "Error loading DSL workflow '%s': %s, falling back to adaptive",
                    workflow,
                    e,
                )
                workflow = "adaptive"
                is_dsl_workflow = False

        # Build command based on workflow type
        if is_dsl_workflow:
            # Use DSL executor for custom workflows
            cmd = [
                sys.executable,
                "-m",
                "adw.workflows.dsl_executor",
                "--workflow",
                workflow,
                "--adw-id",
                adw_id,
                "--worktree-name",
                worktree,
                "--task",
                task_description,
                "--verbose",
            ]
        elif workflow == "adaptive":
            # Use adaptive workflow with auto-detection
            cmd = [
                sys.executable,
                "-m",
                "adw.workflows.adaptive",
                "--adw-id",
                adw_id,
                "--worktree-name",
                worktree,
                "--task",
                task_description,
                "--complexity",
                "auto",
                "--model",
                model,
                "--verbose",
            ]
            if priority:
                cmd.extend(["--priority", priority])
        elif workflow in complexity_mapping:
            # Use adaptive workflow with explicit complexity for legacy workflow names
            cmd = [
                sys.executable,
                "-m",
                "adw.workflows.adaptive",
                "--adw-id",
                adw_id,
                "--worktree-name",
                worktree,
                "--task",
                task_description,
                "--complexity",
                complexity_mapping[workflow],
                "--model",
                model,
                "--verbose",
            ]
        else:
            # Fallback to adaptive workflow
            cmd = [
                sys.executable,
                "-m",
                "adw.workflows.adaptive",
                "--adw-id",
                adw_id,
                "--worktree-name",
                worktree,
                "--task",
                task_description,
                "--complexity",
                "auto",
                "--model",
                model,
                "--verbose",
            ]

        # Spawn process
        env = os.environ.copy()
        env["ADW_ID"] = adw_id

        # Use DEVNULL for stdout to avoid pipe buffer deadlock
        process = subprocess.Popen(
            cmd,
            env=env,
            start_new_session=True,  # Survives parent death
            stdout=subprocess.DEVNULL,
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
            "--model",
            model,
            "--output-format",
            "stream-json",
            "--print",
            prompt,
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

    def poll(self) -> list[tuple[str, int, str]]:
        """Poll agents for completion.

        Returns:
            List of (adw_id, return_code, stderr) for completed agents.
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

                completed.append((adw_id, code, stderr_msg))
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
