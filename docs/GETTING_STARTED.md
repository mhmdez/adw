# Getting Started with ADW

Get up and running with ADW in under 5 minutes.

## Prerequisites

Before you begin, ensure you have:

- **Python 3.11+** installed
- **Git 2.35+** (for worktree support)
- **Claude Code** installed and configured
- A **git repository** to work in

### Verify Prerequisites

```bash
python --version    # Should be 3.11+
git --version       # Should be 2.35+
which claude        # Should show Claude Code path
```

## Installation

Choose your preferred installation method:

```bash
# Using uv (recommended)
uv tool install adw-cli

# Using pipx
pipx install adw-cli

# Using pip
pip install adw-cli
```

Verify the installation:

```bash
adw --version
adw doctor  # Check system health
```

## Step 1: Initialize Your Project

Navigate to your project and initialize ADW:

```bash
cd your-project
adw init
```

This creates:
- `.claude/` - Claude Code configuration and hooks
- `tasks.md` - Task tracking board
- `specs/` - Feature specifications directory
- Updates `CLAUDE.md` with project context

### Smart Initialization (Recommended)

For better project understanding:

```bash
adw init --smart
```

This uses Claude Code to analyze your codebase and generate tailored configurations.

## Step 2: Create Your First Task

### Option A: Interactive Mode (Recommended for beginners)

Start an interactive session with Claude:

```bash
adw new "Add user authentication"
```

Claude will:
1. Analyze the task
2. Create an implementation plan
3. Execute the plan
4. Update task status automatically

### Option B: Add to Task Board

Add tasks to `tasks.md` for autonomous processing:

```bash
adw add "Fix login button styling"
adw add "Add dark mode toggle" --priority high
adw add "Refactor auth module" --tag backend
```

Then start the daemon:

```bash
adw run
```

## Step 3: Monitor Progress

### TUI Dashboard (Recommended)

Open the interactive dashboard:

```bash
adw
```

**Keyboard Shortcuts:**
| Key | Action |
|-----|--------|
| `?` | Show all keyboard shortcuts |
| `m` | Send message to running agent |
| `l` | Toggle log panel |
| `e` | Toggle event stream |
| `q` | Quit dashboard |

### CLI Monitoring

```bash
adw status           # Overview of tasks and daemon
adw list             # List all tasks
adw list --status pending  # Filter by status
adw logs <task_id>   # View specific task logs
adw logs <task_id> --follow  # Stream logs in real-time
```

## Understanding Task Format

Tasks in `tasks.md` use a simple format with status indicators:

```markdown
## Worktree: main

[✅, abc123de] Setup database schema
[🟡, def456gh] Implementing login endpoint
[⏰] Add OAuth integration (blocked)
[] Create user profile page
[❌, ghi789jk] Failed: Fix edge case
```

### Status Indicators

| Status | Meaning |
|--------|---------|
| `[]` | Pending - Ready to start |
| `[⏰]` | Blocked - Waiting for dependencies |
| `[🟡, id]` | In Progress - Currently executing |
| `[✅, id]` | Completed - Successfully finished |
| `[❌, id]` | Failed - Needs attention |

### Task Tags

Control execution with inline tags:

```markdown
[] Complex feature {opus}    # Use Opus model (complex reasoning)
[] Quick fix {haiku}         # Use Haiku model (simple tasks)
[] Standard task {sonnet}    # Use Sonnet model (default)
[] High priority {p0}        # Priority level (p0=highest, p3=lowest)
```

## Choosing a Workflow

ADW offers multiple workflows for different scenarios:

| Workflow | Best For | Phases |
|----------|----------|--------|
| `simple` | Quick fixes, well-defined tasks | Build → Update |
| `standard` | Features needing planning | Plan → Build → Update |
| `sdlc` | Complex features, full lifecycle | Plan → Implement → Test → Review → Document → Update |

**Specify workflow when creating tasks:**

```bash
adw new "Fix typo in readme" --workflow simple
adw new "Add user settings page" --workflow standard
adw new "Implement payment system" --workflow sdlc
```

## Next Steps

### Explore Examples

```bash
adw examples list              # See all categories
adw examples quickstart        # Getting started examples
adw examples beginner          # Beginner-friendly commands
adw examples search "github"   # Search by topic
```

### Common Workflows

**Fix a bug:**
```bash
adw new "Fix: Login fails on mobile" --workflow simple
```

**Add a feature:**
```bash
adw new "Add dark mode toggle" --workflow standard
```

**Complex feature with tests:**
```bash
adw new "Implement user authentication" --workflow sdlc
```

**Process GitHub issues:**
```bash
adw github watch --label adw
```

**Run multiple tasks in parallel:**
```bash
adw run --max-concurrent 3
```

### Learn More

- [CLI Reference](CLI_REFERENCE.md) - Complete command documentation
- [Configuration](CONFIGURATION.md) - All configuration options
- [Workflows Guide](examples/WORKFLOWS.md) - Detailed workflow documentation
- [GitHub Integration](examples/GITHUB_INTEGRATION.md) - GitHub automation
- [Troubleshooting](TROUBLESHOOTING.md) - Common issues and solutions

## Quick Reference Card

```bash
# Initialization
adw init              # Initialize project
adw init --smart      # Initialize with Claude analysis
adw doctor            # Check system health

# Task Management
adw new "task"        # Interactive task
adw add "task"        # Add to task board
adw list              # List tasks
adw status            # Show status
adw cancel <id>       # Cancel task
adw retry <id>        # Retry failed task

# Execution
adw run               # Start autonomous daemon
adw run --dry-run     # Preview what would run
adw pause             # Pause daemon
adw resume            # Resume daemon

# Monitoring
adw                   # Open TUI dashboard
adw logs <id>         # View task logs
adw watch             # Watch daemon activity

# Help
adw --help            # Main help
adw <command> --help  # Command-specific help
adw examples all      # All examples
```

## Getting Help

If you encounter issues:

1. Check the [Troubleshooting Guide](TROUBLESHOOTING.md)
2. Run `adw doctor` to diagnose problems
3. Check `adw examples search <topic>` for relevant examples
4. Report issues at https://github.com/mhmdez/adw/issues
