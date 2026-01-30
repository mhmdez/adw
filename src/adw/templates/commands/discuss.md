# /discuss - Start a feature discussion

Start an interactive planning session for a complex feature.

## Input

$ARGUMENTS - Feature description or problem statement

## Process

1. **Understand the request**
   - Read CLAUDE.md to understand project conventions
   - Identify the scope and goals of the feature

2. **Explore the codebase**
   - Search for relevant existing code and patterns
   - Identify files that will need modification
   - Look for similar implementations to reference

3. **Ask clarifying questions**
   - Use AskUserQuestion for ambiguous requirements
   - Clarify edge cases and error handling
   - Understand user preferences for implementation approach

4. **Create a specification**
   - Write a detailed spec to `specs/{feature-name}.md`
   - Include:
     - Overview and goals
     - Technical approach
     - Files to modify/create
     - Testing strategy
     - Acceptance criteria
   - Set Status: PENDING_APPROVAL

5. **Report to user**
   - Summarize the proposed approach
   - Highlight any concerns or trade-offs
   - Tell user to run `adw approve {spec-name}` when ready

## Output

A spec file in specs/ with Status: PENDING_APPROVAL

## Example

```
/discuss add user authentication with OAuth
```

Creates `specs/user-authentication.md` with detailed implementation plan.
