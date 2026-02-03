"""Workspace module for multi-repo orchestration.

Enables ADW to work across multiple repositories like a real development team,
allowing coordination of tasks, dependencies, and pull requests across separate codebases.
"""

from .config import (
    Relationship,
    RepoConfig,
    Workspace,
    WorkspaceConfig,
    add_repo,
    get_active_workspace,
    get_repo_by_name,
    get_repo_by_path,
    get_workspace_config_path,
    init_workspace,
    list_repos,
    load_workspace,
    remove_repo,
    save_workspace,
)
from .context import (
    RepoContext,
    WorkspaceContext,
    build_workspace_prompt_context,
    get_api_contracts,
    load_workspace_context,
    read_file_from_workspace,
)
from .tasks import (
    CrossRepoDependency,
    CrossRepoTask,
    WorkspaceTaskQueue,
    add_cross_repo_task,
    detect_repo_from_path,
    load_workspace_tasks,
    parse_task_spec,
)

__all__ = [
    # Data classes - config
    "RepoConfig",
    "Relationship",
    "Workspace",
    "WorkspaceConfig",
    # Data classes - tasks
    "CrossRepoTask",
    "CrossRepoDependency",
    "WorkspaceTaskQueue",
    # Data classes - context
    "RepoContext",
    "WorkspaceContext",
    # Functions - config
    "get_workspace_config_path",
    "load_workspace",
    "save_workspace",
    "init_workspace",
    "add_repo",
    "remove_repo",
    "list_repos",
    "get_repo_by_name",
    "get_repo_by_path",
    "get_active_workspace",
    # Functions - tasks
    "load_workspace_tasks",
    "detect_repo_from_path",
    "parse_task_spec",
    "add_cross_repo_task",
    # Functions - context
    "load_workspace_context",
    "read_file_from_workspace",
    "get_api_contracts",
    "build_workspace_prompt_context",
]
