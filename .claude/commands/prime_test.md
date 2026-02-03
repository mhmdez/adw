# /prime_test - Prime context for testing

Load context specific to writing and running tests.

## Metadata

```yaml
allowed-tools: [Read, Bash, Glob, Grep]
description: Prime context for testing
```

## Input

$ARGUMENTS - Feature or module to test (optional)

## Purpose

Quickly load testing-relevant context for writing effective tests. Focuses on test locations, mocking patterns, coverage requirements, and testing conventions used in the codebase.

## When to Use

- Writing new tests
- Adding test coverage
- Debugging test failures
- Understanding testing patterns
- Setting up test fixtures

## Process

### 1. Detect Test Framework

Identify the testing framework(s) used:

```bash
# Check for test configuration files
git ls-files | grep -E "pytest\.ini|setup\.cfg|pyproject\.toml|jest\.config|vitest\.config|karma\.conf" | head -5
```

Read the test configuration to understand:
- Test framework (pytest, jest, vitest, mocha, go test, cargo test)
- Test runner configuration
- Coverage settings
- Custom fixtures or plugins

### 2. Test Directory Structure

Map the test organization:

```bash
# Find test directories
git ls-files | grep -E "test|spec" | head -20

# Count tests by directory
find . -name "*test*.py" -o -name "*.spec.ts" -o -name "*.test.js" 2>/dev/null | head -20
```

Document:
- Test file locations (`tests/`, `__tests__/`, `spec/`, alongside source)
- Naming conventions (`test_*.py`, `*.spec.ts`, `*.test.js`)
- Integration vs unit test separation

### 3. Mocking Patterns

Identify mocking and fixture patterns:

```bash
# Python mocking
git grep -n "mock\|patch\|MagicMock\|@pytest.fixture" | head -10

# JavaScript/TypeScript mocking
git grep -n "jest\.mock\|vi\.mock\|sinon\|stub" | head -10

# Fixture files
git ls-files | grep -E "fixture|conftest|setup" | head -5
```

Note:
- Mock libraries used (unittest.mock, pytest-mock, jest, vitest, sinon)
- Common fixtures and factories
- Test database or API mocking

### 4. Coverage Requirements

Check coverage configuration:

```bash
# Coverage config
git grep -n "coverage\|--cov\|c8\|nyc" | head -5

# Coverage reports
git ls-files | grep -E "coverage|\.coveragerc|\.nycrc" | head -3
```

Document:
- Coverage tool (coverage.py, c8, nyc, istanbul)
- Required coverage thresholds
- Excluded paths/files

### 5. Testing Conventions

Look for testing patterns:

```bash
# Test examples
git ls-files | grep -E "test_.*\.py$|\.spec\.ts$|\.test\.js$" | head -5
```

Read 1-2 example test files to understand:
- Test structure (describe/it, class-based, function-based)
- Setup/teardown patterns
- Assertion style
- Test data management

### 6. Feature-Specific Tests

If `$ARGUMENTS` is provided, find related tests:

```bash
# Find tests for the feature
git ls-files | grep -E "test|spec" | xargs grep -l "$ARGUMENTS" 2>/dev/null | head -5

# Find source files to understand what needs testing
git grep -n "$ARGUMENTS" --include="*.py" --include="*.ts" --include="*.js" | grep -v test | head -10
```

### 7. Report Summary

Provide a summary including:

- **Framework**: Test framework and configuration
- **Structure**: Test file organization
- **Mocking**: How to mock dependencies
- **Coverage**: Current coverage requirements
- **Patterns**: Testing conventions to follow
- **Related Tests**: Existing tests for `$ARGUMENTS`

## Output Format

```
Testing Context
===============

Framework:
- Tool: {pytest, jest, vitest, etc.}
- Config: {config file location}
- Run: {test command, e.g., "pytest tests/", "npm test"}

Structure:
- Unit tests: {location}
- Integration tests: {location}
- Naming: {pattern, e.g., "test_*.py"}

Mocking:
- Library: {mock library}
- Fixtures: {fixture file locations}
- Common mocks: {frequently mocked dependencies}

Coverage:
- Tool: {coverage tool}
- Threshold: {required percentage}
- Report: {report command}

Conventions:
- Style: {describe/it, class-based, etc.}
- Assertions: {assert, expect, etc.}
- Data: {how test data is managed}

Related Tests (for "$ARGUMENTS"):
- {test_file.py - description}

Context primed for testing.
```

## Example Usage

```
/prime_test "user authentication"

Loads testing context and finds auth-related tests.
```

```
/prime_test

Loads general testing context for the codebase.
```

## Notes

- **Framework-aware**: Detects and adapts to test framework
- **Pattern-focused**: Shows how to write tests like existing ones
- **Coverage-conscious**: Highlights coverage requirements
- **Practical**: Provides runnable commands

## Test Framework Reference

### Python (pytest)
```python
# Test function
def test_feature():
    result = function()
    assert result == expected

# Fixtures
@pytest.fixture
def sample_data():
    return {"key": "value"}

# Mocking
@patch("module.dependency")
def test_with_mock(mock_dep):
    mock_dep.return_value = "mocked"
```

### JavaScript/TypeScript (Jest/Vitest)
```typescript
// Test suite
describe("Feature", () => {
  it("should work", () => {
    const result = feature();
    expect(result).toBe(expected);
  });
});

// Mocking
jest.mock("./dependency");
vi.mock("./dependency");
```

### Go
```go
func TestFeature(t *testing.T) {
    result := Feature()
    if result != expected {
        t.Errorf("got %v, want %v", result, expected)
    }
}
```

## Anti-Patterns

Avoid these mistakes:

- **Don't**: Write tests without understanding existing patterns
  **Do**: Follow established testing conventions

- **Don't**: Skip mocking external dependencies
  **Do**: Isolate units with proper mocks

- **Don't**: Ignore coverage requirements
  **Do**: Check coverage before completing

## Integration

This command works well with:
- `/prime` - General codebase orientation
- `/prime_feature` - Feature development context
- `/test` - Run tests after writing them
