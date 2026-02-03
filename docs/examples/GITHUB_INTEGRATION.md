# GitHub Integration Guide

Automate GitHub issue processing with ADW.

## Overview

ADW can:
- Watch GitHub repos for new issues
- Convert issues to tasks automatically
- Create PRs when tasks complete
- Fix PR review comments automatically

## Setup

### Environment

Set your GitHub token:
```bash
export GITHUB_TOKEN=ghp_your_token_here
```

Or configure in `~/.adw/config.toml`:
```toml
[github]
token = "ghp_your_token_here"
```

### Permissions Required

Your token needs:
- `repo` - Full repository access
- `issues` - Read/write issues
- `pull_requests` - Create/read PRs

## Watching Issues

### Basic Watching

```bash
adw github watch
```

This polls the current repo for issues with the `adw` label.

### Custom Label

```bash
adw github watch --label auto-fix
```

### Custom Interval

```bash
adw github watch --interval 300  # Check every 5 minutes
```

### Specific Repository

```bash
adw github watch --repo owner/repo
```

### Dry Run

Preview without creating tasks:
```bash
adw github watch --dry-run
```

## Issue Templates

ADW parses issue templates for configuration.

### YAML Frontmatter

```markdown
---
type: feature
priority: p1
workflow: sdlc
model: opus
tags: [frontend, auth]
---

Add user login functionality.

## Description
Implement OAuth login with Google and GitHub providers.
```

### Label-Based Configuration

Apply labels to issues:
- `workflow:sdlc` - Use SDLC workflow
- `workflow:simple` - Use simple workflow
- `model:opus` - Use Opus model
- `priority:p0` - High priority

### Inline Tags

In issue body:
```markdown
{opus} Use Opus model for this
{sdlc} Full SDLC workflow
{p0} Urgent priority
```

## Processing Single Issues

```bash
# By issue number
adw github process 123

# Full reference
adw github process owner/repo#123
```

## PR Review Integration

### Watch a PR

```bash
adw github watch-pr 456
```

This polls for new review comments.

### Auto-Fix Comments

```bash
adw github fix-comments 456
```

ADW parses actionable comments:
- "Change X to Y"
- "Add error handling"
- "Fix the typo in..."
- GitHub suggestion blocks

Non-actionable comments are filtered:
- "LGTM"
- Questions
- Praise

### Batch Mode

Fix all comments at once:
```bash
adw github fix-comments 456 --batch
```

### Dry Run

Preview fixes:
```bash
adw github fix-comments 456 --dry-run
```

## Cross-Repo PRs

Link related PRs for coordinated merging.

### Create Link Group

```bash
adw pr link owner/frontend#10 owner/backend#20
```

### View Links

```bash
adw pr list
adw pr show group-id
```

### Merge All

```bash
adw pr merge group-id
```

Options:
- `--method squash` - Squash merge
- `--method rebase` - Rebase merge
- `--force` - Merge even if not all approved

### Cancel Link

```bash
adw pr unlink group-id
```

## Workflow Examples

### Full Automation

```bash
# Terminal 1: Watch for issues
adw github watch

# Terminal 2: Run autonomous daemon
adw run

# Issues become tasks, tasks become PRs
```

### Manual Review

```bash
# Watch issues but require approval
adw github watch --require-approval

# Approve task to proceed
adw approve-task abc123de
```

### PR Review Loop

```bash
# 1. Create PR
# 2. Watch for review
adw github watch-pr 456

# 3. When comments arrive, fix them
adw github fix-comments 456

# 4. Push fixes, repeat until approved
```

## Configuration

In `~/.adw/config.toml`:

```toml
[github]
token = "ghp_your_token"
default_label = "adw"
poll_interval = 300
auto_create_pr = true
require_approval = false
```

## Troubleshooting

### Rate Limiting

GitHub has API rate limits. If you hit them:
```bash
# Check remaining calls
gh api rate_limit

# Increase poll interval
adw github watch --interval 600
```

### Authentication Errors

```bash
# Verify token
gh auth status

# Test connection
adw github test
```

### Missing Labels

Ensure your repo has the labels you're watching:
```bash
gh label create adw --description "Auto-processed by ADW"
```

## Best Practices

1. **Use descriptive issue titles** - They become task descriptions
2. **Apply priority labels** - p0/p1 get processed first
3. **Use templates** - Consistent metadata extraction
4. **Review PRs** - ADW creates PRs, humans review them
5. **Set reasonable intervals** - Don't poll too frequently
