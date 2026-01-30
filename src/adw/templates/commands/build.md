# /build - Direct implementation

Implement a well-defined, straightforward task directly without creating a spec.

Use this for:
- Small bug fixes
- Simple feature additions
- Clear, well-scoped changes
- Tasks with obvious implementation

## Input

$ARGUMENTS - What to build (clear and specific)

## Process

1. **Understand the task**
   - Read CLAUDE.md for project conventions
   - Verify the task is well-scoped
   - If task is complex, suggest using /discuss instead

2. **Plan the implementation**
   - Identify files to modify
   - Review existing patterns
   - Consider edge cases

3. **Implement**
   - Write clean, tested code
   - Follow project conventions
   - Keep changes focused and minimal

4. **Validate**
   - Run linting and type checks
   - Run relevant tests
   - Verify the implementation works

5. **Report completion**
   - Summarize what was done
   - List files changed
   - Note any follow-up needed

## Example

```
/build fix the login button alignment on mobile
```

Directly implements the fix without creating a spec.
