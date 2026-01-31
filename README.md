# ADW - AI Developer Workflow CLI

Autonomous AI development orchestration. ADW is a self-improving build system that coordinates Claude Code agents to plan, implement, test, and review features with full parallelization and observability.

## What Makes ADW Different?

| Feature | ADW | Traditional CI/CD | Manual Claude Use |
|---------|-----|-------------------|-------------------|
| **Autonomous Execution** | ✅ Daemon picks up tasks | ⚠️ Manual triggers | ❌ Full manual |
| **Parallel Task Execution** | ✅ Multiple worktrees | ⚠️ Single branch | ❌ Sequential |
| **Dependency Management** | ✅ Auto-resolved | ⚠️ Manual DAG | ❌ Manual tracking |
| **Live Observability** | ✅ Real-time TUI + logs | ⚠️ Post-execution | ❌ None |
| **Bidirectional Communication** | ✅ Message injection | ❌ No interaction | ✅ Interactive |
| **Self-Improvement** | ✅ Expert system | ❌ Static | ⚠️ Manual learning |
| **GitHub Integration** | ✅ Issue → PR workflow | ⚠️ Custom scripts | ❌ Manual |
| **Workflow Flexibility** | ✅ 4 workflow types | ⚠️ Fixed pipelines | ✅ Flexible |

## Installation

```bash
# Using uv (recommended)
uv tool install adw

# Using pipx
pipx install adw

# Using pip
pip install adw
```

## Quick Start

### Interactive Mode (Manual)

```bash
# Initialize in your project
cd my-project
adw init

# Open interactive dashboard
adw

# Start a new feature discussion
adw new "add user authentication"
```

### Autonomous Mode (Zero-Touch)

```bash
# Initialize
cd my-project
adw init

# Add tasks to tasks.md (or generate from specs)
# Then start the autonomous daemon
adw run

# ADW will:
# - Pick up eligible tasks
# - Spawn agents in parallel
# - Handle dependencies automatically
# - Stream logs to TUI
# - Update task status atomically
```

## Commands

| Command | Description |
|---------|-------------|
| `adw` | Open interactive TUI dashboard with live task monitoring |
| `adw init` | Initialize ADW in current project |
| `adw new <description>` | Start a new task discussion |
| `adw run` | Start autonomous task execution daemon |
| `adw status` | Show task and spec status |
| `adw verify [task_id]` | Verify completed work |
| `adw approve [spec]` | Approve a pending spec |
| `adw worktree list` | List active worktrees |
| `adw worktree create <name>` | Create isolated worktree |
| `adw worktree remove <name>` | Remove worktree |
| `adw github watch` | Watch GitHub for new issues/PRs |
| `adw github process <issue>` | Process a GitHub issue as task |
| `adw update` | Update ADW to latest version |
| `adw doctor` | Check installation health |
| `adw version` | Show version info |

## Core Features

### 🤖 Autonomous Task Execution

ADW can run completely autonomously, picking up tasks from `tasks.md` and executing them in parallel:

```bash
adw run
```

The daemon:
- Monitors `tasks.md` for eligible tasks
- Checks dependencies and blocks
- Spawns agents in isolated worktrees
- Enforces concurrent task limits
- Streams live logs to the TUI

### 🎯 Interactive TUI Dashboard

Real-time monitoring with a Textual-based interface:

```bash
adw
```

Features:
- Live task status updates
- Streaming agent logs with syntax highlighting
- Send messages to running agents
- Task filtering and navigation
- Status bar with system metrics

### 🌳 Git Worktree Isolation

Execute tasks in parallel using isolated worktrees:

```bash
adw worktree create feature-auth
```

Each worktree gets:
- Isolated filesystem
- Dedicated port allocation
- Environment variable isolation
- Independent git state

### 📡 Bidirectional Agent Communication

Send messages to running agents:

```
# In TUI, press 'm' and type:
> Please add error handling for edge case X
```

Agents receive messages via hook and can respond in real-time.

### 🔄 Advanced Workflow System

Multiple workflow types:

**Simple Build**: Quick, well-defined tasks
```python
from adw.workflows import simple_workflow
simple_workflow(task_id, "Fix the login bug")
```

**Standard**: Plan → Implement → Update
```python
from adw.workflows import standard_workflow
standard_workflow(task_id, "Add user profile page")
```

**Full SDLC**: Plan → Implement → Test → Review → Document → Update
```python
from adw.workflows import run_sdlc_workflow
run_sdlc_workflow(task_id, spec_path, model="opus")
```

**Prototypes**: Scaffolding generators (Vite+Vue, uv scripts, Bun)

### 🔍 Full Observability

Hook system captures every agent action:

- **Context Bundles**: Automatic session snapshots
- **Universal Logger**: All tool calls and outputs logged
- **Custom Output Styles**: Concise formatting for agents
- **Load Bundle**: Resume from any previous session

### 🐙 GitHub Integration

Trigger workflows from GitHub:

```bash
# Polling mode
adw github watch --interval 300

# Process specific issue
adw github process 123
```

Automatically:
- Fetches issue details
- Creates task in tasks.md
- Spawns agent workflow
- Creates PR when complete

### 🧠 Self-Improving Expert System

ADW includes a meta-learning system:

```
# In Claude Code
/experts:cc_expert "How do I optimize parallel execution?"
/experts:cc_expert:improve
/load_ai_docs https://docs.anthropic.com/...
```

The expert system learns from documentation and improves its knowledge base over time.

## Project Structure

After running `adw init`, your project will have:

```
your-project/
├── .claude/
│   ├── commands/            # Slash commands for Claude
│   │   ├── discuss.md
│   │   ├── build.md
│   │   ├── verify.md
│   │   ├── plan.md
│   │   ├── implement.md
│   │   ├── test.md
│   │   ├── review.md
│   │   ├── document.md
│   │   ├── load_ai_docs.md
│   │   └── experts/
│   │       ├── cc_expert.md
│   │       └── cc_expert_improve.md
│   ├── hooks/               # Event hooks for observability
│   │   ├── check_messages.py
│   │   ├── context_bundle_builder.py
│   │   └── universal_logger.py
│   ├── output-styles/       # Custom output formatting
│   │   └── concise-done.md
│   ├── settings.json        # Hook configuration
│   └── agents/              # Specialized agent configs
│       ├── frontend.md
│       ├── backend.md
│       └── ...
├── agents/                  # Agent execution directories
│   └── {adw_id}/
│       ├── agent.log        # Structured agent logs
│       ├── adw_messages.jsonl  # Bidirectional messages
│       └── context/         # Session snapshots
├── specs/                   # Feature specifications
├── tasks.md                 # Task tracking board
├── CLAUDE.md                # Project instructions for Claude
└── ai_docs/                 # Documentation for expert system
```

## Slash Commands

Use these in Claude Code:

| Command | Purpose | Workflow Phase |
|---------|---------|----------------|
| `/discuss` | Plan a complex feature interactively | Planning |
| `/build` | Implement a simple, well-defined task | Implementation |
| `/plan` | Create detailed implementation plan | SDLC: Plan |
| `/implement` | Execute a task's implementation plan | SDLC: Implement |
| `/test` | Create and run comprehensive tests | SDLC: Test |
| `/review` | Review code quality and correctness | SDLC: Review |
| `/document` | Generate documentation for features | SDLC: Document |
| `/verify` | Review implementation before commit | Verification |
| `/status` | Check what needs attention | Monitoring |
| `/approve_spec` | Approve spec and create tasks | Planning |
| `/load_ai_docs` | Load external docs into expert system | Learning |
| `/experts:cc_expert` | Query the Claude Code expert system | Learning |
| `/experts:cc_expert:improve` | Improve expert knowledge base | Learning |

## Technical Capabilities

### Parallel Execution with Isolation

- **Git Worktrees**: Each task runs in isolated worktree
- **Port Allocation**: Automatic port assignment prevents conflicts
- **Environment Isolation**: Task-specific env vars and configuration
- **Concurrent Limits**: Configurable max parallel tasks

### Dependency Management

- **Task Dependencies**: Automatic dependency graph resolution
- **Blocking**: Tasks wait for dependencies to complete
- **Eligibility Checking**: Only ready tasks get scheduled

### Real-Time Observability

- **Structured Logging**: JSONL format with timestamps and context
- **Live Streaming**: TUI updates in real-time as agents work
- **Context Bundles**: Complete session snapshots for debugging
- **Message Injection**: Send instructions to running agents

### Workflow Orchestration

Multiple workflow types for different use cases:
- **Simple**: Quick fixes, no planning phase
- **Standard**: Planning + implementation
- **SDLC**: Full 6-phase development cycle
- **Prototype**: Project scaffolding generators

### Model Selection Strategy

- Opus for: Architecture decisions, complex reasoning, planning
- Sonnet for: Most implementation tasks (default)
- Haiku for: Simple, repetitive tasks

## Configuration

### CLAUDE.md

ADW adds an orchestration section to your `CLAUDE.md` (or creates one if it doesn't exist). This file tells Claude about your project structure, commands, and conventions.

### Project Detection

`adw init` automatically detects your project type:

- **Frontend**: React, Vue, Svelte, Next.js, Nuxt
- **Backend**: Python (FastAPI, Django), Node.js (Express, NestJS), Go
- **Monorepo**: pnpm workspaces, Lerna, Nx, Turborepo

And generates appropriate agent configurations.

### Autonomous Execution

Configure the cron daemon in `.adw/config.json`:

```json
{
  "max_concurrent_tasks": 3,
  "check_interval": 60,
  "worktree_enabled": true,
  "default_workflow": "standard"
}
```

## Task Format

Tasks in `tasks.md` use ADW ID format with emoji status indicators:

```markdown
## Worktree: main

[✅, abc123de] Setup database schema
[🟡, def456gh] Implement login endpoint
[⏰] Add OAuth integration (blocked)
[] Create user profile page

## Worktree: feature-payments

[🟡, ghi789jk] Integrate Stripe API
[] Add payment history view
```

Status indicators:
- `[]` - Ready to start (pending)
- `[⏰]` - Blocked by dependencies
- `[🟡, adw_id]` - In progress
- `[✅, adw_id]` - Completed
- `[❌, adw_id]` - Failed

Each task gets a unique ADW ID (8-char hex) for tracking across the system.

## Spec Format

Specs in `specs/` follow this format:

```markdown
# Feature Name

Status: PENDING_APPROVAL

## Overview
What this feature does...

## Technical Approach
How it will be implemented...

## Files to Modify
- src/components/Login.tsx
- src/api/auth.ts

## Testing Strategy
How it will be tested...

## Acceptance Criteria
- [ ] User can log in
- [ ] Session persists
```

## Architecture

ADW is built on a modular architecture:

- **Agent System**: Process management, state persistence, model selection
- **TUI**: Textual-based dashboard with reactive state
- **Workflows**: Simple, Standard, SDLC, and Prototype generators
- **Triggers**: Cron daemon, GitHub polling, webhook handlers
- **Protocol**: Message passing, log streaming
- **Integrations**: GitHub API, more coming soon

All components communicate through:
- Filesystem protocol (JSONL logs, messages)
- Git worktrees for isolation
- Ports for network isolation
- Environment variables for configuration

## Requirements

- Python 3.11+
- [Claude Code](https://claude.ai/code) installed
- Git 2.35+ (for worktree support)

## Use Cases

### 1. Solo Developer: Autonomous Feature Development

```bash
# Add tasks to tasks.md manually or via /discuss
adw run
# Walk away. ADW executes tasks in parallel, handling dependencies.
# Check TUI for progress: adw
```

### 2. Team: GitHub-Triggered Workflows

```bash
# Start GitHub watcher
adw github watch

# When issue #123 is labeled "adw:feature"
# → ADW creates task
# → Spawns worktree
# → Runs full SDLC workflow
# → Creates PR with implementation
```

### 3. Code Review: Interactive Agent Assistance

```bash
adw
# Select running task
# Press 'm' to send message:
> "Add unit tests for error cases"
# Agent receives message and adds tests
```

### 4. Self-Improvement: Expert System Learning

```
# In Claude Code
/load_ai_docs https://docs.example.com/api
/experts:cc_expert "What's the best way to handle rate limiting?"
/experts:cc_expert:improve
```

### 5. Prototyping: Fast Project Scaffolding

```python
from adw.workflows import run_prototype_workflow
run_prototype_workflow("vite_vue", "my-new-app")
# → Creates Vite+Vue project
# → Sets up routing, state management
# → Generates documentation
```

## Development

```bash
# Clone the repo
git clone https://github.com/mhmdez/adw.git
cd adw

# Install dependencies (includes textual, watchfiles, httpx)
uv sync

# Run locally
uv run adw --help

# Run tests
uv run pytest

# Run with coverage
uv run pytest --cov=src/adw --cov-report=html

# Lint and type check
uv run ruff check .
uv run mypy src

# Run the TUI in development
uv run adw

# Test autonomous execution (dry run)
uv run adw run --dry-run
```

## Testing ADW with ADW

ADW was built using itself! See `tasks.md` for the meta-build process:

```bash
# ADW building ADW
adw run
# → Picks up tasks from tasks.md
# → Executes in parallel worktrees
# → Uses hooks for observability
# → Updates task status atomically
```

## Roadmap

ADW is under active development. Current status:

- ✅ Core agent system (Phase 1-5)
- ✅ Message injection (Phase 6)
- ✅ Autonomous execution (Phase 7)
- ✅ Worktree isolation (Phase 8)
- ✅ Observability hooks (Phase 9)
- ✅ SDLC workflows (Phase 10)
- ✅ GitHub integration (Phase 11)
- ✅ Expert system (Phase 12)
- 🚧 CLI polish and full integration
- 🚧 Webhook handlers
- 📋 VSCode extension
- 📋 Slack/Discord integration
- 📋 Cloud execution platform

See `tasks.md` for detailed build progress.

## Contributing

Contributions are welcome! ADW uses itself for development.

```bash
# Fork and clone
git clone https://github.com/yourusername/adw.git
cd adw

# Install with dev dependencies
uv sync

# Make changes and run tests
uv run pytest

# Submit PR
# ADW can help review: /review
```

## Philosophy

ADW embraces:
- **Zero-Touch Engineering**: Automation over manual orchestration
- **Parallel by Default**: Worktrees enable true parallelization
- **Observable Systems**: Full visibility into agent behavior
- **Self-Improvement**: Systems that learn and evolve
- **Filesystem Protocols**: Simple, debuggable, language-agnostic

## License

MIT License - see [LICENSE](LICENSE) for details.

## Links

- [GitHub Repository](https://github.com/mhmdez/adw)
- [Issue Tracker](https://github.com/mhmdez/adw/issues)
- [Claude Code Documentation](https://claude.ai/code)

---

Built with ADW by ADW 🤖
