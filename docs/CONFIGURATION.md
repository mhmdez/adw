# ADW Configuration Reference

Complete reference for all ADW configuration options.

## Configuration File

ADW uses a single configuration file at `~/.adw/config.toml`. The file is organized into sections for different aspects of the system.

### File Location

```bash
# View config file path
adw config path

# Default location
~/.adw/config.toml
```

### Configuration Priority

Configuration values are loaded in this order (later sources override earlier):

1. **Defaults** - Built-in default values
2. **Config file** - `~/.adw/config.toml`
3. **Environment variables** - Highest priority (overrides file)

## Managing Configuration

### View Configuration

```bash
# Show all configuration
adw config show

# Show with secrets visible
adw config show --secrets

# Show as JSON
adw config show --json

# Show specific section
adw config show --section core
```

### Get/Set Values

```bash
# Get a specific value
adw config get core.default_model

# Set a value
adw config set core.default_model opus
adw config set daemon.max_concurrent 5

# List all available keys
adw config keys
```

### Edit Configuration

```bash
# Open in $EDITOR
adw config edit

# Reset to defaults
adw config reset
adw config reset --section daemon  # Reset only daemon section
```

---

## Configuration Sections

### [core] - Core Settings

Basic ADW behavior settings.

```toml
[core]
tasks_file = "tasks.md"        # Path to task board file
default_workflow = "sdlc"       # Default workflow: simple, standard, sdlc
default_model = "sonnet"        # Default model: sonnet, opus, haiku
project_root = ""               # Override project root detection
auto_detect_type = true         # Auto-detect project type
```

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `tasks_file` | string | `"tasks.md"` | Relative path to tasks file |
| `default_workflow` | string | `"sdlc"` | Workflow for new tasks: `simple`, `standard`, `sdlc` |
| `default_model` | string | `"sonnet"` | Model for tasks: `sonnet`, `opus`, `haiku` |
| `project_root` | string | `""` | Override automatic project root detection |
| `auto_detect_type` | bool | `true` | Automatically detect project type (React, FastAPI, etc.) |

**Environment Variables:**
- None (use `ADW_CONFIG` for custom config file path)

---

### [daemon] - Daemon Settings

Settings for the autonomous task execution daemon (`adw run`).

```toml
[daemon]
poll_interval = 5.0            # Seconds between task checks
max_concurrent = 3             # Maximum simultaneous agents
auto_start = true              # Automatically start eligible tasks
notifications = true           # Enable desktop notifications
webhooks = true                # Enable webhook notifications
```

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `poll_interval` | float | `5.0` | Seconds between checking for eligible tasks |
| `max_concurrent` | int | `3` | Maximum agents running simultaneously |
| `auto_start` | bool | `true` | Automatically start tasks when eligible |
| `notifications` | bool | `true` | Send desktop notifications |
| `webhooks` | bool | `true` | Send webhook notifications |

**Tips:**
- Increase `max_concurrent` for more parallelism (requires more CPU/memory)
- Increase `poll_interval` to reduce resource usage
- Disable `notifications` for headless/server deployments

---

### [ui] - UI Settings

Settings for the TUI dashboard and notifications.

```toml
[ui]
show_logo = true                          # Show ASCII logo in TUI
theme = "auto"                            # Theme: auto, dark, light
notification_sound_success = "Glass"       # macOS sound for success
notification_sound_failure = "Basso"       # macOS sound for failure
notification_on_start = false              # Notify when tasks start
log_level = "info"                         # Logging level
```

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `show_logo` | bool | `true` | Show ADW ASCII logo in TUI header |
| `theme` | string | `"auto"` | Color theme: `auto`, `dark`, `light` |
| `notification_sound_success` | string | `"Glass"` | macOS sound for task completion |
| `notification_sound_failure` | string | `"Basso"` | macOS sound for task failure |
| `notification_on_start` | bool | `false` | Notify when tasks start (not just complete) |
| `log_level` | string | `"info"` | Logging verbosity: `debug`, `info`, `warning`, `error` |

**macOS Notification Sounds:**
Available sounds: `Basso`, `Blow`, `Bottle`, `Frog`, `Funk`, `Glass`, `Hero`, `Morse`, `Ping`, `Pop`, `Purr`, `Sosumi`, `Submarine`, `Tink`

---

### [workflow] - Workflow Settings

Settings for workflow execution behavior.

```toml
[workflow]
default_timeout = 600          # Default phase timeout (seconds)
default_retries = 2            # Max retries per phase
test_timeout = 300             # Test execution timeout (seconds)
enable_checkpoints = true      # Save checkpoints for recovery
enable_wip_commits = true      # Create WIP commits on pause
```

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `default_timeout` | int | `600` | Phase timeout in seconds (10 minutes) |
| `default_retries` | int | `2` | Maximum retry attempts per phase |
| `test_timeout` | int | `300` | Test execution timeout in seconds |
| `enable_checkpoints` | bool | `true` | Save checkpoints for task recovery |
| `enable_wip_commits` | bool | `true` | Create `[WIP]` commits when pausing |

**Tips:**
- Increase `default_timeout` for complex tasks
- Set `enable_checkpoints = true` to recover from failures
- Use `enable_wip_commits = true` to preserve partial progress

---

### [workspace] - Workspace Settings

Settings for git worktrees and multi-repo coordination.

```toml
[workspace]
enable_worktrees = true        # Use git worktrees for isolation
default_branch = "main"        # Default git branch name
auto_cleanup = true            # Auto-cleanup completed worktrees
active_workspace = "default"   # Currently active workspace
```

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enable_worktrees` | bool | `true` | Use git worktrees for task isolation |
| `default_branch` | string | `"main"` | Default branch for new worktrees |
| `auto_cleanup` | bool | `true` | Automatically remove worktrees after completion |
| `active_workspace` | string | `"default"` | Active workspace for multi-repo setups |

---

### [slack] - Slack Integration

Slack integration settings for notifications and slash commands.

```toml
[slack]
bot_token = ""                 # Slack bot token (xoxb-...)
signing_secret = ""            # Slack signing secret
channel_id = ""                # Default notification channel
notification_events = ["task_started", "task_completed", "task_failed"]
```

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `bot_token` | string | `""` | Slack bot OAuth token (starts with `xoxb-`) |
| `signing_secret` | string | `""` | Slack app signing secret for request verification |
| `channel_id` | string | `""` | Default channel ID for notifications |
| `notification_events` | list | `["task_started", "task_completed", "task_failed"]` | Events to notify |

**Environment Variables:**
| Variable | Config Key |
|----------|------------|
| `SLACK_BOT_TOKEN` | `slack.bot_token` |
| `SLACK_SIGNING_SECRET` | `slack.signing_secret` |
| `SLACK_CHANNEL_ID` | `slack.channel_id` |

**Setup:**
1. Create a Slack app at https://api.slack.com/apps
2. Enable Bot Token Scopes: `chat:write`, `channels:read`
3. Install to workspace
4. Copy Bot Token and Signing Secret

---

### [linear] - Linear Integration

Linear integration settings for issue tracking.

```toml
[linear]
api_key = ""                   # Linear API key
team_id = ""                   # Team ID to poll
poll_interval = 60             # Seconds between polls
filter_states = ["Backlog", "Todo", "Triage"]  # States to process
sync_comments = true           # Sync ADW updates as comments
label_filter = []              # Only process issues with these labels
```

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `api_key` | string | `""` | Linear personal API key |
| `team_id` | string | `""` | Team ID to poll for issues |
| `poll_interval` | int | `60` | Seconds between issue polls |
| `filter_states` | list | `["Backlog", "Todo", "Triage"]` | Only process issues in these states |
| `sync_comments` | bool | `true` | Post ADW updates as Linear comments |
| `label_filter` | list | `[]` | Only process issues with these labels |

**Environment Variables:**
| Variable | Config Key |
|----------|------------|
| `LINEAR_API_KEY` | `linear.api_key` |
| `LINEAR_TEAM_ID` | `linear.team_id` |
| `LINEAR_POLL_INTERVAL` | `linear.poll_interval` |

**Setup:**
1. Get API key from Linear Settings > API
2. Find team ID from URL or API

---

### [notion] - Notion Integration

Notion integration settings for task management.

```toml
[notion]
api_key = ""                   # Notion integration API key
database_id = ""               # Database ID to poll
poll_interval = 60             # Seconds between polls
status_property = "Status"     # Name of status property
title_property = "Name"        # Name of title property
workflow_property = "Workflow" # Name of workflow property
model_property = "Model"       # Name of model property
priority_property = "Priority" # Name of priority property
adw_id_property = "ADW ID"     # Name of ADW ID property
filter_status = ["To Do", "Not Started"]  # Statuses to process
```

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `api_key` | string | `""` | Notion integration secret |
| `database_id` | string | `""` | Database ID to poll |
| `poll_interval` | int | `60` | Seconds between polls |
| `status_property` | string | `"Status"` | Property name for status |
| `title_property` | string | `"Name"` | Property name for task title |
| `workflow_property` | string | `"Workflow"` | Property for workflow selection |
| `model_property` | string | `"Model"` | Property for model selection |
| `priority_property` | string | `"Priority"` | Property for priority |
| `adw_id_property` | string | `"ADW ID"` | Property to store ADW task ID |
| `filter_status` | list | `["To Do", "Not Started"]` | Statuses to process |

**Environment Variables:**
| Variable | Config Key |
|----------|------------|
| `NOTION_API_KEY` | `notion.api_key` |
| `NOTION_DATABASE_ID` | `notion.database_id` |
| `NOTION_POLL_INTERVAL` | `notion.poll_interval` |

**Setup:**
1. Create integration at https://www.notion.so/my-integrations
2. Share database with integration
3. Copy integration secret and database ID

---

### [github] - GitHub Integration

GitHub integration settings.

```toml
[github]
token = ""                     # GitHub PAT (optional, uses gh CLI)
owner = ""                     # Default repository owner
repo = ""                      # Default repository name
poll_interval = 300            # Seconds between issue polls
labels = []                    # Only process issues with these labels
```

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `token` | string | `""` | GitHub personal access token (optional) |
| `owner` | string | `""` | Default repository owner |
| `repo` | string | `""` | Default repository name |
| `poll_interval` | int | `300` | Seconds between polls (5 minutes) |
| `labels` | list | `[]` | Only process issues with these labels |

**Environment Variables:**
| Variable | Config Key |
|----------|------------|
| `GITHUB_TOKEN` | `github.token` |
| `GH_TOKEN` | `github.token` (alternative) |
| `GITHUB_OWNER` | `github.owner` |
| `GITHUB_REPO` | `github.repo` |

**Note:** If `token` is not set, ADW uses the `gh` CLI for authentication.

---

### [webhook] - Webhook Settings

Generic webhook settings for external notifications.

```toml
[webhook]
url = ""                       # Webhook URL for notifications
events = ["task_completed", "task_failed"]  # Events to send
secret = ""                    # Optional signing secret
```

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `url` | string | `""` | Webhook URL to POST notifications |
| `events` | list | `["task_completed", "task_failed"]` | Events to send |
| `secret` | string | `""` | HMAC signing secret for verification |

**Environment Variables:**
| Variable | Config Key |
|----------|------------|
| `ADW_WEBHOOK_URL` | `webhook.url` |
| `ADW_WEBHOOK_SECRET` | `webhook.secret` |
| `ADW_WEBHOOK_EVENTS` | `webhook.events` (comma-separated) |

**Available Events:**
- `task_started` - Task execution began
- `task_completed` - Task finished successfully
- `task_failed` - Task failed
- `approval_required` - Human approval needed

---

### [plugins] - Plugin Settings

Plugin-specific configuration (nested by plugin name).

```toml
[plugins.qmd]
enabled = true
collection_path = ".qmd"

[plugins.custom_plugin]
some_setting = "value"
```

---

## Example Configuration

Complete example configuration file:

```toml
# ADW Configuration
# ~/.adw/config.toml

[config]
version = "1.0"

[core]
tasks_file = "tasks.md"
default_workflow = "sdlc"
default_model = "sonnet"
auto_detect_type = true

[daemon]
poll_interval = 5.0
max_concurrent = 3
auto_start = true
notifications = true
webhooks = true

[ui]
show_logo = true
theme = "auto"
notification_sound_success = "Glass"
notification_sound_failure = "Basso"
log_level = "info"

[workflow]
default_timeout = 600
default_retries = 2
test_timeout = 300
enable_checkpoints = true
enable_wip_commits = true

[workspace]
enable_worktrees = true
default_branch = "main"
auto_cleanup = true
active_workspace = "default"

[slack]
channel_id = "C0123456789"
notification_events = ["task_completed", "task_failed"]

[linear]
team_id = "team-abc123"
poll_interval = 60
filter_states = ["Backlog", "Todo"]
sync_comments = true

[notion]
poll_interval = 60
status_property = "Status"
title_property = "Name"
filter_status = ["To Do", "Not Started"]

[github]
poll_interval = 300
labels = ["adw", "auto"]

[webhook]
url = "https://example.com/webhook"
events = ["task_completed", "task_failed"]
```

---

## Environment Variables Summary

### Core
| Variable | Description |
|----------|-------------|
| `ADW_CONFIG` | Custom config file path |
| `ADW_DEBUG` | Enable debug mode (1/true) |

### Slack
| Variable | Description |
|----------|-------------|
| `SLACK_BOT_TOKEN` | Slack bot OAuth token |
| `SLACK_SIGNING_SECRET` | Slack signing secret |
| `SLACK_CHANNEL_ID` | Default channel ID |

### Linear
| Variable | Description |
|----------|-------------|
| `LINEAR_API_KEY` | Linear API key |
| `LINEAR_TEAM_ID` | Team ID |
| `LINEAR_POLL_INTERVAL` | Poll interval |

### Notion
| Variable | Description |
|----------|-------------|
| `NOTION_API_KEY` | Notion integration secret |
| `NOTION_DATABASE_ID` | Database ID |
| `NOTION_POLL_INTERVAL` | Poll interval |

### GitHub
| Variable | Description |
|----------|-------------|
| `GITHUB_TOKEN` | Personal access token |
| `GH_TOKEN` | Alternative token variable |
| `GITHUB_OWNER` | Repository owner |
| `GITHUB_REPO` | Repository name |

### Webhooks
| Variable | Description |
|----------|-------------|
| `ADW_WEBHOOK_URL` | Webhook URL |
| `ADW_WEBHOOK_SECRET` | Signing secret |
| `ADW_WEBHOOK_EVENTS` | Comma-separated events |

---

## See Also

- [Getting Started](GETTING_STARTED.md) - Quick start guide
- [CLI Reference](CLI_REFERENCE.md) - Complete command documentation
- [Integrations Guide](examples/INTEGRATIONS.md) - Integration setup guides
- [Troubleshooting](TROUBLESHOOTING.md) - Common issues and solutions
