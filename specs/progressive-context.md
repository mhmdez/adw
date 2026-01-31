# Progressive Context Building

*For projects that start empty and grow over time*

---

## The Problem

When a user runs `adw init` in an empty folder:
- No files to analyze
- No stack to detect
- CLAUDE.md would be useless boilerplate

But as they build, context should accumulate.

---

## Solution: Progressive Context

### Phase 1: Minimal Scaffold

Empty project gets a starter CLAUDE.md:

```markdown
# CLAUDE.md

## Project Overview

*This project is just getting started. Context will build as you work.*

## What We've Built So Far

*Nothing yet — complete some tasks to see progress here.*

## Development Commands

*Add your commands here as you set things up.*

## Architecture

*Will be documented as the project takes shape.*
```

### Phase 2: Post-Task Learning

After each task completes, the agent:
1. Summarizes what was built/changed
2. Updates relevant CLAUDE.md sections
3. Adds to "What We've Built" changelog

Example flow:
```
Task: "Set up Next.js with TypeScript"
↓
Agent completes task
↓
Agent appends to CLAUDE.md:
  - Stack: Next.js 14, TypeScript, Tailwind
  - Structure: src/app/, src/components/
  - Commands: npm run dev, npm run build
```

### Phase 3: Context Refresh

Command to manually refresh context:
```bash
adw refresh    # Re-analyze project, update CLAUDE.md
```

Or automatic refresh every N tasks.

---

## Implementation

### 1. Detect Empty Project

```python
def is_empty_project(path: Path) -> bool:
    """Check if project is empty or near-empty."""
    files = list(path.iterdir())
    # Ignore common non-code files
    ignore = {'.git', '.gitignore', 'README.md', 'LICENSE', '.adw', '.claude'}
    meaningful = [f for f in files if f.name not in ignore]
    return len(meaningful) < 3
```

### 2. Starter Template

For empty projects, generate a growth-oriented CLAUDE.md:

```python
EMPTY_PROJECT_TEMPLATE = """# CLAUDE.md

## Project Overview

This project is just starting. As you build, this file will document:
- Tech stack and dependencies
- Project structure
- Development commands
- Architecture decisions

## Progress Log

<!-- ADW will append completed tasks here -->

## Tech Stack

*Will be detected as you add dependencies.*

## Commands

*Add your development commands here.*

## Notes

*Capture important decisions and context.*
"""
```

### 3. Post-Task Hook

In the workflow, after task completion:

```python
async def post_task_update(task: Task, result: TaskResult):
    """Update context after task completion."""
    if not result.success:
        return
    
    claude_md = Path("CLAUDE.md")
    if not claude_md.exists():
        return
    
    # Generate summary of what changed
    summary = await generate_task_summary(task, result)
    
    # Append to Progress Log section
    append_to_section(claude_md, "Progress Log", summary)
    
    # If stack changed, update Tech Stack section
    if result.dependencies_added:
        update_tech_stack(claude_md, result.dependencies_added)
```

### 4. Refresh Command

```bash
adw refresh [--full]
```

- Without `--full`: Quick detection + update
- With `--full`: Deep Claude Code analysis

---

## User Flow

### Empty Folder Start

```
$ mkdir my-project && cd my-project
$ adw init

Initializing ADW in my-project...
  ✓ Detected: Empty project
  ✓ Created starter CLAUDE.md
  ✓ Set up progressive learning

Your project will learn as you build!
Run 'adw new "set up next.js"' to start.
```

### After First Task

```
$ adw new "set up next.js with typescript"
# ... agent works ...

Task completed! Updating context...
  + Added: Next.js 14, TypeScript, Tailwind
  + Structure: src/app/, public/
  + Commands: npm run dev
```

### After Several Tasks

CLAUDE.md now looks like:

```markdown
# CLAUDE.md

## Project Overview

A Next.js web application with TypeScript.

## Progress Log

### 2024-02-01
- ✅ Set up Next.js with TypeScript
- ✅ Added Tailwind CSS
- ✅ Created auth system with NextAuth

### 2024-02-02
- ✅ Built dashboard layout
- ✅ Added Prisma + PostgreSQL

## Tech Stack

- **Framework:** Next.js 14 (App Router)
- **Language:** TypeScript
- **Styling:** Tailwind CSS
- **Auth:** NextAuth.js
- **Database:** PostgreSQL + Prisma

## Commands

```bash
npm run dev      # Start dev server
npm run build    # Production build
npm run db:push  # Push Prisma schema
```

## Architecture

```
src/
├── app/           # Next.js App Router
├── components/    # React components
├── lib/           # Utilities
└── prisma/        # Database schema
```
```

---

## Priority

| Feature | Effort | Impact |
|---------|--------|--------|
| Empty project detection | Low | High |
| Starter template | Low | High |
| Post-task learning | Medium | High |
| Refresh command | Medium | Medium |

Start with detection + template, add learning hooks later.
