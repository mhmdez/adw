# ADW Integrations Guide

Complete guide for integrating ADW with external services: Slack, Linear, Notion, and Webhooks.

## Overview

ADW supports multiple integrations for triggering tasks and receiving notifications:

| Integration | Purpose | Features |
|-------------|---------|----------|
| **Slack** | Team notifications & slash commands | Task creation, status updates, approvals |
| **Linear** | Issue tracking | Bidirectional sync, auto-processing |
| **Notion** | Task database | Database polling, status sync |
| **Webhooks** | External triggers | API for any service |
| **GitHub** | Issue/PR automation | See [GitHub Guide](GITHUB_INTEGRATION.md) |

---

## Slack Integration

### Setup

#### 1. Create Slack App

1. Go to https://api.slack.com/apps
2. Click "Create New App" → "From scratch"
3. Name it (e.g., "ADW Bot") and select workspace

#### 2. Configure Bot Permissions

Under "OAuth & Permissions", add these Bot Token Scopes:
- `chat:write` - Send messages
- `channels:read` - Read channel info
- `commands` - Slash commands
- `im:write` - Direct messages

#### 3. Install to Workspace

1. Click "Install to Workspace"
2. Copy the **Bot User OAuth Token** (starts with `xoxb-`)

#### 4. Get Signing Secret

1. Go to "Basic Information"
2. Copy the **Signing Secret**

#### 5. Configure ADW

```bash
# Using environment variables (recommended)
export SLACK_BOT_TOKEN="xoxb-your-token"
export SLACK_SIGNING_SECRET="your-signing-secret"
export SLACK_CHANNEL_ID="C0123456789"  # Optional default channel

# Or using config file
adw config set slack.bot_token "xoxb-your-token"
adw config set slack.signing_secret "your-signing-secret"
adw config set slack.channel_id "C0123456789"
```

#### 6. Start Slack Server

```bash
# Start webhook server
adw slack start --port 3000

# Test connection
adw slack test
```

#### 7. Configure Slack App URLs

In your Slack app settings:

**Slash Commands:**
- Create command `/adw`
- Request URL: `https://your-domain.com/slack/commands`

**Interactivity:**
- Enable interactivity
- Request URL: `https://your-domain.com/slack/interactions`

**Event Subscriptions:**
- Enable events
- Request URL: `https://your-domain.com/slack/events`

### Usage

#### Slash Commands

```
/adw create Add user authentication
/adw status
/adw status abc123de
/adw approve abc123de
/adw reject abc123de Not the right approach
/adw help
```

#### Send Notifications

```bash
# Send test message
adw slack send "#general" "Hello from ADW!"

# Notify task thread
adw slack notify abc123de --event completed --pr-url "https://github.com/..."
adw slack notify abc123de --event failed --error "Test failures"
```

#### Automatic Notifications

ADW sends automatic notifications for:
- Task started (if enabled)
- Task completed
- Task failed
- Approval required

Configure events in config:
```toml
[slack]
notification_events = ["task_started", "task_completed", "task_failed", "approval_required"]
```

### Button Interactions

When ADW posts an approval request, users can:
- Click **Approve** to approve the task
- Click **Reject** to reject (opens modal for reason)

---

## Linear Integration

### Setup

#### 1. Get API Key

1. Go to Linear Settings → API
2. Create a personal API key
3. Copy the key

#### 2. Find Team ID

The team ID is in your Linear URLs:
```
https://linear.app/YOUR-WORKSPACE/team/TEAM-ID/...
```

Or use the API:
```bash
adw linear test  # Shows available teams
```

#### 3. Configure ADW

```bash
# Using environment variables
export LINEAR_API_KEY="lin_api_xxxxx"
export LINEAR_TEAM_ID="your-team-id"

# Or using config
adw config set linear.api_key "lin_api_xxxxx"
adw config set linear.team_id "your-team-id"
```

### Usage

#### Watch for Issues

```bash
# Continuous watching
adw linear watch

# With options
adw linear watch --interval 30 --team-id "other-team"

# Dry run (show what would happen)
adw linear watch --dry-run
```

#### Process Single Issue

```bash
adw linear sync TEAM-123
adw linear sync TEAM-123 --dry-run
```

#### One-shot Processing

```bash
# Process all pending issues once (for cron)
adw linear process
```

### Issue Configuration

Control task behavior using Linear issue properties:

#### Labels

Add labels to control execution:
- `workflow:simple` - Use simple workflow
- `workflow:standard` - Use standard workflow
- `workflow:sdlc` - Use full SDLC workflow
- `model:opus` - Use Opus model
- `model:haiku` - Use Haiku model

#### Priority Mapping

| Linear Priority | ADW Priority |
|-----------------|--------------|
| Urgent (1) | p0 |
| High (2) | p1 |
| Medium (3) | p2 |
| Low (4) | p3 |

### Bidirectional Sync

ADW posts comments to Linear issues:
- When task starts
- When task completes (with PR link)
- When task fails (with error details)

Configure sync:
```toml
[linear]
sync_comments = true
```

### Filter Configuration

Control which issues are processed:

```toml
[linear]
filter_states = ["Backlog", "Todo", "Triage"]  # Only these states
label_filter = ["adw", "auto"]                  # Only with these labels
```

---

## Notion Integration

### Setup

#### 1. Create Integration

1. Go to https://www.notion.so/my-integrations
2. Click "New integration"
3. Give it a name and select workspace
4. Copy the **Internal Integration Secret**

#### 2. Share Database

1. Open your Notion database
2. Click "..." → "Add connections"
3. Select your integration

#### 3. Get Database ID

The database ID is in the URL:
```
https://notion.so/workspace/DATABASE-ID?v=...
```

#### 4. Configure ADW

```bash
# Using environment variables
export NOTION_API_KEY="secret_xxxxx"
export NOTION_DATABASE_ID="your-database-id"

# Or using config
adw config set notion.api_key "secret_xxxxx"
adw config set notion.database_id "your-database-id"
```

### Database Schema

Your Notion database should have these properties:

| Property | Type | Purpose |
|----------|------|---------|
| Name | Title | Task description |
| Status | Status/Select | Task status |
| Priority | Select | Priority level (Critical, High, Medium, Low) |
| Workflow | Select | Workflow type (simple, standard, sdlc) |
| Model | Select | Model (sonnet, opus, haiku) |
| ADW ID | Text | Automatically set by ADW |

Configure property names:
```toml
[notion]
title_property = "Name"
status_property = "Status"
priority_property = "Priority"
workflow_property = "Workflow"
model_property = "Model"
adw_id_property = "ADW ID"
filter_status = ["To Do", "Not Started"]
```

### Usage

#### Watch Database

```bash
# Continuous watching
adw notion watch

# With options
adw notion watch --interval 30 --database-id "other-db"

# Dry run
adw notion watch --dry-run
```

#### One-shot Processing

```bash
adw notion process
adw notion process --dry-run
```

#### Test Connection

```bash
adw notion test
```

### Bidirectional Sync

ADW updates Notion pages:
- Sets ADW ID when processing starts
- Updates status when task completes/fails

---

## Webhook Integration

### Generic Webhooks

ADW can send notifications to any webhook URL.

#### Configuration

```bash
# Using environment variables
export ADW_WEBHOOK_URL="https://your-service.com/webhook"
export ADW_WEBHOOK_SECRET="optional-signing-secret"
export ADW_WEBHOOK_EVENTS="task_completed,task_failed"

# Or using config
adw config set webhook.url "https://your-service.com/webhook"
adw config set webhook.secret "optional-signing-secret"
```

#### Webhook Payload

ADW sends JSON payloads:

```json
{
  "event": "task_completed",
  "timestamp": "2026-02-03T12:34:56Z",
  "task": {
    "id": "abc123de",
    "description": "Add user authentication",
    "status": "completed",
    "workflow": "sdlc",
    "model": "sonnet"
  },
  "result": {
    "pr_url": "https://github.com/owner/repo/pull/123",
    "duration_seconds": 342
  }
}
```

#### Signature Verification

If `webhook.secret` is set, ADW signs requests with HMAC-SHA256:

```
X-ADW-Signature: sha256=<signature>
```

Verify in your server:
```python
import hmac
import hashlib

def verify_signature(payload, signature, secret):
    expected = 'sha256=' + hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)
```

### Webhook API Server

ADW can also receive webhooks to trigger tasks.

#### Start Server

```bash
adw webhook start --port 8080
```

#### API Endpoints

**Create Task:**
```bash
curl -X POST http://localhost:8080/api/tasks \
  -H "Authorization: Bearer <api-key>" \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Add user authentication",
    "workflow": "sdlc",
    "model": "sonnet",
    "priority": "high"
  }'
```

**Get Task Status:**
```bash
curl http://localhost:8080/api/tasks/<task_id> \
  -H "Authorization: Bearer <api-key>"
```

#### API Key Management

```bash
# Generate key
adw webhook key generate "my-service" --rate-limit 100

# List keys
adw webhook key list

# Disable key
adw webhook key disable <key_id>

# Re-enable key
adw webhook key enable <key_id>

# Revoke permanently
adw webhook key revoke <key_id>
```

#### Rate Limiting

Each API key has a rate limit (requests per hour). Default: 100.

```bash
adw webhook key generate "high-volume" --rate-limit 1000
```

---

## Discord Integration

### Using Webhooks

Discord webhooks work with ADW's generic webhook support:

1. **Create Discord Webhook:**
   - Server Settings → Integrations → Webhooks
   - Copy webhook URL

2. **Configure ADW:**
   ```bash
   adw config set webhook.url "https://discord.com/api/webhooks/..."
   ```

3. **Format Notifications:**
   ADW sends embeds compatible with Discord's webhook format.

---

## Integration Examples

### CI/CD Pipeline

Trigger ADW from GitHub Actions:

```yaml
# .github/workflows/adw-task.yml
name: ADW Task
on:
  issues:
    types: [labeled]

jobs:
  trigger:
    if: github.event.label.name == 'adw'
    runs-on: ubuntu-latest
    steps:
      - name: Trigger ADW
        run: |
          curl -X POST https://your-adw-server.com/api/tasks \
            -H "Authorization: Bearer ${{ secrets.ADW_API_KEY }}" \
            -H "Content-Type: application/json" \
            -d '{
              "description": "${{ github.event.issue.title }}",
              "workflow": "sdlc",
              "callback_url": "https://your-server.com/callback"
            }'
```

### Slack + Linear Workflow

1. Create issue in Linear with `adw` label
2. ADW polls Linear, creates task
3. ADW posts updates to Slack thread
4. Team members can approve/reject via Slack

### Notion Dashboard

1. Create Notion database for task management
2. Add tasks with priority and workflow settings
3. ADW polls and processes tasks
4. Status automatically updates in Notion

---

## Troubleshooting Integrations

### Connection Test Failed

```bash
# Test each integration
adw slack test
adw linear test
adw notion test
adw webhook test https://example.com/webhook
```

### Events Not Sending

1. Check configuration:
   ```bash
   adw config show --section slack
   ```

2. Check daemon is running:
   ```bash
   adw status
   ```

3. Enable debug mode:
   ```bash
   ADW_DEBUG=1 adw run
   ```

### Rate Limits

- **Linear:** 1000 requests/hour
- **Notion:** 3 requests/second
- **Slack:** Varies by endpoint

Increase poll intervals if hitting limits:
```toml
[linear]
poll_interval = 120

[notion]
poll_interval = 120
```

---

## Security Best Practices

1. **Use environment variables** for secrets, not config files
2. **Set webhook secrets** for signature verification
3. **Use HTTPS** for all webhook URLs
4. **Rotate API keys** periodically
5. **Limit API key rate limits** appropriately
6. **Monitor webhook logs:**
   ```bash
   adw webhook logs --follow
   ```

---

## See Also

- [GitHub Integration](GITHUB_INTEGRATION.md) - GitHub-specific guide
- [Configuration Reference](../CONFIGURATION.md) - All config options
- [CLI Reference](../CLI_REFERENCE.md) - Command documentation
- [Troubleshooting](../TROUBLESHOOTING.md) - Common issues
