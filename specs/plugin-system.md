# ADW Plugin System Spec

## Summary

A lightweight plugin system that makes ADW extensible. Plugins can add CLI commands, hook into task lifecycle, and manage their own dependencies.

## Goals

1. **Minimal core** — ADW stays small, plugins add features
2. **Easy installation** — `adw plugin install <name>`
3. **Lifecycle hooks** — Plugins integrate with task phases
4. **Self-contained** — Each plugin manages its own deps
5. **Discoverable** — List available/installed plugins

## Architecture

### Plugin Structure

```
~/.adw/plugins/
├── qmd/
│   ├── plugin.toml        # Metadata
│   ├── __init__.py        # Entry point
│   └── ...
└── github/
    ├── plugin.toml
    └── __init__.py
```

### plugin.toml

```toml
[plugin]
name = "qmd"
version = "0.1.0"
description = "Semantic search and context injection"
author = "StudiBudi"

[plugin.requires]
adw = ">=0.4.0"
external = ["bun", "qmd"]  # External CLI dependencies

[plugin.commands]
# Adds 'adw qmd' command group
qmd = "commands:qmd_group"

[plugin.hooks]
on_init = "hooks:on_init"
on_plan = "hooks:on_plan"
on_complete = "hooks:on_complete"

[plugin.config]
# Default config values
auto_context = true
max_results = 5
```

### Plugin Base Class

```python
# adw/plugins/base.py

from abc import ABC
from pathlib import Path
from typing import Any

class Plugin(ABC):
    """Base class for ADW plugins."""
    
    name: str
    version: str
    
    def __init__(self, config: dict):
        self.config = config
        self.enabled = config.get("enabled", True)
    
    # Lifecycle hooks (all optional)
    def on_init(self, project_path: Path) -> None:
        """Called during 'adw init'."""
        pass
    
    def on_plan(self, task: str, context: str) -> str:
        """Called before planner phase. Returns modified context."""
        return context
    
    def on_implement(self, task: str, plan: str) -> str:
        """Called before builder phase. Returns modified plan."""
        return plan
    
    def on_complete(self, task: str, result: dict) -> None:
        """Called after task completion."""
        pass
    
    def on_fail(self, task: str, error: str) -> None:
        """Called on task failure."""
        pass
    
    # CLI extension
    def get_commands(self) -> list:
        """Return Click command groups to register."""
        return []
    
    # Status
    def status(self) -> dict:
        """Return plugin status for 'adw plugin status'."""
        return {"enabled": self.enabled}
    
    # Installation hooks
    @classmethod
    def install(cls) -> bool:
        """Called during plugin installation."""
        return True
    
    @classmethod
    def uninstall(cls) -> bool:
        """Called during plugin removal."""
        return True
```

### Plugin Manager

```python
# adw/plugins/manager.py

class PluginManager:
    """Discovers, loads, and manages plugins."""
    
    PLUGINS_DIR = Path.home() / ".adw" / "plugins"
    REGISTRY_URL = "https://adw.studibudi.ai/plugins"  # Future
    
    def __init__(self):
        self._plugins: dict[str, Plugin] = {}
        self._load_plugins()
    
    def _load_plugins(self) -> None:
        """Discover and load installed plugins."""
        if not self.PLUGINS_DIR.exists():
            return
        
        for plugin_dir in self.PLUGINS_DIR.iterdir():
            if plugin_dir.is_dir() and (plugin_dir / "plugin.toml").exists():
                self._load_plugin(plugin_dir)
    
    def _load_plugin(self, path: Path) -> None:
        """Load a single plugin."""
        # Parse plugin.toml
        # Import plugin module
        # Instantiate with config
        pass
    
    def install(self, name: str) -> bool:
        """Install a plugin by name."""
        # Check registry or local path
        # Download/copy files
        # Run plugin.install()
        # Install external deps if needed
        pass
    
    def uninstall(self, name: str) -> bool:
        """Remove a plugin."""
        pass
    
    def get(self, name: str) -> Plugin | None:
        """Get loaded plugin by name."""
        return self._plugins.get(name)
    
    @property
    def all(self) -> list[Plugin]:
        """All loaded plugins."""
        return list(self._plugins.values())
    
    # Hook dispatchers
    def dispatch_init(self, project_path: Path) -> None:
        for plugin in self.all:
            if plugin.enabled:
                plugin.on_init(project_path)
    
    def dispatch_plan(self, task: str, context: str) -> str:
        for plugin in self.all:
            if plugin.enabled:
                context = plugin.on_plan(task, context)
        return context
    
    def dispatch_complete(self, task: str, result: dict) -> None:
        for plugin in self.all:
            if plugin.enabled:
                plugin.on_complete(task, result)
```

## CLI Commands

```bash
# Plugin management
adw plugin list                    # Show installed plugins
adw plugin install qmd             # Install from registry
adw plugin install ./my-plugin     # Install from local path
adw plugin install gh:user/repo    # Install from GitHub
adw plugin remove qmd              # Uninstall
adw plugin update qmd              # Update to latest
adw plugin status                  # Show all plugin statuses

# Plugin commands (added by plugins)
adw qmd search "query"             # From qmd plugin
adw github pr create               # From github plugin
```

## Config Integration

### Global config (~/.adw/config.toml)

```toml
[plugins]
auto_update = false

[plugins.qmd]
enabled = true
auto_context = true
max_results = 5

[plugins.github]
enabled = true
auto_pr = false
```

### Project config (.adw/config.toml)

```toml
# Override global settings per-project
[plugins.qmd]
collection = "my-project"
max_results = 10
```

## Built-in Plugins (Phase 1)

### 1. qmd (Semantic Search)

Converted from current `integrations/qmd.py`:

```python
class QmdPlugin(Plugin):
    name = "qmd"
    version = "0.1.0"
    
    def on_init(self, project_path):
        if self._is_qmd_available():
            self._init_collection(project_path)
            self._setup_mcp_config(project_path)
    
    def on_plan(self, task, context):
        results = self._search(task)
        if results:
            context += f"\n\n## Relevant Context\n{results}"
        return context
    
    def get_commands(self):
        return [qmd_command_group]
    
    @classmethod
    def install(cls):
        # Check for bun, install qmd if needed
        return install_qmd_cli()
```

### 2. github (Future)

```python
class GithubPlugin(Plugin):
    name = "github"
    
    def on_complete(self, task, result):
        if self.config.get("auto_pr"):
            self._create_pr(task, result)
    
    def get_commands(self):
        return [github_command_group]
```

## Installation Flow

```
adw plugin install qmd
  │
  ├─► Check plugin registry/source
  │
  ├─► Download plugin files to ~/.adw/plugins/qmd/
  │
  ├─► Parse plugin.toml
  │
  ├─► Check external deps (bun, qmd)
  │     └─► Prompt: "qmd requires bun. Install? [Y/n]"
  │
  ├─► Run plugin.install()
  │
  └─► Add to config with defaults
```

## Implementation Plan

### Phase 1: Core Infrastructure
- [ ] `adw/plugins/base.py` — Plugin base class
- [ ] `adw/plugins/manager.py` — Plugin manager
- [ ] `adw/plugins/config.py` — Plugin config handling
- [ ] CLI commands: `adw plugin list/install/remove/status`

### Phase 2: Convert qmd
- [ ] Move `integrations/qmd.py` → `~/.adw/plugins/qmd/`
- [ ] Create `plugin.toml`
- [ ] Implement lifecycle hooks
- [ ] Test installation flow

### Phase 3: Hook Integration
- [ ] Update `init.py` to dispatch `on_init`
- [ ] Update workflows to dispatch `on_plan`, `on_complete`
- [ ] Update CLI to register plugin commands

### Phase 4: Distribution (Future)
- [ ] Plugin registry API
- [ ] `adw plugin search`
- [ ] Version management

## File Changes

```
src/adw/
├── plugins/
│   ├── __init__.py
│   ├── base.py          # Plugin base class
│   ├── manager.py       # Plugin manager
│   ├── config.py        # Config handling
│   ├── registry.py      # Plugin discovery (future)
│   └── builtins/        # Built-in plugins (optional)
│       └── qmd/
│           ├── __init__.py
│           └── plugin.toml
├── cli.py               # Add plugin commands
├── init.py              # Dispatch on_init
└── workflows/
    └── standard.py      # Dispatch on_plan, on_complete
```

## Timeline

- Phase 1: 2 hours
- Phase 2: 1 hour  
- Phase 3: 1 hour
- Total: ~4 hours
