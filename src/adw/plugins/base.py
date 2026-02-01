"""Plugin base class for ADW plugins."""

from __future__ import annotations

from abc import ABC
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import click


class Plugin(ABC):
    """Base class for ADW plugins.
    
    Plugins can:
    - Hook into task lifecycle (init, plan, implement, complete, fail)
    - Add CLI commands
    - Manage their own configuration
    - Handle installation/uninstallation
    
    Example:
        class MyPlugin(Plugin):
            name = "my-plugin"
            version = "1.0.0"
            description = "Does something cool"
            
            def on_plan(self, task: str, context: str) -> str:
                return context + "\\n\\nExtra context from my plugin"
    """
    
    # Required metadata
    name: str = "unnamed"
    version: str = "0.0.0"
    description: str = ""
    
    # Optional metadata
    author: str = ""
    requires_external: list[str] = []  # External CLI tools needed
    
    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize plugin with config.
        
        Args:
            config: Plugin configuration from .adw/config.toml
        """
        self.config = config or {}
        self.enabled = self.config.get("enabled", True)
    
    # =========================================================================
    # Lifecycle Hooks
    # =========================================================================
    
    def on_init(self, project_path: Path) -> None:
        """Called during 'adw init'.
        
        Use this to set up plugin resources for a project.
        
        Args:
            project_path: Path to project being initialized
        """
        pass
    
    def on_plan(self, task: str, context: str) -> str:
        """Called before planner phase.
        
        Use this to inject additional context for planning.
        
        Args:
            task: Task description
            context: Current context string
            
        Returns:
            Modified context string
        """
        return context
    
    def on_implement(self, task: str, plan: str) -> str:
        """Called before builder/implement phase.
        
        Use this to modify the plan before implementation.
        
        Args:
            task: Task description
            plan: Current plan/spec content
            
        Returns:
            Modified plan string
        """
        return plan
    
    def on_complete(self, task: str, result: dict[str, Any]) -> None:
        """Called after task completes successfully.
        
        Use this for post-task actions like notifications, PR creation, etc.
        
        Args:
            task: Task description
            result: Result dict with keys like 'commit_hash', 'files_changed', etc.
        """
        pass
    
    def on_fail(self, task: str, error: str) -> None:
        """Called when a task fails.
        
        Use this for error reporting, notifications, etc.
        
        Args:
            task: Task description
            error: Error message
        """
        pass
    
    # =========================================================================
    # CLI Extension
    # =========================================================================
    
    def get_commands(self) -> list[click.Command | click.Group]:
        """Return Click commands to register.
        
        Commands are registered under 'adw <plugin-name> <command>'.
        
        Returns:
            List of Click command objects
        """
        return []
    
    # =========================================================================
    # Status & Info
    # =========================================================================
    
    def status(self) -> dict[str, Any]:
        """Return plugin status for 'adw plugin status'.
        
        Returns:
            Dict with status info (enabled, version, custom fields)
        """
        return {
            "name": self.name,
            "version": self.version,
            "enabled": self.enabled,
        }
    
    def check_requirements(self) -> tuple[bool, str | None]:
        """Check if external requirements are met.
        
        Returns:
            Tuple of (success, error_message)
        """
        import shutil
        
        for req in self.requires_external:
            if not shutil.which(req):
                return False, f"Missing required tool: {req}"
        return True, None
    
    # =========================================================================
    # Installation Hooks
    # =========================================================================
    
    @classmethod
    def install(cls, plugin_dir: Path) -> tuple[bool, str | None]:
        """Called during plugin installation.
        
        Override to perform custom installation steps.
        
        Args:
            plugin_dir: Directory where plugin is installed
            
        Returns:
            Tuple of (success, error_message)
        """
        return True, None
    
    @classmethod
    def uninstall(cls, plugin_dir: Path) -> tuple[bool, str | None]:
        """Called during plugin removal.
        
        Override to perform cleanup.
        
        Args:
            plugin_dir: Directory where plugin is installed
            
        Returns:
            Tuple of (success, error_message)
        """
        return True, None
