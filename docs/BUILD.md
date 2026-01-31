# Building ADW: Self-Bootstrapping System

> **Meta-Engineering**: Building ADW using ADW principles

This document explains how ADW builds itself using its own task management and agentic workflow patterns.

---

## Overview

ADW is designed to bootstrap itself:

1. **Phase 1-3**: Manual bootstrap using `scripts/bootstrap.py`
2. **Phase 4+**: ADW takes over, building itself

The system uses:
- `tasks.md` as the central task board
- Phase specs in `specs/` as implementation guides
- Claude Code agents to execute tasks
- Dependency tracking via `[⏰]` blocked markers

---

## Quick Start

```bash
# 1. Ensure Claude Code is installed
claude --version

# 2. Run the bootstrap (starts with Phase 1)
python scripts/bootstrap.py

# 3. Once Phase 4 is complete, ADW can take over
adw run
```

---

## Build Phases

| Phase | Name | Description | Self-Building? |
|-------|------|-------------|----------------|
| 1 | Foundation | Core models, executor, state | Bootstrap |
| 2 | TUI Shell | Empty dashboard layout | Bootstrap |
| 3 | Task System | Parser, widgets, state sync | Bootstrap |
| 4 | Agent System | Spawn, manage, workflows | **ADW takes over** |
| 5 | Log Streaming | Watch files, display logs | ADW |
| 6 | Messages | User → Agent communication | ADW |
| 7 | Cron | Autonomous execution | ADW |
| 8 | Worktrees | Parallel isolation | ADW |
| 9 | Observability | Hooks, context bundles | ADW |
| 10 | Workflows | SDLC, prototypes | ADW |
| 11 | GitHub | External integration | ADW |
| 12 | Self-Improvement | Expert systems | ADW |

---

## Bootstrap Script

The `scripts/bootstrap.py` script handles initial bootstrapping:

```bash
# Run all eligible tasks
python scripts/bootstrap.py

# Run only up to phase 3
python scripts/bootstrap.py --phase 3

# Dry run - see what would happen
python scripts/bootstrap.py --dry-run

# Run specific task
python scripts/bootstrap.py --task "Create src/adw/agent/models.py"
```

### How Bootstrap Works

1. **Parses** `tasks.md` to find all tasks
2. **Identifies eligible** tasks (not blocked, not done)
3. **Executes** each task with Claude Code
4. **Updates** task status in `tasks.md`
5. **Re-checks** eligibility after each task
6. **Stops** on failure (fix and re-run)

---

## Task Board Structure

`tasks.md` uses this format:

```markdown
## Worktree: phase-01-foundation

[] Task ready to start
[⏰] Task blocked until above tasks complete
[🟡, abc12345] Task in progress (shows ADW ID)
[✅, def67890] Task completed (shows ADW ID)
[❌, ghi78901] Task failed // Failed: error message

[] Task with tags {opus}
[] Another task {sonnet, priority:high}
```

### Status Markers

| Marker | Meaning |
|--------|---------|
| `[]` | Ready to start |
| `[⏰]` | Blocked (waiting for dependencies) |
| `[🟡, id]` | In progress |
| `[✅, id]` | Completed |
| `[❌, id]` | Failed |

### Tags

| Tag | Effect |
|-----|--------|
| `{opus}` | Use Claude Opus |
| `{sonnet}` | Use Claude Sonnet (default) |

---

## Dependency System

Tasks within a worktree section are ordered. A `[⏰]` blocked task becomes eligible when ALL tasks above it are `[✅]` completed.

```markdown
## Worktree: example

[] First task          ← Eligible immediately
[⏰] Second task       ← Eligible after first completes
[⏰] Third task        ← Eligible after first AND second complete
```

This ensures proper build order without complex dependency graphs.

---

## Phase Specs

Each phase has a detailed specification in `specs/`:

- `specs/phase-01-foundation.md`
- `specs/phase-02-tui-shell.md`
- `specs/phase-03-task-system.md`
- `specs/phase-04-agent-system.md`
- `specs/phase-05-log-streaming.md`
- `specs/phase-06-to-12-summary.md`

Specs contain:
- Objective
- Deliverables with code
- File structure
- Validation criteria

---

## Transition to Self-Building

After Phase 4 (Agent System), ADW can build itself:

```bash
# Bootstrap completes phases 1-4
python scripts/bootstrap.py --phase 4

# ADW takes over for remaining phases
adw run
```

At this point:
- TUI is functional
- Agent spawning works
- Tasks can be executed automatically
- Logs stream to dashboard

---

## Monitoring Build Progress

### During Bootstrap

Watch the console output. Each task shows:
- Task description
- ADW ID assigned
- Model being used
- Success/failure status

### After ADW Takes Over

```bash
# Open the dashboard
adw

# Or run in background
adw run --background
```

The TUI shows:
- All tasks with status
- Running agents
- Live logs
- Progress indicators

---

## Troubleshooting

### Task Failed

1. Check the error in `tasks.md`
2. Look at logs in `agents/{adw_id}/`
3. Fix the issue manually if needed
4. Re-run bootstrap (it continues from where it stopped)

### Claude Code Not Found

```bash
# Install Claude Code
# Visit: https://claude.ai/code
```

### Dependency Issues

If tasks seem stuck:
1. Check that prerequisite tasks are `[✅]`
2. Ensure `[⏰]` markers are correct
3. Run `python scripts/bootstrap.py --dry-run` to see what's eligible

---

## Full Build Commands

```bash
# Complete fresh build
rm -rf agents/  # Clean previous runs
python scripts/bootstrap.py

# Or phase by phase
python scripts/bootstrap.py --phase 1
python scripts/bootstrap.py --phase 2
python scripts/bootstrap.py --phase 3
python scripts/bootstrap.py --phase 4
adw run  # ADW takes over
```

---

## Architecture Documents

For detailed specifications:

- `docs/ZERO_TOUCH_ENGINEERING_SPEC.md` - Complete system spec
- `docs/UX_ARCHITECTURE_SPEC.md` - TUI design and architecture
- `docs/BUILD.md` - This document

---

## Contributing

When adding new features:

1. Add tasks to `tasks.md` in appropriate phase
2. Create/update spec in `specs/`
3. Use `[⏰]` for dependencies
4. Tag complex tasks with `{opus}`
5. Run `adw run` or bootstrap to execute

The system will automatically pick up and execute new tasks!
