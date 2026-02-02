# Spec: Entry Points

## Job to Be Done
Start work from wherever the team communicates — GitHub, Slack, Linear, webhooks.

## Acceptance Criteria

### 1. GitHub Issues (Existing)
- [ ] Already implemented: `adw github watch`
- [ ] Enhancement: Support issue templates
- [ ] Enhancement: Parse labels for workflow selection

### 2. Notion Integration
- [ ] Create `src/adw/integrations/notion.py`
- [ ] Poll Notion database for tasks
- [ ] Parse task from Notion properties:
  - Title → task description
  - Status → ADW status
  - Tags → workflow type
- [ ] Sync status back to Notion
- [ ] CLI: `adw notion watch`

### 3. Slack Integration
- [ ] Create `src/adw/integrations/slack.py`
- [ ] Slack app with OAuth
- [ ] Slash commands:
  - `/adw create <task>` — Create task
  - `/adw status` — Show queue status
  - `/adw approve <id>` — Approve task
- [ ] Thread updates for progress
- [ ] Button interactions for approve/reject

### 4. Linear Integration
- [ ] Create `src/adw/integrations/linear.py`
- [ ] Linear API authentication
- [ ] Bidirectional sync:
  - Linear issue → ADW task
  - ADW status → Linear status
- [ ] CLI: `adw linear sync`

### 5. Webhook Trigger
- [ ] Create `src/adw/triggers/webhook.py`
- [ ] HTTP endpoint: `POST /api/tasks`
- [ ] Payload:
  ```json
  {"description": "...", "workflow": "sdlc", "repo": "..."}
  ```
- [ ] API key authentication
- [ ] Response with task ID
- [ ] Callback URL for completion notification

### 6. Telegram Bot (Bonus)
- [ ] Create `src/adw/integrations/telegram.py`
- [ ] Commands: `/task`, `/status`, `/approve`
- [ ] Progress updates in chat

## Technical Notes
- Each integration is a separate plugin
- Unified task creation API internally
- Rate limiting for external APIs

## Testing
- [ ] Mock tests for each integration
- [ ] Webhook endpoint tests
