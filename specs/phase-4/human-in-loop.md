# Spec: Human-in-the-Loop Gates

## Job to Be Done
Allow humans to review and approve plans before implementation, with support for iterative feedback.

## Acceptance Criteria

### 1. HIL Status
- [ ] Add task status: `awaiting_review`
- [ ] Task pauses after planning phase
- [ ] Shows in TUI with special highlight
- [ ] Sends notification when ready for review

### 2. Plan Approval Gate
- [ ] After /plan phase, create approval request
- [ ] Store in `agents/<task_id>/APPROVAL_REQUEST.md`
- [ ] Contains:
  - Task description
  - Proposed plan
  - Files to be modified
  - Estimated effort
  - Risk assessment
- [ ] Commands: `adw approve <task_id>`, `adw reject <task_id>`

### 3. Continue Prompts
- [ ] Support iterative refinement:
  ```
  adw continue <task_id> "Add input validation"
  ```
- [ ] Adds feedback to task context
- [ ] Re-runs current phase with new instructions
- [ ] Track all continue prompts in history

### 4. Reject with Reason
- [ ] `adw reject <task_id> --reason "Wrong approach"`
- [ ] Returns task to planning phase
- [ ] Injects rejection reason into context
- [ ] Logs rejection for learning

### 5. Skip Gates Config
- [ ] Config option: `auto_approve: true`
- [ ] Per-task override: `{hil: false}`
- [ ] Environment variable: `ADW_AUTO_APPROVE=1`
- [ ] Default: gates enabled for production

## Technical Notes
- Approval request expires after 24 hours
- Multiple reviewers support (future)
- Integration with Slack/Discord for notifications

## Testing
- [ ] Test approval flow end-to-end
- [ ] Test continue prompt handling
- [ ] Test rejection and re-planning
