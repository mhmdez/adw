"""Unified context for multi-repo workspaces.

Enables agents to read files from any repository in the workspace
and understand cross-repo relationships.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import RepoConfig, load_workspace

logger = logging.getLogger(__name__)


@dataclass
class RepoContext:
    """Context information for a single repository."""

    name: str
    path: Path
    type: str
    claude_md: str | None = None
    architecture_md: str | None = None
    readme_md: str | None = None
    key_files: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "path": str(self.path),
            "type": self.type,
            "has_claude_md": self.claude_md is not None,
            "has_architecture_md": self.architecture_md is not None,
            "has_readme_md": self.readme_md is not None,
            "key_files": self.key_files,
        }


@dataclass
class WorkspaceContext:
    """Unified context across multiple repositories."""

    workspace_name: str
    repos: list[RepoContext] = field(default_factory=list)
    relationships: dict[str, list[str]] = field(default_factory=dict)  # {repo: [deps]}
    shared_patterns: list[str] = field(default_factory=list)

    @property
    def repo_names(self) -> list[str]:
        """List of repository names."""
        return [r.name for r in self.repos]

    def get_repo(self, name: str) -> RepoContext | None:
        """Get a repository context by name."""
        for repo in self.repos:
            if repo.name == name:
                return repo
        return None

    def to_prompt_section(self) -> str:
        """Generate a context section for inclusion in prompts."""
        lines = [
            "## Workspace Context",
            "",
            f"**Workspace:** {self.workspace_name}",
            f"**Repositories:** {len(self.repos)}",
            "",
        ]

        for repo in self.repos:
            lines.append(f"### {repo.name} ({repo.type or 'unknown'})")
            lines.append(f"- Path: `{repo.path}`")
            if repo.key_files:
                lines.append(f"- Key files: {', '.join(repo.key_files[:5])}")
            if repo.name in self.relationships and self.relationships[repo.name]:
                deps = ", ".join(self.relationships[repo.name])
                lines.append(f"- Depends on: {deps}")
            lines.append("")

        if self.shared_patterns:
            lines.append("### Shared Patterns")
            for pattern in self.shared_patterns:
                lines.append(f"- {pattern}")
            lines.append("")

        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "workspace_name": self.workspace_name,
            "repos": [r.to_dict() for r in self.repos],
            "relationships": self.relationships,
            "shared_patterns": self.shared_patterns,
        }


def load_workspace_context(config_path: Path | None = None) -> WorkspaceContext | None:
    """Load unified context for all repositories in workspace.

    Args:
        config_path: Path to workspace config.

    Returns:
        WorkspaceContext object or None if no workspace configured.
    """
    config = load_workspace(config_path)
    workspace = config.get_active()

    if not workspace:
        return None

    repos = []
    relationships: dict[str, list[str]] = {}

    for repo_config in workspace.enabled_repos:
        repo_ctx = _load_repo_context(repo_config)
        if repo_ctx:
            repos.append(repo_ctx)

        # Get dependencies
        deps = workspace.get_dependencies(repo_config.name)
        if deps:
            relationships[repo_config.name] = deps

    # Detect shared patterns
    shared = _detect_shared_patterns(repos)

    return WorkspaceContext(
        workspace_name=workspace.name,
        repos=repos,
        relationships=relationships,
        shared_patterns=shared,
    )


def _load_repo_context(repo: RepoConfig) -> RepoContext | None:
    """Load context for a single repository."""
    if not repo.exists():
        logger.warning(f"Repository path does not exist: {repo.path}")
        return None

    path = repo.resolved_path

    # Load documentation files
    claude_md = _read_file(path / "CLAUDE.md")
    architecture_md = _read_file(path / "ARCHITECTURE.md")
    readme_md = _read_file(path / "README.md")

    # Detect key files
    key_files = _detect_key_files(path, repo.type)

    return RepoContext(
        name=repo.name,
        path=path,
        type=repo.type,
        claude_md=claude_md,
        architecture_md=architecture_md,
        readme_md=readme_md,
        key_files=key_files,
    )


def _read_file(path: Path) -> str | None:
    """Read a file if it exists."""
    if path.exists() and path.is_file():
        try:
            return path.read_text()
        except Exception:
            return None
    return None


def _detect_key_files(path: Path, repo_type: str) -> list[str]:
    """Detect key files in a repository based on type."""
    key_files = []

    # Common files
    common = [
        "package.json",
        "pyproject.toml",
        "requirements.txt",
        "Cargo.toml",
        "go.mod",
        "tsconfig.json",
        ".env.example",
    ]
    for f in common:
        if (path / f).exists():
            key_files.append(f)

    # Type-specific files
    type_specific: dict[str, list[str]] = {
        "nextjs": ["next.config.js", "next.config.mjs", "app/layout.tsx", "pages/_app.tsx"],
        "react": ["src/App.tsx", "src/App.jsx", "src/index.tsx"],
        "vue": ["src/App.vue", "src/main.ts", "vite.config.ts"],
        "fastapi": ["main.py", "app/main.py", "src/main.py"],
        "django": ["manage.py", "settings.py", "urls.py"],
        "flask": ["app.py", "application.py", "wsgi.py"],
        "go": ["main.go", "cmd/main.go"],
        "rust": ["src/main.rs", "src/lib.rs"],
    }

    for f in type_specific.get(repo_type, []):
        if (path / f).exists():
            key_files.append(f)

    return key_files[:10]  # Limit to 10


def _detect_shared_patterns(repos: list[RepoContext]) -> list[str]:
    """Detect patterns shared across repositories."""
    patterns = []

    # Check for common documentation patterns
    has_claude_md = sum(1 for r in repos if r.claude_md)
    if has_claude_md >= 2:
        patterns.append("CLAUDE.md documentation convention")

    # Check for API contracts (openapi, swagger)
    # This would need more sophisticated detection

    return patterns


def read_file_from_workspace(
    file_path: str,
    repo_name: str | None = None,
    config_path: Path | None = None,
) -> str | None:
    """Read a file from any repository in the workspace.

    Args:
        file_path: Path to file (relative to repo root).
        repo_name: Repository name. If None, searches all repos.
        config_path: Path to workspace config.

    Returns:
        File contents or None if not found.
    """
    config = load_workspace(config_path)
    workspace = config.get_active()

    if not workspace:
        # No workspace, try current directory
        full_path = Path.cwd() / file_path
        return _read_file(full_path)

    if repo_name:
        # Read from specific repo
        repo = workspace.get_repo(repo_name)
        if repo:
            full_path = repo.resolved_path / file_path
            return _read_file(full_path)
        return None

    # Search all repos
    for repo in workspace.enabled_repos:
        full_path = repo.resolved_path / file_path
        content = _read_file(full_path)
        if content:
            return content

    return None


def get_api_contracts(config_path: Path | None = None) -> dict[str, Any]:
    """Extract API contracts from workspace repositories.

    Looks for OpenAPI specs, TypeScript interfaces, and other
    API definition files.

    Args:
        config_path: Path to workspace config.

    Returns:
        Dictionary mapping repo names to their API contracts.
    """
    config = load_workspace(config_path)
    workspace = config.get_active()

    contracts: dict[str, Any] = {}

    if not workspace:
        return contracts

    for repo in workspace.enabled_repos:
        repo_contracts = _extract_repo_contracts(repo)
        if repo_contracts:
            contracts[repo.name] = repo_contracts

    return contracts


def _extract_repo_contracts(repo: RepoConfig) -> dict[str, Any] | None:
    """Extract API contracts from a repository."""
    if not repo.exists():
        return None

    path = repo.resolved_path
    contracts: dict[str, Any] = {}

    # Look for OpenAPI specs
    openapi_paths = [
        "openapi.yaml",
        "openapi.json",
        "swagger.yaml",
        "swagger.json",
        "api/openapi.yaml",
        "docs/openapi.yaml",
    ]
    for spec_path in openapi_paths:
        full_path = path / spec_path
        if full_path.exists():
            contracts["openapi"] = str(full_path)
            break

    # Look for TypeScript types
    type_paths = [
        "types/index.ts",
        "src/types/index.ts",
        "src/types/api.ts",
        "shared/types.ts",
    ]
    for type_path in type_paths:
        full_path = path / type_path
        if full_path.exists():
            contracts["typescript_types"] = str(full_path)
            break

    # Look for Python type stubs or schemas
    python_paths = [
        "schemas.py",
        "models.py",
        "app/schemas.py",
        "src/schemas.py",
    ]
    for py_path in python_paths:
        full_path = path / py_path
        if full_path.exists():
            contracts["python_schemas"] = str(full_path)
            break

    return contracts if contracts else None


def build_workspace_prompt_context(
    task_description: str,
    target_repo: str | None = None,
    config_path: Path | None = None,
) -> str:
    """Build context section for agent prompts in multi-repo workspace.

    Args:
        task_description: Description of the current task.
        target_repo: Primary repository for the task.
        config_path: Path to workspace config.

    Returns:
        Formatted context string for inclusion in prompts.
    """
    ctx = load_workspace_context(config_path)

    if not ctx:
        return ""

    lines = [
        "---",
        "## Multi-Repo Workspace Context",
        "",
        f"You are working in the **{ctx.workspace_name}** workspace.",
        "",
    ]

    # Describe available repositories
    lines.append("### Available Repositories")
    for repo in ctx.repos:
        marker = " **(current)**" if repo.name == target_repo else ""
        lines.append(f"- **{repo.name}**{marker} ({repo.type or 'unknown'}): `{repo.path}`")
        if repo.name in ctx.relationships and ctx.relationships[repo.name]:
            deps = ", ".join(ctx.relationships[repo.name])
            lines.append(f"  - Depends on: {deps}")

    lines.append("")

    # Add cross-repo notes
    if target_repo and ctx.relationships.get(target_repo):
        deps = ctx.relationships[target_repo]
        lines.append("### Cross-Repo Dependencies")
        lines.append(f"This repo depends on: {', '.join(deps)}")
        lines.append("You can read files from these repos if needed.")
        lines.append("")

    # Add shared patterns
    if ctx.shared_patterns:
        lines.append("### Shared Patterns")
        for pattern in ctx.shared_patterns:
            lines.append(f"- {pattern}")
        lines.append("")

    lines.append("---")
    lines.append("")

    return "\n".join(lines)
