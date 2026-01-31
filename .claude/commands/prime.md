# /prime - Prime context for current codebase

Load essential context for working in this codebase.

## Metadata

```yaml
allowed-tools: [Read, Bash, Glob]
description: Prime context for current codebase
```

## Purpose

Quickly load essential context about the current codebase at the start of a session or when context becomes stale. This provides a lightweight alternative to reading extensive documentation, focusing on the most critical information needed to begin work.

## When to Use

- Starting a new Claude Code session
- After a long break from working on the project
- When context feels stale or incomplete
- Before switching to work on a different area of the codebase
- After major refactoring or restructuring

## Process

### 1. Core Files

Read the essential project documentation:

- **CLAUDE.md** (if exists, first 200 lines max)
  - Project-specific instructions and conventions
  - Key architectural decisions
  - Development workflow

- **README.md** (first 100 lines)
  - Project overview and purpose
  - Installation and setup
  - Basic usage examples

- **Project config** (full file)
  - `package.json` for Node.js projects
  - `pyproject.toml` for Python projects
  - `Cargo.toml` for Rust projects
  - Other language-specific config files

### 2. Project Structure

Understand the codebase layout:

```bash
git ls-files
```

- Note key directories (src/, tests/, docs/, etc.)
- Identify main entry points
- Observe file naming conventions
- Understand module organization

### 3. Recent Activity

Get context on recent changes:

```bash
git log --oneline -10
```

- Recent commits and their messages
- Active areas of development
- Commit message conventions
- Development velocity

### 4. Report Summary

Provide a concise summary including:

- **Project Type**: Web app, CLI tool, library, etc.
- **Tech Stack**: Languages, frameworks, key dependencies
- **Architecture**: Monolith, microservices, modules, etc.
- **Key Patterns**: Testing approach, code organization, conventions
- **Status**: Active development, stable, experimental

## Output Format

```
Project: {Name}
Type: {CLI/Web/Library/etc}
Stack: {Languages and frameworks}

Structure:
- {Key directory 1}: {Purpose}
- {Key directory 2}: {Purpose}
- ...

Recent Activity:
- {Brief note on recent commits}

Patterns Observed:
- {Convention 1}
- {Convention 2}

Context primed. Ready to work.
```

## Example Usage

```
/prime

Loads core context about the codebase.
```

## Notes

- **Lightweight**: Only reads essential files to minimize token usage
- **Fast**: Designed for quick context loading at session start
- **Repeatable**: Safe to run multiple times without context bloat
- **Focused**: Skips implementation details, focuses on orientation
- **Limits**: Respects line limits to avoid context overflow

## Best Practices

- Run this at the start of every session
- Re-run after returning from a break
- Combine with `/plan` for feature work
- Use `/load_bundle` if resuming specific work
- Don't read entire files - respect the limits

## Anti-Patterns

Avoid these mistakes:

- **Don't**: Read every file in the project
  **Do**: Read only the essentials listed above

- **Don't**: Deep dive into implementation details
  **Do**: Get high-level orientation first

- **Don't**: Load full git history
  **Do**: Check only recent commits (last 10)

- **Don't**: Read large CLAUDE.md files completely
  **Do**: Stop at 200 lines for initial priming

## Integration

This command is designed to work with:
- `/plan` - After priming, create implementation plans
- `/load_bundle` - Load detailed context from previous sessions
- `/experts:cc_expert` - Query expert knowledge about patterns
- Feature-specific priming commands (when implemented)

## Performance

Approximate token usage:
- CLAUDE.md (200 lines): ~1500 tokens
- README.md (100 lines): ~750 tokens
- Config file: ~300-1000 tokens
- Git structure: ~500 tokens
- Git log: ~300 tokens

**Total**: ~3,500-4,000 tokens (lightweight for quick orientation)
