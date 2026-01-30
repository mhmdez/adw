# /verify - Verify implementation

Review completed work before committing.

## Input

$ARGUMENTS - Task ID or description of what to verify

## Process

1. **Gather context**
   - Read the spec if one exists
   - Load task details from tasks.md
   - Understand acceptance criteria

2. **Review changes**
   - Run `git diff` to see all changes
   - Review each modified file
   - Check for:
     - Code quality
     - Test coverage
     - Documentation
     - Security concerns

3. **Run validation**
   - Run linting (`npm run lint` or `ruff check .`)
   - Run type checking (`tsc` or `mypy`)
   - Run tests (`npm test` or `pytest`)

4. **Present to user**
   - Show summary of changes
   - Report validation results
   - Ask: Approve / Request changes / Reject

5. **If approved**
   - Stage changes with `git add`
   - Create commit with descriptive message
   - Update task status to DONE in tasks.md

6. **If rejected**
   - Note the issues
   - Mark task as needs-revision
   - Provide guidance for fixes

## Example

```
/verify TASK-001
```

Reviews implementation for TASK-001 and prompts for approval.
