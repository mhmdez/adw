# /prime_bug - Prime context for bug fixing

Load context specific to debugging and fixing bugs.

## Metadata

```yaml
allowed-tools: [Read, Bash, Glob, Grep]
description: Prime context for bug fixing
```

## Input

$ARGUMENTS - Bug description or error message

## Purpose

Quickly load debugging-relevant context for investigating and fixing bugs. Focuses on error handling patterns, logging conventions, and common failure modes in the codebase.

## When to Use

- Investigating a bug report
- Debugging test failures
- Tracing error propagation
- Understanding failure modes
- Fixing production issues

## Process

### 1. Run Base Prime

Execute the core priming workflow to understand project context:

```bash
git log --oneline -5
```

Read essential config files to understand the environment.

### 2. Error Handling Patterns

Search for error handling patterns in the codebase:

```bash
# Find try/except blocks (Python)
git grep -n "except.*:" --count | head -10

# Find error handling (JavaScript/TypeScript)
git grep -n "catch\s*(" --count | head -10

# Find error classes/types
git grep -n "class.*Error\|class.*Exception" | head -10
```

Note the patterns:
- How exceptions are caught and re-raised
- Custom error classes used
- Error response formats

### 3. Logging Conventions

Identify logging patterns:

```bash
# Find logging statements
git grep -n "log\.\|logger\.\|console\.\|print(" --count | head -10

# Find log configuration
git ls-files | grep -i log | head -5
```

Document:
- Logging framework used (logging, winston, pino, etc.)
- Log levels (debug, info, warn, error)
- Log format and structure

### 4. Debug Techniques

Look for debugging infrastructure:

- Debugger configurations (`.vscode/launch.json`, `pyrightconfig.json`)
- Debug flags and environment variables
- Test fixtures and mocks
- REPL or interactive debugging support

```bash
git ls-files | grep -E "debug|\.vscode|launch\.json" | head -5
```

### 5. Bug-Specific Context

If `$ARGUMENTS` is provided, search for related code:

```bash
# Search for related terms
git grep -n "$ARGUMENTS" | head -20

# Find related test files
git ls-files | grep -i test | xargs grep -l "$ARGUMENTS" 2>/dev/null | head -5
```

### 6. Common Failure Modes

Identify common issues in the codebase:

- Recent bug-related commits:
  ```bash
  git log --oneline --all --grep="fix\|bug\|issue" -10
  ```

- Known issues or TODOs:
  ```bash
  git grep -n "TODO\|FIXME\|XXX\|HACK\|BUG" | head -10
  ```

### 7. Report Summary

Provide a summary including:

- **Error Patterns**: How errors are typically handled
- **Logging**: Where to find logs, log levels used
- **Debug Tools**: Available debugging infrastructure
- **Related Code**: Files related to `$ARGUMENTS`
- **Recent Fixes**: Relevant recent bug fixes

## Output Format

```
Bug Investigation Context
=========================

Error Handling:
- Pattern: {how errors are caught/thrown}
- Custom errors: {list of error classes}
- Response format: {how errors are returned to users}

Logging:
- Framework: {logging library}
- Config: {log config file location}
- Levels used: {debug, info, warn, error}

Debug Infrastructure:
- Debugger: {VS Code, pdb, node --inspect, etc.}
- Debug flags: {DEBUG=1, NODE_ENV=development, etc.}

Related Code (for "$ARGUMENTS"):
- {file1:line - brief description}
- {file2:line - brief description}

Recent Bug Fixes:
- {commit hash} {fix description}

Common Issues:
- {FIXME/TODO locations}

Context primed for bug investigation.
```

## Example Usage

```
/prime_bug "TypeError in user authentication"

Loads debugging context and searches for authentication-related code.
```

```
/prime_bug

Loads general debugging context for the codebase.
```

## Notes

- **Focused**: Prioritizes debugging-relevant files
- **Actionable**: Provides specific file locations to investigate
- **Historical**: Shows recent bug fixes for patterns
- **Lightweight**: Limits searches to avoid context overflow

## Anti-Patterns

Avoid these mistakes:

- **Don't**: Read full source files during priming
  **Do**: Get file locations, then read targeted sections

- **Don't**: Attempt to fix the bug during priming
  **Do**: Gather context first, then investigate

- **Don't**: Ignore error handling patterns
  **Do**: Understand how errors flow through the system

## Integration

This command works well with:
- `/prime` - General codebase orientation
- `/test` - Run relevant tests
- `/review` - Code review after fixing
