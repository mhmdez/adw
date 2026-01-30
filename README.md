# ADW - AI Developer Workflow CLI

Orchestrate Claude Code for any project. ADW provides a structured workflow for planning, implementing, and reviewing features with AI assistance.

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

```bash
# Initialize in your project
cd my-project
adw init

# Open interactive dashboard
adw

# Start a new feature discussion
adw new "add user authentication"
```

## Commands

| Command | Description |
|---------|-------------|
| `adw` | Open interactive dashboard |
| `adw init` | Initialize ADW in current project |
| `adw new <description>` | Start a new task discussion |
| `adw status` | Show task and spec status |
| `adw verify [task_id]` | Verify completed work |
| `adw approve [spec]` | Approve a pending spec |
| `adw update` | Update ADW to latest version |
| `adw doctor` | Check installation health |
| `adw version` | Show version info |

## Workflow

### 1. Discuss & Plan

Start with `/discuss` to explore a feature:

```bash
adw new "implement dark mode"
```

This opens Claude Code and:
- Explores your codebase for relevant patterns
- Asks clarifying questions
- Creates a detailed spec in `specs/dark-mode.md`

### 2. Approve & Decompose

Review and approve the spec:

```bash
adw approve dark-mode
```

Claude decomposes the spec into implementable tasks in `tasks.md`.

### 3. Implement

Work through tasks:

```bash
# In Claude Code
/implement TASK-001
```

### 4. Verify & Commit

Review changes before committing:

```bash
adw verify TASK-001
```

Claude reviews the implementation, runs tests, and creates a commit if approved.

## Project Structure

After running `adw init`, your project will have:

```
your-project/
├── .claude/
│   ├── commands/     # Slash commands for Claude
│   │   ├── discuss.md
│   │   ├── build.md
│   │   ├── verify.md
│   │   └── ...
│   └── agents/       # Specialized agent configs
│       ├── frontend.md
│       ├── backend.md
│       └── ...
├── specs/            # Feature specifications
├── tasks.md          # Task tracking
└── CLAUDE.md         # Project instructions for Claude
```

## Slash Commands

Use these in Claude Code:

| Command | Purpose |
|---------|---------|
| `/discuss` | Plan a complex feature interactively |
| `/build` | Implement a simple, well-defined task |
| `/verify` | Review implementation before commit |
| `/status` | Check what needs attention |
| `/approve_spec` | Approve spec and create tasks |
| `/plan` | Create detailed implementation plan |
| `/implement` | Execute a task's implementation plan |
| `/review` | Review code or pull request |

## Configuration

### CLAUDE.md

ADW adds an orchestration section to your `CLAUDE.md` (or creates one if it doesn't exist). This file tells Claude about your project structure, commands, and conventions.

### Project Detection

`adw init` automatically detects your project type:

- **Frontend**: React, Vue, Svelte, Next.js, Nuxt
- **Backend**: Python (FastAPI, Django), Node.js (Express, NestJS), Go
- **Monorepo**: pnpm workspaces, Lerna, Nx, Turborepo

And generates appropriate agent configurations.

## Task Format

Tasks in `tasks.md` follow this format:

```markdown
- [ ] TASK-001: Implement login endpoint
  - Status: pending
  - Spec: specs/authentication.md
- [x] TASK-002: Setup database schema (done)
- [-] TASK-003: Add OAuth (blocked)
```

Status values:
- `pending` - Not started
- `in_progress` - Currently being worked on
- `done` - Completed
- `blocked` - Waiting on something
- `failed` - Could not complete

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

## Requirements

- Python 3.10+
- [Claude Code](https://claude.ai/code) installed

## Development

```bash
# Clone the repo
git clone https://github.com/studibudi/adw.git
cd adw

# Install dependencies
uv sync

# Run locally
uv run adw --help

# Run tests
uv run pytest

# Lint
uv run ruff check .
uv run mypy src
```

## License

MIT License - see [LICENSE](LICENSE) for details.
