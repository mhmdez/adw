# ADW - AI Developer Workflow CLI

> **Project Context**: This is ADW (AI Developer Workflow), an autonomous AI development orchestration system that coordinates Claude Code agents to plan, implement, test, and review features with full parallelization and observability.

---

## Project Overview

ADW is a Python CLI tool built with:
- **Runtime**: Python 3.11+ with uv package manager
- **TUI**: Textual framework for interactive dashboard
- **State**: Filesystem-based protocol (JSONL, markdown)
- **Orchestration**: Git worktrees for parallel task execution
- **Integration**: Claude Code as the execution engine

**Repository**: https://github.com/mhmdez/adw

---

## Core Architecture

### Directory Structure

```
adw/
├── src/adw/
│   ├── agent/           # Agent management and execution
│   │   ├── executor.py      # Claude Code subprocess spawning
│   │   ├── manager.py       # Process lifecycle management
│   │   ├── state.py         # Persistent state (JSONL)
│   │   ├── worktree.py      # Git worktree isolation
│   │   ├── ports.py         # Port allocation for parallel tasks
│   │   ├── environment.py   # Environment variable isolation
│   │   ├── task_parser.py   # Parse tasks.md format
│   │   └── task_updater.py  # Atomic task status updates
│   ├── tui/             # Textual TUI dashboard
│   │   ├── app.py           # Main TUI application
│   │   ├── state.py         # Reactive app state
│   │   ├── log_watcher.py   # Watch agent logs
│   │   ├── log_formatter.py # Format JSONL events
│   │   ├── log_buffer.py    # Buffer for log display
│   │   └── widgets/         # TUI components
│   ├── workflows/       # Workflow orchestration
│   │   ├── simple.py        # Quick build-update workflow
│   │   ├── standard.py      # Plan-implement-update workflow
│   │   ├── sdlc.py          # Full 6-phase SDLC
│   │   └── prototype.py     # Project scaffolding generators
│   ├── triggers/        # Task triggers
│   │   ├── cron.py          # Autonomous daemon
│   │   ├── github.py        # GitHub issue polling
│   │   └── webhook.py       # FastAPI webhook handler
│   ├── integrations/    # External integrations
│   │   └── github.py        # GitHub API wrapper
│   ├── protocol/        # Communication protocols
│   │   └── messages.py      # Message passing models
│   └── cli.py           # Click CLI commands
├── .claude/             # Claude Code configuration
│   ├── settings.json        # Hook configuration
│   ├── commands/            # Slash commands
│   │   ├── load_ai_docs.md
│   │   ├── create_agent.md
│   │   └── experts/
│   │       ├── cc_expert.md
│   │       └── cc_expert_improve.md
│   ├── hooks/               # Event hooks
│   │   ├── check_messages.py
│   │   ├── context_bundle_builder.py
│   │   └── universal_logger.py
│   └── output-styles/       # Output formatting
│       ├── concise-done.md
│       └── concise-ultra.md
├── agents/              # Agent execution directories
│   └── {adw_id}/
│       ├── agent.log        # Structured JSONL logs
│       ├── adw_messages.jsonl  # Bidirectional messages
│       └── context/         # Session snapshots
├── specs/               # Feature specifications
├── tasks.md             # Task tracking board
└── ai_docs/             # Documentation for expert system
```

---

## Task Management System

### tasks.md Format

ADW uses `tasks.md` as a task board with status tracking:

```markdown
## Worktree: main

[✅, abc123de] Completed task
[🟡, def456gh] In-progress task
[⏰] Blocked task (waiting for dependencies)
[] Ready to start task
[❌, ghi789jk] Failed task

## Worktree: feature-auth

[] Implement login endpoint {opus}
[] Add OAuth integration {sonnet}
```

**Status Indicators**:
- `[]` = Pending (ready to start)
- `[⏰]` = Blocked (waiting for dependencies)
- `[🟡, adw_id]` = In progress
- `[✅, adw_id]` = Completed
- `[❌, adw_id]` = Failed

**Tags**:
- `{opus}` = Use Claude Opus for complex reasoning
- `{sonnet}` = Use Claude Sonnet (default)
- `{haiku}` = Use Claude Haiku for simple tasks

**ADW ID**: 8-character hex identifier for tracking (e.g., `abc123de`)

### Dependency System

Tasks within a worktree section are ordered. A `[⏰]` blocked task becomes eligible when ALL tasks above it are `[✅]` completed.

```markdown
## Worktree: example

[] First task          ← Eligible immediately
[⏰] Second task       ← Eligible after first completes
[⏰] Third task        ← Eligible after first AND second complete
```

### Task Updates

Status updates are atomic via `src/adw/agent/task_updater.py`:
- Lock file prevents concurrent modifications
- Preserves exact formatting and line breaks
- Updates only the specific task by ADW ID
- Used by workflows to mark progress

---

## Workflow System

ADW provides multiple workflow types for different use cases:

### 1. Simple Workflow (`simple.py`)

**When to use**: Quick, well-defined tasks without planning phase

```python
from adw.workflows import simple_workflow
simple_workflow(task_id="abc123de", description="Fix login bug")
```

**Phases**:
1. Build - Execute task directly
2. Update - Mark task complete in tasks.md

### 2. Standard Workflow (`standard.py`)

**When to use**: Features requiring planning before implementation

```python
from adw.workflows import standard_workflow
standard_workflow(task_id="def456gh", description="Add user profile page")
```

**Phases**:
1. Plan - Create implementation plan
2. Implement - Execute the plan
3. Update - Mark task complete

### 3. Full SDLC Workflow (`sdlc.py`)

**When to use**: Complex features requiring full development lifecycle

```python
from adw.workflows import run_sdlc_workflow
run_sdlc_workflow(
    task_id="ghi789jk",
    spec_path="specs/feature-auth.md",
    model="opus"
)
```

**Phases**:
1. Plan - Detailed technical design
2. Implement - Execute implementation
3. Test - Create and run tests
4. Review - Code quality review
5. Document - Generate documentation
6. Update - Mark complete and commit

### 4. Prototype Workflows (`prototype.py`)

**When to use**: Project scaffolding and code generation

Available prototypes:
- `vite_vue` - Vite + Vue 3 project
- `uv_script` - Python uv script template
- `bun_scripts` - Bun + TypeScript project

---

## Agent Execution

### Spawning Agents

Agents run as Claude Code subprocesses:

```python
from adw.agent.executor import spawn_agent

agent = spawn_agent(
    task_id="abc123de",
    prompt="Implement user authentication",
    worktree_path="/path/to/worktree",
    model="sonnet"
)
```

### Agent Lifecycle

1. **Spawn**: Create subprocess with Claude Code
2. **Execute**: Agent works autonomously in worktree
3. **Log**: All actions logged to `agents/{adw_id}/agent.log`
4. **Message**: User can inject messages via `adw_messages.jsonl`
5. **Complete**: Agent updates task status and exits

### Agent Logs

Format: JSONL (JSON Lines) in `agents/{adw_id}/agent.log`

```jsonl
{"timestamp": "2026-01-31T12:34:56Z", "event": "tool_use", "tool": "Read", "params": {"file_path": "src/auth.py"}}
{"timestamp": "2026-01-31T12:35:12Z", "event": "tool_result", "tool": "Read", "status": "success"}
{"timestamp": "2026-01-31T12:35:30Z", "event": "message", "role": "assistant", "content": "I've read the file..."}
```

TUI streams and formats these logs in real-time.

---

## Parallel Execution with Worktrees

### Git Worktree Isolation

Each task can run in an isolated git worktree:

```bash
adw worktree create feature-auth
adw worktree list
adw worktree remove feature-auth
```

**Benefits**:
- Parallel task execution without conflicts
- Independent git state per task
- Isolated filesystem changes
- Automatic cleanup on completion

### Port Allocation

`src/adw/agent/ports.py` manages port assignment:
- Allocates unique ports for each task
- Prevents conflicts in parallel dev servers
- Tracked in state file
- Auto-released on task completion

### Environment Isolation

`src/adw/agent/environment.py` provides:
- Task-specific environment variables
- Isolated configuration per worktree
- Override system defaults
- Clean environment for testing

---

## Autonomous Execution

### Cron Daemon

Start autonomous task execution:

```bash
adw run
```

The daemon (`src/adw/triggers/cron.py`):
1. Monitors `tasks.md` for eligible tasks
2. Checks dependencies and blocks
3. Enforces concurrent task limits
4. Spawns agents in isolated worktrees
5. Streams logs to TUI
6. Updates task status atomically
7. Loops until all tasks complete

**Configuration** (`.adw/config.json`):
```json
{
  "max_concurrent_tasks": 3,
  "check_interval": 60,
  "worktree_enabled": true,
  "default_workflow": "standard"
}
```

---

## Bidirectional Communication

### Message Injection

Send messages to running agents via TUI or CLI:

**TUI**: Press `m` and type message
**File**: Write to `agents/{adw_id}/adw_messages.jsonl`

```jsonl
{"timestamp": "2026-01-31T12:40:00Z", "role": "user", "content": "Add error handling for edge case X", "priority": "normal"}
```

**Priorities**:
- `normal` - Agent reads on next check
- `high` - Interrupt current operation
- `interrupt` - Immediate context switch

### Message Hook

`.claude/hooks/check_messages.py` runs periodically:
1. Reads `adw_messages.jsonl`
2. Injects new messages into agent context
3. Marks messages as read
4. Agent responds in conversation

---

## Observability System

### Hooks

Configured in `.claude/settings.json`:

```json
{
  "hooks": {
    "beforeToolUse": [".claude/hooks/universal_logger.py"],
    "afterToolUse": [".claude/hooks/universal_logger.py"],
    "afterResponse": [".claude/hooks/context_bundle_builder.py"],
    "beforePromptSubmit": [".claude/hooks/check_messages.py"]
  }
}
```

**Available Hooks**:
- `check_messages.py` - Inject user messages
- `universal_logger.py` - Log all tool calls
- `context_bundle_builder.py` - Snapshot session state

### Context Bundles

Automatic session snapshots in `agents/{adw_id}/context/`:
- Full conversation history
- Tool call trace
- Current state snapshot
- Resume capability

### Output Styles

Custom formatting in `.claude/output-styles/`:
- `concise-done.md` - Minimal completion messages
- `concise-ultra.md` - Ultra-compact output

Agents use these to reduce log verbosity.

---

## GitHub Integration

### Issue Triggering

Watch GitHub issues and trigger workflows:

```bash
# Polling mode
adw github watch --interval 300

# Process specific issue
adw github process 123
```

**Workflow**:
1. Fetch issue details via GitHub API
2. Create task in `tasks.md`
3. Spawn agent with SDLC workflow
4. Create PR when complete
5. Link PR to original issue

### Webhook Handler

FastAPI server for GitHub webhooks (`src/adw/triggers/webhook.py`):

```bash
adw webhook start --port 8080
```

Responds to:
- `issues.opened` - Create task
- `issues.labeled` - Trigger workflow
- `pull_request.opened` - Run review

---

## Expert System

### Querying Experts

Use slash commands in Claude Code:

```
/experts:cc_expert "How do I optimize parallel execution?"
```

Searches knowledge base in `.claude/commands/experts/cc_expert.md`

### Improving Knowledge

```
/experts:cc_expert:improve
```

Prompts for new patterns, practices, or learnings to add.

### Loading Documentation

```
/load_ai_docs https://docs.anthropic.com/...
/load_ai_docs docs/
```

Fetches and processes documentation into expert knowledge base.

---

## Commands Reference

### CLI Commands

| Command | Description |
|---------|-------------|
| `adw` | Open interactive TUI dashboard |
| `adw init` | Initialize ADW in project |
| `adw new <description>` | Start new task discussion |
| `adw run` | Start autonomous daemon |
| `adw status` | Show task status |
| `adw verify [task_id]` | Verify completed work |
| `adw worktree list` | List active worktrees |
| `adw worktree create <name>` | Create isolated worktree |
| `adw worktree remove <name>` | Remove worktree |
| `adw github watch` | Watch GitHub issues |
| `adw github process <issue>` | Process GitHub issue |

### Slash Commands

Available in Claude Code sessions:

| Command | Purpose |
|---------|---------|
| `/load_ai_docs` | Load documentation into expert system |
| `/create_agent` | Generate specialized agent config |
| `/experts:cc_expert` | Query Claude Code expert |
| `/experts:cc_expert:improve` | Improve expert knowledge |

---

## Development Commands

### Running Locally

```bash
# Install dependencies
uv sync

# Run CLI
uv run adw --help

# Run TUI
uv run adw

# Run tests
uv run pytest

# Type check
uv run mypy src

# Lint
uv run ruff check .
```

### Testing

```bash
# Full test suite
uv run pytest

# With coverage
uv run pytest --cov=src/adw --cov-report=html

# Specific test
uv run pytest tests/test_agent/test_executor.py

# Watch mode
uv run pytest-watch
```

---

## Conventions

### Code Style

- **Formatting**: Ruff (enforced)
- **Type hints**: Required for public APIs
- **Docstrings**: Google style
- **Imports**: Sorted with isort rules

### Naming

- **Files**: `snake_case.py`
- **Classes**: `PascalCase`
- **Functions**: `snake_case`
- **Constants**: `UPPER_SNAKE_CASE`
- **Private**: `_leading_underscore`

### Git Workflow

- **Branch**: Feature branches from `main`
- **Commits**: Conventional commits format
- **PRs**: Require passing tests
- **Merges**: Squash and merge

### Task Workflow

When working on ADW:

1. **Find task** in `tasks.md` or create new one
2. **Check dependencies** - ensure not blocked
3. **Create worktree** if needed for isolation
4. **Execute task** manually or with `adw run`
5. **Update status** in `tasks.md` when complete
6. **Commit changes** with descriptive message

---

## Project Principles

### Zero-Touch Engineering

ADW embraces automation over manual orchestration:
- Tasks self-execute via daemon
- Dependencies auto-resolve
- Status updates are atomic
- Parallel execution by default

### Filesystem Protocols

Simple, debuggable, language-agnostic:
- JSONL for structured logs
- Markdown for human-readable state
- Files for message passing
- Git for version control

### Observable Systems

Full visibility into agent behavior:
- Structured logging (JSONL)
- Real-time TUI streaming
- Context bundle snapshots
- Hook-based instrumentation

### Self-Improvement

Systems that learn and evolve:
- Expert system accumulates knowledge
- Documentation auto-loads
- Patterns extracted from practice
- Meta-agents for code generation

---

## Additional Resources

- **Main Docs**: `README.md` - User-facing documentation
- **Architecture**: `docs/ZERO_TOUCH_ENGINEERING_SPEC.md` - Complete system spec
- **UX Design**: `docs/UX_ARCHITECTURE_SPEC.md` - TUI architecture
- **Build Guide**: `docs/BUILD.md` - Self-bootstrapping process
- **Task Board**: `tasks.md` - Current build progress
- **Specs**: `specs/` - Phase implementation specs

---

## When Working on ADW

### For Implementation Tasks

1. Check `tasks.md` for context
2. Read relevant spec in `specs/`
3. Understand dependencies
4. Execute in appropriate worktree
5. Update task status when complete

### For Bug Fixes

1. Reproduce the issue
2. Check recent commits for context
3. Fix the bug with minimal changes
4. Add test if missing
5. Update relevant documentation

### For New Features

1. Discuss approach first
2. Create spec if complex
3. Add tasks to `tasks.md`
4. Use appropriate workflow
5. Document in README.md

### For Refactoring

1. Ensure tests exist first
2. Refactor incrementally
3. Keep tests passing
4. Update documentation
5. No feature changes mixed in

---

**Remember**: ADW builds itself. When in doubt, check how existing code handles similar patterns. The codebase is self-documenting through its structure and conventions.
