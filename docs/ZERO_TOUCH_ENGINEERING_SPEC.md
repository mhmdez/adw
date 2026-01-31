# ADW: Zero-Touch Engineering Specification

> **Vision**: A CLI tool that enables anyone to initialize any project and achieve autonomous end-to-end software development with minimal human intervention.

**Document Version**: 1.0
**Based on**: Analysis of tac-8 agentic engineering repositories
**Target**: Top-tier, production-ready agentic development workflow

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Architecture Overview](#2-architecture-overview)
3. [Core Concepts](#3-core-concepts)
4. [Phase 1: Foundation](#4-phase-1-foundation)
5. [Phase 2: Autonomous Execution](#5-phase-2-autonomous-execution)
6. [Phase 3: Parallel Isolation](#6-phase-3-parallel-isolation)
7. [Phase 4: Observability & Context](#7-phase-4-observability--context)
8. [Phase 5: Advanced Workflows](#8-phase-5-advanced-workflows)
9. [Phase 6: Integrations](#9-phase-6-integrations)
10. [Phase 7: Self-Improvement](#10-phase-7-self-improvement)
11. [Implementation Roadmap](#11-implementation-roadmap)
12. [File Structure](#12-file-structure)
13. [API Reference](#13-api-reference)

---

## 1. Executive Summary

### 1.1 Current State

ADW currently provides:
- Project detection and initialization
- Slash commands for planning (`/discuss`, `/plan`)
- Spec-driven development workflow
- Task tracking in `tasks.md`
- Basic agent templates

**Limitation**: Every step requires manual human invocation. The system is a toolkit, not an autonomous workflow engine.

### 1.2 Target State

ADW will become a **zero-touch engineering platform** where:

```
Human: "adw new 'Add user authentication with OAuth'"
  ↓
System autonomously:
  1. Creates spec with clarifying questions (if needed)
  2. Decomposes into tasks
  3. Creates isolated worktree
  4. Plans implementation
  5. Implements code
  6. Runs tests
  7. Reviews against spec
  8. Generates documentation
  9. Creates PR
  ↓
Human: Reviews PR, provides feedback or merges
```

### 1.3 Key Differentiators

| Capability | Current | Zero-Touch |
|------------|---------|------------|
| Execution | Manual per-step | Autonomous end-to-end |
| Parallelism | None | Multiple tasks simultaneously |
| Isolation | Shared repo | Git worktrees per task |
| Tracking | None | ADW ID + full audit trail |
| Observability | None | Real-time dashboard + hooks |
| Context | Static CLAUDE.md | Dynamic priming + bundles |
| Recovery | Manual | Auto-retry + graceful degradation |
| Learning | Static prompts | Self-improving expert system |

### 1.4 Design Principles

1. **Isolation First**: Every execution runs in its own sandbox
2. **Composability**: Complex workflows built from simple, chainable phases
3. **State-Driven**: Persistent JSON state enables loose coupling
4. **Observable**: Every action logged and traceable
5. **Resilient**: Failures don't cascade; auto-retry on transient errors
6. **Extensible**: New workflows via composition, not modification
7. **Context-Efficient**: Minimize tokens, maximize capability

---

## 2. Architecture Overview

### 2.1 System Layers

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER INTERFACE                           │
│  CLI Commands │ Dashboard │ GitHub/Notion │ Webhooks            │
└─────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────────┐
│                      ORCHESTRATION LAYER                        │
│  Cron Trigger │ Webhook Handler │ Task Router │ State Manager   │
└─────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────────┐
│                        WORKFLOW LAYER                           │
│  Plan │ Build │ Test │ Review │ Document │ Ship                 │
└─────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────────┐
│                         AGENT LAYER                             │
│  Agent Executor │ Template Engine │ Model Selector │ Retry      │
└─────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────────┐
│                      ISOLATION LAYER                            │
│  Worktree Manager │ Port Allocator │ Environment Isolation      │
└─────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────────┐
│                     OBSERVABILITY LAYER                         │
│  Hooks │ Context Bundles │ Logging │ Metrics │ Dashboard        │
└─────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────────┐
│                       STORAGE LAYER                             │
│  tasks.md │ specs/ │ agents/{adw_id}/ │ trees/ │ SQLite         │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Data Flow

```
┌──────────┐     ┌─────────────┐     ┌──────────────┐
│  Input   │────▶│   Trigger   │────▶│  Task Router │
│ (Human/  │     │ (Cron/Hook/ │     │  (Classify + │
│  GitHub) │     │  Webhook)   │     │   Delegate)  │
└──────────┘     └─────────────┘     └──────────────┘
                                            │
                    ┌───────────────────────┼───────────────────────┐
                    ▼                       ▼                       ▼
            ┌──────────────┐       ┌──────────────┐       ┌──────────────┐
            │  Worktree 1  │       │  Worktree 2  │       │  Worktree 3  │
            │  (Task A)    │       │  (Task B)    │       │  (Task C)    │
            └──────────────┘       └──────────────┘       └──────────────┘
                    │                       │                       │
                    ▼                       ▼                       ▼
            ┌──────────────┐       ┌──────────────┐       ┌──────────────┐
            │ Plan→Build→  │       │ Plan→Build→  │       │ Plan→Build→  │
            │ Test→Review  │       │ Test→Review  │       │ Test→Review  │
            └──────────────┘       └──────────────┘       └──────────────┘
                    │                       │                       │
                    └───────────────────────┼───────────────────────┘
                                            ▼
                                    ┌──────────────┐
                                    │ Update Status│
                                    │ Create PR    │
                                    │ Notify Human │
                                    └──────────────┘
```

### 2.3 Core Components

| Component | Purpose | Location |
|-----------|---------|----------|
| **CLI** | User interface | `src/adw/cli.py` |
| **Agent Executor** | Run Claude Code with retry | `src/adw/agent/executor.py` |
| **State Manager** | Persistent workflow state | `src/adw/agent/state.py` |
| **Worktree Manager** | Git isolation | `src/adw/agent/worktree.py` |
| **Task Router** | Classify and delegate | `src/adw/agent/router.py` |
| **Cron Trigger** | Autonomous monitoring | `src/adw/triggers/cron.py` |
| **Hook System** | Observability | `src/adw/hooks/` |
| **Dashboard** | Real-time UI | `src/adw/dashboard/` |

---

## 3. Core Concepts

### 3.1 ADW ID (Execution Identifier)

Every workflow execution gets a unique 8-character identifier:

```python
import uuid

def generate_adw_id() -> str:
    """Generate unique 8-character execution identifier."""
    return uuid.uuid4().hex[:8]  # e.g., "a1b2c3d4"
```

**Usage**:
- Track all outputs: `agents/{adw_id}/`
- Identify agent runs: `planner-{adw_id}`, `builder-{adw_id}`
- Correlate logs, commits, PRs
- Enable resume/retry of specific executions

### 3.2 Task Status State Machine

```
                    ┌─────────────────┐
                    │                 │
                    ▼                 │
┌────┐    ┌────────────┐    ┌────────────┐
│ [] │───▶│    [⏰]    │───▶│    [🟡]    │
│new │    │  blocked   │    │in_progress │
└────┘    └────────────┘    └────────────┘
              │                   │
              │                   ├─────────────┐
              │                   ▼             ▼
              │            ┌────────────┐ ┌────────────┐
              │            │    [✅]    │ │    [❌]    │
              │            │   done     │ │  failed    │
              │            └────────────┘ └────────────┘
              │                   │             │
              │                   ▼             ▼
              │            ┌────────────────────────┐
              └───────────▶│  Can unblock [⏰] tasks│
                           └────────────────────────┘
```

**Task Format in tasks.md**:
```markdown
## Feature: User Authentication

[] Design OAuth flow                                    # Pending
[⏰] Implement OAuth provider {opus}                    # Blocked until above done
[🟡, abc12345] Add token refresh                       # In progress (ADW ID shown)
[✅ def67890, commit123] Create login UI               # Done (commit hash)
[❌, ghi78901] Add SAML support // Failed: timeout     # Failed with reason
```

### 3.3 Tag System

Tags in `{curly braces}` control execution:

| Tag | Category | Effect |
|-----|----------|--------|
| `{opus}` | Model | Use Claude Opus (complex reasoning) |
| `{sonnet}` | Model | Use Claude Sonnet (default, faster) |
| `{haiku}` | Model | Use Claude Haiku (simple tasks) |
| `{plan}` | Workflow | Force plan-implement workflow |
| `{build}` | Workflow | Direct build (skip planning) |
| `{prototype:vite_vue}` | Prototype | Generate Vue app |
| `{prototype:uv_script}` | Prototype | Generate Python CLI |
| `{prototype:bun_scripts}` | Prototype | Generate TypeScript |
| `{worktree:custom-name}` | Isolation | Custom worktree name |
| `{priority:high}` | Scheduling | Process first |
| `{depends:TASK-001}` | Dependencies | Explicit dependency |

### 3.4 Workflow Types

**Simple Workflow** (2 phases):
```
/build → /update_task
```
Best for: Bug fixes, small features, data changes

**Standard Workflow** (4 phases):
```
/plan → /implement → /test → /update_task
```
Best for: New features, refactoring

**Full SDLC Workflow** (6 phases):
```
/plan → /implement → /test → /review → /document → /ship
```
Best for: Production features, complex changes

**Prototype Workflow** (specialized):
```
/plan_{prototype_type} → /implement → /update_task
```
Best for: Rapid application generation

### 3.5 The 7 Levels of Agentic Prompts

From `agentic-prompt-engineering`, prompts have increasing sophistication:

| Level | Type | Description |
|-------|------|-------------|
| 1 | High-Level | Static, reusable instructions |
| 2 | Workflow | Sequential steps with variables |
| 3 | Control Flow | Conditions and loops |
| 4 | Delegate | Spawns sub-agents |
| 5 | Higher-Order | Accepts prompts as input |
| 6 | Template Meta | Generates new prompts |
| 7 | Self-Improving | Updates itself with learnings |

ADW commands should target **Level 4-5** for most operations, with expert systems at **Level 7**.

---

## 4. Phase 1: Foundation

### 4.1 Agent Executor Module

**File**: `src/adw/agent/executor.py`

The core execution engine for running Claude Code programmatically:

```python
"""Agent execution engine for ADW."""

from __future__ import annotations

import json
import os
import subprocess
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel


class RetryCode(Enum):
    """Classification of errors for retry logic."""
    NONE = "none"                           # Success or non-retryable
    CLAUDE_CODE_ERROR = "claude_code_error" # CLI error (retryable)
    TIMEOUT_ERROR = "timeout_error"         # Timeout (retryable)
    EXECUTION_ERROR = "execution_error"     # Execution failed (retryable)
    RATE_LIMIT = "rate_limit"               # Rate limited (retryable with backoff)


class AgentPromptRequest(BaseModel):
    """Request to execute a direct prompt."""
    prompt: str
    adw_id: str
    agent_name: str = "default"
    model: Literal["haiku", "sonnet", "opus"] = "sonnet"
    working_dir: str | None = None
    timeout: int = 300  # 5 minutes default
    dangerously_skip_permissions: bool = False


class AgentTemplateRequest(BaseModel):
    """Request to execute a slash command template."""
    slash_command: str  # e.g., "/plan", "/build"
    args: list[str] = field(default_factory=list)
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


def generate_adw_id() -> str:
    """Generate unique 8-character execution identifier."""
    return uuid.uuid4().hex[:8]


def get_safe_subprocess_env() -> dict[str, str]:
    """Get filtered environment for subprocess execution.

    Only passes essential variables to prevent leakage.
    """
    safe_vars = [
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "CLAUDE_CODE_PATH",
        "HOME",
        "USER",
        "PATH",
        "SHELL",
        "TERM",
        "LANG",
        "LC_ALL",
    ]

    env = {k: v for k, v in os.environ.items() if k in safe_vars}
    env["PYTHONUNBUFFERED"] = "1"  # Real-time output
    return env


def get_output_dir(adw_id: str, agent_name: str) -> Path:
    """Get output directory for agent execution."""
    output_dir = Path("agents") / adw_id / agent_name
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def parse_jsonl_output(jsonl_content: str) -> list[dict]:
    """Parse JSONL output from Claude Code --stream-json."""
    messages = []
    for line in jsonl_content.strip().split("\n"):
        if line.strip():
            try:
                messages.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return messages


def extract_result_message(messages: list[dict]) -> str:
    """Extract final result text from parsed messages."""
    for msg in reversed(messages):
        if msg.get("type") == "result":
            return msg.get("result", "")
        if msg.get("type") == "assistant" and msg.get("message", {}).get("content"):
            content = msg["message"]["content"]
            if isinstance(content, list):
                text_parts = [c.get("text", "") for c in content if c.get("type") == "text"]
                return "\n".join(text_parts)
            return str(content)
    return ""


def check_for_error(messages: list[dict]) -> tuple[bool, str | None]:
    """Check if execution resulted in error."""
    for msg in messages:
        if msg.get("type") == "error":
            return True, msg.get("error", {}).get("message", "Unknown error")
        if msg.get("type") == "result" and not msg.get("success", True):
            return True, msg.get("error", "Execution failed")
    return False, None


def prompt_claude_code(request: AgentPromptRequest) -> AgentPromptResponse:
    """Execute a prompt with Claude Code CLI.

    Args:
        request: The prompt request configuration.

    Returns:
        AgentPromptResponse with output and status.
    """
    import time
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

    # Execute
    try:
        result = subprocess.run(
            cmd,
            cwd=request.working_dir,
            capture_output=True,
            text=True,
            timeout=request.timeout,
            env=get_safe_subprocess_env(),
        )

        duration = time.time() - start_time

        # Save raw output
        raw_output_path = output_dir / "cc_raw_output.jsonl"
        raw_output_path.write_text(result.stdout)

        # Parse output
        messages = parse_jsonl_output(result.stdout)

        # Save parsed JSON
        json_output_path = output_dir / "cc_raw_output.json"
        json_output_path.write_text(json.dumps(messages, indent=2))

        # Check for errors
        has_error, error_msg = check_for_error(messages)

        if has_error:
            return AgentPromptResponse(
                output=result.stdout,
                success=False,
                retry_code=RetryCode.EXECUTION_ERROR,
                error_message=error_msg,
                duration_seconds=duration,
            )

        # Extract result
        result_text = extract_result_message(messages)

        # Save final result
        final_path = output_dir / "cc_final_result.txt"
        final_path.write_text(result_text)

        # Extract session ID if present
        session_id = None
        for msg in messages:
            if msg.get("session_id"):
                session_id = msg["session_id"]
                break

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


def prompt_claude_code_with_retry(
    request: AgentPromptRequest,
    max_retries: int = 3,
    retry_delays: list[int] | None = None,
) -> AgentPromptResponse:
    """Execute prompt with automatic retry on transient failures.

    Args:
        request: The prompt request configuration.
        max_retries: Maximum retry attempts.
        retry_delays: Delays between retries in seconds.

    Returns:
        AgentPromptResponse from successful execution or final failure.
    """
    import time

    if retry_delays is None:
        retry_delays = [1, 3, 5]

    last_response = None

    for attempt in range(max_retries + 1):
        response = prompt_claude_code(request)
        last_response = response

        if response.success:
            return response

        # Check if retryable
        if response.retry_code == RetryCode.NONE:
            return response  # Non-retryable error

        if attempt < max_retries:
            delay = retry_delays[min(attempt, len(retry_delays) - 1)]

            # Extra delay for rate limits
            if response.retry_code == RetryCode.RATE_LIMIT:
                delay *= 3

            time.sleep(delay)

    return last_response or AgentPromptResponse(
        output="",
        success=False,
        error_message="Max retries exceeded",
    )


def execute_template(request: AgentTemplateRequest) -> AgentPromptResponse:
    """Execute a slash command template.

    Args:
        request: Template execution request.

    Returns:
        AgentPromptResponse with execution results.
    """
    # Build the slash command with arguments
    if request.args:
        args_str = " ".join(f'"{arg}"' if " " in arg else arg for arg in request.args)
        prompt = f"{request.slash_command} {args_str}"
    else:
        prompt = request.slash_command

    # Convert to prompt request
    prompt_request = AgentPromptRequest(
        prompt=prompt,
        adw_id=request.adw_id,
        agent_name=request.agent_name,
        model=request.model,
        working_dir=request.working_dir,
        timeout=request.timeout,
        dangerously_skip_permissions=request.dangerously_skip_permissions,
    )

    return prompt_claude_code_with_retry(prompt_request)
```

### 4.2 State Manager Module

**File**: `src/adw/agent/state.py`

Persistent state management for workflow coordination:

```python
"""Persistent state management for ADW workflows."""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class ADWState(BaseModel):
    """Persistent workflow state."""

    # Identity
    adw_id: str
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())

    # Task info
    task_description: str = ""
    task_id: str | None = None
    task_tags: list[str] = Field(default_factory=list)

    # Workflow info
    workflow_type: Literal["simple", "standard", "full", "prototype"] = "standard"
    current_phase: str = "init"
    phases_completed: list[str] = Field(default_factory=list)

    # Git info
    worktree_name: str | None = None
    worktree_path: str | None = None
    branch_name: str | None = None
    commit_hash: str | None = None

    # Ports (for apps that need servers)
    backend_port: int | None = None
    frontend_port: int | None = None

    # Artifacts
    plan_file: str | None = None
    spec_file: str | None = None

    # Model selection
    model_set: Literal["base", "heavy"] = "base"

    # Execution history
    all_phases: list[str] = Field(default_factory=list)
    errors: list[dict] = Field(default_factory=list)

    @classmethod
    def get_state_path(cls, adw_id: str) -> Path:
        """Get path to state file for given ADW ID."""
        return Path("agents") / adw_id / "adw_state.json"

    @classmethod
    def load(cls, adw_id: str) -> ADWState | None:
        """Load state from file system.

        Args:
            adw_id: The ADW ID to load state for.

        Returns:
            ADWState if found, None otherwise.
        """
        state_path = cls.get_state_path(adw_id)
        if not state_path.exists():
            return None

        try:
            data = json.loads(state_path.read_text())
            return cls(**data)
        except (json.JSONDecodeError, ValueError):
            return None

    @classmethod
    def create(cls, adw_id: str, **kwargs) -> ADWState:
        """Create new state with given ADW ID.

        Args:
            adw_id: The ADW ID for this workflow.
            **kwargs: Additional state fields.

        Returns:
            New ADWState instance (not yet saved).
        """
        return cls(adw_id=adw_id, **kwargs)

    def save(self, phase: str | None = None) -> Path:
        """Save state to file system.

        Args:
            phase: Optional phase name to record.

        Returns:
            Path to saved state file.
        """
        if phase:
            self.current_phase = phase
            if phase not in self.phases_completed:
                self.phases_completed.append(phase)
            if phase not in self.all_phases:
                self.all_phases.append(phase)

        self.updated_at = datetime.now().isoformat()

        state_path = self.get_state_path(self.adw_id)
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(self.model_dump_json(indent=2))

        return state_path

    def add_error(self, phase: str, error: str, recoverable: bool = True) -> None:
        """Record an error.

        Args:
            phase: Phase where error occurred.
            error: Error message.
            recoverable: Whether workflow can continue.
        """
        self.errors.append({
            "phase": phase,
            "error": error,
            "recoverable": recoverable,
            "timestamp": datetime.now().isoformat(),
        })

    def to_stdout(self) -> None:
        """Write state to stdout for piping to next script."""
        print(self.model_dump_json())

    @classmethod
    def from_stdin(cls) -> ADWState | None:
        """Read state from stdin (piped from previous script).

        Returns:
            ADWState if valid JSON received, None otherwise.
        """
        if sys.stdin.isatty():
            return None

        try:
            data = json.loads(sys.stdin.read())
            return cls(**data)
        except (json.JSONDecodeError, ValueError):
            return None

    def is_phase_complete(self, phase: str) -> bool:
        """Check if a phase has been completed."""
        return phase in self.phases_completed

    def get_model_for_phase(self, phase: str) -> str:
        """Get appropriate model for a phase based on model_set.

        Args:
            phase: The workflow phase.

        Returns:
            Model name ("haiku", "sonnet", or "opus").
        """
        # Model selection map
        phase_models = {
            "plan": {"base": "sonnet", "heavy": "opus"},
            "implement": {"base": "sonnet", "heavy": "opus"},
            "test": {"base": "sonnet", "heavy": "sonnet"},
            "review": {"base": "sonnet", "heavy": "opus"},
            "document": {"base": "sonnet", "heavy": "opus"},
            "build": {"base": "sonnet", "heavy": "opus"},
        }

        phase_config = phase_models.get(phase, {"base": "sonnet", "heavy": "sonnet"})
        return phase_config.get(self.model_set, "sonnet")
```

### 4.3 Data Models

**File**: `src/adw/agent/models.py`

Pydantic models for type-safe data handling:

```python
"""Data models for ADW agent system."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    """Task status markers."""
    PENDING = "[]"
    BLOCKED = "[⏰]"
    IN_PROGRESS = "[🟡]"
    DONE = "[✅]"
    FAILED = "[❌]"


class SystemTag(str, Enum):
    """System-recognized tags."""
    # Models
    OPUS = "opus"
    SONNET = "sonnet"
    HAIKU = "haiku"

    # Workflows
    PLAN = "plan"
    BUILD = "build"
    FULL_SDLC = "full_sdlc"

    # Prototypes
    PROTOTYPE_VITE_VUE = "prototype:vite_vue"
    PROTOTYPE_UV_SCRIPT = "prototype:uv_script"
    PROTOTYPE_BUN = "prototype:bun_scripts"
    PROTOTYPE_MCP = "prototype:uv_mcp"

    # Priority
    PRIORITY_HIGH = "priority:high"
    PRIORITY_LOW = "priority:low"


class Task(BaseModel):
    """Represents a task from tasks.md."""

    id: str | None = None
    description: str
    status: TaskStatus = TaskStatus.PENDING
    adw_id: str | None = None
    commit_hash: str | None = None
    error_message: str | None = None
    tags: list[str] = Field(default_factory=list)
    worktree_name: str | None = None
    line_number: int | None = None  # For updating tasks.md

    @property
    def is_eligible(self) -> bool:
        """Check if task is eligible for pickup."""
        return self.status in (TaskStatus.PENDING, TaskStatus.BLOCKED)

    @property
    def model(self) -> str:
        """Get model from tags, default to sonnet."""
        if "opus" in self.tags:
            return "opus"
        if "haiku" in self.tags:
            return "haiku"
        return "sonnet"

    @property
    def workflow_type(self) -> str:
        """Get workflow type from tags."""
        if "build" in self.tags:
            return "simple"
        if "full_sdlc" in self.tags:
            return "full"
        if any(t.startswith("prototype:") for t in self.tags):
            return "prototype"
        return "standard"

    @property
    def prototype_type(self) -> str | None:
        """Get prototype type if this is a prototype task."""
        for tag in self.tags:
            if tag.startswith("prototype:"):
                return tag.split(":")[1]
        return None


class Worktree(BaseModel):
    """Represents a git worktree section in tasks.md."""

    name: str
    tasks: list[Task] = Field(default_factory=list)

    def get_eligible_tasks(self) -> list[Task]:
        """Get tasks eligible for execution.

        Rules:
        - [] tasks are always eligible
        - [⏰] tasks are eligible only if ALL tasks above are [✅]
        """
        eligible = []

        for i, task in enumerate(self.tasks):
            if task.status == TaskStatus.PENDING:
                eligible.append(task)
            elif task.status == TaskStatus.BLOCKED:
                # Check all tasks above
                tasks_above = self.tasks[:i]
                all_done = all(t.status == TaskStatus.DONE for t in tasks_above)
                if all_done:
                    eligible.append(task)

        return eligible


class WorktreeTaskGroup(BaseModel):
    """Group of eligible tasks for a worktree."""

    worktree_name: str
    tasks: list[Task]


class ProcessTasksResponse(BaseModel):
    """Response from task processing."""

    groups: list[WorktreeTaskGroup] = Field(default_factory=list)
    total_eligible: int = 0

    @property
    def has_work(self) -> bool:
        return self.total_eligible > 0


class WorkflowSummary(BaseModel):
    """Summary of a completed workflow."""

    adw_id: str
    task_description: str
    workflow_type: str
    success: bool
    phases_completed: list[str]
    commit_hash: str | None = None
    error_message: str | None = None
    duration_seconds: float = 0.0
    pr_url: str | None = None
```

### 4.4 Output Directory Structure

Every execution creates organized output:

```
agents/
└── {adw_id}/                           # e.g., abc12345/
    ├── adw_state.json                  # Persistent workflow state
    │
    ├── planner-{adw_id}/               # Planning phase outputs
    │   ├── cc_raw_output.jsonl         # Raw Claude Code stream
    │   ├── cc_raw_output.json          # Parsed messages
    │   ├── cc_final_result.txt         # Extracted result
    │   └── prompts/
    │       └── plan.txt                # Actual prompt sent
    │
    ├── builder-{adw_id}/               # Build phase outputs
    │   ├── cc_raw_output.jsonl
    │   ├── cc_raw_output.json
    │   └── cc_final_result.txt
    │
    ├── tester-{adw_id}/                # Test phase outputs
    │   └── ...
    │
    ├── reviewer-{adw_id}/              # Review phase outputs
    │   ├── ...
    │   └── screenshots/                # Visual verification
    │
    ├── {adw_id}_plan_spec.md           # Generated plan
    └── workflow_summary.json           # Final summary
```

### 4.5 Model Selection Strategy

**File**: `src/adw/agent/model_selector.py`

```python
"""Dynamic model selection for ADW agents."""

from __future__ import annotations

from typing import Literal


# Model selection based on slash command and model set
SLASH_COMMAND_MODEL_MAP: dict[str, dict[str, str]] = {
    # Planning commands - complex reasoning benefits from Opus
    "/plan": {"base": "sonnet", "heavy": "opus"},
    "/discuss": {"base": "sonnet", "heavy": "opus"},
    "/feature": {"base": "sonnet", "heavy": "opus"},
    "/bug": {"base": "sonnet", "heavy": "opus"},
    "/chore": {"base": "sonnet", "heavy": "sonnet"},

    # Implementation - can use Opus for complex code
    "/implement": {"base": "sonnet", "heavy": "opus"},
    "/build": {"base": "sonnet", "heavy": "opus"},

    # Testing - Sonnet is usually sufficient
    "/test": {"base": "sonnet", "heavy": "sonnet"},
    "/resolve_failed_test": {"base": "sonnet", "heavy": "opus"},

    # Review - benefits from deeper reasoning
    "/review": {"base": "sonnet", "heavy": "opus"},
    "/verify": {"base": "sonnet", "heavy": "opus"},

    # Documentation - Opus for comprehensive docs
    "/document": {"base": "sonnet", "heavy": "opus"},

    # Simple operations - Haiku is sufficient
    "/status": {"base": "haiku", "heavy": "haiku"},
    "/update_task": {"base": "haiku", "heavy": "sonnet"},
    "/mark_in_progress": {"base": "haiku", "heavy": "haiku"},

    # Prototypes - complex scaffolding
    "/plan_vite_vue": {"base": "sonnet", "heavy": "opus"},
    "/plan_uv_script": {"base": "sonnet", "heavy": "opus"},
    "/plan_bun_scripts": {"base": "sonnet", "heavy": "opus"},
}


def get_model_for_command(
    slash_command: str,
    model_set: Literal["base", "heavy"] = "base",
    override: str | None = None,
) -> str:
    """Get appropriate model for a slash command.

    Args:
        slash_command: The slash command being executed.
        model_set: Whether to use base or heavy models.
        override: Explicit model override from tags.

    Returns:
        Model name: "haiku", "sonnet", or "opus".
    """
    # Explicit override takes precedence
    if override and override in ("haiku", "sonnet", "opus"):
        return override

    # Look up in command map
    command_config = SLASH_COMMAND_MODEL_MAP.get(
        slash_command,
        {"base": "sonnet", "heavy": "sonnet"}  # Default
    )

    return command_config.get(model_set, "sonnet")


def get_model_from_tags(tags: list[str]) -> str | None:
    """Extract model override from task tags.

    Args:
        tags: List of task tags.

    Returns:
        Model name if specified, None otherwise.
    """
    for tag in tags:
        if tag in ("opus", "sonnet", "haiku"):
            return tag
    return None


def should_use_heavy_model(task_description: str, tags: list[str]) -> bool:
    """Determine if heavy model set should be used.

    Heuristics:
    - Explicit {opus} tag
    - Complex keywords in description
    - Prototype tasks

    Args:
        task_description: The task description.
        tags: Task tags.

    Returns:
        True if heavy model set recommended.
    """
    # Explicit tag
    if "opus" in tags:
        return True

    # Prototype tasks are complex
    if any(t.startswith("prototype:") for t in tags):
        return True

    # Keywords suggesting complexity
    complex_keywords = [
        "architecture", "redesign", "refactor", "migrate",
        "security", "authentication", "authorization",
        "performance", "optimization", "scale",
        "database", "schema", "migration",
        "api design", "system design",
    ]

    description_lower = task_description.lower()
    if any(kw in description_lower for kw in complex_keywords):
        return True

    return False
```

---

## 5. Phase 2: Autonomous Execution

### 5.1 Task Parser

**File**: `src/adw/agent/task_parser.py`

Parse tasks.md into structured data:

```python
"""Parse tasks.md into structured task objects."""

from __future__ import annotations

import re
from pathlib import Path

from .models import Task, TaskStatus, Worktree, ProcessTasksResponse, WorktreeTaskGroup


# Regex patterns for parsing tasks.md
WORKTREE_PATTERN = re.compile(r"^##\s+(?:Git\s+)?Worktree[:\s]+(.+)$", re.IGNORECASE)
TASK_PATTERN = re.compile(
    r"^(\[(?P<status>[^\]]*)\])"  # Status marker
    r"(?:\s*,?\s*(?P<adw_id>[a-f0-9]{8}))?"  # Optional ADW ID
    r"(?:\s*,?\s*(?P<commit>[a-f0-9]{7,40}))?"  # Optional commit hash
    r"\s+"
    r"(?P<description>.+?)"  # Task description
    r"(?:\s*\{(?P<tags>[^}]+)\})?"  # Optional tags
    r"(?:\s*//\s*(?P<error>.+))?"  # Optional error message
    r"\s*$"
)

STATUS_MAP = {
    "": TaskStatus.PENDING,
    "⏰": TaskStatus.BLOCKED,
    "🟡": TaskStatus.IN_PROGRESS,
    "✅": TaskStatus.DONE,
    "❌": TaskStatus.FAILED,
}


def parse_status(status_str: str) -> TaskStatus:
    """Parse status string to TaskStatus enum."""
    # Clean up the status string
    status_clean = status_str.strip().split(",")[0].strip()

    for marker, status in STATUS_MAP.items():
        if marker in status_clean or status_clean == marker:
            return status

    return TaskStatus.PENDING


def parse_tags(tags_str: str | None) -> list[str]:
    """Parse tags from {tag1, tag2} format."""
    if not tags_str:
        return []

    return [t.strip().lower() for t in tags_str.split(",") if t.strip()]


def parse_tasks_md(content: str) -> list[Worktree]:
    """Parse tasks.md content into Worktree objects.

    Args:
        content: Raw content of tasks.md file.

    Returns:
        List of Worktree objects with their tasks.
    """
    worktrees: list[Worktree] = []
    current_worktree: Worktree | None = None

    for line_num, line in enumerate(content.split("\n"), 1):
        line = line.rstrip()

        # Check for worktree header
        worktree_match = WORKTREE_PATTERN.match(line)
        if worktree_match:
            if current_worktree:
                worktrees.append(current_worktree)
            current_worktree = Worktree(name=worktree_match.group(1).strip())
            continue

        # Check for task line
        task_match = TASK_PATTERN.match(line)
        if task_match and current_worktree:
            groups = task_match.groupdict()

            task = Task(
                description=groups["description"].strip(),
                status=parse_status(groups["status"] or ""),
                adw_id=groups.get("adw_id"),
                commit_hash=groups.get("commit"),
                error_message=groups.get("error"),
                tags=parse_tags(groups.get("tags")),
                worktree_name=current_worktree.name,
                line_number=line_num,
            )
            current_worktree.tasks.append(task)

    # Don't forget the last worktree
    if current_worktree:
        worktrees.append(current_worktree)

    return worktrees


def load_tasks(tasks_file: Path | None = None) -> list[Worktree]:
    """Load and parse tasks from tasks.md.

    Args:
        tasks_file: Path to tasks.md. Defaults to ./tasks.md.

    Returns:
        List of parsed Worktree objects.
    """
    if tasks_file is None:
        tasks_file = Path("tasks.md")

    if not tasks_file.exists():
        return []

    content = tasks_file.read_text()
    return parse_tasks_md(content)


def get_eligible_tasks(tasks_file: Path | None = None) -> ProcessTasksResponse:
    """Get all tasks eligible for execution.

    Args:
        tasks_file: Path to tasks.md.

    Returns:
        ProcessTasksResponse with eligible task groups.
    """
    worktrees = load_tasks(tasks_file)

    groups: list[WorktreeTaskGroup] = []
    total = 0

    for worktree in worktrees:
        eligible = worktree.get_eligible_tasks()
        if eligible:
            groups.append(WorktreeTaskGroup(
                worktree_name=worktree.name,
                tasks=eligible,
            ))
            total += len(eligible)

    return ProcessTasksResponse(groups=groups, total_eligible=total)


def has_pending_tasks(tasks_file: Path | None = None) -> bool:
    """Quick check if there are any pending tasks.

    More efficient than full parsing for cron checks.

    Args:
        tasks_file: Path to tasks.md.

    Returns:
        True if pending tasks exist.
    """
    if tasks_file is None:
        tasks_file = Path("tasks.md")

    if not tasks_file.exists():
        return False

    content = tasks_file.read_text()

    # Quick regex check for pending markers
    return bool(re.search(r"\[\s*\]|\[⏰\]", content))
```

### 5.2 Task Updater

**File**: `src/adw/agent/task_updater.py`

Atomically update task status in tasks.md:

```python
"""Atomic task status updates for tasks.md."""

from __future__ import annotations

import re
from pathlib import Path

from .models import TaskStatus


def update_task_status(
    tasks_file: Path,
    task_description: str,
    new_status: TaskStatus,
    adw_id: str | None = None,
    commit_hash: str | None = None,
    error_message: str | None = None,
) -> bool:
    """Update a task's status in tasks.md.

    Args:
        tasks_file: Path to tasks.md.
        task_description: Task description to find.
        new_status: New status to set.
        adw_id: ADW ID to record.
        commit_hash: Commit hash for completed tasks.
        error_message: Error message for failed tasks.

    Returns:
        True if task was found and updated.
    """
    if not tasks_file.exists():
        return False

    content = tasks_file.read_text()
    lines = content.split("\n")
    updated = False

    # Escape description for regex
    desc_escaped = re.escape(task_description.strip())

    for i, line in enumerate(lines):
        # Check if this line contains the task
        if not re.search(rf"\]\s*.*{desc_escaped}", line, re.IGNORECASE):
            continue

        # Build new status marker
        if new_status == TaskStatus.PENDING:
            status_marker = "[]"
        elif new_status == TaskStatus.BLOCKED:
            status_marker = "[⏰]"
        elif new_status == TaskStatus.IN_PROGRESS:
            status_marker = f"[🟡, {adw_id}]" if adw_id else "[🟡]"
        elif new_status == TaskStatus.DONE:
            parts = ["✅"]
            if commit_hash:
                parts.append(commit_hash[:9])
            if adw_id:
                parts.append(adw_id)
            status_marker = f"[{', '.join(parts)}]"
        elif new_status == TaskStatus.FAILED:
            status_marker = f"[❌, {adw_id}]" if adw_id else "[❌]"
        else:
            continue

        # Extract tags from original line
        tags_match = re.search(r"\{([^}]+)\}", line)
        tags = f" {{{tags_match.group(1)}}}" if tags_match else ""

        # Build new line
        new_line = f"{status_marker} {task_description.strip()}{tags}"

        # Add error message for failed tasks
        if new_status == TaskStatus.FAILED and error_message:
            new_line += f" // Failed: {error_message}"

        lines[i] = new_line
        updated = True
        break

    if updated:
        tasks_file.write_text("\n".join(lines))

    return updated


def mark_task_in_progress(
    tasks_file: Path,
    task_description: str,
    adw_id: str,
) -> bool:
    """Mark a task as in-progress with ADW ID.

    This should be called immediately when picking up a task
    to prevent duplicate execution.

    Args:
        tasks_file: Path to tasks.md.
        task_description: Task to mark.
        adw_id: ADW ID for this execution.

    Returns:
        True if successfully marked.
    """
    return update_task_status(
        tasks_file=tasks_file,
        task_description=task_description,
        new_status=TaskStatus.IN_PROGRESS,
        adw_id=adw_id,
    )


def mark_task_done(
    tasks_file: Path,
    task_description: str,
    adw_id: str,
    commit_hash: str | None = None,
) -> bool:
    """Mark a task as completed.

    Args:
        tasks_file: Path to tasks.md.
        task_description: Task to mark.
        adw_id: ADW ID of this execution.
        commit_hash: Git commit hash of changes.

    Returns:
        True if successfully marked.
    """
    return update_task_status(
        tasks_file=tasks_file,
        task_description=task_description,
        new_status=TaskStatus.DONE,
        adw_id=adw_id,
        commit_hash=commit_hash,
    )


def mark_task_failed(
    tasks_file: Path,
    task_description: str,
    adw_id: str,
    error_message: str,
) -> bool:
    """Mark a task as failed with error message.

    Args:
        tasks_file: Path to tasks.md.
        task_description: Task to mark.
        adw_id: ADW ID of this execution.
        error_message: Why the task failed.

    Returns:
        True if successfully marked.
    """
    return update_task_status(
        tasks_file=tasks_file,
        task_description=task_description,
        new_status=TaskStatus.FAILED,
        adw_id=adw_id,
        error_message=error_message,
    )
```

### 5.3 Cron Trigger

**File**: `src/adw/triggers/cron.py`

The autonomous monitoring daemon:

```python
"""Autonomous task monitoring and execution trigger."""

from __future__ import annotations

import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

from ..agent.executor import generate_adw_id
from ..agent.task_parser import get_eligible_tasks, has_pending_tasks
from ..agent.task_updater import mark_task_in_progress
from ..agent.models import Task


console = Console()


@dataclass
class CronConfig:
    """Configuration for cron trigger."""

    # Timing
    polling_interval: int = 5  # seconds between checks
    max_runtime: int | None = None  # None = run forever

    # Limits
    max_concurrent_tasks: int = 5
    max_tasks_per_cycle: int = 3

    # Paths
    tasks_file: Path = field(default_factory=lambda: Path("tasks.md"))
    worktree_base: Path = field(default_factory=lambda: Path("trees"))

    # Behavior
    dry_run: bool = False
    verbose: bool = True

    # Workflow scripts
    simple_workflow: str = "adw_build_update.py"
    standard_workflow: str = "adw_plan_implement_update.py"
    full_workflow: str = "adw_sdlc.py"
    prototype_workflow: str = "adw_prototype.py"


@dataclass
class CronStats:
    """Statistics for cron execution."""

    cycles: int = 0
    tasks_started: int = 0
    tasks_completed: int = 0
    tasks_failed: int = 0
    errors: int = 0


class CronTrigger:
    """Autonomous task monitoring and execution trigger.

    Continuously monitors tasks.md and delegates eligible tasks
    to workflow agents.
    """

    def __init__(self, config: CronConfig | None = None):
        self.config = config or CronConfig()
        self.stats = CronStats()
        self._active_tasks: dict[str, subprocess.Popen] = {}
        self._running = False

    def run_once(self) -> int:
        """Run a single monitoring cycle.

        Returns:
            Number of tasks started this cycle.
        """
        self.stats.cycles += 1
        tasks_started = 0

        # Quick check for pending tasks
        if not has_pending_tasks(self.config.tasks_file):
            if self.config.verbose:
                console.print("[dim]No pending tasks[/dim]")
            return 0

        # Get eligible tasks
        response = get_eligible_tasks(self.config.tasks_file)

        if not response.has_work:
            if self.config.verbose:
                console.print("[dim]No eligible tasks (may be blocked)[/dim]")
            return 0

        if self.config.verbose:
            console.print(f"[cyan]Found {response.total_eligible} eligible task(s)[/cyan]")

        # Process each worktree group
        for group in response.groups:
            for task in group.tasks:
                # Check concurrent limit
                self._cleanup_completed_tasks()
                if len(self._active_tasks) >= self.config.max_concurrent_tasks:
                    console.print("[yellow]Max concurrent tasks reached[/yellow]")
                    return tasks_started

                # Check per-cycle limit
                if tasks_started >= self.config.max_tasks_per_cycle:
                    console.print("[yellow]Max tasks per cycle reached[/yellow]")
                    return tasks_started

                # Delegate the task
                if self._delegate_task(task, group.worktree_name):
                    tasks_started += 1
                    self.stats.tasks_started += 1

        return tasks_started

    def run_continuous(self) -> None:
        """Run continuous monitoring loop."""
        self._running = True
        start_time = time.time()

        console.print(Panel(
            f"[bold green]ADW Cron Trigger Started[/bold green]\n\n"
            f"Polling interval: {self.config.polling_interval}s\n"
            f"Max concurrent: {self.config.max_concurrent_tasks}\n"
            f"Tasks file: {self.config.tasks_file}",
            title="[bold]Autonomous Mode[/bold]"
        ))

        try:
            while self._running:
                # Check max runtime
                if self.config.max_runtime:
                    elapsed = time.time() - start_time
                    if elapsed >= self.config.max_runtime:
                        console.print("[yellow]Max runtime reached[/yellow]")
                        break

                try:
                    self.run_once()
                except Exception as e:
                    self.stats.errors += 1
                    console.print(f"[red]Error in cycle: {e}[/red]")

                time.sleep(self.config.polling_interval)

        except KeyboardInterrupt:
            console.print("\n[yellow]Shutting down...[/yellow]")

        finally:
            self._running = False
            self._print_stats()

    def stop(self) -> None:
        """Stop the continuous monitoring loop."""
        self._running = False

    def _delegate_task(self, task: Task, worktree_name: str) -> bool:
        """Delegate a task to a workflow agent.

        Args:
            task: The task to execute.
            worktree_name: Name of the worktree.

        Returns:
            True if successfully delegated.
        """
        adw_id = generate_adw_id()

        # Mark task as in-progress IMMEDIATELY
        # This prevents duplicate pickup on next cycle
        if not mark_task_in_progress(
            self.config.tasks_file,
            task.description,
            adw_id,
        ):
            console.print(f"[red]Failed to mark task in-progress: {task.description[:50]}[/red]")
            return False

        # Determine workflow script
        workflow_script = self._get_workflow_script(task)

        # Build command
        cmd = [
            sys.executable,
            workflow_script,
            "--adw-id", adw_id,
            "--worktree-name", worktree_name,
            "--task", task.description,
            "--model", task.model,
        ]

        if task.prototype_type:
            cmd.extend(["--prototype", task.prototype_type])

        if self.config.dry_run:
            console.print(Panel(
                f"[yellow]DRY RUN[/yellow]\n"
                f"Would execute: {' '.join(cmd)}",
                title=f"Task: {task.description[:50]}..."
            ))
            return True

        # Spawn subprocess (non-blocking)
        try:
            # Use start_new_session so the process survives if parent dies
            process = subprocess.Popen(
                cmd,
                start_new_session=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self._active_tasks[adw_id] = process

            console.print(Panel(
                f"[green]Delegated[/green]\n"
                f"ADW ID: {adw_id}\n"
                f"Worktree: {worktree_name}\n"
                f"Model: {task.model}\n"
                f"Workflow: {workflow_script}",
                title=f"Task: {task.description[:50]}..."
            ))

            return True

        except Exception as e:
            console.print(f"[red]Failed to spawn workflow: {e}[/red]")
            self.stats.errors += 1
            return False

    def _get_workflow_script(self, task: Task) -> str:
        """Get the appropriate workflow script for a task."""
        workflow_type = task.workflow_type

        if workflow_type == "simple":
            return self.config.simple_workflow
        elif workflow_type == "full":
            return self.config.full_workflow
        elif workflow_type == "prototype":
            return self.config.prototype_workflow
        else:
            return self.config.standard_workflow

    def _cleanup_completed_tasks(self) -> None:
        """Remove completed tasks from active tracking."""
        completed = []

        for adw_id, process in self._active_tasks.items():
            if process.poll() is not None:
                completed.append(adw_id)

                if process.returncode == 0:
                    self.stats.tasks_completed += 1
                else:
                    self.stats.tasks_failed += 1

        for adw_id in completed:
            del self._active_tasks[adw_id]

    def _print_stats(self) -> None:
        """Print execution statistics."""
        console.print(Panel(
            f"Cycles: {self.stats.cycles}\n"
            f"Tasks started: {self.stats.tasks_started}\n"
            f"Tasks completed: {self.stats.tasks_completed}\n"
            f"Tasks failed: {self.stats.tasks_failed}\n"
            f"Errors: {self.stats.errors}",
            title="[bold]Cron Statistics[/bold]"
        ))


def run_cron(
    polling_interval: int = 5,
    max_concurrent: int = 5,
    dry_run: bool = False,
) -> None:
    """Start the cron trigger.

    Args:
        polling_interval: Seconds between checks.
        max_concurrent: Max simultaneous tasks.
        dry_run: If True, don't actually execute.
    """
    config = CronConfig(
        polling_interval=polling_interval,
        max_concurrent_tasks=max_concurrent,
        dry_run=dry_run,
    )

    trigger = CronTrigger(config)
    trigger.run_continuous()
```

### 5.4 Workflow Orchestrators

**File**: `src/adw/workflows/standard.py`

Standard Plan → Implement → Update workflow:

```python
"""Standard workflow: Plan → Implement → Update."""

from __future__ import annotations

import sys
import time
from pathlib import Path

import click
from rich.console import Console

from ..agent.executor import (
    AgentTemplateRequest,
    execute_template,
    generate_adw_id,
)
from ..agent.state import ADWState
from ..agent.task_updater import mark_task_done, mark_task_failed
from ..agent.worktree import create_worktree, get_worktree_path


console = Console()


def run_standard_workflow(
    task_description: str,
    worktree_name: str,
    adw_id: str | None = None,
    model: str = "sonnet",
    working_dir: str | None = None,
) -> bool:
    """Execute standard plan-implement-update workflow.

    Args:
        task_description: What to implement.
        worktree_name: Git worktree name.
        adw_id: Execution ID (generated if not provided).
        model: Model to use.
        working_dir: Override working directory.

    Returns:
        True if workflow succeeded.
    """
    start_time = time.time()
    adw_id = adw_id or generate_adw_id()

    # Initialize state
    state = ADWState.create(
        adw_id=adw_id,
        task_description=task_description,
        worktree_name=worktree_name,
        workflow_type="standard",
    )

    # Determine working directory
    if working_dir:
        work_dir = working_dir
    else:
        worktree_path = get_worktree_path(worktree_name)
        if worktree_path and worktree_path.exists():
            work_dir = str(worktree_path)
        else:
            work_dir = None

    state.worktree_path = work_dir
    state.save("init")

    console.print(f"[bold cyan]Starting workflow {adw_id}[/bold cyan]")
    console.print(f"Task: {task_description[:60]}...")
    console.print(f"Worktree: {worktree_name}")

    success = True
    commit_hash = None
    error_message = None

    try:
        # Phase 1: Plan
        console.print("\n[bold]Phase 1: Planning[/bold]")
        state.save("plan")

        plan_response = execute_template(AgentTemplateRequest(
            slash_command="/plan",
            args=[adw_id, task_description],
            adw_id=adw_id,
            agent_name=f"planner-{adw_id}",
            model=state.get_model_for_phase("plan"),
            working_dir=work_dir,
        ))

        if not plan_response.success:
            raise Exception(f"Planning failed: {plan_response.error_message}")

        # Extract plan file path from response
        plan_file = _extract_plan_path(plan_response.output, adw_id)
        state.plan_file = plan_file
        state.save("plan")

        console.print(f"[green]✓ Plan created: {plan_file}[/green]")

        # Phase 2: Implement
        console.print("\n[bold]Phase 2: Implementing[/bold]")
        state.save("implement")

        implement_response = execute_template(AgentTemplateRequest(
            slash_command="/implement",
            args=[plan_file] if plan_file else [task_description],
            adw_id=adw_id,
            agent_name=f"builder-{adw_id}",
            model=state.get_model_for_phase("implement"),
            working_dir=work_dir,
        ))

        if not implement_response.success:
            raise Exception(f"Implementation failed: {implement_response.error_message}")

        # Get commit hash
        commit_hash = _get_commit_hash(work_dir)
        state.commit_hash = commit_hash
        state.save("implement")

        console.print(f"[green]✓ Implementation complete[/green]")
        if commit_hash:
            console.print(f"  Commit: {commit_hash[:9]}")

    except Exception as e:
        success = False
        error_message = str(e)
        state.add_error(state.current_phase, error_message)
        console.print(f"[red]✗ Error: {error_message}[/red]")

    # Phase 3: Update task status
    console.print("\n[bold]Phase 3: Updating task status[/bold]")
    tasks_file = Path("tasks.md")

    if success:
        mark_task_done(tasks_file, task_description, adw_id, commit_hash)
        console.print("[green]✓ Task marked as done[/green]")
    else:
        mark_task_failed(tasks_file, task_description, adw_id, error_message or "Unknown error")
        console.print("[red]✗ Task marked as failed[/red]")

    # Save final state
    duration = time.time() - start_time
    state.save("complete" if success else "failed")

    # Write workflow summary
    _write_workflow_summary(state, success, duration, error_message)

    console.print(f"\n[bold]Workflow {'succeeded' if success else 'failed'}[/bold]")
    console.print(f"Duration: {duration:.1f}s")
    console.print(f"ADW ID: {adw_id}")

    return success


def _extract_plan_path(output: str, adw_id: str) -> str | None:
    """Extract plan file path from planner output."""
    import re

    # Look for spec file path
    patterns = [
        rf"specs/[a-z0-9-]+{adw_id}[a-z0-9-]*\.md",
        rf"agents/{adw_id}/[a-z0-9_]+_plan_spec\.md",
        r"specs/[a-z0-9-]+\.md",
    ]

    for pattern in patterns:
        match = re.search(pattern, output, re.IGNORECASE)
        if match:
            return match.group(0)

    return None


def _get_commit_hash(working_dir: str | None) -> str | None:
    """Get current git commit hash."""
    import subprocess

    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=working_dir,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass

    return None


def _write_workflow_summary(
    state: ADWState,
    success: bool,
    duration: float,
    error_message: str | None,
) -> None:
    """Write workflow summary JSON."""
    import json

    summary = {
        "adw_id": state.adw_id,
        "task_description": state.task_description,
        "workflow_type": state.workflow_type,
        "success": success,
        "phases_completed": state.phases_completed,
        "commit_hash": state.commit_hash,
        "error_message": error_message,
        "duration_seconds": duration,
    }

    summary_path = Path("agents") / state.adw_id / "workflow_summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2))


@click.command()
@click.option("--adw-id", help="Execution ID")
@click.option("--worktree-name", required=True, help="Git worktree name")
@click.option("--task", required=True, help="Task description")
@click.option("--model", default="sonnet", help="Model to use")
def main(adw_id: str | None, worktree_name: str, task: str, model: str):
    """Run standard workflow from CLI."""
    success = run_standard_workflow(
        task_description=task,
        worktree_name=worktree_name,
        adw_id=adw_id,
        model=model,
    )
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
```

---

## 6. Phase 3: Parallel Isolation

### 6.1 Worktree Manager

**File**: `src/adw/agent/worktree.py`

Git worktree management for isolated parallel execution:

```python
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


def cleanup_old_worktrees(max_age_days: int = 7) -> int:
    """Remove worktrees older than specified age.

    Args:
        max_age_days: Maximum age in days.

    Returns:
        Number of worktrees removed.
    """
    import time

    base = get_worktree_base()
    if not base.exists():
        return 0

    removed = 0
    max_age_seconds = max_age_days * 24 * 60 * 60
    now = time.time()

    for item in base.iterdir():
        if not item.is_dir():
            continue

        try:
            mtime = item.stat().st_mtime
            age = now - mtime

            if age > max_age_seconds:
                if remove_worktree(item.name, force=True):
                    removed += 1

        except Exception:
            continue

    if removed:
        console.print(f"[green]Cleaned up {removed} old worktree(s)[/green]")

    return removed
```

### 6.2 Port Allocation

**File**: `src/adw/agent/ports.py`

Deterministic port allocation for parallel app instances:

```python
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
```

### 6.3 Environment Isolation

**File**: `src/adw/agent/environment.py`

```python
"""Environment isolation for ADW agents."""

from __future__ import annotations

import os
from pathlib import Path


# Essential environment variables to pass to agents
SAFE_ENV_VARS = [
    # API Keys (required)
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",

    # Optional API keys
    "GITHUB_TOKEN",
    "REPLICATE_API_TOKEN",
    "ELEVENLABS_API_KEY",

    # System essentials
    "HOME",
    "USER",
    "PATH",
    "SHELL",
    "TERM",
    "LANG",
    "LC_ALL",

    # Python
    "PYTHONUNBUFFERED",
    "VIRTUAL_ENV",

    # Node
    "NODE_ENV",
    "NPM_CONFIG_PREFIX",

    # Git
    "GIT_AUTHOR_NAME",
    "GIT_AUTHOR_EMAIL",
    "GIT_COMMITTER_NAME",
    "GIT_COMMITTER_EMAIL",
]


def get_safe_env() -> dict[str, str]:
    """Get filtered environment for subprocess execution.

    Returns:
        Dictionary of safe environment variables.
    """
    env = {}

    for var in SAFE_ENV_VARS:
        value = os.environ.get(var)
        if value:
            env[var] = value

    # Always set this for real-time output
    env["PYTHONUNBUFFERED"] = "1"

    return env


def get_worktree_env(worktree_path: str | Path) -> dict[str, str]:
    """Get environment for a specific worktree.

    Loads .env and .ports.env from worktree.

    Args:
        worktree_path: Path to the worktree.

    Returns:
        Combined environment dictionary.
    """
    env = get_safe_env()
    worktree = Path(worktree_path)

    # Load .env if exists
    env_file = worktree / ".env"
    if env_file.exists():
        env.update(_parse_env_file(env_file))

    # Load .ports.env if exists
    ports_file = worktree / ".ports.env"
    if ports_file.exists():
        env.update(_parse_env_file(ports_file))

    # Set working directory hint
    env["ADW_WORKTREE"] = str(worktree)

    return env


def _parse_env_file(path: Path) -> dict[str, str]:
    """Parse a .env file into a dictionary."""
    env = {}

    for line in path.read_text().split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        if "=" in line:
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            env[key] = value

    return env
```

---

## 7. Phase 4: Observability & Context

### 7.1 Hook System

**File**: `.claude/settings.json`

Claude Code hooks for observability:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": ".*",
        "command": "uv run $CLAUDE_PROJECT_DIR/.claude/hooks/pre_tool_use.py"
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Read|Write|Edit",
        "command": "uv run $CLAUDE_PROJECT_DIR/.claude/hooks/context_bundle_builder.py"
      },
      {
        "matcher": ".*",
        "command": "uv run $CLAUDE_PROJECT_DIR/.claude/hooks/post_tool_use.py"
      }
    ],
    "UserPromptSubmit": [
      {
        "command": "uv run $CLAUDE_PROJECT_DIR/.claude/hooks/log_prompt.py"
      }
    ],
    "Stop": [
      {
        "command": "uv run $CLAUDE_PROJECT_DIR/.claude/hooks/session_complete.py"
      }
    ],
    "Notification": [
      {
        "command": "uv run $CLAUDE_PROJECT_DIR/.claude/hooks/notification_handler.py"
      }
    ]
  }
}
```

### 7.2 Context Bundle Builder Hook

**File**: `.claude/hooks/context_bundle_builder.py`

Track file operations for context restoration:

```python
#!/usr/bin/env uv run
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Track file operations into context bundles for session restoration."""

import json
import os
import sys
from datetime import datetime
from pathlib import Path


def get_bundle_path() -> Path:
    """Get path to current session's context bundle."""
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
    session_id = os.environ.get("CLAUDE_SESSION_ID", "unknown")

    # Create bundle directory
    bundle_dir = Path(project_dir) / ".claude" / "agents" / "context_bundles"
    bundle_dir.mkdir(parents=True, exist_ok=True)

    # Use date + session for filename
    date_str = datetime.now().strftime("%Y%m%d_%H")
    return bundle_dir / f"{date_str}_{session_id[:8]}.jsonl"


def main():
    # Read hook input from stdin
    try:
        hook_input = json.loads(sys.stdin.read())
    except json.JSONDecodeError:
        sys.exit(0)  # Silent fail - don't disrupt Claude

    tool_name = hook_input.get("tool_name", "")
    tool_input = hook_input.get("tool_input", {})
    tool_result = hook_input.get("tool_result", {})

    # Only track file operations
    if tool_name not in ("Read", "Write", "Edit"):
        sys.exit(0)

    # Build context entry
    entry = {
        "timestamp": datetime.now().isoformat(),
        "session_id": os.environ.get("CLAUDE_SESSION_ID", "unknown"),
        "tool": tool_name,
    }

    if tool_name == "Read":
        entry["file_path"] = tool_input.get("file_path")
        entry["offset"] = tool_input.get("offset")
        entry["limit"] = tool_input.get("limit")
    elif tool_name == "Write":
        entry["file_path"] = tool_input.get("file_path")
        entry["content_length"] = len(tool_input.get("content", ""))
    elif tool_name == "Edit":
        entry["file_path"] = tool_input.get("file_path")
        entry["old_string_length"] = len(tool_input.get("old_string", ""))
        entry["new_string_length"] = len(tool_input.get("new_string", ""))

    # Append to bundle
    bundle_path = get_bundle_path()
    with open(bundle_path, "a") as f:
        f.write(json.dumps(entry) + "\n")

    sys.exit(0)


if __name__ == "__main__":
    main()
```

### 7.3 Universal Hook Logger

**File**: `.claude/hooks/universal_logger.py`

Log all hook events for debugging and analysis:

```python
#!/usr/bin/env uv run
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Universal hook logger for debugging and analysis."""

import json
import os
import sys
from datetime import datetime
from pathlib import Path


def get_log_path() -> Path:
    """Get path to hook log file."""
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
    session_id = os.environ.get("CLAUDE_SESSION_ID", "unknown")

    log_dir = Path(project_dir) / ".claude" / "agents" / "hook_logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    date_str = datetime.now().strftime("%Y%m%d")
    return log_dir / f"{date_str}_{session_id[:8]}.jsonl"


def main():
    hook_name = os.environ.get("CLAUDE_HOOK_NAME", "unknown")

    try:
        hook_input = json.loads(sys.stdin.read())
    except json.JSONDecodeError:
        hook_input = {}

    entry = {
        "timestamp": datetime.now().isoformat(),
        "hook": hook_name,
        "session_id": os.environ.get("CLAUDE_SESSION_ID"),
        "tool_name": hook_input.get("tool_name"),
        "tool_input_keys": list(hook_input.get("tool_input", {}).keys()),
    }

    log_path = get_log_path()
    with open(log_path, "a") as f:
        f.write(json.dumps(entry) + "\n")

    sys.exit(0)


if __name__ == "__main__":
    main()
```

### 7.4 Context Bundle Loader Command

**File**: `.claude/commands/load_bundle.md`

Restore context from previous session:

```markdown
# /load_bundle - Restore context from previous session

Load file context from a previous agent session to continue work.

## Input

$ARGUMENTS - Bundle file path or session ID

## Process

1. **Locate bundle file**
   - If full path provided, use directly
   - If session ID provided, find in `.claude/agents/context_bundles/`
   - If nothing provided, use most recent bundle

2. **Parse bundle**
   - Read JSONL file line by line
   - Extract unique file paths
   - Deduplicate reads (keep most specific: with offset/limit if available)

3. **Load context**
   - For each unique file path:
     - Read the file with original parameters
     - This populates context with the same information

4. **Report**
   - List files loaded
   - Note any files that no longer exist
   - Confirm context restoration

## Output

Context restored with same file knowledge as previous session.

## Example

```
/load_bundle abc12345
```

Loads context from session starting with abc12345.
```

### 7.5 Output Styles

**File**: `.claude/output-styles/concise-done.md`

Token-efficient output style:

```markdown
# Output Style: Concise Done

Minimize output tokens. Respond with just "Done" for most operations.

## Rules

1. **Successful operations**: Respond with "Done"
2. **Operations with output**: Show only the essential result
3. **Errors**: Brief error message only
4. **Questions**: Answer directly, no preamble

## Examples

### File created
```
Done
```

### Code executed successfully
```
Done
```

### Query answered
```
The function is defined at line 42.
```

### Error occurred
```
Error: File not found
```

## When NOT to use

- When user explicitly asks for explanation
- When debugging and details are needed
- When creating documentation
```

**File**: `.claude/output-styles/concise-ultra.md`

Maximum token efficiency:

```markdown
# Output Style: Ultra Concise

Maximum token efficiency. Fragments over sentences.

## Rules

1. No articles (a, an, the)
2. No filler words
3. Fragments OK
4. Lists > prose
5. Symbols > words (✓, ✗, →)

## Examples

### Status update
```
✓ tests passing
✓ lint clean
→ ready for review
```

### Error
```
✗ build failed: missing dep
```

### Answer
```
Line 42, `processUser` fn
```
```

### 7.6 Dynamic Priming Commands

**File**: `.claude/commands/prime.md`

Dynamic context priming instead of bloated CLAUDE.md:

```markdown
# /prime - Prime context for current codebase

Load essential context for working in this codebase.

## Process

1. **Core files**
   - Read CLAUDE.md (if exists, stop at 200 lines)
   - Read README.md (first 100 lines)
   - Read package.json or pyproject.toml

2. **Structure**
   - Run `git ls-files` to understand structure
   - Note key directories

3. **Recent activity**
   - Run `git log --oneline -10` for recent context

4. **Report**
   - Summarize project type and stack
   - Note key patterns observed
   - Confirm ready to work

## Output

Brief summary of codebase understanding.

## Usage

Run at start of session or after context gets stale.

```
/prime
```
```

**File**: `.claude/commands/prime_feature.md`

Feature-specific priming:

```markdown
# /prime_feature - Prime context for feature work

Load context specific to implementing a feature.

## Input

$ARGUMENTS - Feature name or description

## Process

1. **Run base prime**
   - Execute /prime workflow

2. **Feature-specific context**
   - Search for related files: `git grep -l "$ARGUMENTS"`
   - Read spec if exists: `specs/*$ARGUMENTS*.md`
   - Find related tests

3. **Dependencies**
   - Identify imports/dependencies in related files
   - Note patterns used

4. **Report**
   - List relevant files found
   - Summarize patterns to follow
   - Note any existing related code

## Output

Context primed for feature: $ARGUMENTS
```

### 7.7 R&D Context Engineering Principles

From `elite-context-engineering`, follow R&D (Reduce & Delegate):

#### Reduce Strategies

1. **Measure to Manage**
   - Use `/context` command regularly
   - Track token usage across phases
   - Identify context bloat early

2. **Avoid MCP Server Overhead**
   - MCP servers consume context on startup
   - Use project-scoped MCP configs
   - Only enable needed servers

3. **Dynamic Priming over Static**
   - Small CLAUDE.md with essentials only
   - Use `/prime_*` commands for specific contexts
   - Load docs on-demand from `ai_docs/`

4. **Control Output Tokens**
   - Output tokens cost 3-5x input tokens
   - Use concise output styles
   - Minimize verbose responses

#### Delegate Strategies

1. **Use Sub-Agents Properly**
   - Sub-agent system prompts are isolated
   - They respond to primary agent, not user
   - Use for parallel independent work

2. **Architect-Editor Pattern**
   - Separate planning from implementation
   - Planner agent designs
   - Builder agent executes

3. **One Agent, One Purpose**
   - Ship one thing at a time
   - Don't overload single agent
   - Chain focused agents

4. **Reset Over Compact**
   - `/compact` often loses important context
   - Better to reset and re-prime
   - Use context bundles for restoration

---

## 8. Phase 5: Advanced Workflows

### 8.1 Full SDLC Workflow

**File**: `src/adw/workflows/sdlc.py`

Complete software development lifecycle:

```python
"""Full SDLC workflow: Plan → Build → Test → Review → Document → Ship."""

from __future__ import annotations

import sys
import time
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel

from ..agent.executor import AgentTemplateRequest, execute_template, generate_adw_id
from ..agent.state import ADWState
from ..agent.worktree import create_worktree, get_worktree_path
from ..agent.task_updater import mark_task_done, mark_task_failed


console = Console()


SDLC_PHASES = [
    ("plan", "/plan", "Creating implementation plan"),
    ("implement", "/implement", "Implementing solution"),
    ("test", "/test", "Running tests"),
    ("review", "/review", "Reviewing implementation"),
    ("document", "/document", "Generating documentation"),
]


def run_sdlc_workflow(
    task_description: str,
    worktree_name: str,
    adw_id: str | None = None,
    model_set: str = "base",
    skip_phases: list[str] | None = None,
    auto_ship: bool = False,
) -> bool:
    """Execute full SDLC workflow.

    Args:
        task_description: What to implement.
        worktree_name: Git worktree name.
        adw_id: Execution ID.
        model_set: "base" or "heavy" model selection.
        skip_phases: Phases to skip.
        auto_ship: If True, auto-merge on success.

    Returns:
        True if workflow succeeded.
    """
    start_time = time.time()
    adw_id = adw_id or generate_adw_id()
    skip_phases = skip_phases or []

    # Initialize state
    state = ADWState.create(
        adw_id=adw_id,
        task_description=task_description,
        worktree_name=worktree_name,
        workflow_type="full",
        model_set=model_set,
    )

    # Ensure worktree exists
    worktree_path = get_worktree_path(worktree_name)
    if not worktree_path or not worktree_path.exists():
        worktree_path = create_worktree(worktree_name)
        if not worktree_path:
            console.print("[red]Failed to create worktree[/red]")
            return False

    state.worktree_path = str(worktree_path)
    state.save("init")

    console.print(Panel(
        f"[bold]Task:[/bold] {task_description}\n"
        f"[bold]ADW ID:[/bold] {adw_id}\n"
        f"[bold]Worktree:[/bold] {worktree_name}\n"
        f"[bold]Model Set:[/bold] {model_set}",
        title="[bold cyan]SDLC Workflow Started[/bold cyan]"
    ))

    success = True
    error_message = None
    plan_file = None
    commit_hash = None

    # Execute each phase
    for phase_name, slash_command, description in SDLC_PHASES:
        if phase_name in skip_phases:
            console.print(f"[yellow]Skipping {phase_name}[/yellow]")
            continue

        console.print(f"\n[bold]Phase: {phase_name.upper()}[/bold] - {description}")
        state.save(phase_name)

        try:
            # Build args based on phase
            if phase_name == "plan":
                args = [adw_id, task_description]
            elif phase_name == "implement" and plan_file:
                args = [plan_file]
            elif phase_name == "implement":
                args = [task_description]
            else:
                args = [adw_id]

            # Execute phase
            response = execute_template(AgentTemplateRequest(
                slash_command=slash_command,
                args=args,
                adw_id=adw_id,
                agent_name=f"{phase_name}-{adw_id}",
                model=state.get_model_for_phase(phase_name),
                working_dir=str(worktree_path),
            ))

            if not response.success:
                # Some phases can fail gracefully
                if phase_name in ("test", "review"):
                    console.print(f"[yellow]⚠ {phase_name} had issues but continuing[/yellow]")
                    state.add_error(phase_name, response.error_message or "Unknown", recoverable=True)
                else:
                    raise Exception(f"{phase_name} failed: {response.error_message}")

            # Extract artifacts
            if phase_name == "plan":
                plan_file = _extract_plan_path(response.output, adw_id)
                state.plan_file = plan_file
                console.print(f"  [green]✓ Plan: {plan_file}[/green]")

            elif phase_name == "implement":
                commit_hash = _get_commit_hash(str(worktree_path))
                state.commit_hash = commit_hash
                console.print(f"  [green]✓ Commit: {commit_hash[:9] if commit_hash else 'none'}[/green]")

            else:
                console.print(f"  [green]✓ Complete[/green]")

            state.save(phase_name)

        except Exception as e:
            success = False
            error_message = str(e)
            state.add_error(phase_name, error_message, recoverable=False)
            console.print(f"  [red]✗ Error: {error_message}[/red]")
            break

    # Ship phase (create PR)
    if success and auto_ship:
        console.print("\n[bold]Phase: SHIP[/bold] - Creating pull request")
        try:
            pr_url = _create_pull_request(state, worktree_path)
            state.save("ship")
            console.print(f"  [green]✓ PR created: {pr_url}[/green]")
        except Exception as e:
            console.print(f"  [yellow]⚠ PR creation failed: {e}[/yellow]")

    # Update task status
    tasks_file = Path("tasks.md")
    if success:
        mark_task_done(tasks_file, task_description, adw_id, commit_hash)
    else:
        mark_task_failed(tasks_file, task_description, adw_id, error_message or "Unknown")

    # Final summary
    duration = time.time() - start_time
    state.save("complete" if success else "failed")

    console.print(Panel(
        f"[bold]Status:[/bold] {'✓ Success' if success else '✗ Failed'}\n"
        f"[bold]Duration:[/bold] {duration:.1f}s\n"
        f"[bold]Phases:[/bold] {', '.join(state.phases_completed)}\n"
        f"[bold]Commit:[/bold] {commit_hash[:9] if commit_hash else 'none'}",
        title=f"[bold {'green' if success else 'red'}]Workflow Complete[/bold]"
    ))

    return success


def _extract_plan_path(output: str, adw_id: str) -> str | None:
    """Extract plan file path from output."""
    import re
    patterns = [
        rf"specs/[a-z0-9-]*{adw_id}[a-z0-9-]*\.md",
        rf"agents/{adw_id}/[a-z0-9_]*plan[a-z0-9_]*\.md",
        r"specs/[a-z0-9-]+\.md",
    ]
    for pattern in patterns:
        match = re.search(pattern, output, re.IGNORECASE)
        if match:
            return match.group(0)
    return None


def _get_commit_hash(working_dir: str) -> str | None:
    """Get current commit hash."""
    import subprocess
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=working_dir,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except Exception:
        return None


def _create_pull_request(state: ADWState, worktree_path: Path) -> str:
    """Create a pull request for the changes."""
    import subprocess

    # Push branch
    subprocess.run(
        ["git", "push", "-u", "origin", state.branch_name or f"adw-{state.worktree_name}"],
        cwd=worktree_path,
        capture_output=True,
    )

    # Create PR
    result = subprocess.run(
        [
            "gh", "pr", "create",
            "--title", f"[ADW] {state.task_description[:50]}",
            "--body", f"## Summary\n\n{state.task_description}\n\n---\nADW ID: {state.adw_id}",
        ],
        cwd=worktree_path,
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        return result.stdout.strip()

    raise Exception(result.stderr)


@click.command()
@click.option("--adw-id", help="Execution ID")
@click.option("--worktree-name", required=True)
@click.option("--task", required=True)
@click.option("--model-set", default="base", type=click.Choice(["base", "heavy"]))
@click.option("--skip", multiple=True, help="Phases to skip")
@click.option("--auto-ship", is_flag=True, help="Auto-create PR")
def main(adw_id, worktree_name, task, model_set, skip, auto_ship):
    """Run full SDLC workflow."""
    success = run_sdlc_workflow(
        task_description=task,
        worktree_name=worktree_name,
        adw_id=adw_id,
        model_set=model_set,
        skip_phases=list(skip),
        auto_ship=auto_ship,
    )
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
```

### 8.2 Prototype Workflows

**File**: `src/adw/workflows/prototype.py`

Rapid application generation:

```python
"""Prototype workflows for rapid application generation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class PrototypeConfig:
    """Configuration for a prototype type."""
    name: str
    plan_command: str
    description: str
    output_dir: str
    file_patterns: list[str]


# Available prototype types
PROTOTYPES: dict[str, PrototypeConfig] = {
    "vite_vue": PrototypeConfig(
        name="Vite + Vue",
        plan_command="/plan_vite_vue",
        description="Modern Vue 3 application with TypeScript and Vite",
        output_dir="apps/{app_name}",
        file_patterns=[
            "package.json",
            "vite.config.ts",
            "tsconfig.json",
            "src/App.vue",
            "src/main.ts",
            "src/components/*.vue",
            "index.html",
        ],
    ),
    "uv_script": PrototypeConfig(
        name="UV Script",
        plan_command="/plan_uv_script",
        description="Single-file Python CLI with inline dependencies",
        output_dir="apps/{app_name}",
        file_patterns=[
            "main.py",  # With /// script header
        ],
    ),
    "bun_scripts": PrototypeConfig(
        name="Bun TypeScript",
        plan_command="/plan_bun_scripts",
        description="TypeScript application with Bun runtime",
        output_dir="apps/{app_name}",
        file_patterns=[
            "package.json",
            "tsconfig.json",
            "src/index.ts",
            "src/**/*.ts",
        ],
    ),
    "uv_mcp": PrototypeConfig(
        name="MCP Server",
        plan_command="/plan_uv_mcp",
        description="Model Context Protocol server for Claude",
        output_dir="apps/{app_name}",
        file_patterns=[
            "server.py",
            "pyproject.toml",
        ],
    ),
    "fastapi": PrototypeConfig(
        name="FastAPI",
        plan_command="/plan_fastapi",
        description="FastAPI backend with async support",
        output_dir="apps/{app_name}",
        file_patterns=[
            "pyproject.toml",
            "app/main.py",
            "app/routes/*.py",
            "app/models/*.py",
        ],
    ),
}


def get_prototype_config(prototype_type: str) -> PrototypeConfig | None:
    """Get configuration for a prototype type."""
    return PROTOTYPES.get(prototype_type)


def list_prototypes() -> list[PrototypeConfig]:
    """List all available prototype types."""
    return list(PROTOTYPES.values())
```

**File**: `.claude/commands/plan_vite_vue.md`

Vue prototype planning command:

```markdown
# /plan_vite_vue - Plan a Vite + Vue application

Create a detailed implementation plan for a Vue 3 application.

## Input

$1 - ADW ID for tracking
$2 - Application description

## Process

1. **Analyze requirements**
   - Parse the application description
   - Identify core features
   - Determine component structure

2. **Design architecture**
   - Vue 3 Composition API
   - TypeScript throughout
   - Vite for build tooling
   - Tailwind CSS for styling (optional based on needs)

3. **Create plan**
   Write detailed spec to `specs/plan-$1-{slug}.md`:

   ```markdown
   # Plan: {App Name}

   ## Overview
   {Description of what we're building}

   ## Tech Stack
   - Vue 3 with Composition API
   - TypeScript
   - Vite
   - {Additional deps}

   ## File Structure
   apps/{app-name}/
   ├── package.json
   ├── vite.config.ts
   ├── tsconfig.json
   ├── index.html
   ├── src/
   │   ├── main.ts
   │   ├── App.vue
   │   ├── components/
   │   │   └── {components}
   │   ├── composables/
   │   │   └── {composables}
   │   └── types/
   │       └── index.ts
   └── public/

   ## Implementation Steps
   1. Initialize project structure
   2. Create base configuration files
   3. Implement core components
   4. Add business logic
   5. Style and polish

   ## Validation
   - `bun install` completes
   - `bun run dev` starts server
   - Core functionality works
   ```

4. **Return plan path**

## Output

Path to created plan file.
```

### 8.3 Slash Command Templates

**File**: `.claude/commands/plan.md`

```markdown
# /plan - Create implementation plan

Create a detailed implementation plan for a task.

## Input

$1 - ADW ID for tracking
$2 - Task description

## Process

1. **Understand the task**
   - Parse the task description
   - Identify scope and goals
   - Read CLAUDE.md for conventions

2. **Research codebase**
   - Find related existing code
   - Identify patterns to follow
   - Note dependencies

3. **Design solution**
   - Break into discrete steps
   - Identify files to create/modify
   - Plan validation approach

4. **Write specification**
   Save to `specs/plan-$1-{descriptive-slug}.md`:

   ```markdown
   # Implementation Plan: {Title}

   **ADW ID**: $1
   **Created**: {timestamp}

   ## Problem Statement
   {What we're solving}

   ## Approach
   {High-level solution}

   ## Implementation Steps

   ### Step 1: {First step}
   - Files: {files to modify}
   - Changes: {what to change}

   ### Step 2: {Second step}
   ...

   ## Files to Modify
   - `path/to/file.ts` - {what changes}

   ## Files to Create
   - `path/to/new.ts` - {purpose}

   ## Validation
   - {How to verify it works}

   ## Risks & Considerations
   - {Potential issues}
   ```

5. **Report**
   Return the path to the plan file.

## Output

Path to plan file: `specs/plan-$1-{slug}.md`
```

**File**: `.claude/commands/implement.md`

```markdown
# /implement - Execute implementation plan

Implement changes according to a plan file.

## Input

$ARGUMENTS - Path to plan file OR task description

## Process

1. **Load plan**
   - If path provided, read the plan file
   - If description provided, create inline plan

2. **Prime context**
   - Read files mentioned in plan
   - Understand current state

3. **Execute steps**
   For each step in the plan:
   - Make the code changes
   - Follow existing patterns
   - Maintain type safety
   - Add minimal necessary comments

4. **Validate**
   - Run linter if configured
   - Run type checker if configured
   - Run relevant tests

5. **Commit**
   - Stage changed files
   - Create descriptive commit
   - Include ADW ID in commit message

## Guidelines

- Follow existing code patterns
- Don't over-engineer
- Keep changes focused
- Validate as you go

## Output

Summary of changes made and commit hash.
```

**File**: `.claude/commands/test.md`

```markdown
# /test - Run tests and resolve failures

Run project tests and attempt to fix failures.

## Input

$1 - ADW ID for tracking

## Process

1. **Detect test framework**
   - Check for pytest, jest, vitest, etc.
   - Read test configuration

2. **Run tests**
   - Execute test suite
   - Capture output

3. **Analyze results**
   - If all pass: report success
   - If failures: analyze each failure

4. **Fix failures** (up to 3 attempts)
   For each failure:
   - Read the failing test
   - Read the code being tested
   - Identify the issue
   - Fix the code (prefer fixing implementation over test)
   - Re-run to verify

5. **Report**
   - Tests passing/failing count
   - What was fixed
   - Any remaining issues

## Output

Test results summary and any fixes applied.
```

**File**: `.claude/commands/review.md`

```markdown
# /review - Review implementation against spec

Validate that implementation matches the specification.

## Input

$1 - ADW ID for tracking

## Process

1. **Load context**
   - Find plan/spec file for this ADW ID
   - Load the specification requirements

2. **Review implementation**
   For each requirement in spec:
   - Verify it was implemented
   - Check implementation quality
   - Note any deviations

3. **Check quality**
   - Code follows project patterns
   - No obvious bugs
   - Error handling appropriate
   - Types are correct

4. **Generate report**
   Save to `agents/$1/review_report.md`:

   ```markdown
   # Review Report

   ## Requirements Coverage
   - [x] Requirement 1 - Implemented correctly
   - [x] Requirement 2 - Implemented with minor deviation
   - [ ] Requirement 3 - Not implemented

   ## Quality Assessment
   - Code style: ✓
   - Type safety: ✓
   - Error handling: ⚠ Could be improved

   ## Recommendations
   1. {Suggestion}

   ## Verdict
   APPROVED / NEEDS_CHANGES
   ```

## Output

Review verdict and report location.
```

**File**: `.claude/commands/document.md`

```markdown
# /document - Generate documentation

Create documentation for implemented changes.

## Input

$1 - ADW ID for tracking

## Process

1. **Identify changes**
   - Find files modified in this ADW
   - Understand what was implemented

2. **Generate documentation**
   Depending on what was built:

   - **New API endpoints**: Add to API docs
   - **New components**: Add usage examples
   - **New features**: Update README or user docs
   - **Configuration**: Document options

3. **Update existing docs**
   - Find related documentation files
   - Add or update relevant sections
   - Keep consistent style

4. **Create screenshots** (if UI changes)
   - Capture relevant UI states
   - Save to `agents/$1/screenshots/`

## Guidelines

- Match existing documentation style
- Include practical examples
- Don't over-document obvious things
- Focus on "why" and "how to use"

## Output

List of documentation files created/updated.
```

---

## 9. Phase 6: Integrations

### 9.1 GitHub Integration

**File**: `src/adw/integrations/github.py`

```python
"""GitHub integration for ADW."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass


@dataclass
class GitHubIssue:
    """Represents a GitHub issue."""
    number: int
    title: str
    body: str
    labels: list[str]
    state: str


def get_issue(issue_number: int) -> GitHubIssue | None:
    """Fetch a GitHub issue.

    Args:
        issue_number: The issue number.

    Returns:
        GitHubIssue or None if not found.
    """
    try:
        result = subprocess.run(
            ["gh", "issue", "view", str(issue_number), "--json",
             "number,title,body,labels,state"],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            return None

        data = json.loads(result.stdout)
        return GitHubIssue(
            number=data["number"],
            title=data["title"],
            body=data.get("body", ""),
            labels=[l["name"] for l in data.get("labels", [])],
            state=data["state"],
        )

    except Exception:
        return None


def add_issue_comment(issue_number: int, comment: str, adw_id: str) -> bool:
    """Add a comment to a GitHub issue.

    Args:
        issue_number: The issue number.
        comment: Comment text.
        adw_id: ADW ID for tracking (prevents webhook loops).

    Returns:
        True if successful.
    """
    # Prefix with ADW identifier to prevent webhook loops
    full_comment = f"<!-- ADW:{adw_id} -->\n{comment}"

    try:
        result = subprocess.run(
            ["gh", "issue", "comment", str(issue_number), "--body", full_comment],
            capture_output=True,
        )
        return result.returncode == 0

    except Exception:
        return False


def create_pull_request(
    title: str,
    body: str,
    branch: str,
    base: str = "main",
) -> str | None:
    """Create a pull request.

    Args:
        title: PR title.
        body: PR body.
        branch: Source branch.
        base: Target branch.

    Returns:
        PR URL or None if failed.
    """
    try:
        result = subprocess.run(
            [
                "gh", "pr", "create",
                "--title", title,
                "--body", body,
                "--head", branch,
                "--base", base,
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            return result.stdout.strip()

    except Exception:
        pass

    return None


def get_open_issues_with_label(label: str) -> list[GitHubIssue]:
    """Get all open issues with a specific label.

    Args:
        label: Label to filter by.

    Returns:
        List of matching issues.
    """
    try:
        result = subprocess.run(
            [
                "gh", "issue", "list",
                "--label", label,
                "--state", "open",
                "--json", "number,title,body,labels,state",
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            return []

        data = json.loads(result.stdout)
        return [
            GitHubIssue(
                number=item["number"],
                title=item["title"],
                body=item.get("body", ""),
                labels=[l["name"] for l in item.get("labels", [])],
                state=item["state"],
            )
            for item in data
        ]

    except Exception:
        return []
```

### 9.2 GitHub Trigger

**File**: `src/adw/triggers/github.py`

```python
"""GitHub-based triggers for ADW workflows."""

from __future__ import annotations

import time
from pathlib import Path

from rich.console import Console

from ..agent.executor import generate_adw_id
from ..agent.task_updater import mark_task_in_progress
from ..integrations.github import get_open_issues_with_label, add_issue_comment
from ..workflows.standard import run_standard_workflow


console = Console()


def process_github_issues(
    label: str = "adw",
    dry_run: bool = False,
) -> int:
    """Process GitHub issues with ADW label.

    Args:
        label: Label to look for.
        dry_run: If True, don't actually process.

    Returns:
        Number of issues processed.
    """
    issues = get_open_issues_with_label(label)

    if not issues:
        console.print(f"[dim]No open issues with label '{label}'[/dim]")
        return 0

    processed = 0

    for issue in issues:
        adw_id = generate_adw_id()

        console.print(f"[cyan]Processing issue #{issue.number}: {issue.title}[/cyan]")

        if dry_run:
            console.print(f"[yellow]DRY RUN: Would process with ADW ID {adw_id}[/yellow]")
            continue

        # Comment on issue to show we're working on it
        add_issue_comment(
            issue.number,
            f"🤖 ADW is working on this issue.\n\n**ADW ID**: `{adw_id}`",
            adw_id,
        )

        # Run workflow
        worktree_name = f"issue-{issue.number}-{adw_id}"
        success = run_standard_workflow(
            task_description=f"{issue.title}\n\n{issue.body}",
            worktree_name=worktree_name,
            adw_id=adw_id,
        )

        # Update issue with result
        if success:
            add_issue_comment(
                issue.number,
                f"✅ Implementation complete!\n\nADW ID: `{adw_id}`\n\nPlease review the PR.",
                adw_id,
            )
        else:
            add_issue_comment(
                issue.number,
                f"❌ Implementation failed.\n\nADW ID: `{adw_id}`\n\nCheck logs in `agents/{adw_id}/`",
                adw_id,
            )

        processed += 1

    return processed


def run_github_cron(
    label: str = "adw",
    interval: int = 60,
    dry_run: bool = False,
) -> None:
    """Continuously poll GitHub for issues.

    Args:
        label: Label to look for.
        interval: Seconds between checks.
        dry_run: If True, don't actually process.
    """
    console.print(f"[bold]Starting GitHub issue monitor[/bold]")
    console.print(f"Label: {label}")
    console.print(f"Interval: {interval}s")

    try:
        while True:
            process_github_issues(label, dry_run)
            time.sleep(interval)

    except KeyboardInterrupt:
        console.print("\n[yellow]Stopping...[/yellow]")
```

### 9.3 Webhook Handler

**File**: `src/adw/triggers/webhook.py`

```python
"""Webhook handler for real-time GitHub events."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from typing import Any

# Note: Requires fastapi and uvicorn
# pip install fastapi uvicorn


def create_webhook_app():
    """Create FastAPI app for webhook handling."""
    from fastapi import FastAPI, Request, HTTPException

    app = FastAPI(title="ADW Webhook Handler")

    @app.post("/gh-webhook")
    async def github_webhook(request: Request):
        """Handle GitHub webhook events."""
        # Verify signature
        secret = os.environ.get("GITHUB_WEBHOOK_SECRET")
        if secret:
            signature = request.headers.get("X-Hub-Signature-256", "")
            body = await request.body()

            expected = "sha256=" + hmac.new(
                secret.encode(),
                body,
                hashlib.sha256,
            ).hexdigest()

            if not hmac.compare_digest(signature, expected):
                raise HTTPException(status_code=401, detail="Invalid signature")

        payload = await request.json()
        event_type = request.headers.get("X-GitHub-Event", "unknown")

        return handle_github_event(event_type, payload)

    return app


def handle_github_event(event_type: str, payload: dict[str, Any]) -> dict:
    """Handle a GitHub event.

    Args:
        event_type: The event type (issues, issue_comment, etc.)
        payload: The webhook payload.

    Returns:
        Response dict.
    """
    from ..agent.executor import generate_adw_id

    if event_type == "issues":
        action = payload.get("action")
        if action == "labeled":
            label = payload.get("label", {}).get("name")
            if label == "adw":
                issue = payload.get("issue", {})
                adw_id = generate_adw_id()

                # Trigger async workflow
                _trigger_workflow_async(
                    task=issue.get("title", ""),
                    body=issue.get("body", ""),
                    issue_number=issue.get("number"),
                    adw_id=adw_id,
                )

                return {"status": "triggered", "adw_id": adw_id}

    elif event_type == "issue_comment":
        action = payload.get("action")
        if action == "created":
            comment = payload.get("comment", {}).get("body", "")

            # Check for ADW commands in comment
            if comment.strip().lower().startswith("adw "):
                # Skip if this is our own comment
                if "<!-- ADW:" in comment:
                    return {"status": "skipped", "reason": "own comment"}

                issue = payload.get("issue", {})
                adw_id = generate_adw_id()

                _trigger_workflow_async(
                    task=comment[4:],  # Remove "adw " prefix
                    body=issue.get("body", ""),
                    issue_number=issue.get("number"),
                    adw_id=adw_id,
                )

                return {"status": "triggered", "adw_id": adw_id}

    return {"status": "ignored"}


def _trigger_workflow_async(
    task: str,
    body: str,
    issue_number: int,
    adw_id: str,
) -> None:
    """Trigger workflow in background process."""
    import subprocess
    import sys

    subprocess.Popen(
        [
            sys.executable,
            "-m", "adw.workflows.standard",
            "--adw-id", adw_id,
            "--worktree-name", f"issue-{issue_number}-{adw_id}",
            "--task", f"{task}\n\n{body}",
        ],
        start_new_session=True,
    )
```

---

## 10. Phase 7: Self-Improvement

### 10.1 Expert System Architecture

From `agentic-prompt-engineering`, Level 7 prompts that improve themselves:

**File**: `.claude/commands/experts/cc_expert.md`

```markdown
# /experts:cc_expert - Claude Code Expert System

Self-improving expert for Claude Code patterns and best practices.

## Metadata

```yaml
allowed-tools: [Read, Glob, Grep, WebFetch, WebSearch, Edit]
description: Expert system for Claude Code development
```

## Purpose

Provide expert-level guidance on Claude Code development, continuously improving knowledge base.

## Expertise

<!-- This section is updated by /experts:cc_expert:improve -->

### Core Patterns
- Hook system: PreToolUse, PostToolUse, UserPromptSubmit, Stop
- Slash commands in .claude/commands/
- Sub-agents in .claude/agents/
- Output styles for token efficiency

### Best Practices
- Use --stream-json for programmatic output
- Filter subprocess environment for security
- Implement retry logic for transient failures
- Use ADW IDs for execution tracking

### Known Issues
- {Issues discovered during usage}

### Learnings
- {Patterns discovered during usage}

## Workflow

1. **Receive query**
   - Understand what user needs
   - Check if covered by Expertise section

2. **Research if needed**
   - Search ai_docs/ for relevant docs
   - Use WebSearch for latest info
   - Read relevant source files

3. **Provide answer**
   - Give specific, actionable guidance
   - Include code examples
   - Reference documentation

4. **Update expertise** (if new learning)
   - Note pattern for future reference
   - Flag for /experts:cc_expert:improve
```

**File**: `.claude/commands/experts/cc_expert_improve.md`

```markdown
# /experts:cc_expert:improve - Improve CC Expert Knowledge

Update the Claude Code expert system with new learnings.

## Input

$ARGUMENTS - New learning or pattern to add

## Process

1. **Validate learning**
   - Ensure it's accurate
   - Check it's not already documented
   - Verify it's generally applicable

2. **Categorize**
   - Core Patterns
   - Best Practices
   - Known Issues
   - Learnings

3. **Update expertise**
   - Read current .claude/commands/experts/cc_expert.md
   - Add new entry to appropriate section
   - Keep concise and actionable

4. **Confirm**
   - Report what was added
   - Note if it conflicts with existing knowledge

## Output

Confirmation of expertise update.
```

### 10.2 AI Documentation Loader

**File**: `.claude/commands/load_ai_docs.md`

```markdown
# /load_ai_docs - Load AI documentation into context

Fetch and cache documentation from URLs for agent reference.

## Input

$ARGUMENTS - Optional specific doc to load (default: all)

## Documentation Sources

```yaml
# ai_docs/README.md contains:
- claude_code_sdk: https://docs.anthropic.com/claude-code/sdk
- claude_code_hooks: https://docs.anthropic.com/claude-code/hooks
- claude_code_mcp: https://docs.anthropic.com/claude-code/mcp
- anthropic_api: https://docs.anthropic.com/api
```

## Process

1. **Read source list**
   - Load ai_docs/README.md
   - Parse URL entries

2. **Fetch documentation**
   - For each URL (or specific requested doc):
   - Use WebFetch to retrieve content
   - Convert to clean markdown

3. **Cache locally**
   - Save to ai_docs/{name}.md
   - Include fetch timestamp

4. **Load into context**
   - Read cached files
   - Summarize what's available

## Output

List of documentation loaded and available.
```

### 10.3 Meta-Agent Generator

**File**: `.claude/commands/create_agent.md`

```markdown
# /create_agent - Generate a new specialized agent

Create a new sub-agent configuration based on requirements.

## Input

$ARGUMENTS - Description of what the agent should do

## Process

1. **Analyze requirements**
   - What task will this agent perform?
   - What tools does it need?
   - What model is appropriate?

2. **Research patterns**
   - Read existing agents in .claude/agents/
   - Identify similar agents for reference

3. **Generate agent spec**
   Create `.claude/agents/{name}.md`:

   ```markdown
   # {Agent Name}

   ## Metadata

   ```yaml
   allowed-tools: [{minimal tool set}]
   description: {action-oriented description}
   model: {haiku|sonnet|opus}
   ```

   ## Purpose

   {What this agent does and when to use it}

   ## Workflow

   1. {Step 1}
   2. {Step 2}
   ...

   ## Response Format

   {How the agent should format its output}
   ```

4. **Validate**
   - Ensure all required sections present
   - Tools are valid
   - Description is action-oriented

## Output

Path to created agent file.
```

---

## 11. Implementation Roadmap

### Phase 1: Foundation (Week 1-2)

| Task | Priority | Complexity |
|------|----------|------------|
| Agent executor module | P0 | Medium |
| State manager | P0 | Medium |
| Data models | P0 | Low |
| ADW ID generation | P0 | Low |
| Output directory structure | P0 | Low |
| Model selection | P1 | Low |

**Deliverable**: Can execute Claude Code programmatically with retry logic and structured output.

### Phase 2: Autonomous Execution (Week 2-3)

| Task | Priority | Complexity |
|------|----------|------------|
| Task parser | P0 | Medium |
| Task updater | P0 | Medium |
| Cron trigger | P0 | High |
| Standard workflow | P0 | Medium |
| CLI integration | P1 | Medium |

**Deliverable**: Tasks in tasks.md are automatically picked up and executed.

### Phase 3: Parallel Isolation (Week 3-4)

| Task | Priority | Complexity |
|------|----------|------------|
| Worktree manager | P0 | Medium |
| Port allocation | P1 | Low |
| Environment isolation | P1 | Low |
| Concurrent task limits | P1 | Low |
| Worktree cleanup | P2 | Low |

**Deliverable**: Multiple tasks execute in parallel in isolated worktrees.

### Phase 4: Observability (Week 4-5)

| Task | Priority | Complexity |
|------|----------|------------|
| Hook system setup | P0 | Medium |
| Context bundle builder | P1 | Medium |
| Universal logger | P1 | Low |
| Output styles | P1 | Low |
| Prime commands | P1 | Medium |
| Load bundle command | P2 | Medium |

**Deliverable**: Full visibility into agent actions with context restoration.

### Phase 5: Advanced Workflows (Week 5-6)

| Task | Priority | Complexity |
|------|----------|------------|
| Full SDLC workflow | P0 | High |
| Prototype workflows | P1 | High |
| Enhanced slash commands | P1 | Medium |
| Review command | P1 | Medium |
| Document command | P2 | Medium |

**Deliverable**: Complete development workflows from planning to PR.

### Phase 6: Integrations (Week 6-7)

| Task | Priority | Complexity |
|------|----------|------------|
| GitHub issue fetcher | P1 | Medium |
| GitHub trigger | P1 | Medium |
| Webhook handler | P2 | High |
| PR creation | P1 | Medium |
| Issue commenting | P2 | Low |

**Deliverable**: ADW can be triggered from GitHub issues.

### Phase 7: Self-Improvement (Week 7-8)

| Task | Priority | Complexity |
|------|----------|------------|
| Expert system framework | P2 | Medium |
| AI docs loader | P2 | Medium |
| Meta-agent generator | P2 | Medium |
| Knowledge base updates | P3 | Medium |

**Deliverable**: System improves its own knowledge over time.

---

## 12. File Structure

Complete project structure after all phases:

```
adw/
├── pyproject.toml
├── README.md
├── CLAUDE.md
│
├── src/
│   └── adw/
│       ├── __init__.py
│       ├── cli.py                      # Main CLI entry point
│       │
│       ├── agent/                      # Agent execution layer
│       │   ├── __init__.py
│       │   ├── executor.py             # Claude Code execution
│       │   ├── state.py                # Persistent state
│       │   ├── models.py               # Data models
│       │   ├── task_parser.py          # Parse tasks.md
│       │   ├── task_updater.py         # Update task status
│       │   ├── model_selector.py       # Model selection logic
│       │   ├── worktree.py             # Git worktree management
│       │   ├── ports.py                # Port allocation
│       │   └── environment.py          # Environment isolation
│       │
│       ├── triggers/                   # Execution triggers
│       │   ├── __init__.py
│       │   ├── cron.py                 # Continuous monitoring
│       │   ├── github.py               # GitHub polling
│       │   └── webhook.py              # Webhook handler
│       │
│       ├── workflows/                  # Workflow implementations
│       │   ├── __init__.py
│       │   ├── simple.py               # Build-Update workflow
│       │   ├── standard.py             # Plan-Implement-Update
│       │   ├── sdlc.py                 # Full SDLC workflow
│       │   └── prototype.py            # Prototype generation
│       │
│       ├── integrations/               # External integrations
│       │   ├── __init__.py
│       │   ├── github.py               # GitHub API
│       │   └── notion.py               # Notion API (optional)
│       │
│       ├── hooks/                      # Hook implementations
│       │   ├── __init__.py
│       │   └── handlers.py             # Hook handlers
│       │
│       ├── dashboard/                  # Monitoring UI
│       │   ├── __init__.py
│       │   ├── server.py               # Dashboard server
│       │   └── static/                 # UI assets
│       │
│       ├── templates/                  # Templates for init
│       │   ├── commands/               # Slash command templates
│       │   ├── agents/                 # Agent templates
│       │   ├── hooks/                  # Hook script templates
│       │   └── output-styles/          # Output style templates
│       │
│       ├── init.py                     # Project initialization
│       ├── detect.py                   # Project detection
│       ├── tasks.py                    # Task management
│       ├── specs.py                    # Spec management
│       └── update.py                   # Self-update
│
├── tests/
│   ├── test_executor.py
│   ├── test_state.py
│   ├── test_task_parser.py
│   ├── test_worktree.py
│   └── test_workflows.py
│
└── docs/
    ├── ZERO_TOUCH_ENGINEERING_SPEC.md  # This document
    ├── ARCHITECTURE.md
    └── COMMANDS.md
```

---

## 13. API Reference

### 13.1 CLI Commands

```bash
# Core commands
adw                          # Open dashboard (default)
adw init [--force]           # Initialize ADW in project
adw new "description"        # Start new task discussion
adw status                   # Show task/spec status

# Execution commands
adw run                      # Run cron trigger (continuous)
adw run --once               # Run single execution cycle
adw run --dry-run            # Preview without executing

# Task management
adw task list                # List all tasks
adw task add "description"   # Add task to tasks.md
adw task start <id>          # Manually start a task

# Worktree management
adw worktree list            # List worktrees
adw worktree create <name>   # Create worktree
adw worktree remove <name>   # Remove worktree
adw worktree clean           # Clean old worktrees

# Workflow commands
adw workflow simple <task>   # Run simple workflow
adw workflow standard <task> # Run standard workflow
adw workflow sdlc <task>     # Run full SDLC workflow
adw workflow prototype <task> --type vite_vue

# Integration commands
adw github watch             # Watch GitHub for issues
adw github process           # Process labeled issues once

# Utility commands
adw doctor                   # Check installation health
adw update                   # Update to latest version
adw version                  # Show version info
```

### 13.2 Python API

```python
from adw.agent.executor import (
    AgentPromptRequest,
    AgentTemplateRequest,
    prompt_claude_code,
    prompt_claude_code_with_retry,
    execute_template,
    generate_adw_id,
)

from adw.agent.state import ADWState

from adw.agent.worktree import (
    create_worktree,
    remove_worktree,
    worktree_exists,
)

from adw.workflows.standard import run_standard_workflow
from adw.workflows.sdlc import run_sdlc_workflow

from adw.triggers.cron import CronTrigger, CronConfig
```

### 13.3 Configuration

**Environment Variables**:
```bash
# Required
ANTHROPIC_API_KEY=sk-...

# Optional
GITHUB_TOKEN=ghp_...
OPENAI_API_KEY=sk-...
GITHUB_WEBHOOK_SECRET=...

# ADW Configuration
ADW_POLLING_INTERVAL=5
ADW_MAX_CONCURRENT=5
ADW_MODEL_SET=base  # or "heavy"
```

**Project Configuration** (`.adw/config.yaml`):
```yaml
# Workflow defaults
default_workflow: standard
default_model_set: base

# Limits
max_concurrent_tasks: 5
max_tasks_per_cycle: 3
polling_interval: 5

# Worktrees
worktree_base: trees
cleanup_age_days: 7

# Integrations
github:
  enabled: true
  label: adw
  auto_comment: true

# Hooks
hooks:
  context_bundles: true
  universal_logging: true
```

---

## Appendix A: Migration from Current ADW

### Step 1: Update Dependencies

```toml
# pyproject.toml additions
dependencies = [
    "click>=8.1.0",
    "rich>=13.0.0",
    "httpx>=0.25.0",
    "pydantic>=2.0.0",  # NEW
]
```

### Step 2: Create New Modules

1. Copy agent execution modules to `src/adw/agent/`
2. Copy workflow modules to `src/adw/workflows/`
3. Copy trigger modules to `src/adw/triggers/`

### Step 3: Update CLI

Add new commands to `cli.py`:
- `adw run` for cron trigger
- `adw worktree` for worktree management
- `adw workflow` for workflow execution

### Step 4: Update Init

Modify `init.py` to create:
- `.claude/hooks/` with hook scripts
- `.claude/output-styles/` with styles
- Updated command templates

### Step 5: Test Migration

```bash
# Test basic functionality
adw init --force
adw doctor
adw run --once --dry-run
```

---

## Appendix B: Glossary

| Term | Definition |
|------|------------|
| **ADW** | AI Developer Workflow - the system/CLI tool |
| **ADW ID** | 8-character unique identifier for each execution |
| **Worktree** | Git worktree for isolated parallel execution |
| **Phase** | Single step in a workflow (plan, implement, test, etc.) |
| **Workflow** | Sequence of phases (simple, standard, full, prototype) |
| **Hook** | Claude Code event handler for observability |
| **Context Bundle** | JSONL file tracking file operations for context restoration |
| **Model Set** | Collection of model choices (base=sonnet, heavy=opus) |
| **Tag** | Metadata in task description `{tag}` controlling behavior |

---

*End of Zero-Touch Engineering Specification*
