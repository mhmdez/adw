# ADW Quick Start Guide

Get started with ADW in under 5 minutes.

## Prerequisites

- Python 3.11+
- Claude Code installed and configured
- Git repository

## Installation

```bash
# Using uv (recommended)
uv tool install adw-cli

# Or using pip
pip install adw-cli
```

## 1. Initialize Your Project

```bash
cd your-project
adw init
```

This creates:
- `.claude/` - Claude Code configuration
- `tasks.md` - Task tracking board
- `specs/` - Feature specifications

For deeper analysis:
```bash
adw init --smart  # Uses Claude Code to analyze your project
```

## 2. Create Your First Task

### Interactive Mode (Recommended for beginners)

```bash
adw new "Add user authentication"
```

This opens an interactive Claude Code session. The agent will:
1. Plan the implementation
2. Write the code
3. Update task status

### Autonomous Mode

Add tasks to `tasks.md` and let ADW process them:

```bash
# Add a task
adw add "Fix login button styling"

# Start autonomous processing
adw run
```

## 3. Monitor Progress

### TUI Dashboard

```bash
adw  # Opens interactive dashboard
```

Press:
- `?` for keyboard shortcuts
- `m` to send messages to agents
- `q` to quit

### CLI Commands

```bash
adw status        # Daemon status
adw list          # List tasks
adw logs abc123   # View task logs
```

## 4. Understanding tasks.md

Tasks in `tasks.md` use simple status markers:

```markdown
## Worktree: main

[✅, abc123de] Completed task
[🟡, def456gh] In-progress task
[⏰] Blocked task (waiting for dependency)
[] Ready to start task
```

### Task Tags

Control execution with inline tags:

```markdown
[] Complex feature {opus}    # Use Opus model
[] Quick fix {haiku}         # Use Haiku model
[] Standard task {sonnet}    # Use Sonnet (default)
```

## 5. Choose a Workflow

| Workflow | Use Case | Phases |
|----------|----------|--------|
| `simple` | Quick fixes | Build → Update |
| `standard` | Features | Plan → Build → Update |
| `sdlc` | Complex features | Plan → Implement → Test → Review → Document → Update |

```bash
adw new "Task" --workflow simple    # Quick fixes
adw new "Task" --workflow standard  # Most features
adw new "Task" --workflow sdlc      # Complex work
```

## 6. Next Steps

### Browse Examples

```bash
adw examples list           # See all categories
adw examples quickstart     # Getting started examples
adw examples beginner       # Beginner-friendly examples
adw examples search github  # Search by topic
```

### Learn More

- `adw --help` - CLI reference
- `adw <command> --help` - Command-specific help
- [README](../../README.md) - Full documentation
- [CLAUDE.md](../../CLAUDE.md) - Architecture reference

### Common Workflows

**Fix a bug:**
```bash
adw new "Fix: Login fails on mobile" --workflow simple
```

**Add a feature:**
```bash
adw new "Add dark mode toggle" --workflow standard
```

**Process GitHub issues:**
```bash
adw github watch --label adw
```

**Watch multiple tasks:**
```bash
adw run --limit 3  # Run up to 3 tasks concurrently
```

## Troubleshooting

### Claude Code Not Found

Ensure Claude Code is installed:
```bash
which claude
```

### Permission Errors

Run Claude Code with permissions:
```bash
claude --dangerously-skip-permissions
```

### Task Stuck

Cancel and retry:
```bash
adw cancel abc123de
adw retry abc123de
```

Or rollback:
```bash
adw rollback abc123de
```

## Get Help

```bash
adw doctor          # Check system status
adw --help          # Full command list
adw examples all    # All available examples
```
