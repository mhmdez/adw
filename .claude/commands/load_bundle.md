# /load_bundle - Restore context from previous session

Load file context from a previous agent session to continue work.

## Metadata

```yaml
allowed-tools: [Read, Glob, Bash]
description: Restore context from previous session
```

## Purpose

Resume work from a previous Claude Code session by loading all files that were read during that session. This allows you to pick up where you left off with full context.

## When to Use

- Resuming work on a task after session ended
- Reviewing what was done in a previous session
- Debugging by replaying context from a specific session
- Restoring context after crash or interruption
- Starting a similar task to one done before

## Input

$ARGUMENTS - Bundle task ID or path (optional)

- **Task ID**: `abc12345` (8-char task ID)
- **Full path**: `.adw/bundles/abc12345.json`
- **Empty**: Shows available bundles to choose from

## Process

### 1. Locate Bundle

Find the bundle file:

```bash
# List available bundles
adw bundle list

# Or directly check directory
ls .adw/bundles/*.json 2>/dev/null | head -10
```

If no argument provided, list recent bundles for the user to choose.

### 2. Load Bundle Metadata

Read the bundle file:

```bash
# View bundle details
adw bundle show $ARGUMENTS

# Or read JSON directly
cat .adw/bundles/$ARGUMENTS.json
```

Bundle structure:
```json
{
  "task_id": "abc12345",
  "created_at": "2026-01-31T14:30:00",
  "files": [
    {"path": "src/main.py", "lines_start": 1, "lines_end": 100},
    {"path": "src/utils.py", "lines_start": 1, "lines_end": 50}
  ],
  "total_lines": 150,
  "description": "Implemented auth feature",
  "tags": ["auth", "api"]
}
```

### 3. Read Bundle Files

For each file in the bundle:
- Read using the Read tool
- Respect line ranges if specified
- Skip files that no longer exist
- Report any missing files

### 4. Report Summary

```
Context Bundle Loaded: $ARGUMENTS
=================================

Files Restored:
- src/main.py (100 lines)
- src/utils.py (50 lines)
- tests/test_main.py (120 lines)
...

Total: 12 files, 3,400 lines

Missing Files (no longer exist):
- src/old_module.py

Context restored. Ready to continue work.
```

## Example Usage

```
/load_bundle abc12345

Loads context from task abc12345.
```

```
/load_bundle

Lists available bundles to choose from, then loads selected bundle.
```

## CLI Commands

Bundles are managed via the ADW CLI:

```bash
# List all bundles
adw bundle list

# Show bundle details
adw bundle show <task_id>

# Load bundle (shows files)
adw bundle load <task_id>

# Compare two bundles
adw bundle diff <task_id1> <task_id2>

# Find similar bundles
adw bundle suggest "implement authentication"

# Save a new bundle manually
adw bundle save <task_id> src/**/*.py -d "Auth work"

# Delete a bundle
adw bundle delete <task_id>

# Compress old bundles
adw bundle compress --days 7
```

## Output Format

```
Context Bundle: {task_id}
Created: {timestamp}
Description: {description}

Loading {file_count} files ({total_lines} lines)...

✓ src/main.py (100 lines)
✓ src/utils.py (50 lines)
✓ tests/test_main.py (120 lines)
...

Context restored successfully.
```

## Notes

- Context bundles are saved in `.adw/bundles/`
- Files are stored as JSON (compressed to .json.gz after 7 days)
- Binary files are excluded from bundles
- If files changed since bundle creation, current version is loaded
- Use `adw bundle diff` to see what's changed between bundles

## Anti-Patterns

Avoid these mistakes:

- **Don't**: Load a bundle without checking what's in it
  **Do**: Use `adw bundle show` first to review contents

- **Don't**: Assume all bundle files still exist
  **Do**: Handle missing file reports gracefully

- **Don't**: Load very old bundles without reviewing changes
  **Do**: Use `adw bundle diff` to understand what's changed

## Integration

This command works well with:
- `/prime` - Load priming context first, then bundle
- `/prime_feature` - Prime for feature work before loading bundle
- `/plan` - Plan based on restored context
