"""Workspace configuration for multi-repo orchestration.

Manages workspace.toml configuration for coordinating multiple repositories.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Default workspace config location
DEFAULT_WORKSPACE_DIR = Path.home() / ".adw"
DEFAULT_WORKSPACE_FILE = "workspace.toml"


@dataclass
class RepoConfig:
    """Configuration for a single repository in the workspace."""

    name: str
    path: str  # Full path to the repository
    type: str = ""  # Project type (e.g., nextjs, fastapi, python)
    default_branch: str = "main"
    default_workflow: str = "sdlc"
    enabled: bool = True
    added_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for TOML serialization."""
        result: dict[str, Any] = {
            "name": self.name,
            "path": self.path,
            "default_branch": self.default_branch,
            "default_workflow": self.default_workflow,
            "enabled": self.enabled,
        }
        # Only include optional fields if they have values (TOML doesn't support None)
        if self.type:
            result["type"] = self.type
        if self.added_at:
            result["added_at"] = self.added_at.isoformat()
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RepoConfig:
        """Create from dictionary."""
        added_at = None
        if data.get("added_at"):
            try:
                added_at = datetime.fromisoformat(data["added_at"])
            except (ValueError, TypeError):
                pass

        return cls(
            name=data.get("name", ""),
            path=data.get("path", ""),
            type=data.get("type", ""),
            default_branch=data.get("default_branch", "main"),
            default_workflow=data.get("default_workflow", "sdlc"),
            enabled=data.get("enabled", True),
            added_at=added_at,
        )

    @property
    def resolved_path(self) -> Path:
        """Get the resolved absolute path."""
        return Path(self.path).expanduser().resolve()

    def exists(self) -> bool:
        """Check if the repository path exists."""
        return self.resolved_path.exists()

    def is_git_repo(self) -> bool:
        """Check if the path is a git repository."""
        git_dir = self.resolved_path / ".git"
        return git_dir.exists() and git_dir.is_dir()

    def has_adw(self) -> bool:
        """Check if the repository has ADW initialized."""
        adw_dir = self.resolved_path / ".adw"
        return adw_dir.exists() and adw_dir.is_dir()


@dataclass
class Relationship:
    """Dependency relationship between repositories."""

    source: str  # Repo name that depends on target
    target: str  # Repo name that source depends on
    relationship_type: str = "depends_on"  # depends_on, integrates_with

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for TOML serialization."""
        return {
            "source": self.source,
            "target": self.target,
            "type": self.relationship_type,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Relationship:
        """Create from dictionary."""
        return cls(
            source=data.get("source", ""),
            target=data.get("target", ""),
            relationship_type=data.get("type", "depends_on"),
        )


@dataclass
class Workspace:
    """A named workspace containing multiple repositories."""

    name: str
    repos: list[RepoConfig] = field(default_factory=list)
    relationships: list[Relationship] = field(default_factory=list)
    created_at: datetime | None = None
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for TOML serialization."""
        workspace_data: dict[str, Any] = {"name": self.name}
        # Only include optional fields if they have values (TOML doesn't support None)
        if self.description:
            workspace_data["description"] = self.description
        if self.created_at:
            workspace_data["created_at"] = self.created_at.isoformat()

        result: dict[str, Any] = {
            "workspace": workspace_data,
            "repos": [r.to_dict() for r in self.repos],
        }

        if self.relationships:
            result["relationships"] = {}
            for rel in self.relationships:
                if rel.source not in result["relationships"]:
                    result["relationships"][rel.source] = {}
                result["relationships"][rel.source][rel.relationship_type] = rel.target

        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Workspace:
        """Create from dictionary."""
        workspace_data = data.get("workspace", {})

        created_at = None
        if workspace_data.get("created_at"):
            try:
                created_at = datetime.fromisoformat(workspace_data["created_at"])
            except (ValueError, TypeError):
                pass

        # Parse repos
        repos = []
        repos_data = data.get("repos", [])
        if isinstance(repos_data, list):
            repos = [RepoConfig.from_dict(r) for r in repos_data]

        # Parse relationships
        relationships = []
        rel_data = data.get("relationships", {})
        if isinstance(rel_data, dict):
            for source, rels in rel_data.items():
                if isinstance(rels, dict):
                    for rel_type, target in rels.items():
                        relationships.append(
                            Relationship(
                                source=source,
                                target=target,
                                relationship_type=rel_type,
                            )
                        )

        return cls(
            name=workspace_data.get("name", "default"),
            description=workspace_data.get("description", ""),
            repos=repos,
            relationships=relationships,
            created_at=created_at,
        )

    def get_repo(self, name: str) -> RepoConfig | None:
        """Get a repository by name."""
        for repo in self.repos:
            if repo.name == name:
                return repo
        return None

    def get_repo_by_path(self, path: str | Path) -> RepoConfig | None:
        """Get a repository by path."""
        target = Path(path).expanduser().resolve()
        for repo in self.repos:
            if repo.resolved_path == target:
                return repo
        return None

    def add_repo(self, repo: RepoConfig) -> bool:
        """Add a repository to the workspace.

        Returns True if added, False if already exists.
        """
        if self.get_repo(repo.name):
            logger.warning(f"Repository '{repo.name}' already exists in workspace")
            return False

        if self.get_repo_by_path(repo.path):
            logger.warning(f"Repository at '{repo.path}' already exists in workspace")
            return False

        self.repos.append(repo)
        return True

    def remove_repo(self, name: str) -> bool:
        """Remove a repository from the workspace.

        Returns True if removed, False if not found.
        """
        for i, repo in enumerate(self.repos):
            if repo.name == name:
                self.repos.pop(i)
                # Also remove relationships involving this repo
                self.relationships = [r for r in self.relationships if r.source != name and r.target != name]
                return True
        return False

    def get_dependencies(self, repo_name: str) -> list[str]:
        """Get repositories that the given repo depends on."""
        deps = []
        for rel in self.relationships:
            if rel.source == repo_name and rel.relationship_type == "depends_on":
                deps.append(rel.target)
        return deps

    def get_dependents(self, repo_name: str) -> list[str]:
        """Get repositories that depend on the given repo."""
        deps = []
        for rel in self.relationships:
            if rel.target == repo_name and rel.relationship_type == "depends_on":
                deps.append(rel.source)
        return deps

    @property
    def repo_count(self) -> int:
        """Number of repositories in the workspace."""
        return len(self.repos)

    @property
    def enabled_repos(self) -> list[RepoConfig]:
        """Get only enabled repositories."""
        return [r for r in self.repos if r.enabled]


@dataclass
class WorkspaceConfig:
    """Top-level configuration containing multiple workspaces."""

    workspaces: list[Workspace] = field(default_factory=list)
    active_workspace: str = "default"
    config_version: str = "1.0"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for TOML serialization."""
        return {
            "config": {
                "version": self.config_version,
                "active_workspace": self.active_workspace,
            },
            "workspaces": {w.name: w.to_dict() for w in self.workspaces},
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WorkspaceConfig:
        """Create from dictionary."""
        config_data = data.get("config", {})

        workspaces = []
        workspaces_data = data.get("workspaces", {})
        if isinstance(workspaces_data, dict):
            for name, ws_data in workspaces_data.items():
                if isinstance(ws_data, dict):
                    # Ensure workspace name is set
                    if "workspace" not in ws_data:
                        ws_data["workspace"] = {}
                    ws_data["workspace"]["name"] = name
                    workspaces.append(Workspace.from_dict(ws_data))

        return cls(
            workspaces=workspaces,
            active_workspace=config_data.get("active_workspace", "default"),
            config_version=config_data.get("version", "1.0"),
        )

    def get_workspace(self, name: str) -> Workspace | None:
        """Get a workspace by name."""
        for ws in self.workspaces:
            if ws.name == name:
                return ws
        return None

    def get_active(self) -> Workspace | None:
        """Get the active workspace."""
        return self.get_workspace(self.active_workspace)

    def set_active(self, name: str) -> bool:
        """Set the active workspace.

        Returns True if set, False if workspace not found.
        """
        if self.get_workspace(name):
            self.active_workspace = name
            return True
        return False

    def add_workspace(self, workspace: Workspace) -> bool:
        """Add a workspace.

        Returns True if added, False if already exists.
        """
        if self.get_workspace(workspace.name):
            return False
        self.workspaces.append(workspace)
        return True

    def remove_workspace(self, name: str) -> bool:
        """Remove a workspace.

        Returns True if removed, False if not found.
        """
        for i, ws in enumerate(self.workspaces):
            if ws.name == name:
                self.workspaces.pop(i)
                # If removed the active workspace, reset to default
                if self.active_workspace == name:
                    self.active_workspace = "default" if self.workspaces else ""
                return True
        return False


def get_workspace_config_path() -> Path:
    """Get the path to the workspace configuration file."""
    # Allow override via environment variable
    if custom_path := os.environ.get("ADW_WORKSPACE_CONFIG"):
        return Path(custom_path)

    workspace_dir = DEFAULT_WORKSPACE_DIR
    workspace_dir.mkdir(parents=True, exist_ok=True)
    return workspace_dir / DEFAULT_WORKSPACE_FILE


def load_workspace(config_path: Path | None = None) -> WorkspaceConfig:
    """Load workspace configuration from TOML file.

    Args:
        config_path: Path to config file. Uses default if not specified.

    Returns:
        WorkspaceConfig object (empty if file doesn't exist).
    """
    path = config_path or get_workspace_config_path()

    if not path.exists():
        logger.debug(f"Workspace config not found at {path}, returning empty config")
        return WorkspaceConfig()

    try:
        # Use tomli for reading TOML (Python 3.11+ has tomllib)
        try:
            import tomllib
        except ImportError:
            import tomli as tomllib  # type: ignore

        with open(path, "rb") as f:
            data = tomllib.load(f)

        return WorkspaceConfig.from_dict(data)

    except Exception as e:
        logger.error(f"Failed to load workspace config from {path}: {e}")
        return WorkspaceConfig()


def save_workspace(config: WorkspaceConfig, config_path: Path | None = None) -> bool:
    """Save workspace configuration to TOML file.

    Args:
        config: WorkspaceConfig to save.
        config_path: Path to config file. Uses default if not specified.

    Returns:
        True if saved successfully, False otherwise.
    """
    path = config_path or get_workspace_config_path()

    try:
        # Use tomli-w for writing TOML
        import tomli_w

        # Ensure parent directory exists
        path.parent.mkdir(parents=True, exist_ok=True)

        data = config.to_dict()

        with open(path, "wb") as f:
            tomli_w.dump(data, f)

        logger.info(f"Saved workspace config to {path}")
        return True

    except ImportError:
        # Fallback: write as simple TOML manually
        logger.warning("tomli-w not installed, using simple TOML writer")
        return _write_simple_toml(config, path)

    except Exception as e:
        logger.error(f"Failed to save workspace config: {e}")
        return False


def _write_simple_toml(config: WorkspaceConfig, path: Path) -> bool:
    """Write workspace config as simple TOML without tomli-w."""
    try:
        lines = []
        lines.append("# ADW Workspace Configuration")
        lines.append(f"# Generated: {datetime.now().isoformat()}")
        lines.append("")

        # Config section
        lines.append("[config]")
        lines.append(f'version = "{config.config_version}"')
        lines.append(f'active_workspace = "{config.active_workspace}"')
        lines.append("")

        # Workspaces
        for ws in config.workspaces:
            lines.append(f"[workspaces.{ws.name}.workspace]")
            lines.append(f'name = "{ws.name}"')
            if ws.description:
                lines.append(f'description = "{ws.description}"')
            if ws.created_at:
                lines.append(f'created_at = "{ws.created_at.isoformat()}"')
            lines.append("")

            # Repos
            for i, repo in enumerate(ws.repos):
                lines.append(f"[[workspaces.{ws.name}.repos]]")
                lines.append(f'name = "{repo.name}"')
                lines.append(f'path = "{repo.path}"')
                if repo.type:
                    lines.append(f'type = "{repo.type}"')
                lines.append(f'default_branch = "{repo.default_branch}"')
                lines.append(f'default_workflow = "{repo.default_workflow}"')
                lines.append(f"enabled = {str(repo.enabled).lower()}")
                if repo.added_at:
                    lines.append(f'added_at = "{repo.added_at.isoformat()}"')
                lines.append("")

            # Relationships
            if ws.relationships:
                lines.append(f"[workspaces.{ws.name}.relationships]")
                for rel in ws.relationships:
                    lines.append(f"[workspaces.{ws.name}.relationships.{rel.source}]")
                    lines.append(f'{rel.relationship_type} = "{rel.target}"')
                lines.append("")

        path.write_text("\n".join(lines))
        return True

    except Exception as e:
        logger.error(f"Failed to write simple TOML: {e}")
        return False


def init_workspace(
    name: str = "default",
    description: str = "",
    config_path: Path | None = None,
) -> Workspace:
    """Initialize a new workspace.

    Args:
        name: Workspace name.
        description: Optional description.
        config_path: Path to config file.

    Returns:
        The created Workspace object.
    """
    config = load_workspace(config_path)

    # Check if workspace already exists
    existing = config.get_workspace(name)
    if existing:
        logger.info(f"Workspace '{name}' already exists")
        return existing

    # Create new workspace
    workspace = Workspace(
        name=name,
        description=description,
        created_at=datetime.now(),
    )

    config.add_workspace(workspace)
    config.active_workspace = name
    save_workspace(config, config_path)

    logger.info(f"Initialized workspace: {name}")
    return workspace


def add_repo(
    path: str | Path,
    name: str | None = None,
    repo_type: str = "",
    workspace_name: str | None = None,
    config_path: Path | None = None,
) -> RepoConfig | None:
    """Add a repository to the workspace.

    Args:
        path: Path to the repository.
        name: Optional name (defaults to directory name).
        repo_type: Repository type (e.g., 'nextjs', 'fastapi').
        workspace_name: Workspace to add to (uses active if not specified).
        config_path: Path to config file.

    Returns:
        The created RepoConfig, or None if failed.
    """
    config = load_workspace(config_path)

    # Get target workspace
    ws_name = workspace_name or config.active_workspace
    workspace = config.get_workspace(ws_name)

    if not workspace:
        # Create default workspace if needed
        workspace = init_workspace(ws_name, config_path=config_path)
        config = load_workspace(config_path)  # Reload
        workspace = config.get_workspace(ws_name)

    if not workspace:
        logger.error(f"Could not get or create workspace '{ws_name}'")
        return None

    # Resolve path
    resolved = Path(path).expanduser().resolve()
    if not resolved.exists():
        logger.error(f"Repository path does not exist: {resolved}")
        return None

    # Determine name
    repo_name = name or resolved.name

    # Detect type if not provided
    if not repo_type:
        repo_type = _detect_repo_type(resolved)

    # Create repo config
    repo = RepoConfig(
        name=repo_name,
        path=str(resolved),
        type=repo_type,
        added_at=datetime.now(),
    )

    # Add to workspace
    if not workspace.add_repo(repo):
        logger.error(f"Failed to add repository '{repo_name}' to workspace")
        return None

    # Save config
    save_workspace(config, config_path)
    logger.info(f"Added repository '{repo_name}' to workspace '{ws_name}'")
    return repo


def _detect_repo_type(path: Path) -> str:
    """Auto-detect repository type from files."""
    # Check for common config files
    if (path / "next.config.js").exists() or (path / "next.config.mjs").exists():
        return "nextjs"
    if (path / "nuxt.config.ts").exists() or (path / "nuxt.config.js").exists():
        return "nuxt"
    if (path / "vite.config.ts").exists() or (path / "vite.config.js").exists():
        if (path / "src" / "App.vue").exists():
            return "vue"
        return "vite"
    if (path / "angular.json").exists():
        return "angular"

    # Python frameworks
    if (path / "pyproject.toml").exists():
        pyproject = (path / "pyproject.toml").read_text()
        if "fastapi" in pyproject.lower():
            return "fastapi"
        if "django" in pyproject.lower():
            return "django"
        if "flask" in pyproject.lower():
            return "flask"
        return "python"

    if (path / "requirements.txt").exists():
        reqs = (path / "requirements.txt").read_text().lower()
        if "fastapi" in reqs:
            return "fastapi"
        if "django" in reqs:
            return "django"
        if "flask" in reqs:
            return "flask"
        return "python"

    # Node.js
    if (path / "package.json").exists():
        try:
            import json

            pkg = json.loads((path / "package.json").read_text())
            deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
            if "react" in deps:
                return "react"
            if "vue" in deps:
                return "vue"
            if "svelte" in deps:
                return "svelte"
            return "nodejs"
        except (json.JSONDecodeError, OSError):
            return "nodejs"

    # Go
    if (path / "go.mod").exists():
        return "go"

    # Rust
    if (path / "Cargo.toml").exists():
        return "rust"

    return ""


def remove_repo(
    name: str,
    workspace_name: str | None = None,
    config_path: Path | None = None,
) -> bool:
    """Remove a repository from the workspace.

    Args:
        name: Repository name to remove.
        workspace_name: Workspace to remove from (uses active if not specified).
        config_path: Path to config file.

    Returns:
        True if removed, False if not found.
    """
    config = load_workspace(config_path)

    ws_name = workspace_name or config.active_workspace
    workspace = config.get_workspace(ws_name)

    if not workspace:
        logger.error(f"Workspace '{ws_name}' not found")
        return False

    if workspace.remove_repo(name):
        save_workspace(config, config_path)
        logger.info(f"Removed repository '{name}' from workspace '{ws_name}'")
        return True

    logger.error(f"Repository '{name}' not found in workspace '{ws_name}'")
    return False


def list_repos(
    workspace_name: str | None = None,
    config_path: Path | None = None,
) -> list[RepoConfig]:
    """List all repositories in the workspace.

    Args:
        workspace_name: Workspace to list from (uses active if not specified).
        config_path: Path to config file.

    Returns:
        List of RepoConfig objects.
    """
    config = load_workspace(config_path)

    ws_name = workspace_name or config.active_workspace
    workspace = config.get_workspace(ws_name)

    if not workspace:
        return []

    return workspace.repos


def get_repo_by_name(
    name: str,
    workspace_name: str | None = None,
    config_path: Path | None = None,
) -> RepoConfig | None:
    """Get a repository by name.

    Args:
        name: Repository name.
        workspace_name: Workspace to search (uses active if not specified).
        config_path: Path to config file.

    Returns:
        RepoConfig if found, None otherwise.
    """
    config = load_workspace(config_path)

    ws_name = workspace_name or config.active_workspace
    workspace = config.get_workspace(ws_name)

    if not workspace:
        return None

    return workspace.get_repo(name)


def get_repo_by_path(
    path: str | Path,
    workspace_name: str | None = None,
    config_path: Path | None = None,
) -> RepoConfig | None:
    """Get a repository by path.

    Args:
        path: Repository path.
        workspace_name: Workspace to search (uses active if not specified).
        config_path: Path to config file.

    Returns:
        RepoConfig if found, None otherwise.
    """
    config = load_workspace(config_path)

    ws_name = workspace_name or config.active_workspace
    workspace = config.get_workspace(ws_name)

    if not workspace:
        return None

    return workspace.get_repo_by_path(path)


def get_active_workspace(config_path: Path | None = None) -> Workspace | None:
    """Get the currently active workspace.

    Args:
        config_path: Path to config file.

    Returns:
        Active Workspace if exists, None otherwise.
    """
    config = load_workspace(config_path)
    return config.get_active()
