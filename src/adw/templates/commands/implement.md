# /implement - Execute implementation plan

Implement a task following its plan.

## Input

$ARGUMENTS - Task ID to implement

## Process

1. **Load task context**
   - Read task from tasks.md
   - Load associated spec if exists
   - Check for implementation plan

2. **Update status**
   - Mark task as IN_PROGRESS
   - Note start time

3. **Execute plan**
   - Follow plan steps in order
   - For each step:
     - Make the code changes
     - Run validation
     - If issues, fix or report
   - Commit progress incrementally

4. **Run validation**
   - Lint and type check
   - Run relevant tests
   - Manual verification if needed

5. **Complete**
   - If successful, mark ready for verification
   - If blocked, report issues and update status
   - Summarize what was done

## Output

Task implemented and ready for /verify

## Example

```
/implement TASK-001
```

Implements the task following its plan, then prompts:
```
✅ Implementation complete

Changes:
- Created src/config/auth.ts
- Added OAuth callback in src/routes/auth/callback.ts
- Updated middleware in src/middleware/auth.ts

Tests: 12 passing
Lint: No issues

Run `/verify TASK-001` to review and commit
```
