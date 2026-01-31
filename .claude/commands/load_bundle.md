# /load_bundle - Restore context from previous session

Load file context from a previous agent session to continue work.

## Metadata

```yaml
allowed-tools: [Read, Glob, Bash]
description: Restore file context from previous session
```

## Purpose

Resume work from a previous Claude Code session by loading all files that were read during that session. This allows you to pick up where you left off with full context.

## When to Use

- Resuming work on a task after session ended
- Reviewing what was done in a previous session
- Debugging by replaying context from a specific session
- Restoring context after crash or interruption

## Input

$ARGUMENTS - Bundle file path or session ID (optional)

- **Full path**: `.claude/agents/context_bundles/20260131_12_abc12345.jsonl`
- **Session ID**: `abc12345` (first 8 chars)
- **Empty**: Uses most recent bundle

## Process

1. **Locate bundle file**
   - If full path provided, use directly
   - If session ID provided, find in `.claude/agents/context_bundles/`
   - If nothing provided, use most recent bundle

2. **Parse bundle**
   - Read JSONL file line by line
   - Extract unique file paths
   - Deduplicate reads (keep most specific: with offset/limit if available)

3. **Load context**
   - For each unique file path:
     - Read the file with original parameters
     - This populates context with the same information

4. **Report**
   - List files loaded
   - Note any files that no longer exist
   - Confirm context restoration

## Example Usage

```
/load_bundle abc12345

Loads context from session starting with abc12345.
```

```
/load_bundle

Loads context from the most recent session.
```

```
/load_bundle .claude/agents/context_bundles/20260131_12_abc12345.jsonl

Loads context from specific bundle file.
```

## Output

- Session ID and timestamp
- List of files successfully loaded
- Warning for any files that no longer exist
- Total number of files restored

## Notes

- Context bundles are created automatically by the `context_bundle_builder.py` hook
- Only Read, Write, and Edit operations are tracked
- Files are deduplicated to avoid loading the same file multiple times
- If a file has been modified since the bundle was created, you'll get the current version
