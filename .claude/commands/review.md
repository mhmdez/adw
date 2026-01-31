# /review - Code quality review

Perform comprehensive code quality review of completed implementation and tests.

## Metadata

```yaml
allowed-tools: [Read, Glob, Grep, Bash, Write, Edit, TodoWrite]
description: Code quality review
model: opus
```

## Purpose

Conduct thorough code quality review after implementation and testing phases. This phase focuses on code quality, maintainability, security, performance, and adherence to best practices. Uses Opus model for deep analytical reasoning.

## When to Use

- After completing implementation with `/implement` and testing with `/test`
- Following SDLC workflow after test phase
- When code needs quality validation before documentation
- For ensuring production-ready code standards

## Input

$ARGUMENTS - Spec file path, task description, or empty for most recent implementation

- **Spec file**: `specs/feature-name.md`
- **Task description**: "Review user authentication implementation"
- **Empty**: Reviews the most recently tested feature

## Process

### 1. Load Implementation Context

- Read the spec file from `specs/` (if available)
- Identify all files created or modified in implementation
- Review test files and coverage
- Understand the feature's requirements
- Note project conventions and standards

### 2. Create Todo List

Use TodoWrite to track review areas:
- Code quality and style
- Architecture and design patterns
- Security vulnerabilities
- Performance considerations
- Error handling and edge cases
- Documentation and comments
- Test coverage validation
- Mark initial task as in_progress

### 3. Code Quality Review

**Style and Formatting**:
- Consistent with project conventions
- Proper naming (descriptive, consistent)
- Code formatting (spacing, indentation)
- Import organization
- Line length and readability

**Code Organization**:
- Functions are focused and single-purpose
- Classes have clear responsibilities
- File structure is logical
- Module boundaries are clear
- No code duplication

**Readability**:
- Clear variable and function names
- Logical flow and structure
- Appropriate comments (why, not what)
- Complex logic is explained
- Public APIs are documented

### 4. Architecture Review

**Design Patterns**:
- Appropriate patterns used
- Follows existing codebase patterns
- Not over-engineered
- Clear separation of concerns
- Proper abstraction levels

**Dependencies**:
- Minimal coupling between modules
- Dependencies are justified
- No circular dependencies
- Imports are organized
- External dependencies are appropriate

**Scalability**:
- Code can handle growth
- No hardcoded limits
- Extensible design
- Clear extension points

### 5. Security Review

**Input Validation**:
- All user inputs validated
- Type checking where needed
- Bounds checking for arrays/strings
- SQL injection prevention
- XSS prevention (web apps)

**Authentication & Authorization**:
- Proper auth checks
- Session management
- Password handling (if applicable)
- API token security
- Permission validation

**Data Protection**:
- Sensitive data not logged
- No secrets in code
- Secure data storage
- Encryption where needed
- PII handling compliance

**Common Vulnerabilities**:
- No command injection risks
- Path traversal prevention
- CSRF protection (web apps)
- Rate limiting (APIs)
- Resource exhaustion prevention

### 6. Performance Review

**Efficiency**:
- No obvious performance bottlenecks
- Appropriate data structures
- Efficient algorithms
- Database queries optimized
- Caching where beneficial

**Resource Management**:
- Memory leaks prevented
- File handles closed properly
- Connection pooling used
- Resources cleaned up
- No infinite loops/recursion risks

**Async/Concurrency** (if applicable):
- Proper async/await usage
- Race conditions prevented
- Deadlock prevention
- Thread safety where needed
- Concurrent access handled

### 7. Error Handling Review

**Error Coverage**:
- All error paths handled
- Exceptions caught appropriately
- Meaningful error messages
- Proper error propagation
- Graceful degradation

**Edge Cases**:
- Null/None handling
- Empty collections handled
- Boundary conditions covered
- Invalid input handling
- Network failures handled

**Logging**:
- Errors are logged
- Log levels appropriate
- Sensitive data not logged
- Sufficient context in logs
- Debugging information available

### 8. Testing Review

**Test Coverage**:
- Unit tests exist for new code
- Integration tests for workflows
- Edge cases are tested
- Error paths are tested
- Mocks are used appropriately

**Test Quality**:
- Tests are clear and focused
- Tests are deterministic
- Tests are fast
- Good test naming
- Test data is minimal

### 9. Documentation Review

**Code Documentation**:
- Public APIs have docstrings
- Complex logic is commented
- Type hints are present (Python)
- JSDoc comments (JavaScript)
- Parameter descriptions

**README/Docs**:
- User-facing docs updated (if needed)
- API documentation current
- Examples provided
- Migration guide (if breaking changes)

### 10. Generate Review Report

Create review findings and recommendations:

**Format**:
```markdown
# Code Review: {Feature Name}

## Summary

{Brief overview of implementation quality}

## Strengths

- {What was done well}
- {Good patterns observed}
- {Quality highlights}

## Issues Found

### Critical (Must Fix)

- **{Issue}** (file:line)
  - Problem: {Description}
  - Impact: {Why this matters}
  - Fix: {How to resolve}

### Important (Should Fix)

- **{Issue}** (file:line)
  - Problem: {Description}
  - Fix: {Recommendation}

### Minor (Nice to Have)

- **{Issue}** (file:line)
  - Suggestion: {Improvement idea}

## Security

- {Security findings or "No security issues identified"}

## Performance

- {Performance notes or "No performance concerns"}

## Test Coverage

- {Coverage assessment and gaps}

## Recommendations

1. {Priority recommendation}
2. {Additional improvement}

## Approval Status

- [ ] Critical issues resolved
- [ ] Important issues addressed
- [ ] Security validated
- [ ] Tests passing and comprehensive
- [ ] Ready for documentation phase
```

### 11. Create Fixes (If Needed)

If critical or important issues found:

**Critical Issues**:
- Fix immediately using Edit tool
- Re-run tests to verify fix
- Update review report

**Important Issues**:
- Fix if straightforward
- Or document for follow-up
- Update review report

**Minor Issues**:
- Document for future improvement
- Or fix if trivial

### 12. Output Summary

Report:
- Review report path (if created)
- Issues found by severity
- Issues fixed during review
- Test validation results
- Approval status
- Next steps (should be "/document")

## Example Usage

```
/review specs/user-authentication.md

Reviews the implementation from the spec.
```

```
/review Validate user profile implementation

Searches for matching spec and reviews it.
```

```
/review

Reviews the most recently implemented and tested feature.
```

## Response Format

```
Code review complete: {feature name}

Review Summary:
✅ {N} strengths identified
⚠️  {N} issues found ({critical} critical, {important} important, {minor} minor)
🔒 Security: {status}
⚡ Performance: {status}
🧪 Tests: {status}

Critical Issues Fixed:
- {issue 1} - {file:line}
- {issue 2} - {file:line}

Important Issues:
- {issue 1} - {file:line} - {status}

Review Report: {path to review report if created}

Approval Status: {APPROVED / NEEDS FIXES}

Next: {"/document" if approved, or "Fix remaining issues" if not}
```

## Notes

- **Model**: Always use Opus for review (requires deep analytical reasoning)
- **Thoroughness**: Review is critical quality gate - be thorough
- **Standards**: Follow project-specific standards and conventions
- **Security**: Security review is mandatory, not optional
- **Context**: Read all modified files completely
- **Fix Critical**: Critical issues should be fixed during review
- **Document**: Keep detailed notes of issues found
- **Test After Fix**: Re-run tests after fixing critical issues
- **Constructive**: Focus on specific, actionable feedback

## Anti-Patterns

Avoid these common mistakes:

- **Don't**: Rubber-stamp without thorough review
  **Do**: Critically analyze the implementation

- **Don't**: Focus only on style issues
  **Do**: Review architecture, security, and performance

- **Don't**: Miss security vulnerabilities
  **Do**: Specifically look for common security issues

- **Don't**: Ignore error handling paths
  **Do**: Verify all error scenarios are handled

- **Don't**: Accept insufficient test coverage
  **Do**: Ensure critical paths are tested

- **Don't**: Provide vague feedback
  **Do**: Give specific file:line references and fixes

- **Don't**: Skip performance considerations
  **Do**: Review for obvious performance issues

- **Don't**: Approve code with critical issues
  **Do**: Fix or block until critical issues resolved

## Review Checklist

Use this checklist systematically:

### Code Quality
- [ ] Follows project style guide
- [ ] Consistent naming conventions
- [ ] No code duplication
- [ ] Functions are focused
- [ ] Clear and readable

### Architecture
- [ ] Follows existing patterns
- [ ] Proper separation of concerns
- [ ] Minimal coupling
- [ ] Appropriate abstractions
- [ ] Extensible design

### Security
- [ ] Input validation present
- [ ] No injection vulnerabilities
- [ ] Auth/authz implemented correctly
- [ ] Sensitive data protected
- [ ] No hardcoded secrets

### Performance
- [ ] No obvious bottlenecks
- [ ] Efficient algorithms
- [ ] Proper resource management
- [ ] Appropriate caching
- [ ] Optimized queries (if DB)

### Error Handling
- [ ] All errors handled
- [ ] Meaningful error messages
- [ ] Edge cases covered
- [ ] Proper logging
- [ ] Graceful degradation

### Testing
- [ ] Unit tests exist
- [ ] Integration tests present
- [ ] Edge cases tested
- [ ] Error paths tested
- [ ] Tests are clear

### Documentation
- [ ] Public APIs documented
- [ ] Complex logic commented
- [ ] Type hints present
- [ ] README updated (if needed)

## Review Severity Levels

**Critical**: Must be fixed before proceeding
- Security vulnerabilities
- Data corruption risks
- System stability issues
- Breaking changes without migration
- Test failures

**Important**: Should be fixed soon
- Performance issues
- Poor error handling
- Missing edge case handling
- Incomplete test coverage
- Architectural concerns

**Minor**: Nice to have
- Style inconsistencies
- Missing comments
- Refactoring opportunities
- Documentation improvements
- Minor optimizations

## Integration

This command is phase 4 of workflows:
- **SDLC workflow**: /plan → /implement → /test → **/review** → /document → update

The tested implementation from `/test` is input for this command.
The reviewed and approved implementation becomes input for `/document`.

## Success Criteria

Review phase is complete when:
- [ ] All code files reviewed
- [ ] Security analysis performed
- [ ] Performance checked
- [ ] Error handling validated
- [ ] Test coverage assessed
- [ ] Critical issues fixed
- [ ] Important issues addressed or documented
- [ ] Review report created (if issues found)
- [ ] Approval decision made
- [ ] Summary provided

## Language-Specific Checks

### Python

- Type hints present and correct
- Docstrings follow Google/NumPy style
- No mutable default arguments
- Proper exception types used
- Context managers for resources
- List comprehensions not overused
- Virtual environment considerations

### JavaScript/TypeScript

- TypeScript types properly defined
- Async/await used correctly
- Promises handled properly
- No callback hell
- ESLint rules followed
- Dependencies up to date
- Bundle size considered

### Go

- Error handling follows conventions
- Contexts used properly
- Goroutines don't leak
- Mutexes used correctly
- Interfaces are minimal
- No shadowed variables
- go fmt compliance

### Rust

- Ownership rules followed
- Lifetimes are correct
- Error handling uses Result
- No unnecessary clones
- Unsafe code justified
- Clippy warnings addressed
- Documentation tests present

## Common Security Issues

Watch for these vulnerabilities:

**Injection**:
- SQL injection in queries
- Command injection in shell calls
- XSS in web outputs
- LDAP injection
- XML injection

**Authentication**:
- Weak password requirements
- Insecure session handling
- Missing MFA
- Credential exposure
- Token leakage

**Data Exposure**:
- Sensitive data in logs
- API responses leaking data
- Error messages revealing internals
- Unencrypted storage
- Missing access controls

**Configuration**:
- Default credentials
- Debug mode in production
- Overly permissive CORS
- Missing security headers
- Unpatched dependencies

## Performance Red Flags

Look for these issues:

**Database**:
- N+1 query problems
- Missing indexes
- Full table scans
- No query limits
- Missing pagination

**Algorithms**:
- Nested loops (O(n²))
- Unnecessary sorting
- Inefficient searches
- Redundant calculations
- Missing caching

**Resources**:
- Memory leaks
- File handle leaks
- Connection pool exhaustion
- Unbounded collections
- Large object allocations

**Network**:
- Synchronous blocking calls
- No timeout settings
- Missing retry logic
- Lack of connection reuse
- Excessive API calls
