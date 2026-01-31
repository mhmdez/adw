"""Smart project analysis for ADW init.

Uses Claude Code to analyze a project and generate tailored documentation.
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rich.console import Console


console = Console()


@dataclass
class ProjectAnalysis:
    """Result of project analysis."""
    name: str
    description: str
    stack: list[str]
    structure: dict[str, Any]
    commands: dict[str, str]
    key_files: list[str]
    conventions: list[str]
    api_endpoints: list[dict[str, str]] | None = None


ANALYSIS_PROMPT = '''Analyze this project and output a JSON object with the following structure:

{
  "name": "project name",
  "description": "One sentence description of what this project does",
  "stack": ["list", "of", "technologies"],
  "structure": {
    "src": "Source code",
    "tests": "Test files",
    ...key folders and their purpose
  },
  "commands": {
    "dev": "npm run dev",
    "build": "npm run build",
    "test": "npm run test",
    ...common development commands
  },
  "key_files": ["important files to know about"],
  "conventions": ["coding conventions and patterns used"],
  "api_endpoints": [
    {"method": "GET", "path": "/api/users", "description": "List users"},
    ...if this is an API project
  ]
}

Look at:
1. package.json, pyproject.toml, go.mod for dependencies
2. README.md for project description
3. Folder structure for architecture
4. Source files for patterns and conventions
5. API routes if it's a web service

Output ONLY valid JSON, no markdown, no explanation.'''


def run_claude_analysis(project_path: Path, timeout: int = 120) -> dict | None:
    """Run Claude Code to analyze the project.
    
    Args:
        project_path: Path to project root
        timeout: Timeout in seconds
        
    Returns:
        Parsed analysis dict or None on failure
    """
    cmd = [
        "claude",
        "--print", ANALYSIS_PROMPT,
        "--output-format", "text",
        "--dangerously-skip-permissions",
    ]
    
    try:
        result = subprocess.run(
            cmd,
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        
        if result.returncode != 0:
            return None
        
        # Parse JSON from output
        output = result.stdout.strip()
        
        # Try to extract JSON from output
        # Sometimes Claude wraps it in markdown
        if "```json" in output:
            start = output.find("```json") + 7
            end = output.find("```", start)
            output = output[start:end].strip()
        elif "```" in output:
            start = output.find("```") + 3
            end = output.find("```", start)
            output = output[start:end].strip()
        
        return json.loads(output)
        
    except subprocess.TimeoutExpired:
        return None
    except json.JSONDecodeError:
        return None
    except FileNotFoundError:
        return None


def generate_claude_md_from_analysis(analysis: dict, project_path: Path) -> str:
    """Generate CLAUDE.md from analysis results.
    
    Args:
        analysis: Analysis dict from Claude
        project_path: Path to project
        
    Returns:
        Generated CLAUDE.md content
    """
    name = analysis.get("name", project_path.name)
    description = analysis.get("description", "")
    stack = analysis.get("stack", [])
    structure = analysis.get("structure", {})
    commands = analysis.get("commands", {})
    key_files = analysis.get("key_files", [])
    conventions = analysis.get("conventions", [])
    api_endpoints = analysis.get("api_endpoints", [])
    
    content = f"""# CLAUDE.md

This file provides guidance to Claude Code when working with this codebase.

## Project Overview

**{name}** — {description}

**Tech Stack:** {', '.join(stack) if stack else 'Not detected'}

## Project Structure

```
{name}/
"""
    
    for folder, desc in structure.items():
        content += f"├── {folder}/  # {desc}\n"
    
    content += "```\n\n"
    
    if key_files:
        content += "## Key Files\n\n"
        for f in key_files:
            content += f"- `{f}`\n"
        content += "\n"
    
    if commands:
        content += "## Development Commands\n\n```bash\n"
        for name, cmd in commands.items():
            content += f"# {name.capitalize()}\n{cmd}\n\n"
        content += "```\n\n"
    
    if conventions:
        content += "## Conventions\n\n"
        for conv in conventions:
            content += f"- {conv}\n"
        content += "\n"
    
    if api_endpoints:
        content += "## API Endpoints\n\n| Method | Path | Description |\n|--------|------|-------------|\n"
        for ep in api_endpoints:
            content += f"| {ep.get('method', '')} | {ep.get('path', '')} | {ep.get('description', '')} |\n"
        content += "\n"
    
    # Add orchestration section
    content += """
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
    
    return content


def generate_architecture_md(analysis: dict, project_path: Path) -> str:
    """Generate ARCHITECTURE.md from analysis.
    
    Args:
        analysis: Analysis dict from Claude
        project_path: Path to project
        
    Returns:
        Generated ARCHITECTURE.md content
    """
    name = analysis.get("name", project_path.name)
    description = analysis.get("description", "")
    stack = analysis.get("stack", [])
    structure = analysis.get("structure", {})
    
    content = f"""# Architecture Overview

## {name}

{description}

## Tech Stack

"""
    
    for tech in stack:
        content += f"- **{tech}**\n"
    
    content += "\n## Directory Structure\n\n"
    
    for folder, desc in structure.items():
        content += f"### `{folder}/`\n\n{desc}\n\n"
    
    content += """
## Data Flow

*TODO: Document how data flows through the system*

## External Dependencies

*TODO: List external services and APIs*

---

*This file was auto-generated by ADW. Please review and enhance.*
"""
    
    return content


def analyze_project(project_path: Path, verbose: bool = False) -> ProjectAnalysis | None:
    """Analyze a project using Claude Code.
    
    Args:
        project_path: Path to project root
        verbose: Show progress
        
    Returns:
        ProjectAnalysis or None on failure
    """
    if verbose:
        console.print("[dim]Running Claude Code analysis...[/dim]")
    
    result = run_claude_analysis(project_path)
    
    if not result:
        return None
    
    return ProjectAnalysis(
        name=result.get("name", project_path.name),
        description=result.get("description", ""),
        stack=result.get("stack", []),
        structure=result.get("structure", {}),
        commands=result.get("commands", {}),
        key_files=result.get("key_files", []),
        conventions=result.get("conventions", []),
        api_endpoints=result.get("api_endpoints"),
    )
