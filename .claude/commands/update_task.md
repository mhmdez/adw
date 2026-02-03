# /update_task - Update task status or details

Update a task's status, description, or other metadata.

## Input

$ARGUMENTS - Task ID and update (e.g., "TASK-001 blocked by auth issue")

## Process

1. **Parse input**
   - Extract task ID
   - Determine update type:
     - Status change (done, blocked, failed)
     - Description update
     - Dependency change

2. **Validate**
   - Verify task exists
   - Check status transition is valid

3. **Update tasks.md**
   - Modify the task entry
   - Add notes if provided
   - Preserve history

4. **Report**
   - Confirm the update
   - Show new task state

## Status Values

- `pending` - Not started
- `in_progress` - Currently being worked on
- `done` - Completed successfully
- `blocked` - Waiting on something
- `failed` - Could not complete

## Examples

```
/update_task TASK-001 done
```

Marks TASK-001 as done.

```
/update_task TASK-002 blocked waiting for API access
```

Marks TASK-002 as blocked with note.

```
/update_task TASK-003 depends on TASK-001
```

Adds dependency relationship.
