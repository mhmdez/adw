"""Progressive context building for ADW.

Updates CLAUDE.md as tasks are completed, building context over time.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path


def update_progress_log(
    project_path: Path,
    task_description: str,
    success: bool,
    summary: str | None = None,
) -> bool:
    """Update the Progress Log section in CLAUDE.md.
    
    Args:
        project_path: Project root path
        task_description: What the task was
        success: Whether it succeeded
        summary: Optional summary of what was done
        
    Returns:
        True if updated successfully
    """
    claude_md = project_path / "CLAUDE.md"
    
    if not claude_md.exists():
        return False
    
    content = claude_md.read_text()
    
    # Create the log entry
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M")
    
    status = "✅" if success else "❌"
    entry = f"- {status} {task_description[:50]}"
    if summary:
        entry += f" — {summary[:50]}"
    
    # Check for ADW:PROGRESS_LOG marker
    if "<!-- ADW:PROGRESS_LOG -->" in content:
        # Insert after marker
        parts = content.split("<!-- ADW:PROGRESS_LOG -->")
        
        # Check if today's date header exists after marker
        after_marker = parts[1] if len(parts) > 1 else ""
        
        if f"### {date_str}" in after_marker:
            # Add to existing date section
            after_marker = after_marker.replace(
                f"### {date_str}\n",
                f"### {date_str}\n{entry}\n"
            )
        else:
            # Create new date section
            after_marker = f"\n\n### {date_str}\n{entry}\n" + after_marker
        
        content = parts[0] + "<!-- ADW:PROGRESS_LOG -->" + after_marker
    
    elif "## What We've Built So Far" in content:
        # Legacy format - insert after this header
        lines = content.split("\n")
        new_lines = []
        found_section = False
        inserted = False
        
        for line in lines:
            new_lines.append(line)
            
            if "## What We've Built So Far" in line:
                found_section = True
                continue
            
            if found_section and not inserted:
                # Skip any immediate description text
                if line.strip().startswith("*") or line.strip() == "":
                    continue
                
                # Insert our entry
                new_lines.insert(-1, "")
                new_lines.insert(-1, f"### {date_str}")
                new_lines.insert(-1, entry)
                new_lines.insert(-1, "")
                inserted = True
        
        if not inserted and found_section:
            # Section was empty, add at end
            new_lines.append("")
            new_lines.append(f"### {date_str}")
            new_lines.append(entry)
        
        content = "\n".join(new_lines)
    
    else:
        # No progress section found
        return False
    
    claude_md.write_text(content)
    return True


def update_tech_stack(
    project_path: Path,
    technologies: list[str],
) -> bool:
    """Update the Tech Stack section in CLAUDE.md.
    
    Args:
        project_path: Project root path
        technologies: List of detected technologies
        
    Returns:
        True if updated successfully
    """
    claude_md = project_path / "CLAUDE.md"
    
    if not claude_md.exists():
        return False
    
    content = claude_md.read_text()
    
    # Find Tech Stack section
    if "## Tech Stack" not in content:
        return False
    
    # Build new tech stack content
    tech_content = "## Tech Stack\n\n"
    for tech in technologies:
        tech_content += f"- {tech}\n"
    tech_content += "\n"
    
    # Replace section
    pattern = r"## Tech Stack\n.*?(?=\n## |\Z)"
    content = re.sub(pattern, tech_content, content, flags=re.DOTALL)
    
    claude_md.write_text(content)
    return True


def detect_new_dependencies(project_path: Path) -> list[str]:
    """Detect dependencies from common config files.
    
    Args:
        project_path: Project root path
        
    Returns:
        List of detected technologies/dependencies
    """
    technologies = []
    
    # package.json
    package_json = project_path / "package.json"
    if package_json.exists():
        try:
            import json
            data = json.loads(package_json.read_text())
            deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
            
            # Map common packages to friendly names
            pkg_map = {
                "next": "Next.js",
                "react": "React",
                "vue": "Vue.js",
                "svelte": "Svelte",
                "typescript": "TypeScript",
                "tailwindcss": "Tailwind CSS",
                "prisma": "Prisma",
                "@prisma/client": "Prisma",
                "express": "Express",
                "fastify": "Fastify",
            }
            
            for pkg, name in pkg_map.items():
                if pkg in deps:
                    technologies.append(name)
        except:
            pass
    
    # pyproject.toml
    pyproject = project_path / "pyproject.toml"
    if pyproject.exists():
        content = pyproject.read_text()
        
        if "fastapi" in content.lower():
            technologies.append("FastAPI")
        if "django" in content.lower():
            technologies.append("Django")
        if "flask" in content.lower():
            technologies.append("Flask")
        if "sqlalchemy" in content.lower():
            technologies.append("SQLAlchemy")
    
    # requirements.txt
    requirements = project_path / "requirements.txt"
    if requirements.exists():
        content = requirements.read_text().lower()
        
        if "fastapi" in content:
            technologies.append("FastAPI")
        if "django" in content:
            technologies.append("Django")
        if "flask" in content:
            technologies.append("Flask")
    
    return list(set(technologies))
