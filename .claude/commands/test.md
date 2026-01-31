# /test - Create and run tests

Create comprehensive tests for implemented features and validate they pass.

## Metadata

```yaml
allowed-tools: [Read, Glob, Grep, Bash, Write, Edit, TodoWrite]
description: Create and run tests
model: sonnet
```

## Purpose

Create unit tests, integration tests, and validation scripts for completed implementations. Ensure all tests pass before proceeding to code review. This phase focuses on test coverage, edge cases, and validation.

## When to Use

- After completing implementation with `/implement`
- When a feature needs test coverage
- Following SDLC workflow after implementation phase
- For validating bug fixes with regression tests

## Input

$ARGUMENTS - Spec file path, task description, or empty for most recent implementation

- **Spec file**: `specs/feature-name.md`
- **Task description**: "Test user authentication"
- **Empty**: Tests the most recently implemented feature

## Process

### 1. Load Implementation Context

- Read the spec file from `specs/` (if available)
- Identify files created/modified in implementation
- Understand the feature's requirements and acceptance criteria
- Review any existing test patterns in the codebase
- Note testing framework and conventions used

### 2. Analyze Test Requirements

Determine what needs testing:

**From Spec**:
- Review "Testing Plan" section if present
- Identify unit test cases listed
- Note integration scenarios
- Find edge cases to cover

**From Implementation**:
- Public APIs and functions
- Class methods and properties
- Error handling paths
- Edge cases and boundaries
- Integration points

### 3. Create Todo List

Use TodoWrite to track test creation:
- Unit tests for each module/component
- Integration tests for workflows
- Edge case coverage
- Test execution and validation
- Mark initial task as in_progress

### 4. Understand Testing Patterns

Before writing tests, explore existing test structure:

```bash
# Find existing tests
ls tests/

# Check test patterns
```

Use Read/Glob to understand:
- Test file naming conventions (`test_*.py`, `*_test.py`, etc.)
- Testing framework (pytest, unittest, etc.)
- Fixture patterns and helpers
- Assertion styles
- Mock/stub approaches

### 5. Write Tests

Create tests following project conventions:

**Unit Tests**:
- Test individual functions and methods
- Mock external dependencies
- Cover normal cases, edge cases, and errors
- Use descriptive test names
- Keep tests focused and isolated

**Integration Tests**:
- Test component interactions
- Use real dependencies where appropriate
- Test end-to-end scenarios
- Validate data flow

**Test Organization**:
```python
# tests/test_feature/test_module.py

def test_function_normal_case():
    """Test function with valid input."""
    result = function(valid_input)
    assert result == expected_output

def test_function_edge_case():
    """Test function with edge case input."""
    result = function(edge_case_input)
    assert result == expected_edge_output

def test_function_error_handling():
    """Test function raises appropriate error."""
    with pytest.raises(ExpectedError):
        function(invalid_input)
```

**Coverage Goals**:
- All public functions tested
- All error paths tested
- All edge cases covered
- Critical integration points validated

### 6. Run Tests

Execute test suite and verify all pass:

```bash
# Run tests based on project setup
pytest tests/                    # Python
npm test                         # Node.js
cargo test                       # Rust
go test ./...                    # Go

# With coverage
pytest --cov=src --cov-report=term

# Specific test file
pytest tests/test_feature/test_module.py
```

**Validation**:
- All new tests pass
- No existing tests broken
- Coverage meets requirements
- No flaky tests
- Performance acceptable

### 7. Fix Failures

If tests fail:

**Implementation Issues**:
- Fix the implementation code
- Re-run tests to verify fix
- Document what was wrong

**Test Issues**:
- Correct test expectations
- Fix mock setup
- Adjust assertions
- Update test data

**Keep iterating** until all tests pass.

### 8. Output Summary

Report:
- Test files created (with paths)
- Number of tests added
- Coverage metrics (if available)
- Test execution results
- Any failures fixed
- Next steps (should be "/review")

## Example Usage

```
/test specs/user-authentication.md

Creates tests based on the spec's testing plan.
```

```
/test Validate user profile editing

Searches for matching spec and creates tests.
```

```
/test

Tests the most recently implemented feature.
```

## Response Format

```
Tests created and validated: {feature name}

Test Files Created:
- tests/test_feature/test_module.py - {N} unit tests
- tests/test_feature/test_integration.py - {N} integration tests

Test Results:
✅ {N} tests passed
Coverage: {X}%

Test Highlights:
- {Key test scenario}
- {Edge case covered}
- {Integration validated}

All tests passing.

Next: Run `/review` for code quality review
```

## Notes

- **Model**: Use Sonnet for test creation (sufficient for most testing tasks)
- **Coverage**: Aim for high coverage of new code, not 100% of everything
- **Patterns**: Follow existing test conventions in the codebase
- **Isolation**: Unit tests should be fast and isolated
- **Clarity**: Test names should clearly describe what is being tested
- **Fixtures**: Reuse fixtures and helpers from existing tests
- **Mocking**: Mock external dependencies (APIs, databases, filesystem)
- **Assertions**: Use clear, specific assertions
- **Documentation**: Tests serve as documentation - make them readable

## Anti-Patterns

Avoid these common mistakes:

- **Don't**: Write tests that don't actually test anything
  **Do**: Assert specific, meaningful outcomes

- **Don't**: Test implementation details
  **Do**: Test public interfaces and behavior

- **Don't**: Create brittle tests that break on minor changes
  **Do**: Test behavior, not exact output format

- **Don't**: Skip edge cases and error paths
  **Do**: Thoroughly test boundaries and errors

- **Don't**: Write slow, flaky tests
  **Do**: Keep tests fast, deterministic, isolated

- **Don't**: Copy-paste test code without understanding
  **Do**: Follow patterns but adapt to specific needs

- **Don't**: Test external dependencies directly
  **Do**: Mock external APIs, databases, services

- **Don't**: Ignore test failures
  **Do**: Fix all failures before proceeding

## Testing Strategies

### Unit Testing

Focus on individual functions and methods:
- Pure functions first (easiest to test)
- Methods with clear inputs/outputs
- Error handling and validation
- Edge cases and boundaries

### Integration Testing

Test component interactions:
- Module integration points
- Database operations (with test DB)
- API endpoints (with test client)
- File system operations (with temp dirs)

### Edge Cases

Always test:
- Empty inputs ([], "", None, 0)
- Boundary values (min, max, just over/under)
- Invalid inputs (wrong type, malformed data)
- Concurrent access (if applicable)
- Large inputs (performance, memory)

### Test Data

Best practices:
- Use fixtures for common test data
- Keep test data minimal and focused
- Use factories for complex objects
- Avoid hardcoded magic values
- Make test data realistic

## Integration

This command is phase 3 of workflows:
- **SDLC workflow**: /plan → /implement → **/test** → /review → /document → update

The implementation from `/implement` is input for this command.
The validated implementation becomes input for `/review`.

## Success Criteria

Testing phase is complete when:
- [ ] All required tests created
- [ ] Unit tests cover new functionality
- [ ] Integration tests validate workflows
- [ ] Edge cases are tested
- [ ] Error handling is tested
- [ ] All tests pass
- [ ] No existing tests broken
- [ ] Coverage meets requirements (if specified)
- [ ] Test summary reported

## Framework-Specific Notes

### Python (pytest)

```python
# Use fixtures
@pytest.fixture
def sample_data():
    return {"key": "value"}

# Parametrize for multiple cases
@pytest.mark.parametrize("input,expected", [
    (1, 2),
    (2, 4),
    (3, 6),
])
def test_doubles(input, expected):
    assert double(input) == expected

# Test exceptions
def test_raises_error():
    with pytest.raises(ValueError, match="invalid"):
        function_that_raises()
```

### JavaScript (Jest/Vitest)

```javascript
// Use describe/it blocks
describe('feature', () => {
  it('should handle normal case', () => {
    expect(function(input)).toBe(expected);
  });

  it('should handle edge case', () => {
    expect(function(edge)).toBe(edgeExpected);
  });
});

// Mock modules
jest.mock('./module');

// Async tests
it('should handle async', async () => {
  const result = await asyncFunction();
  expect(result).toBe(expected);
});
```

### Go

```go
func TestFunction(t *testing.T) {
    tests := []struct {
        name     string
        input    string
        expected string
    }{
        {"normal case", "input", "output"},
        {"edge case", "edge", "edgeOutput"},
    }

    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            result := Function(tt.input)
            if result != tt.expected {
                t.Errorf("got %v, want %v", result, tt.expected)
            }
        })
    }
}
```

## Debugging Failed Tests

When tests fail:

1. **Read the error message carefully**
   - What assertion failed?
   - What was expected vs actual?
   - Which test failed?

2. **Isolate the failure**
   - Run only the failing test
   - Add debug prints/logs
   - Check test setup

3. **Verify assumptions**
   - Is test data correct?
   - Are mocks configured properly?
   - Is environment set up correctly?

4. **Fix systematically**
   - Fix implementation if code is wrong
   - Fix test if expectations are wrong
   - Update both if requirements changed

5. **Verify the fix**
   - Run the specific test
   - Run all related tests
   - Run full test suite
