# Phase 1: Foundation

**ADW Build Phase**: 1 of 12
**Dependencies**: None
**Estimated Complexity**: Medium

---

## Objective

Create the core building blocks that everything else depends on:
- Data models (Pydantic)
- ADW ID generation
- Basic agent executor
- State manager foundation

---

## Deliverables

### 1.1 Data Models

**File**: `src/adw/agent/models.py`

```python
"""Data models for ADW agent system."""

from __future__ import annotations
from enum import Enum
from typing import Literal
from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    PENDING = "pending"
    BLOCKED = "blocked"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    FAILED = "failed"


class RetryCode(str, Enum):
    NONE = "none"
    CLAUDE_CODE_ERROR = "claude_code_error"
    TIMEOUT_ERROR = "timeout_error"
    EXECUTION_ERROR = "execution_error"
    RATE_LIMIT = "rate_limit"


class AgentPromptRequest(BaseModel):
    """Request to execute a prompt."""
    prompt: str
    adw_id: str
    agent_name: str = "default"
    model: Literal["haiku", "sonnet", "opus"] = "sonnet"
    working_dir: str | None = None
    timeout: int = 300
    dangerously_skip_permissions: bool = False


class AgentPromptResponse(BaseModel):
    """Response from agent execution."""
    output: str
    success: bool
    session_id: str | None = None
    retry_code: RetryCode = RetryCode.NONE
    error_message: str | None = None
    duration_seconds: float = 0.0


class Task(BaseModel):
    """Task from tasks.md."""
    description: str
    status: TaskStatus = TaskStatus.PENDING
    adw_id: str | None = None
    commit_hash: str | None = None
    error_message: str | None = None
    tags: list[str] = Field(default_factory=list)
    worktree_name: str | None = None
    line_number: int | None = None

    @property
    def is_running(self) -> bool:
        return self.status == TaskStatus.IN_PROGRESS

    @property
    def model(self) -> str:
        if "opus" in self.tags:
            return "opus"
        if "haiku" in self.tags:
            return "haiku"
        return "sonnet"


class Worktree(BaseModel):
    """Worktree section from tasks.md."""
    name: str
    tasks: list[Task] = Field(default_factory=list)
```

### 1.2 ADW ID Generation

**File**: `src/adw/agent/utils.py`

```python
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
```

### 1.3 Basic Agent Executor

**File**: `src/adw/agent/executor.py`

```python
"""Agent execution engine."""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

from .models import AgentPromptRequest, AgentPromptResponse, RetryCode
from .utils import generate_adw_id, get_output_dir


# Environment variables safe to pass to subprocess
SAFE_ENV_VARS = [
    "ANTHROPIC_API_KEY",
    "HOME", "USER", "PATH", "SHELL", "TERM", "LANG",
]


def get_safe_env() -> dict[str, str]:
    """Get filtered environment for subprocess."""
    env = {k: v for k, v in os.environ.items() if k in SAFE_ENV_VARS and v}
    env["PYTHONUNBUFFERED"] = "1"
    return env


def prompt_claude_code(request: AgentPromptRequest) -> AgentPromptResponse:
    """Execute a prompt with Claude Code CLI."""
    start_time = time.time()
    output_dir = get_output_dir(request.adw_id, request.agent_name)

    # Build command
    cmd = ["claude"]
    if request.model != "sonnet":
        cmd.extend(["--model", request.model])
    if request.dangerously_skip_permissions:
        cmd.append("--dangerously-skip-permissions")
    cmd.extend(["--output-format", "stream-json"])
    cmd.extend(["--print", request.prompt])

    try:
        result = subprocess.run(
            cmd,
            cwd=request.working_dir,
            capture_output=True,
            text=True,
            timeout=request.timeout,
            env=get_safe_env(),
        )

        duration = time.time() - start_time

        # Save raw output
        (output_dir / "cc_raw_output.jsonl").write_text(result.stdout)

        # Parse JSONL
        messages = []
        for line in result.stdout.strip().split("\n"):
            if line.strip():
                try:
                    messages.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

        # Save parsed
        (output_dir / "cc_raw_output.json").write_text(
            json.dumps(messages, indent=2)
        )

        # Extract result
        result_text = ""
        session_id = None
        has_error = False
        error_msg = None

        for msg in messages:
            if msg.get("session_id"):
                session_id = msg["session_id"]
            if msg.get("type") == "result":
                result_text = msg.get("result", "")
            if msg.get("type") == "error":
                has_error = True
                error_msg = msg.get("error", {}).get("message", "Unknown error")

        # Save final result
        (output_dir / "cc_final_result.txt").write_text(result_text)

        if has_error:
            return AgentPromptResponse(
                output=result_text,
                success=False,
                session_id=session_id,
                retry_code=RetryCode.EXECUTION_ERROR,
                error_message=error_msg,
                duration_seconds=duration,
            )

        return AgentPromptResponse(
            output=result_text,
            success=True,
            session_id=session_id,
            duration_seconds=duration,
        )

    except subprocess.TimeoutExpired:
        return AgentPromptResponse(
            output="",
            success=False,
            retry_code=RetryCode.TIMEOUT_ERROR,
            error_message=f"Timeout after {request.timeout}s",
            duration_seconds=request.timeout,
        )
    except FileNotFoundError:
        return AgentPromptResponse(
            output="",
            success=False,
            retry_code=RetryCode.CLAUDE_CODE_ERROR,
            error_message="Claude Code CLI not found",
            duration_seconds=0,
        )
    except Exception as e:
        return AgentPromptResponse(
            output="",
            success=False,
            retry_code=RetryCode.CLAUDE_CODE_ERROR,
            error_message=str(e),
            duration_seconds=time.time() - start_time,
        )


def prompt_with_retry(
    request: AgentPromptRequest,
    max_retries: int = 3,
    retry_delays: list[int] | None = None,
) -> AgentPromptResponse:
    """Execute prompt with automatic retry."""
    if retry_delays is None:
        retry_delays = [1, 3, 5]

    last_response = None

    for attempt in range(max_retries + 1):
        response = prompt_claude_code(request)
        last_response = response

        if response.success or response.retry_code == RetryCode.NONE:
            return response

        if attempt < max_retries:
            delay = retry_delays[min(attempt, len(retry_delays) - 1)]
            if response.retry_code == RetryCode.RATE_LIMIT:
                delay *= 3
            time.sleep(delay)

    return last_response or AgentPromptResponse(
        output="",
        success=False,
        error_message="Max retries exceeded",
    )
```

### 1.4 State Manager

**File**: `src/adw/agent/state.py`

```python
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
    workflow_type: Literal["simple", "standard", "full", "prototype"] = "standard"
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
        self.errors.append({
            "phase": phase,
            "error": error,
            "timestamp": datetime.now().isoformat(),
        })
```

### 1.5 Package Init

**File**: `src/adw/agent/__init__.py`

```python
"""ADW Agent module."""

from .models import (
    TaskStatus,
    RetryCode,
    AgentPromptRequest,
    AgentPromptResponse,
    Task,
    Worktree,
)
from .utils import generate_adw_id, get_output_dir
from .executor import prompt_claude_code, prompt_with_retry
from .state import ADWState

__all__ = [
    "TaskStatus",
    "RetryCode",
    "AgentPromptRequest",
    "AgentPromptResponse",
    "Task",
    "Worktree",
    "generate_adw_id",
    "get_output_dir",
    "prompt_claude_code",
    "prompt_with_retry",
    "ADWState",
]
```

---

## Validation

1. **Unit tests pass**: `pytest tests/test_agent/`
2. **Can generate ADW ID**: `from adw.agent import generate_adw_id; print(generate_adw_id())`
3. **Can execute simple prompt**:
   ```python
   from adw.agent import AgentPromptRequest, prompt_claude_code
   req = AgentPromptRequest(prompt="echo test", adw_id="test1234")
   resp = prompt_claude_code(req)
   assert resp.success
   ```
4. **State saves and loads**:
   ```python
   from adw.agent import ADWState
   state = ADWState(adw_id="test1234", task_description="Test")
   state.save()
   loaded = ADWState.load("test1234")
   assert loaded.task_description == "Test"
   ```

---

## Files to Create

- `src/adw/agent/__init__.py`
- `src/adw/agent/models.py`
- `src/adw/agent/utils.py`
- `src/adw/agent/executor.py`
- `src/adw/agent/state.py`
- `tests/test_agent/__init__.py`
- `tests/test_agent/test_models.py`
- `tests/test_agent/test_executor.py`
- `tests/test_agent/test_state.py`
