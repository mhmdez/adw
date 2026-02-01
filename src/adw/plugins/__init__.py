"""ADW Plugin System.

Extensible plugin architecture for ADW.
"""

from .base import Plugin
from .manager import PluginManager, get_plugin_manager

__all__ = ["Plugin", "PluginManager", "get_plugin_manager"]
