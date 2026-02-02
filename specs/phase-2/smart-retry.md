# Spec: Smart Retry System

## Job to Be Done
When a phase fails, automatically retry with error context instead of giving up.

## Acceptance Criteria

### 1. Error Context Injection
- [ ] Create `src/adw/retry/context.py`
- [ ] Function: `build_retry_context(error: str, phase: str) -> str`
- [ ] Format error for agent consumption:
  ```
  PREVIOUS ATTEMPT FAILED:
  Phase: implement
  Error: TypeError: 'NoneType' has no attribute 'strip'
  
  Please fix this issue and try again.
  ```
- [ ] Include relevant stack trace (truncated)

### 2. Retry Configuration
- [ ] Add to config: `max_retries` (default: 3)
- [ ] Add to config: `retry_delay_seconds` (default: 2)
- [ ] Per-task override: `{max_retries: 5}` in task config

### 3. Retry Strategies
- [ ] Strategy 1: Same approach with error context
- [ ] Strategy 2: Ask for alternative solution after 2 failures
- [ ] Strategy 3: Simplify task scope after 3 failures
- [ ] Each strategy adds specific instructions to prompt

### 4. Escalation Protocol
- [ ] After max retries, escalate to human
- [ ] Create escalation report:
  - Task description
  - All error messages
  - All attempted solutions
  - Suggested next steps
- [ ] Save to `agents/<task_id>/escalation.md`
- [ ] Send notification (if configured)

### 5. Retry Logging
- [ ] Log each retry attempt with:
  - Attempt number
  - Error that triggered retry
  - Strategy used
  - Duration
- [ ] Store in task history

## Technical Notes
- Exponential backoff: 2s, 4s, 8s between retries
- Context truncation to avoid token overflow
- Clear distinction between retriable and fatal errors

## Testing
- [ ] Unit test for context building
- [ ] Test retry strategies
- [ ] Integration test for full retry flow
