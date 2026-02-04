# ADW Ink TUI

This is the Ink-based TUI bundled with ADW. It is a thin UI that delegates execution to the ADW CLI.

## Requirements

- `adw` available on your PATH
- `tasks.md` present in the working directory (`adw init` creates it)

If `adw` is missing or fails to start, the TUI falls back to running raw `claude` per task.

## How It Works

- New tasks are written to `tasks.md` as pending items.
- The TUI starts `adw run` and streams events using `adw events --follow --json`.
- Task output is stored in `agents/<adw_id>/prompt/cc_raw_output.jsonl`.

## Development

```bash
npm install
npm run build
npm run start
```

## Testing

```bash
npm run test
```
