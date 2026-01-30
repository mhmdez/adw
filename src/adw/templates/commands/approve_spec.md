# /approve_spec - Approve a spec and create tasks

Review and approve a pending spec, then decompose it into tasks.

## Input

$ARGUMENTS - Spec name (filename without .md)

## Process

1. **Load the spec**
   - Read specs/{name}.md
   - Verify Status is PENDING_APPROVAL
   - Parse sections and requirements

2. **Review with user**
   - Summarize the spec
   - Highlight key decisions
   - Ask for final confirmation

3. **Decompose into tasks**
   - Break spec into implementable tasks
   - Each task should be:
     - Completable in a focused session
     - Clear and actionable
     - Testable
   - Identify dependencies between tasks

4. **Update tasks.md**
   - Add new tasks with PENDING status
   - Link tasks to the spec
   - Set up dependency relationships

5. **Update spec status**
   - Change Status to APPROVED
   - Record approval timestamp

## Output

- Spec marked as APPROVED
- Tasks added to tasks.md
- Ready for implementation

## Example

```
/approve_spec user-authentication
```

Approves the user-authentication spec and creates tasks like:
- TASK-001: Set up OAuth provider configuration
- TASK-002: Implement login endpoint
- TASK-003: Add session management
- TASK-004: Create protected route middleware
