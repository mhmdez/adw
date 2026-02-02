# Spec: PR Review Integration

## Job to Be Done
Automatically respond to PR review comments by implementing requested changes.

## Acceptance Criteria

### 1. Comment Watcher
- [ ] Create `src/adw/github/review_watcher.py`
- [ ] Poll for new review comments on ADW-created PRs
- [ ] Use GitHub API: `GET /repos/{owner}/{repo}/pulls/{pr}/comments`
- [ ] Track last-seen comment ID to avoid duplicates

### 2. Comment Parser
- [ ] Extract actionable feedback from comments
- [ ] Detect patterns:
  - "Please change X to Y"
  - "Add error handling for..."
  - "This should be..."
  - "Can you also..."
- [ ] Ignore non-actionable comments (questions, approvals)

### 3. Auto-Fix Implementation
- [ ] For each actionable comment:
  1. Create a mini-task with comment as spec
  2. Check out PR branch
  3. Run implement phase
  4. Commit with message: "fix: address review comment"
  5. Push to same branch
- [ ] Batch multiple comments into single commit when related

### 4. Reviewer Notification
- [ ] Reply to each addressed comment:
  "Fixed in commit abc123. Changes:
  - Added null check
  - Updated error message"
- [ ] Use GitHub API to create comment reply

### 5. Approval Detection
- [ ] Detect when PR is approved
- [ ] Options:
  - Auto-merge if all checks pass
  - Notify human for manual merge
  - Add label "ready-to-merge"

## Technical Notes
- Rate limit: 5000 requests/hour for authenticated
- Use webhook for real-time (future enhancement)
- Keep fix commits atomic and focused

## Testing
- [ ] Test comment parsing patterns
- [ ] Mock GitHub API for integration tests
- [ ] Test batch commit logic
