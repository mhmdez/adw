# /review - Review code or pull request

Review code changes for quality, security, and adherence to patterns.

## Input

$ARGUMENTS - What to review (PR number, branch name, or file paths)

## Process

1. **Gather changes**
   - If PR: fetch PR diff
   - If branch: compare to main
   - If files: read specified files

2. **Analyze code**
   - Check code quality
   - Look for bugs and issues
   - Verify test coverage
   - Check security concerns
   - Validate against project patterns

3. **Provide feedback**
   - Summarize the changes
   - List issues found (critical, major, minor)
   - Suggest improvements
   - Note positive aspects

4. **Rate overall**
   - Approve / Request changes / Reject
   - Provide clear reasoning

## Review Criteria

- **Correctness**: Does it do what it should?
- **Security**: Any vulnerabilities?
- **Performance**: Any obvious issues?
- **Maintainability**: Is it readable and well-structured?
- **Tests**: Adequate coverage?
- **Docs**: Updated if needed?

## Example

```
/review pr 42
```

Reviews PR #42 and provides:
```
## Review: PR #42 - Add user profile page

### Summary
Adds a new profile page with avatar upload and settings.

### Issues

**Critical:**
- None

**Major:**
- Missing input validation in ProfileForm (src/components/ProfileForm.tsx:45)

**Minor:**
- Consider extracting avatar upload to a separate component
- Missing loading state for save button

### Recommendation
Request changes - address the validation issue before merging.
```
