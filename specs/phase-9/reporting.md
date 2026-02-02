# Spec: Reporting & Analytics

## Job to Be Done
Know what ADW is doing and how well it's performing without watching logs.

## Acceptance Criteria

### 1. Daily Summary
- [ ] Create `src/adw/reports/daily.py`
- [ ] Generate at midnight (configurable)
- [ ] Contains:
  - Tasks completed/failed/in-progress
  - Total commits made
  - PRs created/merged
  - Estimated time saved
- [ ] CLI: `adw report daily`

### 2. Weekly Digest
- [ ] Aggregate daily summaries
- [ ] Week-over-week comparison
- [ ] Trends (improving/declining)
- [ ] Highlight: best task, worst task
- [ ] CLI: `adw report weekly`

### 3. Task Metrics
- [ ] Track per task:
  - Duration per phase
  - Retry count
  - Token usage
  - Commits generated
- [ ] Store in `~/.adw/metrics.db`
- [ ] CLI: `adw metrics <task_id>`

### 4. Cost Tracking
- [ ] Calculate API costs per task
- [ ] Use Anthropic pricing:
  - Input: $X per 1M tokens
  - Output: $Y per 1M tokens
- [ ] Daily/weekly/monthly totals
- [ ] CLI: `adw costs --period week`

### 5. Trend Analysis
- [ ] Track over time:
  - Success rate
  - Average task duration
  - Cost per task
  - Retries per task
- [ ] Detect anomalies (sudden increase in failures)
- [ ] Visualize in TUI with sparklines

### 6. Notifications
- [ ] Configurable notification channels
- [ ] Events: task_start, task_complete, task_failed, daily_summary
- [ ] Slack/Discord webhook support
- [ ] CLI: `adw notify "message"`

## Technical Notes
- Metrics are local by default
- Optional: aggregate to cloud dashboard
- Privacy: no code content in metrics

## Testing
- [ ] Test report generation
- [ ] Test cost calculation accuracy
- [ ] Test notification delivery
