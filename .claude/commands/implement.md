# /implement - Execute implementation plan

Execute a detailed implementation plan, creating and modifying code according to specifications.

## Metadata

```yaml
allowed-tools: [Read, Glob, Grep, Bash, Write, Edit, TodoWrite]
description: Execute implementation plan
model: sonnet
```

## Purpose

Execute a previously created implementation plan or task specification. This phase focuses on writing code, following the architecture and steps defined in the planning phase.

## When to Use

- After creating a plan with `/plan`
- When a detailed spec file exists in `specs/`
- For implementing well-defined features or changes
- Following SDLC workflow after planning phase

## Input

$ARGUMENTS - Spec file path or task description

- **Spec file**: `specs/feature-name.md`
- **Task description**: "Implement user authentication" (will look for matching spec)
- **Empty**: Uses most recent spec from `specs/`

## Process

### 1. Load Specification

- Read the spec file from `specs/`
- Parse requirements and technical approach
- Understand architecture and file structure
- Review implementation steps
- Note testing requirements

### 2. Create Todo List

Use TodoWrite to create task list based on implementation steps:
- Break down spec into actionable todos
- Mark dependencies between tasks
- Set initial task as in_progress
- Track progress throughout implementation

### 3. Execute Implementation Steps

Follow the spec's implementation steps in order:

**For each step**:
- Mark todo as in_progress
- Create or modify files as specified
- Follow existing code patterns and conventions
- Apply proper error handling
- Add type hints where applicable
- Keep changes focused and minimal
- Mark todo as completed when done

**Code Quality**:
- Follow project style (Ruff formatting)
- Use meaningful variable/function names
- Add docstrings for public APIs
- Keep functions focused and single-purpose
- Avoid premature optimization

**File Operations**:
- Use Write for new files
- Use Edit for modifying existing files
- Read files before editing to understand context
- Preserve existing formatting and style

### 4. Verify Implementation

After completing all steps:
- Review all modified files
- Check for syntax errors
- Verify imports are correct
- Ensure type hints are valid
- Confirm all requirements are met

### 5. Output Summary

Report:
- Files created (with paths)
- Files modified (with paths)
- Implementation highlights
- Any deviations from plan (if necessary)
- Next steps (should be "/test" or verification)

## Example Usage

```
/implement specs/user-authentication.md

Executes the implementation plan from the spec file.
```

```
/implement Add user profile editing

Searches for matching spec and implements it.
```

```
/implement

Implements the most recently created spec.
```

## Response Format

```
Implementation complete: {feature name}

Files Created:
- path/to/new_file.py - {purpose}
- path/to/another_file.py - {purpose}

Files Modified:
- path/to/existing_file.py - {changes summary}

Implementation Highlights:
- {Key decision or approach}
- {Notable implementation detail}

All {N} tasks completed successfully.

Next: Run `/test` to validate implementation
```

## Notes

- **Model**: Use Sonnet for implementation (Opus only if extremely complex)
- **Follow Spec**: Stick to the plan - don't add extra features
- **Patterns**: Match existing codebase patterns and conventions
- **Minimal Changes**: Only modify what's necessary
- **Context**: Read files before editing to understand existing code
- **Verification**: Check your work before reporting completion
- **Testing**: Note what tests need to be created (implemented in /test phase)
- **Documentation**: Focus on code - docs are added in /document phase
- **Todo Tracking**: Keep todo list updated throughout implementation

## Anti-Patterns

Avoid these common mistakes:

- **Don't**: Add features not in the spec
  **Do**: Implement exactly what was planned

- **Don't**: Refactor unrelated code
  **Do**: Keep changes focused on the task

- **Don't**: Skip reading files before editing
  **Do**: Understand existing code first

- **Don't**: Ignore existing patterns
  **Do**: Follow project conventions

- **Don't**: Add unnecessary complexity
  **Do**: Keep implementation simple and clear

- **Don't**: Forget to update todo list
  **Do**: Track progress with TodoWrite

- **Don't**: Mix implementation with testing/docs
  **Do**: Focus on code - tests come later

## Integration

This command is phase 2 of workflows:
- **Standard workflow**: /plan → **/implement** → update
- **SDLC workflow**: /plan → **/implement** → /test → /review → /document → update

The spec file from `/plan` is input for this command.
The implementation output becomes input for `/test`.

## Error Handling

If implementation encounters issues:

**Blockers**:
- Note the blocker in current todo
- Document the issue
- Ask for clarification if needed
- Don't proceed blindly

**Spec Gaps**:
- If spec is unclear, make reasonable decision
- Document the decision and rationale
- Note in output summary

**Technical Issues**:
- Try alternative approach if first fails
- Document what was tried
- Report the issue clearly

## Success Criteria

Implementation is complete when:
- [ ] All spec requirements implemented
- [ ] All files created/modified as planned
- [ ] Code follows project conventions
- [ ] No syntax errors
- [ ] Type hints are valid
- [ ] Imports are correct
- [ ] Todo list fully completed
- [ ] Summary report provided
