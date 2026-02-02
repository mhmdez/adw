# Spec: Failure Recovery

## Job to Be Done
Handle failures gracefully without losing work or requiring human debugging.

## Acceptance Criteria

### 1. Error Classification
- [ ] Create `src/adw/recovery/classifier.py`
- [ ] Classify errors:
  - `retriable` — Network, rate limit, timeout
  - `fixable` — Test failure, lint error
  - `fatal` — Invalid config, missing deps
  - `unknown` — Unclassified
- [ ] Different recovery strategy per type

### 2. Recovery Strategies
- [ ] `RetryStrategy` — Simple retry with backoff
- [ ] `FixStrategy` — Attempt to fix based on error
- [ ] `SimplifyStrategy` — Reduce task scope
- [ ] `EscalateStrategy` — Give up and notify human

### 3. Partial Commit
- [ ] If task partially completes, save progress
- [ ] Commit working changes with `[WIP]` prefix
- [ ] Track what's done vs remaining
- [ ] Resume from checkpoint on retry

### 4. Checkpoint System
- [ ] Create `src/adw/recovery/checkpoints.py`
- [ ] Save state after each successful step
- [ ] Store in `agents/<task_id>/checkpoints/`
- [ ] Resume from last checkpoint on failure
- [ ] CLI: `adw resume <task_id>`

### 5. Rollback Capability
- [ ] `adw rollback <task_id>` — Undo all task changes
- [ ] Uses git to revert commits
- [ ] Cleans up worktree
- [ ] Returns task to "failed" state

### 6. Escalation Report
- [ ] Generate human-readable failure report
- [ ] Includes:
  - Task description
  - Error messages
  - Attempted solutions
  - Files modified
  - Suggested next steps
- [ ] Send via configured notification channel

## Technical Notes
- Never lose work — checkpoint frequently
- Keep failed state for debugging
- Automatic cleanup after 7 days

## Testing
- [ ] Test error classification
- [ ] Test checkpoint save/restore
- [ ] Test rollback
