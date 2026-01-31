# Phase 4: Agent System

**ADW Build Phase**: 4 of 12
**Dependencies**: Phase 1-3
**Estimated Complexity**: High

---

## Objective

Implement agent spawning and management:
- Spawn Claude Code as background process
- Track running agents by PID and ADW ID
- Wire agent spawning to TUI (new task starts agent)
- Handle agent completion/failure

---

## Deliverables

### 4.1 Agent Manager

**File**: `src/adw/agent/manager.py`

```python
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

        with open(output_file, "w") as f:
            process = subprocess.Popen(
                cmd,
                env=env,
                start_new_session=True,
                stdout=f,
                stderr=subprocess.PIPE,
            )

        agent = AgentProcess(
            adw_id=adw_id,
            pid=process.pid,
            process=process,
            task_description=prompt[:50],
        )

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
                completed.append((adw_id, code))
                del self._agents[adw_id]

                event = "completed" if code == 0 else "failed"
                self.notify(event, adw_id, return_code=code)

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
```

### 4.2 Simple Workflow

**File**: `src/adw/workflows/__init__.py`

```python
"""ADW Workflows."""
```

**File**: `src/adw/workflows/simple.py`

```python
"""Simple workflow: Build → Update."""

from __future__ import annotations

import sys
import time
from pathlib import Path

import click

from ..agent.executor import prompt_with_retry, AgentPromptRequest
from ..agent.state import ADWState
from ..agent.utils import generate_adw_id
from ..agent.task_updater import mark_done, mark_failed


def run_simple_workflow(
    task_description: str,
    worktree_name: str,
    adw_id: str | None = None,
    model: str = "sonnet",
) -> bool:
    """Execute simple build workflow."""
    adw_id = adw_id or generate_adw_id()
    tasks_file = Path("tasks.md")

    # Create state
    state = ADWState(
        adw_id=adw_id,
        task_description=task_description,
        worktree_name=worktree_name,
        workflow_type="simple",
    )
    state.save("init")

    success = True
    error_message = None
    commit_hash = None

    try:
        # Build phase
        state.save("build")

        response = prompt_with_retry(AgentPromptRequest(
            prompt=f"/build {task_description}",
            adw_id=adw_id,
            agent_name=f"builder-{adw_id}",
            model=model,
        ))

        if not response.success:
            raise Exception(response.error_message or "Build failed")

        # Get commit hash
        import subprocess
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            commit_hash = result.stdout.strip()

        state.commit_hash = commit_hash
        state.save("build")

    except Exception as e:
        success = False
        error_message = str(e)
        state.add_error("build", error_message)

    # Update task
    if success:
        mark_done(tasks_file, task_description, adw_id, commit_hash)
    else:
        mark_failed(tasks_file, task_description, adw_id, error_message or "Unknown")

    state.save("complete" if success else "failed")
    return success


@click.command()
@click.option("--adw-id")
@click.option("--worktree-name", required=True)
@click.option("--task", required=True)
@click.option("--model", default="sonnet")
def main(adw_id, worktree_name, task, model):
    success = run_simple_workflow(task, worktree_name, adw_id, model)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
```

### 4.3 Standard Workflow

**File**: `src/adw/workflows/standard.py`

```python
"""Standard workflow: Plan → Implement → Update."""

from __future__ import annotations

import re
import sys
import time
from pathlib import Path

import click

from ..agent.executor import prompt_with_retry, AgentPromptRequest
from ..agent.state import ADWState
from ..agent.utils import generate_adw_id
from ..agent.task_updater import mark_done, mark_failed


def run_standard_workflow(
    task_description: str,
    worktree_name: str,
    adw_id: str | None = None,
    model: str = "sonnet",
) -> bool:
    """Execute standard plan-implement workflow."""
    adw_id = adw_id or generate_adw_id()
    tasks_file = Path("tasks.md")

    state = ADWState(
        adw_id=adw_id,
        task_description=task_description,
        worktree_name=worktree_name,
        workflow_type="standard",
    )
    state.save("init")

    success = True
    error_message = None
    commit_hash = None
    plan_file = None

    try:
        # Plan phase
        state.save("plan")

        plan_response = prompt_with_retry(AgentPromptRequest(
            prompt=f"/plan {adw_id} {task_description}",
            adw_id=adw_id,
            agent_name=f"planner-{adw_id}",
            model=model,
        ))

        if not plan_response.success:
            raise Exception(f"Planning failed: {plan_response.error_message}")

        # Extract plan file from output
        match = re.search(r"specs/[a-z0-9-]+\.md", plan_response.output, re.I)
        if match:
            plan_file = match.group(0)
        state.plan_file = plan_file
        state.save("plan")

        # Implement phase
        state.save("implement")

        impl_args = plan_file if plan_file else task_description
        impl_response = prompt_with_retry(AgentPromptRequest(
            prompt=f"/implement {impl_args}",
            adw_id=adw_id,
            agent_name=f"builder-{adw_id}",
            model=model,
        ))

        if not impl_response.success:
            raise Exception(f"Implementation failed: {impl_response.error_message}")

        # Get commit
        import subprocess
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            commit_hash = result.stdout.strip()

        state.commit_hash = commit_hash
        state.save("implement")

    except Exception as e:
        success = False
        error_message = str(e)
        state.add_error(state.current_phase, error_message)

    # Update task
    if success:
        mark_done(tasks_file, task_description, adw_id, commit_hash)
    else:
        mark_failed(tasks_file, task_description, adw_id, error_message or "Unknown")

    state.save("complete" if success else "failed")
    return success


@click.command()
@click.option("--adw-id")
@click.option("--worktree-name", required=True)
@click.option("--task", required=True)
@click.option("--model", default="sonnet")
def main(adw_id, worktree_name, task, model):
    success = run_standard_workflow(task, worktree_name, adw_id, model)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
```

### 4.4 Wire to TUI

**Update**: `src/adw/tui/app.py`

Add agent manager and new task modal:

```python
# Add to imports
from ..agent.manager import AgentManager
from ..agent.task_updater import mark_in_progress
from ..agent.utils import generate_adw_id

# Add to __init__
def __init__(self):
    super().__init__()
    self.state = AppState()
    self.agent_manager = AgentManager()

    self.state.subscribe(self._on_state_change)
    self.agent_manager.subscribe(self._on_agent_event)

# Add agent event handler
def _on_agent_event(self, event: str, adw_id: str, data: dict) -> None:
    """Handle agent events."""
    if event == "spawned":
        self.notify(f"Agent {adw_id} started")
    elif event == "completed":
        self.notify(f"Agent {adw_id} completed")
        self.state.load_from_tasks_md()  # Refresh
    elif event == "failed":
        self.notify(f"Agent {adw_id} failed", severity="error")
        self.state.load_from_tasks_md()

# Add new task action
async def action_new_task(self) -> None:
    """Create and start new task."""
    # Simple implementation - just prompt for description
    # Full modal comes in later phase

    # For now, use a notify as placeholder
    self.notify("Enter task in status bar input")

# Add method to spawn from input
def spawn_task(self, description: str) -> None:
    """Spawn a new task agent."""
    adw_id = generate_adw_id()
    worktree = f"task-{adw_id}"

    # Mark in progress in tasks.md
    tasks_file = Path("tasks.md")
    mark_in_progress(tasks_file, description, adw_id)

    # Spawn agent
    self.agent_manager.spawn_workflow(
        task_description=description,
        worktree_name=worktree,
        adw_id=adw_id,
    )

    # Refresh state
    self.state.load_from_tasks_md()

# Add polling worker
async def on_mount(self) -> None:
    self.state.load_from_tasks_md()
    self.set_interval(2.0, self._poll_agents)

def _poll_agents(self) -> None:
    """Poll for agent completion."""
    completed = self.agent_manager.poll()
    if completed:
        self.state.load_from_tasks_md()
```

---

## Validation

1. **Can spawn agent**: `AgentManager().spawn_workflow("test", "test-wt")`
2. **Agent runs**: Process visible, creates output in agents/
3. **Completion detected**: poll() returns completed agents
4. **TUI integration**: New task from TUI spawns agent
5. **Status updates**: tasks.md updated on completion

---

## Files to Create

- `src/adw/agent/manager.py`
- `src/adw/workflows/__init__.py`
- `src/adw/workflows/simple.py`
- `src/adw/workflows/standard.py`

## Files to Modify

- `src/adw/tui/app.py` (add agent manager, spawning)
