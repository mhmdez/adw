# /plan - Create implementation plan

Generate a detailed technical implementation plan for a feature or task.

## Metadata

```yaml
allowed-tools: [Read, Glob, Grep, Bash, Write, Edit]
description: Create detailed implementation plan
model: opus
```

## Purpose

Create a comprehensive technical plan before implementation. This phase focuses on understanding requirements, analyzing the codebase, identifying patterns, and designing a clear implementation strategy.

## When to Use

- New feature development requiring architectural decisions
- Complex refactoring that touches multiple files
- Bug fixes that need root cause analysis
- Any task requiring exploration before implementation

## Input

$ARGUMENTS - Task description or spec file path

- **Task description**: "Add user authentication system"
- **Spec reference**: Path to existing spec file if available

## Process

### 1. Understand Requirements

- Parse the task description thoroughly
- Identify core objectives and constraints
- List assumptions that need validation
- Note any ambiguities to clarify

### 2. Explore Codebase

Use Read, Glob, and Grep to understand:
- Existing architecture and patterns
- Similar features already implemented
- Code organization and structure
- Dependencies and integrations
- Testing patterns

### 3. Design Approach

Create a plan covering:

**Architecture**
- Component breakdown
- File structure
- Module responsibilities
- Data flow

**Technical Decisions**
- Libraries/frameworks to use
- Design patterns to follow
- State management approach
- API contracts (if applicable)

**Implementation Steps**
- Ordered list of tasks
- Dependencies between steps
- Estimated complexity per step
- Risk areas requiring extra attention

**Testing Strategy**
- Unit tests needed
- Integration tests needed
- Manual testing scenarios
- Edge cases to cover

**Rollout Considerations**
- Breaking changes (if any)
- Migration path (if applicable)
- Feature flags (if needed)
- Documentation updates required

### 4. Create Spec File

Write plan to `specs/{task-slug}.md`:

```markdown
# {Feature Name}

## Overview

{Brief description of what this implements and why}

## Requirements

- Requirement 1
- Requirement 2
- ...

## Technical Approach

### Architecture

{Component diagram or description}

### File Structure

- `path/to/file.py` - {Purpose}
- `path/to/test.py` - {Test coverage}

### Data Models

{Key data structures, types, or schemas}

### API/Interface

{Public APIs, function signatures, or contracts}

## Implementation Steps

1. **{Step 1}** - {Details}
   - Subtask A
   - Subtask B

2. **{Step 2}** - {Details}
   - Subtask A
   - Subtask B

{...}

## Testing Plan

### Unit Tests

- Test case 1
- Test case 2

### Integration Tests

- Integration scenario 1
- Integration scenario 2

### Edge Cases

- Edge case 1
- Edge case 2

## Risks & Mitigations

- **Risk**: {Description}
  - **Mitigation**: {Strategy}

## Rollout

- [ ] Implementation complete
- [ ] Tests passing
- [ ] Documentation updated
- [ ] Code reviewed

## Dependencies

- Depends on: {Other tasks or features}
- Blocks: {Tasks waiting for this}

## Notes

{Additional context, references, or considerations}
```

### 5. Output Summary

Report:
- Path to created spec file
- Key architectural decisions made
- Any blockers or open questions
- Next steps (should be "/implement")

## Example Usage

```
/plan Add user profile editing feature

Creates specs/user-profile-editing.md with implementation plan.
```

```
/plan specs/feature-auth.md

Analyzes existing spec and creates detailed implementation plan.
```

## Response Format

```
Plan created: specs/{filename}.md

Key Decisions:
- Decision 1: {rationale}
- Decision 2: {rationale}

Architecture:
- {High-level approach summary}

Implementation Steps: {N} steps identified

Next: Run `/implement specs/{filename}.md` to execute this plan
```

## Notes

- **Model**: Always use Opus for planning (complex reasoning required)
- **Exploration**: Spend time understanding existing code before designing
- **Detail**: Be specific - vague plans lead to poor implementations
- **Validation**: If requirements are unclear, note questions in spec
- **Patterns**: Follow existing codebase conventions and patterns
- **Scope**: Keep scope focused - break large features into phases
- **Dependencies**: Identify all external dependencies and prerequisites
- **Testing**: Test strategy is mandatory, not optional

## Anti-Patterns

Avoid these common mistakes:

- **Don't**: Start with implementation details
  **Do**: Start with requirements and architecture

- **Don't**: Make assumptions without validating against codebase
  **Do**: Read existing code to understand patterns

- **Don't**: Create vague, high-level plans
  **Do**: Provide concrete, actionable steps

- **Don't**: Skip the testing section
  **Do**: Define test coverage upfront

- **Don't**: Plan in isolation from existing code
  **Do**: Study similar implementations first

## Integration

This command is phase 1 of workflows:
- **Standard workflow**: /plan → /implement → update
- **SDLC workflow**: /plan → /implement → /test → /review → /document → /release

The spec file created here becomes the input for `/implement`.
