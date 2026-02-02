# Spec: Claude Code Hooks Integration

## Job to Be Done
Integrate Claude Code's hook system to capture tool usage, block dangerous commands, and enable observability.

## Background
Claude Code supports hooks in `.claude/hooks/`:
- `pre_tool_use.py` — Called before every tool execution
- `post_tool_use.py` — Called after every tool execution
- `stop.py` — Called when response completes

## Acceptance Criteria

### 1. Basic Hooks Setup
- [ ] Create `.claude/hooks/pre_tool_use.py`
- [ ] Create `.claude/hooks/post_tool_use.py`
- [ ] Create `.claude/hooks/stop.py`
- [ ] Update `.claude/settings.json` to enable hooks

### 2. Safety Guardrails (pre_tool_use.py)
- [ ] Block dangerous commands:
  - `rm -rf /`
  - `rm -rf ~`
  - Commands touching `/etc`, `/usr`, `/var`
  - Commands with `sudo` unless explicitly allowed
- [ ] Block access to sensitive files:
  - `.env` files
  - `*_SECRET*` files
  - SSH keys
- [ ] Log blocked attempts to `.adw/blocked.log`
- [ ] Return exit code 1 to block, 0 to allow

### 3. Tool Usage Logging (post_tool_use.py)
- [ ] Log all tool calls to `.adw/tool_usage.jsonl`
- [ ] Capture: timestamp, tool_name, parameters, result_summary
- [ ] Rotate log when > 10MB

### 4. Session Completion (stop.py)
- [ ] Log session end to `.adw/sessions.jsonl`
- [ ] Capture: session_id, duration, tools_used_count, files_modified

## Technical Notes
- Hooks receive JSON via stdin with tool call details
- Hooks communicate via exit code (0=continue, 1=block)
- Keep hooks fast (<100ms) to avoid slowing down agent

## Testing
- [ ] Unit test for guardrail patterns
- [ ] Integration test that triggers a blocked command
- [ ] Verify logging works correctly
