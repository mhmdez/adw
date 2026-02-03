# ADW CLI Reference

Complete reference for all ADW command-line interface commands.

## Global Options

These options apply to the main `adw` command:

| Option | Description |
|--------|-------------|
| `--version`, `-v` | Show version information |
| `--debug`, `-d` | Enable debug mode with verbose error output |
| `--no-update-check` | Skip automatic update check |
| `--help` | Show help message |

```bash
adw --version
adw --debug <command>
```

## Core Commands

### `adw`

Open the interactive TUI dashboard.

```bash
adw
```

The dashboard provides:
- Real-time task status monitoring
- Live log streaming with syntax highlighting
- Message injection to running agents
- Event stream visualization

**Keyboard shortcuts in dashboard:**
| Key | Action |
|-----|--------|
| `?` | Show help/keyboard shortcuts |
| `m` | Send message to agent |
| `l` | Toggle log panel |
| `e` | Toggle event stream |
| `q` | Quit |

### `adw dashboard`

Alias for opening the TUI dashboard.

```bash
adw dashboard
```

### `adw init`

Initialize ADW in a project directory.

```bash
adw init [PATH] [OPTIONS]
```

**Arguments:**
| Argument | Description |
|----------|-------------|
| `PATH` | Project path (default: current directory) |

**Options:**
| Option | Description |
|--------|-------------|
| `--force`, `-f` | Overwrite existing files |
| `--smart`, `-s` | Use Claude Code analysis (slower but better) |
| `--quick`, `-q` | Skip analysis, use templates only |
| `--qmd/--no-qmd` | Enable/disable semantic search integration |

**Examples:**
```bash
adw init                    # Initialize current directory
adw init ./my-project       # Initialize specific directory
adw init --smart            # Use Claude Code for analysis
adw init --force --quick    # Fast init, overwrite existing
```

### `adw new`

Start a new interactive task discussion with Claude.

```bash
adw new <DESCRIPTION> [OPTIONS]
```

**Arguments:**
| Argument | Description |
|----------|-------------|
| `DESCRIPTION` | Task description |

**Options:**
| Option | Description |
|--------|-------------|
| `--workflow`, `-w` | Workflow type: simple, standard, sdlc |

**Examples:**
```bash
adw new "Add user authentication"
adw new "Fix login bug" --workflow simple
adw new "Implement payment system" --workflow sdlc
```

### `adw add`

Add a new task to `tasks.md`.

```bash
adw add <DESCRIPTION> [OPTIONS]
```

**Options:**
| Option | Description |
|--------|-------------|
| `--priority`, `-p` | Priority: high, medium, low |
| `--tag`, `-t` | Add tags (can be used multiple times) |

**Examples:**
```bash
adw add "Fix typo in readme"
adw add "Urgent security fix" --priority high
adw add "Refactor auth" --tag backend --tag auth
```

### `adw list`

List tasks from `tasks.md`.

```bash
adw list [OPTIONS]
```

**Options:**
| Option | Description |
|--------|-------------|
| `--status`, `-s` | Filter by status: pending, in_progress, completed, failed |
| `--all`, `-a` | Include completed tasks |

**Examples:**
```bash
adw list
adw list --status pending
adw list --all
```

### `adw status`

Show overview of tasks and daemon status.

```bash
adw status
```

### `adw run`

Start the autonomous task execution daemon.

```bash
adw run [OPTIONS]
```

**Options:**
| Option | Description | Default |
|--------|-------------|---------|
| `--poll-interval`, `-p` | Seconds between task checks | 5 |
| `--max-concurrent`, `-m` | Maximum simultaneous agents | 3 |
| `--tasks-file`, `-f` | Path to tasks.md | tasks.md |
| `--dry-run`, `-d` | Show eligible tasks without running | false |
| `--no-notifications` | Disable desktop notifications | false |

**Examples:**
```bash
adw run
adw run --max-concurrent 5
adw run --dry-run
adw run --poll-interval 10 --no-notifications
```

### `adw cancel`

Cancel a running or pending task.

```bash
adw cancel <TASK_ID>
```

**Examples:**
```bash
adw cancel abc123de
```

### `adw retry`

Retry a failed task.

```bash
adw retry <TASK_ID>
```

**Examples:**
```bash
adw retry abc123de
```

### `adw verify`

Verify completed task before committing.

```bash
adw verify [TASK_ID]
```

### `adw history`

Show task execution history.

```bash
adw history [OPTIONS]
```

**Options:**
| Option | Description | Default |
|--------|-------------|---------|
| `--days`, `-d` | Number of days to show | 7 |
| `--failed`, `-f` | Show only failed tasks | false |
| `--all`, `-a` | Show all history | false |

---

## Monitoring Commands

### `adw watch`

Watch daemon activity in real-time.

```bash
adw watch [OPTIONS]
```

**Options:**
| Option | Description |
|--------|-------------|
| `--once` | Show once and exit |

### `adw logs`

View logs for a specific task.

```bash
adw logs <TASK_ID> [OPTIONS]
```

**Options:**
| Option | Description | Default |
|--------|-------------|---------|
| `--follow`, `-f` | Follow logs (like tail -f) | false |
| `--lines`, `-n` | Number of lines to show | 50 |

**Examples:**
```bash
adw logs abc123de
adw logs abc123de --follow
adw logs abc123de -n 100
```

### `adw pause`

Pause the daemon (running tasks will finish).

```bash
adw pause
```

### `adw resume`

Resume a paused daemon.

```bash
adw resume
```

---

## Approval Commands

### `adw approve`

Approve a pending spec and decompose into tasks.

```bash
adw approve <SPEC_NAME>
```

### `adw approve-task`

Approve a task awaiting human review.

```bash
adw approve-task <TASK_ID>
```

### `adw reject-task`

Reject a task with a reason.

```bash
adw reject-task <TASK_ID> --reason <REASON>
```

**Options:**
| Option | Description |
|--------|-------------|
| `--reason`, `-r` | Rejection reason (required) |

### `adw continue-task`

Add iterative feedback to a task.

```bash
adw continue-task <TASK_ID> <FEEDBACK>
```

### `adw pending-approvals`

List all tasks awaiting approval.

```bash
adw pending-approvals
```

---

## Git Worktree Commands

### `adw worktree list`

List all git worktrees.

```bash
adw worktree list
```

### `adw worktree create`

Create a new isolated worktree.

```bash
adw worktree create <NAME> [OPTIONS]
```

**Options:**
| Option | Description |
|--------|-------------|
| `--branch`, `-b` | Branch name for the worktree |

**Examples:**
```bash
adw worktree create feature-auth
adw worktree create hotfix-123 --branch hotfix/issue-123
```

### `adw worktree remove`

Remove a worktree.

```bash
adw worktree remove <NAME> [OPTIONS]
```

**Options:**
| Option | Description |
|--------|-------------|
| `--force`, `-f` | Force removal with uncommitted changes |

---

## GitHub Integration Commands

### `adw github watch`

Watch GitHub for new issues with a specific label.

```bash
adw github watch [OPTIONS]
```

**Options:**
| Option | Description | Default |
|--------|-------------|---------|
| `--label`, `-l` | Label to watch | adw |
| `--interval`, `-i` | Seconds between checks | 300 |
| `--dry-run`, `-d` | Show what would run | false |

**Examples:**
```bash
adw github watch
adw github watch --label feature-request --interval 60
adw github watch --dry-run
```

### `adw github process`

Process a specific GitHub issue.

```bash
adw github process <ISSUE_NUMBER> [OPTIONS]
```

**Options:**
| Option | Description |
|--------|-------------|
| `--dry-run`, `-d` | Show without executing |

**Examples:**
```bash
adw github process 123
adw github process 123 --dry-run
```

### `adw github watch-pr`

Watch a PR for review comments.

```bash
adw github watch-pr <PR_NUMBER> [OPTIONS]
```

**Options:**
| Option | Description | Default |
|--------|-------------|---------|
| `--interval`, `-i` | Seconds between checks | 60 |
| `--auto-fix`, `-a` | Auto-fix actionable comments | false |
| `--dry-run`, `-d` | Show without fixing | false |

### `adw github fix-comments`

Fix actionable review comments on a PR.

```bash
adw github fix-comments <PR_NUMBER> [OPTIONS]
```

**Options:**
| Option | Description |
|--------|-------------|
| `--all`, `-a` | Fix all pending comments |
| `--dry-run`, `-d` | Show without fixing |

---

## Integration Commands

### Notion Integration

#### `adw notion watch`

Watch Notion database for new tasks.

```bash
adw notion watch [OPTIONS]
```

**Options:**
| Option | Description | Default |
|--------|-------------|---------|
| `--interval`, `-i` | Seconds between checks | 60 |
| `--dry-run`, `-d` | Show what would run | false |
| `--database-id`, `-db` | Override database ID | - |

#### `adw notion test`

Test Notion connection.

```bash
adw notion test
```

#### `adw notion process`

Process pending Notion tasks once.

```bash
adw notion process [OPTIONS]
```

**Options:**
| Option | Description |
|--------|-------------|
| `--dry-run`, `-d` | Show without processing |

### Slack Integration

#### `adw slack start`

Start Slack webhook server.

```bash
adw slack start [OPTIONS]
```

**Options:**
| Option | Description | Default |
|--------|-------------|---------|
| `--port`, `-p` | Port to listen on | 3000 |
| `--host`, `-h` | Host to bind | 0.0.0.0 |
| `--reload` | Enable auto-reload | false |

#### `adw slack test`

Test Slack connection.

```bash
adw slack test
```

#### `adw slack send`

Send a test message to Slack.

```bash
adw slack send <CHANNEL> <MESSAGE>
```

#### `adw slack notify`

Notify a task's Slack thread.

```bash
adw slack notify <ADW_ID> [OPTIONS]
```

**Options:**
| Option | Description |
|--------|-------------|
| `--event`, `-e` | Event: started, completed, failed, approval |
| `--error` | Error message (for failed) |
| `--pr-url` | PR URL (for completed) |

### Linear Integration

#### `adw linear watch`

Watch Linear for new issues.

```bash
adw linear watch [OPTIONS]
```

**Options:**
| Option | Description | Default |
|--------|-------------|---------|
| `--interval`, `-i` | Seconds between checks | 60 |
| `--dry-run`, `-d` | Show what would run | false |
| `--team-id`, `-t` | Override team ID | - |

#### `adw linear test`

Test Linear connection.

```bash
adw linear test
```

#### `adw linear process`

Process pending Linear issues once.

```bash
adw linear process [OPTIONS]
```

#### `adw linear sync`

Sync a specific Linear issue.

```bash
adw linear sync <ISSUE_IDENTIFIER> [OPTIONS]
```

**Examples:**
```bash
adw linear sync TEAM-123
adw linear sync TEAM-123 --dry-run
```

---

## PR Linking Commands (Multi-Repo)

### `adw pr link`

Link multiple PRs for coordinated changes.

```bash
adw pr link <PR1> <PR2> [...] [OPTIONS]
```

**Options:**
| Option | Description |
|--------|-------------|
| `--description`, `-d` | Description of linked PRs |
| `--no-atomic` | Disable atomic merge requirement |

**Examples:**
```bash
adw pr link owner/repo#123 owner/other#456
adw pr link #123 #456 -d "Feature X across repos"
```

### `adw pr list`

List PR link groups.

```bash
adw pr list [OPTIONS]
```

**Options:**
| Option | Description |
|--------|-------------|
| `--all`, `-a` | Include completed groups |

### `adw pr show`

Show details of a PR link group.

```bash
adw pr show <GROUP_ID> [OPTIONS]
```

**Options:**
| Option | Description |
|--------|-------------|
| `--refresh`, `-r` | Refresh status from GitHub |

### `adw pr merge`

Merge all PRs in a link group.

```bash
adw pr merge <GROUP_ID> [OPTIONS]
```

**Options:**
| Option | Description | Default |
|--------|-------------|---------|
| `--method`, `-m` | Merge method: squash, merge, rebase | squash |
| `--force`, `-f` | Force merge if not all ready | false |

### `adw pr unlink`

Cancel a PR link group.

```bash
adw pr unlink <GROUP_ID>
```

---

## Webhook Commands

### `adw webhook start`

Start the webhook server for external triggers.

```bash
adw webhook start [OPTIONS]
```

**Options:**
| Option | Description | Default |
|--------|-------------|---------|
| `--host`, `-h` | Host to bind | 0.0.0.0 |
| `--port`, `-p` | Port to listen on | 8080 |
| `--reload` | Enable auto-reload | false |

### `adw webhook test`

Test a webhook URL.

```bash
adw webhook test <URL> [OPTIONS]
```

**Options:**
| Option | Description |
|--------|-------------|
| `--event`, `-e` | Event type: completed, failed, started |

### `adw webhook show`

Show current webhook configuration.

```bash
adw webhook show
```

### `adw webhook logs`

View webhook activity logs.

```bash
adw webhook logs [OPTIONS]
```

**Options:**
| Option | Description | Default |
|--------|-------------|---------|
| `--limit`, `-n` | Number of entries | 20 |
| `--key-id`, `-k` | Filter by API key ID | - |
| `--follow`, `-f` | Follow log output | false |

### API Key Management

#### `adw webhook key generate`

Generate a new API key.

```bash
adw webhook key generate <NAME> [OPTIONS]
```

**Options:**
| Option | Description | Default |
|--------|-------------|---------|
| `--rate-limit`, `-r` | Requests per hour | 100 |
| `--expires`, `-e` | Days until expiration | - |

#### `adw webhook key list`

List API keys.

```bash
adw webhook key list [OPTIONS]
```

**Options:**
| Option | Description |
|--------|-------------|
| `--all`, `-a` | Include disabled keys |

#### `adw webhook key revoke`

Permanently revoke an API key.

```bash
adw webhook key revoke <KEY_ID> [OPTIONS]
```

**Options:**
| Option | Description |
|--------|-------------|
| `--yes`, `-y` | Skip confirmation |

#### `adw webhook key disable`

Temporarily disable an API key.

```bash
adw webhook key disable <KEY_ID>
```

#### `adw webhook key enable`

Re-enable a disabled API key.

```bash
adw webhook key enable <KEY_ID>
```

---

## Configuration Commands

### `adw config show`

Show current configuration.

```bash
adw config show [OPTIONS]
```

**Options:**
| Option | Description |
|--------|-------------|
| `--secrets` | Show sensitive values |
| `--json` | Output as JSON |
| `--section` | Show specific section |

### `adw config get`

Get a specific configuration value.

```bash
adw config get <KEY>
```

**Examples:**
```bash
adw config get core.default_model
adw config get daemon.max_concurrent
```

### `adw config set`

Set a configuration value.

```bash
adw config set <KEY> <VALUE>
```

**Examples:**
```bash
adw config set core.default_model opus
adw config set daemon.max_concurrent 5
```

### `adw config keys`

List all available configuration keys.

```bash
adw config keys [OPTIONS]
```

**Options:**
| Option | Description |
|--------|-------------|
| `--section` | Filter by section |

### `adw config edit`

Open configuration in your editor ($EDITOR).

```bash
adw config edit
```

### `adw config path`

Show configuration file path.

```bash
adw config path
```

### `adw config reset`

Reset configuration to defaults.

```bash
adw config reset [OPTIONS]
```

**Options:**
| Option | Description |
|--------|-------------|
| `--section` | Reset only specific section |
| `--yes` | Skip confirmation |

### `adw config migrate`

Migrate from old configuration format.

```bash
adw config migrate
```

---

## Utility Commands

### `adw doctor`

Check ADW installation health.

```bash
adw doctor
```

Checks:
- Python version
- Git version
- Claude Code availability
- Configuration validity
- Integration connections

### `adw version`

Show version information.

```bash
adw version
```

### `adw update`

Update ADW to latest version.

```bash
adw update
```

### `adw completion`

Generate shell completion script.

```bash
adw completion [SHELL]
```

**Arguments:**
| Argument | Description |
|----------|-------------|
| `SHELL` | Shell type: bash, zsh, fish |

**Examples:**
```bash
# Add to your shell configuration
adw completion bash >> ~/.bashrc
adw completion zsh >> ~/.zshrc
adw completion fish >> ~/.config/fish/completions/adw.fish
```

### `adw notify`

Send a test desktop notification.

```bash
adw notify [MESSAGE] [OPTIONS]
```

**Options:**
| Option | Description |
|--------|-------------|
| `--sound`, `-s` | Notification sound |

### `adw refresh`

Refresh project context.

```bash
adw refresh [PATH] [OPTIONS]
```

**Options:**
| Option | Description |
|--------|-------------|
| `--full`, `-f` | Full Claude Code analysis |

### `adw examples`

Browse available examples.

```bash
adw examples <SUBCOMMAND>
```

**Subcommands:**
| Subcommand | Description |
|------------|-------------|
| `list` | Show all categories |
| `quickstart` | Getting started examples |
| `tasks` | Task management examples |
| `workflows` | Workflow examples |
| `github` | GitHub integration examples |
| `monitoring` | Monitoring examples |
| `parallel` | Parallel execution examples |
| `config` | Configuration examples |
| `integrations` | Integration examples |
| `beginner` | Beginner-friendly examples |
| `intermediate` | Intermediate examples |
| `advanced` | Advanced examples |
| `search <keyword>` | Search examples by keyword |
| `all` | Show all examples |

**Options (all subcommands):**
| Option | Description |
|--------|-------------|
| `--verbose` | Show detailed notes |

---

## Environment Variables

ADW recognizes these environment variables:

### Core
| Variable | Description |
|----------|-------------|
| `ADW_CONFIG` | Custom config file path |
| `ADW_DEBUG` | Enable debug mode (1/true) |

### Integrations
| Variable | Description |
|----------|-------------|
| `SLACK_BOT_TOKEN` | Slack bot token |
| `SLACK_SIGNING_SECRET` | Slack signing secret |
| `SLACK_CHANNEL_ID` | Default Slack channel |
| `LINEAR_API_KEY` | Linear API key |
| `LINEAR_TEAM_ID` | Linear team ID |
| `NOTION_API_KEY` | Notion integration API key |
| `NOTION_DATABASE_ID` | Notion database ID |
| `GITHUB_TOKEN` | GitHub personal access token |
| `GH_TOKEN` | Alternative GitHub token |

### Webhooks
| Variable | Description |
|----------|-------------|
| `ADW_WEBHOOK_URL` | Webhook notification URL |
| `ADW_WEBHOOK_SECRET` | Webhook signing secret |
| `ADW_WEBHOOK_EVENTS` | Comma-separated event list |

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 2 | Invalid arguments |
| 3 | Configuration error |
| 4 | Task not found |
| 5 | Integration error |

---

## See Also

- [Getting Started](GETTING_STARTED.md) - Quick start guide
- [Configuration Reference](CONFIGURATION.md) - All configuration options
- [Troubleshooting](TROUBLESHOOTING.md) - Common issues and solutions
- [Workflows Guide](examples/WORKFLOWS.md) - Detailed workflow documentation
