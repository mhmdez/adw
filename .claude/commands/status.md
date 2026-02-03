# /status - Check what needs attention

Show current status of tasks, specs, and what needs your attention.

## Input

$ARGUMENTS - Optional filter (e.g., "pending", "failed", "specs")

## Process

1. **Load project state**
   - Read tasks.md for task status
   - Scan specs/ for spec status
   - Check git status for uncommitted changes

2. **Identify action items**
   - Tasks that are blocked or failed
   - Specs pending approval
   - Tasks in progress that may be stale

3. **Present overview**
   - Task counts by status
   - List of actionable items
   - Recommendations for next steps

## Output

Status report with:
- Task summary (pending/in_progress/done/blocked/failed)
- Specs pending approval
- Suggested next actions

## Example

```
/status
```

Shows:
```
Tasks: 3 pending, 1 in_progress, 5 done, 1 blocked

⚠ 2 specs pending approval:
  • user-auth: Add OAuth authentication
  • dark-mode: Implement theme switching

Next: Run `adw approve user-auth` to approve the spec
```
