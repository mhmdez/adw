# ADW Troubleshooting Guide

Solutions for common issues when using ADW.

## Quick Diagnostics

Before diving into specific issues, run diagnostics:

```bash
# Check system health
adw doctor

# Enable debug mode for verbose output
ADW_DEBUG=1 adw <command>
# or
adw --debug <command>
```

---

## Installation Issues

### Python Version Too Old

**Error:** `Python 3.11+ required`

**Solution:**
```bash
# Check your Python version
python --version

# Install Python 3.11+ using pyenv
pyenv install 3.11
pyenv global 3.11

# Or using brew (macOS)
brew install python@3.11
```

### Claude Code Not Found

**Error:** `Claude Code not found` or `command not found: claude`

**Solution:**
```bash
# Verify Claude Code is installed
which claude

# If not installed, install it from:
# https://claude.ai/code

# Ensure it's in your PATH
export PATH="$PATH:/path/to/claude"
```

### Git Version Too Old

**Error:** `Git 2.35+ required for worktree support`

**Solution:**
```bash
# Check Git version
git --version

# Update Git (macOS)
brew upgrade git

# Update Git (Ubuntu/Debian)
sudo apt-get update && sudo apt-get install git
```

### Permission Denied During Install

**Error:** `Permission denied` when installing with pip

**Solution:**
```bash
# Use uv (recommended)
uv tool install adw-cli

# Or use pipx
pipx install adw-cli

# Or install to user directory
pip install --user adw-cli
```

---

## Initialization Issues

### Project Already Initialized

**Error:** `ADW already initialized. Use --force to overwrite.`

**Solution:**
```bash
# Reinitialize with force flag
adw init --force

# Or remove existing config first
rm -rf .claude/ tasks.md specs/
adw init
```

### Not a Git Repository

**Error:** `Not a git repository`

**Solution:**
```bash
# Initialize git first
git init

# Then initialize ADW
adw init
```

### Smart Init Fails

**Error:** `Smart initialization failed`

**Solution:**
```bash
# Fall back to quick init
adw init --quick

# Or check Claude Code permissions
claude --dangerously-skip-permissions
```

---

## Task Execution Issues

### Task Stuck in Progress

**Symptoms:** Task shows `[🟡, id]` for extended time

**Solutions:**

1. **Check if agent is running:**
   ```bash
   adw watch
   adw logs <task_id> --follow
   ```

2. **Cancel and retry:**
   ```bash
   adw cancel <task_id>
   adw retry <task_id>
   ```

3. **Rollback and restart:**
   ```bash
   adw rollback <task_id>
   adw retry <task_id>
   ```

### Task Keeps Failing

**Symptoms:** Task repeatedly fails with `[❌, id]`

**Solutions:**

1. **Check the escalation report:**
   ```bash
   adw escalation <task_id>
   ```

2. **View detailed logs:**
   ```bash
   adw logs <task_id>
   ```

3. **Break into smaller tasks:**
   Edit `tasks.md` to split the task

4. **Use a more capable model:**
   Add `{opus}` tag to the task

### Daemon Not Picking Up Tasks

**Symptoms:** Tasks stay `[]` (pending) but don't start

**Solutions:**

1. **Check daemon status:**
   ```bash
   adw status
   ```

2. **Check if daemon is paused:**
   ```bash
   adw resume  # Resume if paused
   ```

3. **Verify tasks are eligible:**
   ```bash
   adw run --dry-run
   ```

---

## Ink TUI (Node) Issues

### ADW CLI Not Found

**Symptoms:** TUI logs `ADW CLI not found` and falls back to raw Claude.

**Solutions:**
```bash
which adw
uv tool install adw-cli
```

Ensure the `adw` binary is on your PATH, then restart the TUI.

### No Live Events in TUI

**Symptoms:** Tasks run but the Ink TUI shows no streaming updates.

**Solutions:**
```bash
adw events --follow --json
```

If this fails, confirm the observability DB is writable and `adw` is up to date.

### Task Logs Missing

**Symptoms:** TUI shows `Agent log not available yet (no ADW ID assigned).`

**Solutions:**
- Run the daemon so tasks get an ADW ID: `adw run`
- Then check logs: `adw logs <task_id>`
- In fallback mode, logs live under `agents/<TASK-ID>/prompt/cc_raw_output.jsonl`

4. **Check for blocking tasks:**
   Look for `[⏰]` tasks above your pending task

5. **Restart the daemon:**
   ```bash
   # Stop existing daemon (Ctrl+C)
   adw run
   ```

### Claude Code Permission Errors

**Error:** `Claude Code requires --dangerously-skip-permissions`

**Solution:**
ADW needs Claude Code to run autonomously. Either:

1. **Configure Claude Code to allow autonomous execution**

2. **Or run with permissions flag:**
   ```bash
   claude --dangerously-skip-permissions
   ```

---

## TUI Dashboard Issues

### Dashboard Won't Start

**Error:** `Could not open terminal` or blank screen

**Solutions:**

1. **Check terminal compatibility:**
   Use a modern terminal (iTerm2, Alacritty, kitty, Windows Terminal)

2. **Try different terminal:**
   ```bash
   # Run in a different terminal emulator
   xterm -e adw
   ```

3. **Check TERM environment:**
   ```bash
   echo $TERM
   export TERM=xterm-256color
   adw
   ```

### Log Panel Empty

**Symptoms:** Dashboard shows no logs

**Solutions:**

1. **Verify agent is running:**
   ```bash
   adw status
   ```

2. **Check log file exists:**
   ```bash
   ls agents/*/agent.log
   ```

3. **Toggle log panel:**
   Press `l` in dashboard

### Keyboard Shortcuts Not Working

**Symptoms:** Key presses ignored

**Solutions:**

1. **Press `?` for help** - shows all shortcuts

2. **Check if modal is open** - press `Escape` to close

3. **Restart dashboard:**
   Press `q` and reopen with `adw`

---

## Git Worktree Issues

### Worktree Creation Fails

**Error:** `Failed to create worktree`

**Solutions:**

1. **Check for existing worktree:**
   ```bash
   adw worktree list
   git worktree list
   ```

2. **Remove stale worktree:**
   ```bash
   adw worktree remove <name> --force
   # or
   git worktree prune
   ```

3. **Verify git version:**
   ```bash
   git --version  # Needs 2.35+
   ```

### Changes Lost After Worktree Removal

**Prevention:**
- Always commit or stash changes before removing worktrees
- Use `adw worktree remove <name>` instead of `git worktree remove`

**Recovery:**
```bash
# Check git reflog
git reflog

# Recover commits
git checkout <commit-hash>
```

---

## Integration Issues

### GitHub Integration Not Working

**Error:** `GitHub authentication failed`

**Solutions:**

1. **Check gh CLI authentication:**
   ```bash
   gh auth status
   gh auth login
   ```

2. **Or set token in config:**
   ```bash
   adw config set github.token <your-token>
   ```

3. **Verify repository access:**
   ```bash
   gh repo view
   ```

### Slack Notifications Not Sending

**Error:** `Slack notification failed`

**Solutions:**

1. **Test connection:**
   ```bash
   adw slack test
   ```

2. **Verify credentials:**
   ```bash
   adw config show --section slack
   ```

3. **Check environment variables:**
   ```bash
   echo $SLACK_BOT_TOKEN
   echo $SLACK_SIGNING_SECRET
   ```

4. **Verify bot permissions:**
   - Ensure bot has `chat:write` and `channels:read` scopes
   - Ensure bot is added to the channel

### Linear/Notion Not Syncing

**Solutions:**

1. **Test connection:**
   ```bash
   adw linear test
   adw notion test
   ```

2. **Check API key:**
   ```bash
   adw config show --secrets --section linear
   adw config show --secrets --section notion
   ```

3. **Verify poll is running:**
   ```bash
   adw linear watch --dry-run
   adw notion watch --dry-run
   ```

---

## Configuration Issues

### Config File Corrupt

**Error:** `Failed to parse config.toml`

**Solutions:**

1. **Reset configuration:**
   ```bash
   adw config reset --yes
   ```

2. **Or manually fix:**
   ```bash
   adw config edit
   # Fix TOML syntax errors
   ```

3. **Backup and recreate:**
   ```bash
   mv ~/.adw/config.toml ~/.adw/config.toml.bak
   adw config show  # Creates new default config
   ```

### Environment Variables Not Applied

**Symptoms:** Config values don't match environment

**Solutions:**

1. **Verify variable is exported:**
   ```bash
   echo $SLACK_BOT_TOKEN
   export SLACK_BOT_TOKEN="xoxb-..."
   ```

2. **Check variable name:**
   Environment variables are case-sensitive

3. **Reload config:**
   Restart the command/daemon after setting variables

### Wrong Config File Loaded

**Symptoms:** Settings don't match expected

**Solutions:**

1. **Check which config is used:**
   ```bash
   adw config path
   ```

2. **Use custom config:**
   ```bash
   export ADW_CONFIG=/path/to/config.toml
   ```

---

## Performance Issues

### Daemon Using Too Much CPU

**Solutions:**

1. **Increase poll interval:**
   ```bash
   adw config set daemon.poll_interval 30
   ```

2. **Reduce concurrent tasks:**
   ```bash
   adw config set daemon.max_concurrent 1
   ```

### Tasks Running Slowly

**Solutions:**

1. **Use faster model for simple tasks:**
   Add `{haiku}` tag to simple tasks

2. **Reduce task scope:**
   Break large tasks into smaller ones

3. **Enable worktrees for parallelism:**
   ```bash
   adw config set workspace.enable_worktrees true
   ```

### Out of Memory

**Symptoms:** Tasks killed, system slowdown

**Solutions:**

1. **Reduce concurrent tasks:**
   ```bash
   adw config set daemon.max_concurrent 1
   ```

2. **Increase swap space (Linux):**
   ```bash
   sudo fallocate -l 4G /swapfile
   sudo mkswap /swapfile
   sudo swapon /swapfile
   ```

---

## Recovery Operations

### Rollback a Failed Task

```bash
# Rollback all changes from a task
adw rollback <task_id>

# Rollback to specific checkpoint
adw checkpoints <task_id>  # List checkpoints
adw rollback <task_id> --checkpoint <checkpoint_id>
```

### Resume Interrupted Task

```bash
# Resume from last checkpoint
adw resume-task <task_id>
```

### Recover from Corrupted State

```bash
# Reset ADW state
rm -rf agents/*/
rm .adw/*.jsonl

# Reinitialize
adw init --force
```

### Clean Up Stale Processes

```bash
# Find Claude processes
ps aux | grep claude

# Kill if necessary
pkill -f "claude.*adw"
```

---

## Common Error Messages

### "Task not found"

**Cause:** Invalid task ID

**Solution:**
```bash
adw list --all  # Find correct task ID
```

### "Dependency not found: X"

**Cause:** Missing Python package

**Solution:**
```bash
pip install X
# or
uv pip install X
```

### "Rate limit exceeded"

**Cause:** Too many API calls

**Solution:**
- Wait and retry
- Increase poll intervals
- Use webhook triggers instead of polling

### "Connection refused"

**Cause:** Service not running

**Solution:**
```bash
# For webhook server
adw webhook start

# For Slack server
adw slack start
```

---

## Getting Help

If you can't resolve an issue:

1. **Check examples:**
   ```bash
   adw examples search <topic>
   ```

2. **Enable debug mode:**
   ```bash
   ADW_DEBUG=1 adw <command> 2>&1 | tee debug.log
   ```

3. **Report issue:**
   - Visit https://github.com/mhmdez/adw/issues
   - Include:
     - ADW version (`adw --version`)
     - Python version (`python --version`)
     - OS and version
     - Debug output
     - Steps to reproduce

---

## See Also

- [Getting Started](GETTING_STARTED.md) - Setup guide
- [CLI Reference](CLI_REFERENCE.md) - Command documentation
- [Configuration](CONFIGURATION.md) - All configuration options
