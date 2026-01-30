# /plan - Create implementation plan

Create a detailed implementation plan for a task or feature.

## Input

$ARGUMENTS - Task ID or feature description

## Process

1. **Understand scope**
   - If task ID provided, load from tasks.md
   - If description, analyze the request
   - Read spec if one exists

2. **Analyze codebase**
   - Identify relevant files and patterns
   - Find similar implementations
   - Note architectural considerations

3. **Create step-by-step plan**
   - Break into atomic steps
   - Order by dependencies
   - Estimate complexity of each step

4. **Consider risks**
   - Identify potential issues
   - Plan for edge cases
   - Note testing requirements

5. **Present plan**
   - Clear numbered steps
   - Files to modify for each step
   - Validation criteria

## Output

Detailed implementation plan ready for execution.

## Example

```
/plan TASK-001
```

Creates a plan like:
```
## Implementation Plan: TASK-001

### Step 1: Create auth configuration
- File: src/config/auth.ts
- Add OAuth provider settings
- Validation: Config loads without errors

### Step 2: Implement OAuth callback
- File: src/routes/auth/callback.ts
- Handle provider response
- Validation: Callback redirects correctly

...
```
