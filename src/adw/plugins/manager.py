"""Plugin manager for discovering, loading, and managing plugins."""

from __future__ import annotations

import importlib.util
import shutil
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .base import Plugin

# Singleton instance
_manager: "PluginManager | None" = None


def get_plugin_manager() -> "PluginManager":
    """Get the global plugin manager instance."""
    global _manager
    if _manager is None:
        _manager = PluginManager()
    return _manager


class PluginManager:
    """Discovers, loads, and manages ADW plugins.
    
    Plugins are stored in ~/.adw/plugins/<name>/ and must have:
    - __init__.py with a Plugin subclass
    - plugin.toml with metadata (optional but recommended)
    
    Usage:
        manager = get_plugin_manager()
        manager.dispatch_plan("my task", "context")
    """
    
    PLUGINS_DIR = Path.home() / ".adw" / "plugins"
    BUILTIN_PLUGINS = ["qmd"]  # Plugins that come with ADW
    
    def __init__(self):
        self._plugins: dict[str, Plugin] = {}
        self._config: dict[str, dict] = {}
        self._load_config()
        self._load_plugins()
    
    def _load_config(self) -> None:
        """Load plugin config from ~/.adw/config.toml."""
        config_path = Path.home() / ".adw" / "config.toml"
        if not config_path.exists():
            return
        
        try:
            import tomllib
        except ImportError:
            try:
                import tomli as tomllib
            except ImportError:
                return
        
        try:
            with open(config_path, "rb") as f:
                config = tomllib.load(f)
            self._config = config.get("plugins", {})
        except Exception:
            pass
    
    def _load_plugins(self) -> None:
        """Discover and load installed plugins."""
        # Load built-in plugins first
        self._load_builtin_plugins()
        
        # Then load user plugins
        if not self.PLUGINS_DIR.exists():
            return
        
        for plugin_dir in self.PLUGINS_DIR.iterdir():
            if plugin_dir.is_dir():
                self._load_plugin(plugin_dir)
    
    def _load_builtin_plugins(self) -> None:
        """Load plugins that come bundled with ADW."""
        for name in self.BUILTIN_PLUGINS:
            try:
                # Import from adw.plugins.builtins.<name>
                module = importlib.import_module(f"adw.plugins.builtins.{name}")
                plugin_class = getattr(module, "plugin_class", None)
                if plugin_class:
                    config = self._config.get(name, {})
                    self._plugins[name] = plugin_class(config)
            except ImportError:
                # Built-in not available, skip
                pass
    
    def _load_plugin(self, plugin_dir: Path) -> bool:
        """Load a single plugin from directory.
        
        Args:
            plugin_dir: Path to plugin directory
            
        Returns:
            True if loaded successfully
        """
        name = plugin_dir.name
        init_file = plugin_dir / "__init__.py"
        
        if not init_file.exists():
            return False
        
        try:
            # Load module dynamically
            spec = importlib.util.spec_from_file_location(
                f"adw_plugin_{name}",
                init_file,
            )
            if spec is None or spec.loader is None:
                return False
            
            module = importlib.util.module_from_spec(spec)
            sys.modules[f"adw_plugin_{name}"] = module
            spec.loader.exec_module(module)
            
            # Get plugin class
            plugin_class = getattr(module, "plugin_class", None)
            if plugin_class is None:
                # Try to find any Plugin subclass
                from .base import Plugin
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (
                        isinstance(attr, type) 
                        and issubclass(attr, Plugin) 
                        and attr is not Plugin
                    ):
                        plugin_class = attr
                        break
            
            if plugin_class is None:
                return False
            
            # Instantiate with config
            config = self._config.get(name, {})
            self._plugins[name] = plugin_class(config)
            return True
            
        except Exception as e:
            # Log error but don't crash
            print(f"Failed to load plugin {name}: {e}")
            return False
    
    # =========================================================================
    # Plugin Access
    # =========================================================================
    
    def get(self, name: str) -> "Plugin | None":
        """Get a loaded plugin by name."""
        return self._plugins.get(name)
    
    @property
    def all(self) -> list["Plugin"]:
        """Get all loaded plugins."""
        return list(self._plugins.values())
    
    @property
    def enabled(self) -> list["Plugin"]:
        """Get all enabled plugins."""
        return [p for p in self._plugins.values() if p.enabled]
    
    def is_installed(self, name: str) -> bool:
        """Check if a plugin is installed."""
        return name in self._plugins
    
    # =========================================================================
    # Hook Dispatchers
    # =========================================================================
    
    def dispatch_init(self, project_path: Path) -> None:
        """Dispatch on_init to all enabled plugins."""
        for plugin in self.enabled:
            try:
                plugin.on_init(project_path)
            except Exception as e:
                print(f"Plugin {plugin.name} on_init error: {e}")
    
    def dispatch_plan(self, task: str, context: str) -> str:
        """Dispatch on_plan to all enabled plugins.
        
        Returns modified context.
        """
        for plugin in self.enabled:
            try:
                context = plugin.on_plan(task, context)
            except Exception as e:
                print(f"Plugin {plugin.name} on_plan error: {e}")
        return context
    
    def dispatch_implement(self, task: str, plan: str) -> str:
        """Dispatch on_implement to all enabled plugins.
        
        Returns modified plan.
        """
        for plugin in self.enabled:
            try:
                plan = plugin.on_implement(task, plan)
            except Exception as e:
                print(f"Plugin {plugin.name} on_implement error: {e}")
        return plan
    
    def dispatch_complete(self, task: str, result: dict) -> None:
        """Dispatch on_complete to all enabled plugins."""
        for plugin in self.enabled:
            try:
                plugin.on_complete(task, result)
            except Exception as e:
                print(f"Plugin {plugin.name} on_complete error: {e}")
    
    def dispatch_fail(self, task: str, error: str) -> None:
        """Dispatch on_fail to all enabled plugins."""
        for plugin in self.enabled:
            try:
                plugin.on_fail(task, error)
            except Exception as e:
                print(f"Plugin {plugin.name} on_fail error: {e}")
    
    # =========================================================================
    # Installation
    # =========================================================================
    
    def install(self, source: str) -> tuple[bool, str]:
        """Install a plugin.
        
        Args:
            source: Plugin name, local path, or gh:user/repo
            
        Returns:
            Tuple of (success, message)
        """
        # Determine source type
        if source.startswith("gh:") or source.startswith("github:"):
            return self._install_from_github(source)
        elif Path(source).exists():
            return self._install_from_path(Path(source))
        else:
            return self._install_builtin(source)
    
    def _install_builtin(self, name: str) -> tuple[bool, str]:
        """Install a built-in plugin."""
        if name not in self.BUILTIN_PLUGINS:
            return False, f"Unknown plugin: {name}"
        
        if name in self._plugins:
            return False, f"Plugin {name} is already installed"
        
        # For built-in, just enable in config
        self._update_config(name, {"enabled": True})
        
        # Reload
        self._load_builtin_plugins()
        
        if name in self._plugins:
            # Run install hook
            plugin = self._plugins[name]
            plugin_dir = self.PLUGINS_DIR / name
            plugin_dir.mkdir(parents=True, exist_ok=True)
            success, error = plugin.install(plugin_dir)
            if not success:
                return False, error or "Installation failed"
            return True, f"Installed {name} v{plugin.version}"
        
        return False, f"Failed to load plugin {name}"
    
    def _install_from_path(self, path: Path) -> tuple[bool, str]:
        """Install a plugin from local path."""
        if not path.is_dir():
            return False, f"Not a directory: {path}"
        
        name = path.name
        dest = self.PLUGINS_DIR / name
        
        if dest.exists():
            return False, f"Plugin {name} already exists"
        
        # Copy plugin
        dest.mkdir(parents=True, exist_ok=True)
        shutil.copytree(path, dest, dirs_exist_ok=True)
        
        # Load it
        if self._load_plugin(dest):
            plugin = self._plugins[name]
            success, error = plugin.install(dest)
            if not success:
                shutil.rmtree(dest)
                return False, error or "Installation failed"
            return True, f"Installed {name} from {path}"
        
        shutil.rmtree(dest)
        return False, "Failed to load plugin"
    
    def _install_from_github(self, source: str) -> tuple[bool, str]:
        """Install a plugin from GitHub."""
        # Parse gh:user/repo or github:user/repo
        repo = source.split(":", 1)[1]
        name = repo.split("/")[-1]
        
        # Clone to temp, then copy
        import tempfile
        import subprocess
        
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                ["git", "clone", "--depth", "1", f"https://github.com/{repo}.git", tmpdir],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                return False, f"Failed to clone: {result.stderr}"
            
            return self._install_from_path(Path(tmpdir))
    
    def uninstall(self, name: str) -> tuple[bool, str]:
        """Uninstall a plugin.
        
        Args:
            name: Plugin name
            
        Returns:
            Tuple of (success, message)
        """
        if name not in self._plugins:
            return False, f"Plugin {name} is not installed"
        
        plugin = self._plugins[name]
        plugin_dir = self.PLUGINS_DIR / name
        
        # Run uninstall hook
        success, error = plugin.uninstall(plugin_dir)
        if not success:
            return False, error or "Uninstall hook failed"
        
        # Remove from loaded plugins
        del self._plugins[name]
        
        # Remove files
        if plugin_dir.exists():
            shutil.rmtree(plugin_dir)
        
        # Update config
        self._update_config(name, {"enabled": False})
        
        return True, f"Uninstalled {name}"
    
    def _update_config(self, name: str, updates: dict) -> None:
        """Update plugin config in ~/.adw/config.toml."""
        config_path = Path.home() / ".adw" / "config.toml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            import tomllib
        except ImportError:
            try:
                import tomli as tomllib
            except ImportError:
                return
        
        config = {}
        if config_path.exists():
            try:
                with open(config_path, "rb") as f:
                    config = tomllib.load(f)
            except Exception:
                pass
        
        if "plugins" not in config:
            config["plugins"] = {}
        if name not in config["plugins"]:
            config["plugins"][name] = {}
        
        config["plugins"][name].update(updates)
        
        # Write back (simple format, not full TOML writer)
        self._write_config(config_path, config)
    
    def _write_config(self, path: Path, config: dict) -> None:
        """Write config dict to TOML file (simple implementation)."""
        lines = []
        
        for section, values in config.items():
            if isinstance(values, dict):
                for subsection, subvalues in values.items():
                    if isinstance(subvalues, dict):
                        lines.append(f"[{section}.{subsection}]")
                        for k, v in subvalues.items():
                            lines.append(f"{k} = {self._toml_value(v)}")
                        lines.append("")
                    else:
                        if not any(l.startswith(f"[{section}]") for l in lines):
                            lines.append(f"[{section}]")
                        lines.append(f"{subsection} = {self._toml_value(subvalues)}")
        
        path.write_text("\n".join(lines))
    
    def _toml_value(self, v: Any) -> str:
        """Convert Python value to TOML string."""
        if isinstance(v, bool):
            return "true" if v else "false"
        elif isinstance(v, str):
            return f'"{v}"'
        elif isinstance(v, (int, float)):
            return str(v)
        elif isinstance(v, list):
            return "[" + ", ".join(self._toml_value(x) for x in v) + "]"
        return str(v)
