"""Project initialization for ADW."""

from __future__ import annotations

import importlib.resources
from pathlib import Path
from typing import TYPE_CHECKING

from rich.console import Console

from .detect import Detection, detect_project, get_project_summary, is_monorepo

if TYPE_CHECKING:
    from collections.abc import Iterator

console = Console()


def get_template_path(template_name: str) -> str:
    """Get the content of a template file.

    Args:
        template_name: Name of the template file (e.g., "commands/discuss.md").

    Returns:
        Template content as string.
    """
    try:
        files = importlib.resources.files("adw.templates")
        template_file = files.joinpath(template_name)
        content = template_file.read_text()
        return content if isinstance(content, str) else ""
    except (FileNotFoundError, TypeError, AttributeError):
        return ""


def list_templates(subdir: str = "") -> Iterator[str]:
    """List all template files in a subdirectory.

    Args:
        subdir: Subdirectory within templates (e.g., "commands").

    Yields:
        Template file names.
    """
    try:
        files = importlib.resources.files("adw.templates")
        if subdir:
            files = files.joinpath(subdir)
        for item in files.iterdir():
            name = getattr(item, "name", None)
            if name and not name.startswith("_"):
                yield name
    except (FileNotFoundError, TypeError, AttributeError):
        pass


def create_directory(path: Path) -> bool:
    """Create a directory if it doesn't exist.

    Args:
        path: Path to create.

    Returns:
        True if directory was created.
    """
    if not path.exists():
        path.mkdir(parents=True)
        return True
    return False


def create_file(path: Path, content: str, force: bool = False) -> bool:
    """Create a file with content.

    Args:
        path: Path to create.
        content: File content.
        force: Overwrite if exists.

    Returns:
        True if file was created/updated.
    """
    if path.exists() and not force:
        return False

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return True


def generate_claude_md(detections: list[Detection], project_path: Path) -> str:
    """Generate CLAUDE.md content based on project detection.

    Args:
        detections: Detected project components.
        project_path: Path to project root.

    Returns:
        Generated CLAUDE.md content.
    """
    project_name = project_path.name
    summary = get_project_summary(detections)

    content = f"""# CLAUDE.md

This file provides guidance to Claude Code when working with this codebase.

## Project Overview

**{project_name}** - {summary}

## Development Commands

"""

    # Add stack-specific commands
    for d in detections:
        if d.stack in ("react", "vue", "svelte", "nextjs", "nuxt"):
            content += """### Frontend
```bash
npm install          # Install dependencies
npm run dev          # Start dev server
npm run build        # Production build
npm run lint         # Run linter
npm run test         # Run tests
```

"""
        elif d.stack in ("python", "fastapi", "django", "flask"):
            content += """### Backend (Python)
```bash
uv sync              # Install dependencies (or: pip install -r requirements.txt)
uv run pytest        # Run tests
uv run ruff check .  # Lint
uv run mypy .        # Type check
```

"""
        elif d.stack in ("node", "express", "nestjs"):
            content += """### Backend (Node)
```bash
npm install          # Install dependencies
npm run dev          # Start dev server
npm run build        # Build
npm run test         # Run tests
npm run lint         # Lint
```

"""
        elif d.stack == "go":
            content += """### Backend (Go)
```bash
go build             # Build
go test ./...        # Run tests
go run .             # Run
```

"""

    # Add orchestration section
    content += """## Multi-Agent Orchestration

This project uses ADW (AI Developer Workflow) for task orchestration.

### Key Commands (in Claude Code)

| Command | Purpose |
|---------|---------|
| `/discuss` | Interactive planning for complex features |
| `/approve_spec` | Approve spec, create tasks |
| `/verify` | Review implementation before commit |
| `/status` | Check what needs your attention |
| `/build` | Direct implementation for simple tasks |

### Relevant Files

- `tasks.md` - Multi-Agent Task List
- `specs/` - Feature specifications
- `.claude/commands/` - Slash commands

"""

    return content


def append_orchestration_section(existing_content: str) -> str:
    """Append orchestration section to existing CLAUDE.md if not present.

    Args:
        existing_content: Existing CLAUDE.md content.

    Returns:
        Updated content with orchestration section.
    """
    if "Multi-Agent Orchestration" in existing_content:
        return existing_content

    orchestration_section = """

## Multi-Agent Orchestration

This project uses ADW (AI Developer Workflow) for task orchestration.

### Key Commands (in Claude Code)

| Command | Purpose |
|---------|---------|
| `/discuss` | Interactive planning for complex features |
| `/approve_spec` | Approve spec, create tasks |
| `/verify` | Review implementation before commit |
| `/status` | Check what needs your attention |
| `/build` | Direct implementation for simple tasks |

### Relevant Files

- `tasks.md` - Multi-Agent Task List
- `specs/` - Feature specifications
- `.claude/commands/` - Slash commands
"""

    return existing_content.rstrip() + orchestration_section


def select_agent_templates(detections: list[Detection]) -> list[str]:
    """Select which agent templates to include based on detections.

    Args:
        detections: Detected project components.

    Returns:
        List of agent template names to include.
    """
    templates = ["_base.md"]

    categories = {d.category for d in detections}

    if "frontend" in categories:
        templates.append("frontend.md")
    if "backend" in categories:
        templates.append("backend.md")
    if "fullstack" in categories:
        templates.append("fullstack.md")

    return templates


def init_project(
    project_path: Path | None = None,
    force: bool = False,
) -> dict[str, list[str]]:
    """Initialize ADW in a project.

    Args:
        project_path: Path to project root. Defaults to current directory.
        force: Overwrite existing files.

    Returns:
        Dictionary with created/skipped file lists.
    """
    if project_path is None:
        project_path = Path.cwd()

    result: dict[str, list[str]] = {
        "created": [],
        "skipped": [],
        "updated": [],
    }

    # Detect project type
    console.print("[dim]Detecting project type...[/dim]")
    detections = detect_project(project_path)

    if detections:
        summary = get_project_summary(detections)
        console.print(f"[green]Detected: {summary}[/green]")
    else:
        console.print("[yellow]Could not detect project type. Using generic templates.[/yellow]")

    # Check for monorepo
    if is_monorepo(project_path):
        console.print("[cyan]Detected monorepo structure[/cyan]")

    # Create directories
    claude_dir = project_path / ".claude"
    commands_dir = claude_dir / "commands"
    agents_dir = claude_dir / "agents"
    specs_dir = project_path / "specs"

    for dir_path in [claude_dir, commands_dir, agents_dir, specs_dir]:
        if create_directory(dir_path):
            result["created"].append(str(dir_path.relative_to(project_path)))

    # Create tasks.md
    tasks_path = project_path / "tasks.md"
    tasks_content = get_template_path("tasks.md")
    if create_file(tasks_path, tasks_content, force):
        result["created"].append("tasks.md")
    else:
        result["skipped"].append("tasks.md")

    # Create command templates
    for template_name in list_templates("commands"):
        template_content = get_template_path(f"commands/{template_name}")
        if template_content:
            cmd_path = commands_dir / template_name
            if create_file(cmd_path, template_content, force):
                result["created"].append(f".claude/commands/{template_name}")
            else:
                result["skipped"].append(f".claude/commands/{template_name}")

    # Create agent templates based on detection
    agent_templates = select_agent_templates(detections)
    for template_name in agent_templates:
        template_content = get_template_path(f"agents/{template_name}")
        if template_content:
            agent_path = agents_dir / template_name
            if create_file(agent_path, template_content, force):
                result["created"].append(f".claude/agents/{template_name}")
            else:
                result["skipped"].append(f".claude/agents/{template_name}")

    # Handle CLAUDE.md
    claude_md_path = project_path / "CLAUDE.md"
    if claude_md_path.exists() and not force:
        # Append orchestration section if not present
        existing = claude_md_path.read_text()
        updated = append_orchestration_section(existing)
        if updated != existing:
            claude_md_path.write_text(updated)
            result["updated"].append("CLAUDE.md")
        else:
            result["skipped"].append("CLAUDE.md")
    else:
        # Generate new CLAUDE.md
        content = generate_claude_md(detections, project_path)
        if create_file(claude_md_path, content, force):
            result["created"].append("CLAUDE.md")
        else:
            result["skipped"].append("CLAUDE.md")

    return result


def print_init_summary(result: dict[str, list[str]]) -> None:
    """Print a summary of initialization results.

    Args:
        result: Result dictionary from init_project.
    """
    if result["created"]:
        console.print("\n[green]Created:[/green]")
        for path in result["created"]:
            console.print(f"  + {path}")

    if result["updated"]:
        console.print("\n[cyan]Updated:[/cyan]")
        for path in result["updated"]:
            console.print(f"  ~ {path}")

    if result["skipped"]:
        console.print("\n[yellow]Skipped (already exist):[/yellow]")
        for path in result["skipped"]:
            console.print(f"  - {path}")

    console.print()
    console.print("[green]ADW initialized successfully![/green]")
    console.print()
    console.print("Next steps:")
    console.print("  1. Review the generated CLAUDE.md")
    console.print("  2. Run [cyan]adw[/cyan] to open the dashboard")
    console.print("  3. Run [cyan]adw new \"your feature\"[/cyan] to start planning")
