# ADW UX Enhancements Spec

## Overview
Enhance ADW CLI for smooth human workflow with task management, monitoring, and shell integration.

## Features

### 1. Shell Autocomplete
- Tab completion for commands
- Dynamic completion for task IDs (from tasks.md)
- Completion for worktree names
- Support: bash, zsh, fish

### 2. Task Management Commands
```bash
adw add "description"      # Quick add task to tasks.md
adw list                   # Show all tasks with status
adw list --running         # Show only running tasks
adw list --pending         # Show only pending tasks
adw pause <task-id>        # Pause running task
adw resume <task-id>       # Resume paused task
adw cancel <task-id>       # Cancel running/pending task
adw retry <task-id>        # Retry failed task
adw priority <id> <1-5>    # Set task priority
```

### 3. Monitoring Commands
```bash
adw watch                  # Follow daemon output (like tail -f)
adw logs <task-id>         # Stream agent output for task
adw progress               # Show progress dashboard
```

### 4. Status Improvements
- Fix `adw status` to read tasks.md correctly
- Show running tasks with phase (plan/implement)
- Show recent completions/failures
- Show daemon status (running/stopped)

### 5. Notifications
- Desktop notification on task complete/fail
- Optional webhook callback
- Sound alert option

### 6. Other Usability
- Colored output with rich formatting
- Spinner/progress indicators
- Confirmation prompts for destructive actions
- `adw config` for user preferences
- `adw history` for recent task runs

## Implementation Priority
1. Fix `adw status` + `adw list`
2. `adw add`
3. Shell autocomplete
4. `adw watch` + `adw logs`
5. Control commands (pause/resume/cancel/retry)
6. Notifications
