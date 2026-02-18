"""
plugins.py — Provara Plugin System

Extension points for custom event types, reducers, and export formats.

Plugin Discovery:
    Plugins are discovered via setuptools entry_points:
    
    [project.entry-points."provara.plugins"]
    my_plugin = "my_package:MyPlugin"

Usage:
    from provara.plugins import registry
    
    # Auto-discover plugins
    registry.discover_plugins()
    
    # List registered plugins
    for event_type in registry.list_event_types():
        print(f"Event type: {event_type.name}")
    
    # Register plugin programmatically
    registry.register_event_type(MyCustomEventPlugin())
"""

from __future__ import annotations
from typing import Protocol, Any, Callable, Iterator, Dict, List, Optional
from pathlib import Path
import importlib.metadata
import json


# ---------------------------------------------------------------------------
# Protocol Definitions
# ---------------------------------------------------------------------------

class EventTypePlugin(Protocol):
    """Plugin that defines a custom event type.
    
    Attributes:
        name: Reverse-domain event type name (e.g., "com.acme.audit.login")
        schema: JSON Schema dict for validating event payload
    """
    name: str
    schema: dict[str, Any]
    
    def validate(self, data: dict[str, Any]) -> bool:
        """Validate event data against schema.
        
        Args:
            data: Event payload dict to validate.
            
        Returns:
            True if valid.
            
        Raises:
            ValueError: If validation fails with description of error.
        """
        ...
    
    def cli_command(self) -> str | None:
        """Optional CLI subcommand name.
        
        Returns:
            CLI command name (e.g., "login" for `provara append --type login`)
            or None if no CLI command is provided.
        """
        ...


class ReducerPlugin(Protocol):
    """Plugin that processes events into derived state.
    
    Attributes:
        name: Unique reducer identifier (reverse-domain notation recommended)
    """
    name: str
    
    def reduce(self, events: Iterator[dict]) -> dict[str, Any]:
        """Process event stream and return derived state.
        
        Args:
            events: Iterator of event dicts. Consumed exactly once.
            
        Returns:
            Derived state dict (must be JSON-serializable).
        """
        ...


class ExportPlugin(Protocol):
    """Plugin that exports vault data in a custom format.
    
    Attributes:
        name: Export format name (e.g., "csv", "siem-splunk")
    """
    name: str
    
    def export(self, vault_path: str, output_path: str) -> None:
        """Export vault to custom format.
        
        Args:
            vault_path: Path to vault directory.
            output_path: Path to output file or directory.
        """
        ...


# ---------------------------------------------------------------------------
# Plugin Registry
# ---------------------------------------------------------------------------

class PluginRegistry:
    """Central registry for Provara plugins.
    
    Thread-safe for reads after initialization. Plugin discovery
    should complete before concurrent access.
    """
    
    # Reserved core event types that cannot be overridden by plugins
    RESERVED_EVENT_TYPES = frozenset({
        "GENESIS", "OBSERVATION", "ASSERTION", "ATTESTATION", "RETRACTION",
        "KEY_REVOCATION", "KEY_PROMOTION", "REDUCER_EPOCH",
        "SIGNED_STATEMENT", "RECEIPT"
    })
    
    def __init__(self) -> None:
        self._event_types: Dict[str, EventTypePlugin] = {}
        self._reducers: Dict[str, ReducerPlugin] = {}
        self._exports: Dict[str, ExportPlugin] = {}
        self._discovered: bool = False
        self._plugin_sources: Dict[str, str] = {}  # name -> source (package:module)
    
    def register_event_type(self, plugin: EventTypePlugin) -> None:
        """Register a custom event type plugin.
        
        Args:
            plugin: EventTypePlugin instance.
            
        Raises:
            ValueError: If name collides with reserved type or existing plugin.
        """
        if plugin.name in self.RESERVED_EVENT_TYPES:
            raise ValueError(
                f"Event type name '{plugin.name}' is reserved for core types. "
                f"Reserved: {sorted(self.RESERVED_EVENT_TYPES)}"
            )
        
        if plugin.name in self._event_types:
            existing = self._event_types[plugin.name]
            raise ValueError(
                f"Event type name collision for '{plugin.name}'. "
                f"Existing: {existing.__class__.__module__}.{existing.__class__.__name__}. "
                f"New: {plugin.__class__.__module__}.{plugin.__class__.__name__}."
            )
        
        self._event_types[plugin.name] = plugin
        self._plugin_sources[plugin.name] = f"{plugin.__class__.__module__}:{plugin.__class__.__name__}"
    
    def register_reducer(self, plugin: ReducerPlugin) -> None:
        """Register a custom reducer plugin.
        
        Args:
            plugin: ReducerPlugin instance.
            
        Raises:
            ValueError: If name collides with existing reducer.
        """
        if plugin.name in self._reducers:
            existing = self._reducers[plugin.name]
            raise ValueError(
                f"Reducer name collision for '{plugin.name}'. "
                f"Existing: {existing.__class__.__module__}.{existing.__class__.__name__}. "
                f"New: {plugin.__class__.__module__}.{plugin.__class__.__name__}."
            )
        
        self._reducers[plugin.name] = plugin
        self._plugin_sources[plugin.name] = f"{plugin.__class__.__module__}:{plugin.__class__.__name__}"
    
    def register_export(self, plugin: ExportPlugin) -> None:
        """Register a custom export format plugin.
        
        Args:
            plugin: ExportPlugin instance.
            
        Raises:
            ValueError: If name collides with existing export format.
        """
        if plugin.name in self._exports:
            existing = self._exports[plugin.name]
            raise ValueError(
                f"Export format name collision for '{plugin.name}'. "
                f"Existing: {existing.__class__.__module__}.{existing.__class__.__name__}. "
                f"New: {plugin.__class__.__module__}.{plugin.__class__.__name__}."
            )
        
        self._exports[plugin.name] = plugin
        self._plugin_sources[plugin.name] = f"{plugin.__class__.__module__}:{plugin.__class__.__name__}"
    
    def get_event_type(self, name: str) -> EventTypePlugin | None:
        """Get event type plugin by name.
        
        Args:
            name: Event type name.
            
        Returns:
            EventTypePlugin or None if not found.
        """
        return self._event_types.get(name)
    
    def get_reducer(self, name: str) -> ReducerPlugin | None:
        """Get reducer plugin by name.
        
        Args:
            name: Reducer name.
            
        Returns:
            ReducerPlugin or None if not found.
        """
        return self._reducers.get(name)
    
    def get_export(self, name: str) -> ExportPlugin | None:
        """Get export plugin by name.
        
        Args:
            name: Export format name.
            
        Returns:
            ExportPlugin or None if not found.
        """
        return self._exports.get(name)
    
    def list_event_types(self) -> List[EventTypePlugin]:
        """List all registered event type plugins.
        
        Returns:
            List of EventTypePlugin instances.
        """
        return list(self._event_types.values())
    
    def list_reducers(self) -> List[ReducerPlugin]:
        """List all registered reducer plugins.
        
        Returns:
            List of ReducerPlugin instances.
        """
        return list(self._reducers.values())
    
    def list_exports(self) -> List[ExportPlugin]:
        """List all registered export format plugins.
        
        Returns:
            List of ExportPlugin instances.
        """
        return list(self._exports.values())
    
    def discover_plugins(self) -> None:
        """Auto-discover plugins via entry_points (setuptools).
        
        Entry points are registered in pyproject.toml:
        
        [project.entry-points."provara.plugins"]
        my_plugin = "my_package:MyPlugin"
        
        This method is idempotent — calling multiple times has no effect.
        """
        if self._discovered:
            return
        
        try:
            entry_points = importlib.metadata.entry_points()
            
            # Handle both Python 3.10+ (select) and older (dict access)
            if hasattr(entry_points, 'select'):
                plugins = entry_points.select(group='provara.plugins')
            else:
                plugins = entry_points.get('provara.plugins', [])
            
            for ep in plugins:
                try:
                    plugin_class = ep.load()
                    
                    # Instantiate the plugin
                    if callable(plugin_class):
                        plugin_instance = plugin_class()
                    else:
                        plugin_instance = plugin_class
                    
                    # Register based on plugin type
                    if hasattr(plugin_instance, 'schema') and hasattr(plugin_instance, 'validate'):
                        self.register_event_type(plugin_instance)
                    if hasattr(plugin_instance, 'reduce'):
                        self.register_reducer(plugin_instance)
                    if hasattr(plugin_instance, 'export'):
                        self.register_export(plugin_instance)
                    
                    self._plugin_sources[ep.name] = f"{ep.module}:{ep.attr}"
                    
                except Exception as e:
                    # Log but don't fail — one bad plugin shouldn't break others
                    import warnings
                    warnings.warn(f"Failed to load plugin '{ep.name}': {e}")
        
        except importlib.metadata.PackageNotFoundError:
            # No plugins installed — that's fine
            pass
        
        self._discovered = True
    
    def reload(self) -> None:
        """Force re-discovery of plugins.
        
        Use for testing or dynamic plugin loading.
        """
        self._event_types.clear()
        self._reducers.clear()
        self._exports.clear()
        self._plugin_sources.clear()
        self._discovered = False
        self.discover_plugins()
    
    def get_plugin_info(self) -> List[Dict[str, str]]:
        """Get information about all discovered plugins.
        
        Returns:
            List of dicts with keys: name, type, source
        """
        info = []
        for name, plugin in self._event_types.items():
            info.append({
                "name": name,
                "type": "event_type",
                "source": self._plugin_sources.get(name, "unknown")
            })
        for name, plugin in self._reducers.items():
            info.append({
                "name": name,
                "type": "reducer",
                "source": self._plugin_sources.get(name, "unknown")
            })
        for name, plugin in self._exports.items():
            info.append({
                "name": name,
                "type": "export",
                "source": self._plugin_sources.get(name, "unknown")
            })
        return info


# ---------------------------------------------------------------------------
# Global Registry Instance
# ---------------------------------------------------------------------------

registry = PluginRegistry()


# ---------------------------------------------------------------------------
# Validation Helper
# ---------------------------------------------------------------------------

def validate_event_with_plugins(event_type: str, payload: dict[str, Any]) -> tuple[bool, str]:
    """Validate an event using registered plugins.
    
    Args:
        event_type: Event type name.
        payload: Event payload dict.
        
    Returns:
        Tuple of (is_valid, error_message).
        error_message is empty if valid.
    """
    plugin = registry.get_event_type(event_type)
    
    if plugin is None:
        # Unknown type — let core handle it
        return True, ""
    
    try:
        if plugin.validate(payload):
            return True, ""
        return False, f"Validation failed for event type '{event_type}'"
    except ValueError as e:
        return False, str(e)
    except Exception as e:
        return False, f"Validation error: {e}"
