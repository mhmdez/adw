# Spec: Test Validation System

## Job to Be Done
Ensure ADW produces working code by running tests after implementation and retrying on failure.

## Acceptance Criteria

### 1. Test Framework Detection
- [ ] Create `src/adw/testing/detector.py`
- [ ] Auto-detect test framework from project:
  - `pytest.ini` or `pyproject.toml [tool.pytest]` → pytest
  - `jest.config.js` → jest
  - `vitest.config.ts` → vitest
  - `package.json scripts.test` → npm test
- [ ] Return: framework name, test command

### 2. Test Execution
- [ ] Create `src/adw/testing/runner.py`
- [ ] Function: `run_tests(command: str) -> TestResult`
- [ ] Capture stdout/stderr
- [ ] Parse exit code (0=pass, non-zero=fail)
- [ ] Extract failure details from output

### 3. Test Result Parsing
- [ ] Parse pytest output for:
  - Number of tests passed/failed/skipped
  - Failed test names and error messages
  - Coverage percentage (if available)
- [ ] Parse jest/vitest output similarly
- [ ] Return structured `TestResult` object

### 4. Retry on Failure
- [ ] In workflow, if tests fail:
  1. Extract error messages
  2. Feed errors back to agent as context
  3. Re-run implement phase
  4. Max 3 retries before escalation
- [ ] Log each retry attempt

### 5. Test Report in Task Output
- [ ] Include test results in task completion message
- [ ] Format: "Tests: 42 passed, 2 failed, 1 skipped"
- [ ] Include failed test names if any

## Technical Notes
- Use subprocess with timeout (default 5 minutes)
- Stream output for long-running test suites
- Support `--no-tests` flag to skip validation

## Testing
- [ ] Test detection for each framework
- [ ] Test parsing for pytest output
- [ ] Integration test for retry flow
