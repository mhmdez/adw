"""Project type detection for ADW."""

from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

ProjectCategory = Literal["frontend", "backend", "fullstack"]
ProjectStack = Literal[
    "react", "vue", "svelte", "nextjs", "nuxt",
    "python", "fastapi", "django", "flask",
    "node", "express", "nestjs",
    "go", "rust",
    "unknown"
]


@dataclass
class Detection:
    """A detected project component."""

    category: ProjectCategory
    stack: ProjectStack
    confidence: float  # 0.0 to 1.0


def detect_project(path: Path | None = None) -> list[Detection]:
    """Detect project type from files in current directory.

    Args:
        path: Directory to analyze. Defaults to current directory.

    Returns:
        List of detected project components.
    """
    if path is None:
        path = Path.cwd()

    detections: list[Detection] = []

    # Check for package.json (Node/Frontend)
    package_json = path / "package.json"
    if package_json.exists():
        try:
            pkg = json.loads(package_json.read_text())
            deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}

            # Next.js (fullstack)
            if "next" in deps:
                detections.append(Detection("fullstack", "nextjs", 0.95))
            # Nuxt (fullstack)
            elif "nuxt" in deps:
                detections.append(Detection("fullstack", "nuxt", 0.95))
            # React
            elif "react" in deps:
                detections.append(Detection("frontend", "react", 0.9))
            # Vue
            elif "vue" in deps:
                detections.append(Detection("frontend", "vue", 0.9))
            # Svelte
            elif "svelte" in deps:
                detections.append(Detection("frontend", "svelte", 0.9))
            # NestJS (backend)
            elif "@nestjs/core" in deps:
                detections.append(Detection("backend", "nestjs", 0.9))
            # Express (backend)
            elif "express" in deps:
                detections.append(Detection("backend", "express", 0.85))
            # Generic Node
            else:
                detections.append(Detection("backend", "node", 0.5))
        except (json.JSONDecodeError, OSError):
            pass

    # Check for pyproject.toml (Python)
    pyproject = path / "pyproject.toml"
    if pyproject.exists():
        try:
            data = tomllib.loads(pyproject.read_text())
            deps = data.get("project", {}).get("dependencies", [])
            optional_deps = data.get("project", {}).get("optional-dependencies", {})
            all_deps = deps + [d for group in optional_deps.values() for d in group]
            deps_str = " ".join(all_deps).lower()

            if "fastapi" in deps_str:
                detections.append(Detection("backend", "fastapi", 0.95))
            elif "django" in deps_str:
                detections.append(Detection("backend", "django", 0.95))
            elif "flask" in deps_str:
                detections.append(Detection("backend", "flask", 0.9))
            else:
                detections.append(Detection("backend", "python", 0.7))
        except (OSError, KeyError):
            pass

    # Check for requirements.txt (Python fallback)
    requirements = path / "requirements.txt"
    if requirements.exists() and not pyproject.exists():
        try:
            content = requirements.read_text().lower()
            if "fastapi" in content:
                detections.append(Detection("backend", "fastapi", 0.9))
            elif "django" in content:
                detections.append(Detection("backend", "django", 0.9))
            elif "flask" in content:
                detections.append(Detection("backend", "flask", 0.85))
            else:
                detections.append(Detection("backend", "python", 0.6))
        except OSError:
            pass

    # Check for go.mod (Go)
    if (path / "go.mod").exists():
        detections.append(Detection("backend", "go", 0.95))

    # Check for Cargo.toml (Rust)
    if (path / "Cargo.toml").exists():
        detections.append(Detection("backend", "rust", 0.95))

    # Deduplicate by category (keep highest confidence)
    seen_categories: dict[str, Detection] = {}
    for d in detections:
        existing = seen_categories.get(d.category)
        if existing is None or d.confidence > existing.confidence:
            seen_categories[d.category] = d

    return list(seen_categories.values())


def get_project_summary(detections: list[Detection]) -> str:
    """Get a human-readable summary of detected project types.

    Args:
        detections: List of detections from detect_project().

    Returns:
        Human-readable summary string.
    """
    if not detections:
        return "Unknown project type"

    parts = []
    for d in sorted(detections, key=lambda x: x.category):
        parts.append(f"{d.stack.title()} ({d.category})")

    return " + ".join(parts)


def is_monorepo(path: Path | None = None) -> bool:
    """Check if the project appears to be a monorepo.

    Args:
        path: Directory to analyze. Defaults to current directory.

    Returns:
        True if the project appears to be a monorepo.
    """
    if path is None:
        path = Path.cwd()

    # Check for common monorepo indicators
    monorepo_indicators = [
        path / "pnpm-workspace.yaml",
        path / "lerna.json",
        path / "nx.json",
        path / "rush.json",
        path / "turbo.json",
    ]

    for indicator in monorepo_indicators:
        if indicator.exists():
            return True

    # Check for packages/ or apps/ directories
    if (path / "packages").is_dir() or (path / "apps").is_dir():
        return True

    # Check package.json for workspaces
    package_json = path / "package.json"
    if package_json.exists():
        try:
            pkg = json.loads(package_json.read_text())
            if "workspaces" in pkg:
                return True
        except (json.JSONDecodeError, OSError):
            pass

    return False
