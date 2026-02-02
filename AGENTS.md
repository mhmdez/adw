# AGENTS.md

Operational guide for ADW CLI. Keep under 60 lines.

## Build & Run

```bash
# Install in dev mode
uv pip install -e .

# Run CLI
adw --help

# Run TUI dashboard
adw dashboard
```

## Validation

Run these after implementing:

```bash
# Tests
uv run pytest tests/ -v

# Typecheck
uv run mypy src/adw/

# Lint
uv run ruff check src/

# Format check
uv run ruff format --check src/
```

## Codebase Structure

```
src/adw/
├── __init__.py          # Version, entry points
├── cli.py               # Click CLI commands
├── daemon.py            # Background daemon
├── executor.py          # Task execution
├── parser.py            # Task file parsing
├── workflows/           # SDLC workflows
│   ├── standard.py
│   └── simple.py
├── integrations/        # External integrations
│   └── github.py
├── triggers/            # Event triggers
│   └── github.py
└── tui/                 # Textual TUI
    └── app.py
```

## Key Patterns

- Entry point: `src/adw/cli.py` (Click)
- Workflows: `src/adw/workflows/` (plan → implement → test → review)
- Tests: `tests/` directory (pytest)
- Config: `~/.adw/config.toml`

## Operational Notes

- Install: `uv tool install adw-cli` or `pip install adw-cli`
- PyPI package name: `adw-cli` (not `adw`)
- Claude CLI requires `--dangerously-skip-permissions` for automation
