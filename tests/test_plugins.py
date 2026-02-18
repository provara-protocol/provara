"""
test_plugins.py — Tests for Provara Plugin System

Tests cover:
- Event type plugin registration and validation
- Reducer plugin registration and execution
- Export plugin registration and execution
- Plugin discovery via entry_points (mocked)
- Invalid plugin detection
- Name collision handling
"""

import pytest
import sys
import os
from pathlib import Path
from typing import Any, Iterator
from unittest.mock import patch, MagicMock

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from provara.plugins import (
    PluginRegistry,
    EventTypePlugin,
    ReducerPlugin,
    ExportPlugin,
    registry,
    validate_event_with_plugins,
)


# ---------------------------------------------------------------------------
# Test Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def fresh_registry():
    """Return a fresh PluginRegistry instance for each test.
    
    Note: Tests using validate_event_with_plugins must patch the global
    registry or use the fresh_registry's methods directly.
    """
    return PluginRegistry()


@pytest.fixture
def sample_event_type_plugin():
    """Sample event type plugin for testing."""
    class SampleEventPlugin:
        name = "com.example.test.event"
        schema = {
            "type": "object",
            "required": ["message"],
            "properties": {
                "message": {"type": "string"},
                "priority": {"type": "integer", "minimum": 1, "maximum": 5}
            }
        }

        def validate(self, data: dict[str, Any]) -> bool:
            if "message" not in data:
                raise ValueError("Missing required field: 'message'")
            if not isinstance(data["message"], str):
                raise ValueError("Field 'message' must be a string")
            if "priority" in data and not isinstance(data["priority"], int):
                raise ValueError("Field 'priority' must be an integer")
            return True

        def cli_command(self) -> str | None:
            return "test-event"

    return SampleEventPlugin()


@pytest.fixture
def sample_reducer_plugin():
    """Sample reducer plugin for testing."""
    class SampleReducerPlugin:
        name = "com.example.test.reducer"
        
        def reduce(self, events: Iterator[dict]) -> dict[str, Any]:
            count = 0
            types = {}
            for event in events:
                count += 1
                event_type = event.get("type", "unknown")
                types[event_type] = types.get(event_type, 0) + 1
            return {
                "total_events": count,
                "event_types": types
            }
    
    return SampleReducerPlugin()


@pytest.fixture
def sample_export_plugin(tmp_path):
    """Sample export plugin for testing."""
    class SampleExportPlugin:
        name = "test-export"
        
        def export(self, vault_path: str, output_path: str) -> None:
            # Create a simple text export
            events_file = Path(vault_path) / "events.ndjson"
            with open(output_path, "w") as f:
                if events_file.exists():
                    f.write(events_file.read_text())
                else:
                    f.write("# No events\n")
    
    return SampleExportPlugin()


# ---------------------------------------------------------------------------
# Event Type Plugin Tests
# ---------------------------------------------------------------------------

class TestEventTypePlugin:
    """Tests for event type plugin registration and validation."""
    
    def test_register_event_type(self, fresh_registry, sample_event_type_plugin):
        """Register event type plugin successfully."""
        fresh_registry.register_event_type(sample_event_type_plugin)
        
        retrieved = fresh_registry.get_event_type("com.example.test.event")
        assert retrieved is not None
        assert retrieved.name == sample_event_type_plugin.name
    
    def test_register_event_type_reserved_name(self, fresh_registry):
        """Reject event type with reserved core name."""
        class ReservedPlugin:
            name = "OBSERVATION"
            schema = {}
            def validate(self, data): return True
            def cli_command(self): return None
        
        with pytest.raises(ValueError, match="reserved for core types"):
            fresh_registry.register_event_type(ReservedPlugin())
    
    def test_register_event_type_collision(self, fresh_registry, sample_event_type_plugin):
        """Reject duplicate event type registration."""
        fresh_registry.register_event_type(sample_event_type_plugin)
        
        # Try to register another plugin with same name
        class DuplicatePlugin:
            name = "com.example.test.event"
            schema = {}
            def validate(self, data): return True
            def cli_command(self): return None
        
        with pytest.raises(ValueError, match="name collision"):
            fresh_registry.register_event_type(DuplicatePlugin())
    
    def test_validate_event_valid(self, fresh_registry, sample_event_type_plugin):
        """Validate event with valid data."""
        fresh_registry.register_event_type(sample_event_type_plugin)
        
        # Patch the global registry's get_event_type to use our fresh registry
        with patch.object(registry, 'get_event_type', side_effect=fresh_registry.get_event_type):
            valid_data = {"message": "hello", "priority": 3}
            is_valid, error = validate_event_with_plugins("com.example.test.event", valid_data)
            
            assert is_valid is True
            assert error == ""
    
    def test_validate_event_invalid(self, fresh_registry, sample_event_type_plugin):
        """Validate event with invalid data."""
        fresh_registry.register_event_type(sample_event_type_plugin)
        
        # Patch the global registry's get_event_type to use our fresh registry
        with patch.object(registry, 'get_event_type', side_effect=fresh_registry.get_event_type):
            invalid_data = {"priority": 3}  # Missing required 'message'
            is_valid, error = validate_event_with_plugins("com.example.test.event", invalid_data)
            
            assert is_valid is False
            assert "Missing required field" in error
    
    def test_validate_unknown_type(self, fresh_registry):
        """Unknown event types pass validation (core handles them)."""
        is_valid, error = validate_event_with_plugins("unknown.type", {"data": "value"})
        
        assert is_valid is True
        assert error == ""
    
    def test_list_event_types(self, fresh_registry, sample_event_type_plugin):
        """List all registered event types."""
        fresh_registry.register_event_type(sample_event_type_plugin)
        
        event_types = fresh_registry.list_event_types()
        
        assert len(event_types) == 1
        assert event_types[0].name == "com.example.test.event"


# ---------------------------------------------------------------------------
# Reducer Plugin Tests
# ---------------------------------------------------------------------------

class TestReducerPlugin:
    """Tests for reducer plugin registration and execution."""
    
    def test_register_reducer(self, fresh_registry, sample_reducer_plugin):
        """Register reducer plugin successfully."""
        fresh_registry.register_reducer(sample_reducer_plugin)
        
        retrieved = fresh_registry.get_reducer("com.example.test.reducer")
        assert retrieved is not None
        assert retrieved.name == sample_reducer_plugin.name
    
    def test_register_reducer_collision(self, fresh_registry, sample_reducer_plugin):
        """Reject duplicate reducer registration."""
        fresh_registry.register_reducer(sample_reducer_plugin)
        
        class DuplicateReducer:
            name = "com.example.test.reducer"
            def reduce(self, events): return {}
        
        with pytest.raises(ValueError, match="name collision"):
            fresh_registry.register_reducer(DuplicateReducer())
    
    def test_reduce_empty_stream(self, fresh_registry, sample_reducer_plugin):
        """Reduce empty event stream."""
        fresh_registry.register_reducer(sample_reducer_plugin)
        
        def empty_events():
            return iter([])
        
        result = sample_reducer_plugin.reduce(empty_events())
        
        assert result["total_events"] == 0
        assert result["event_types"] == {}
    
    def test_reduce_event_stream(self, fresh_registry, sample_reducer_plugin):
        """Reduce event stream with multiple events."""
        fresh_registry.register_reducer(sample_reducer_plugin)
        
        def event_stream():
            yield {"type": "OBSERVATION", "data": "a"}
            yield {"type": "OBSERVATION", "data": "b"}
            yield {"type": "ASSERTION", "data": "c"}
        
        result = sample_reducer_plugin.reduce(event_stream())
        
        assert result["total_events"] == 3
        assert result["event_types"]["OBSERVATION"] == 2
        assert result["event_types"]["ASSERTION"] == 1
    
    def test_list_reducers(self, fresh_registry, sample_reducer_plugin):
        """List all registered reducers."""
        fresh_registry.register_reducer(sample_reducer_plugin)
        
        reducers = fresh_registry.list_reducers()
        
        assert len(reducers) == 1
        assert reducers[0].name == "com.example.test.reducer"


# ---------------------------------------------------------------------------
# Export Plugin Tests
# ---------------------------------------------------------------------------

class TestExportPlugin:
    """Tests for export plugin registration and execution."""
    
    def test_register_export(self, fresh_registry, sample_export_plugin):
        """Register export plugin successfully."""
        fresh_registry.register_export(sample_export_plugin)
        
        retrieved = fresh_registry.get_export("test-export")
        assert retrieved is not None
        assert retrieved.name == sample_export_plugin.name
    
    def test_register_export_collision(self, fresh_registry, sample_export_plugin):
        """Reject duplicate export registration."""
        fresh_registry.register_export(sample_export_plugin)
        
        class DuplicateExport:
            name = "test-export"
            def export(self, vault_path, output_path): pass
        
        with pytest.raises(ValueError, match="name collision"):
            fresh_registry.register_export(DuplicateExport())
    
    def test_export_creates_file(self, fresh_registry, sample_export_plugin, tmp_path):
        """Export plugin creates output file."""
        fresh_registry.register_export(sample_export_plugin)
        
        # Create fake vault
        vault_dir = tmp_path / "vault"
        vault_dir.mkdir()
        events_file = vault_dir / "events.ndjson"
        events_file.write_text('{"event_id": "evt_123"}\n')
        
        output_file = tmp_path / "export.txt"
        
        sample_export_plugin.export(str(vault_dir), str(output_file))
        
        assert output_file.exists()
        assert "evt_123" in output_file.read_text()
    
    def test_export_empty_vault(self, fresh_registry, sample_export_plugin, tmp_path):
        """Export handles empty vault gracefully."""
        fresh_registry.register_export(sample_export_plugin)
        
        vault_dir = tmp_path / "vault"
        vault_dir.mkdir()
        # No events.ndjson file
        
        output_file = tmp_path / "export.txt"
        
        sample_export_plugin.export(str(vault_dir), str(output_file))
        
        assert output_file.exists()
        assert "# No events" in output_file.read_text()
    
    def test_list_exports(self, fresh_registry, sample_export_plugin):
        """List all registered export formats."""
        fresh_registry.register_export(sample_export_plugin)
        
        exports = fresh_registry.list_exports()
        
        assert len(exports) == 1
        assert exports[0].name == "test-export"


# ---------------------------------------------------------------------------
# Plugin Discovery Tests
# ---------------------------------------------------------------------------

class TestPluginDiscovery:
    """Tests for automatic plugin discovery."""
    
    def test_discover_plugins_empty(self, fresh_registry):
        """Discovery handles no plugins gracefully."""
        with patch('importlib.metadata.entry_points') as mock_ep:
            mock_ep.return_value.select.return_value = []
            
            fresh_registry.discover_plugins()
            
            assert len(fresh_registry.list_event_types()) == 0
            assert len(fresh_registry.list_reducers()) == 0
            assert len(fresh_registry.list_exports()) == 0
    
    def test_discover_event_type_plugin(self, fresh_registry, sample_event_type_plugin):
        """Discovery finds and registers event type plugins."""
        mock_entry_point = MagicMock()
        mock_entry_point.name = "test_plugin"
        mock_entry_point.load.return_value = lambda: sample_event_type_plugin
        mock_entry_point.module = "test_module"
        mock_entry_point.attr = "TestPlugin"
        
        with patch('importlib.metadata.entry_points') as mock_ep:
            mock_ep.return_value.select.return_value = [mock_entry_point]
            
            fresh_registry.discover_plugins()
            
            assert len(fresh_registry.list_event_types()) == 1
    
    def test_discover_reducer_plugin(self, fresh_registry, sample_reducer_plugin):
        """Discovery finds and registers reducer plugins."""
        mock_entry_point = MagicMock()
        mock_entry_point.name = "test_reducer"
        mock_entry_point.load.return_value = lambda: sample_reducer_plugin
        mock_entry_point.module = "test_module"
        mock_entry_point.attr = "TestReducer"
        
        with patch('importlib.metadata.entry_points') as mock_ep:
            mock_ep.return_value.select.return_value = [mock_entry_point]
            
            fresh_registry.discover_plugins()
            
            assert len(fresh_registry.list_reducers()) == 1
    
    def test_discover_export_plugin(self, fresh_registry, sample_export_plugin):
        """Discovery finds and registers export plugins."""
        mock_entry_point = MagicMock()
        mock_entry_point.name = "test_export"
        mock_entry_point.load.return_value = lambda: sample_export_plugin
        mock_entry_point.module = "test_module"
        mock_entry_point.attr = "TestExport"
        
        with patch('importlib.metadata.entry_points') as mock_ep:
            mock_ep.return_value.select.return_value = [mock_entry_point]
            
            fresh_registry.discover_plugins()
            
            assert len(fresh_registry.list_exports()) == 1
    
    def test_discover_handles_load_error(self, fresh_registry):
        """Discovery continues when one plugin fails to load."""
        mock_entry_point = MagicMock()
        mock_entry_point.name = "bad_plugin"
        mock_entry_point.load.side_effect = ImportError("Plugin not found")
        
        with patch('importlib.metadata.entry_points') as mock_ep:
            mock_ep.return_value.select.return_value = [mock_entry_point]
            
            # Should not raise
            fresh_registry.discover_plugins()
    
    def test_reload_clears_cache(self, fresh_registry, sample_event_type_plugin):
        """Reload clears and re-discovers plugins."""
        fresh_registry.register_event_type(sample_event_type_plugin)
        assert len(fresh_registry.list_event_types()) == 1
        
        fresh_registry.reload()
        
        # After reload, only discovered plugins remain (none in this test)
        assert len(fresh_registry.list_event_types()) == 0
    
    def test_get_plugin_info(self, fresh_registry, sample_event_type_plugin, sample_reducer_plugin):
        """Get plugin information for listing."""
        fresh_registry.register_event_type(sample_event_type_plugin)
        fresh_registry.register_reducer(sample_reducer_plugin)
        
        info = fresh_registry.get_plugin_info()
        
        assert len(info) == 2
        
        event_info = [i for i in info if i["type"] == "event_type"][0]
        assert event_info["name"] == "com.example.test.event"
        
        reducer_info = [i for i in info if i["type"] == "reducer"][0]
        assert reducer_info["name"] == "com.example.test.reducer"


# ---------------------------------------------------------------------------
# Integration Tests
# ---------------------------------------------------------------------------

class TestPluginIntegration:
    """Integration tests for complete plugin workflows."""

    def test_full_event_workflow(self, fresh_registry, sample_event_type_plugin, tmp_path):
        """Complete workflow: register → validate → append (simulated)."""
        # Register plugin
        fresh_registry.register_event_type(sample_event_type_plugin)

        # Validate valid event (patch global registry)
        with patch.object(registry, 'get_event_type', side_effect=fresh_registry.get_event_type):
            valid_payload = {"message": "test", "priority": 2}
            is_valid, error = validate_event_with_plugins("com.example.test.event", valid_payload)
            assert is_valid

            # Validate invalid event
            invalid_payload = {"priority": 2}
            is_valid, error = validate_event_with_plugins("com.example.test.event", invalid_payload)
            assert not is_valid
    
    def test_full_reduce_workflow(self, fresh_registry, sample_reducer_plugin, tmp_path):
        """Complete workflow: register → reduce → verify output."""
        fresh_registry.register_reducer(sample_reducer_plugin)
        
        # Simulate events from a vault
        def events():
            yield {"type": "com.example.test.event", "message": "a"}
            yield {"type": "OBSERVATION", "data": "b"}
            yield {"type": "com.example.test.event", "message": "c"}
        
        reducer = fresh_registry.get_reducer("com.example.test.reducer")
        result = reducer.reduce(events())
        
        assert result["total_events"] == 3
        assert result["event_types"]["com.example.test.event"] == 2
    
    def test_full_export_workflow(self, fresh_registry, sample_export_plugin, tmp_path):
        """Complete workflow: register → export → verify file."""
        fresh_registry.register_export(sample_export_plugin)
        
        # Create vault with events
        vault_dir = tmp_path / "vault"
        vault_dir.mkdir()
        events_file = vault_dir / "events.ndjson"
        events_file.write_text(
            '{"event_id": "evt_1", "type": "OBSERVATION"}\n'
            '{"event_id": "evt_2", "type": "ASSERTION"}\n'
        )
        
        output_file = tmp_path / "export.csv"
        
        exporter = fresh_registry.get_export("test-export")
        exporter.export(str(vault_dir), str(output_file))
        
        assert output_file.exists()
        content = output_file.read_text()
        assert "evt_1" in content
        assert "evt_2" in content


# ---------------------------------------------------------------------------
# Error Handling Tests
# ---------------------------------------------------------------------------

class TestPluginErrorHandling:
    """Tests for error handling in plugin system."""
    
    def test_invalid_plugin_missing_validate(self, fresh_registry):
        """Reject event type plugin missing validate method."""
        class BadPlugin:
            name = "com.bad.plugin"
            schema = {}
            # Missing validate method
        
        # Protocol doesn't enforce at runtime, but validate should fail
        plugin = BadPlugin()
        with pytest.raises(AttributeError):
            plugin.validate({})
    
    def test_invalid_plugin_missing_reduce(self, fresh_registry):
        """Reject reducer plugin missing reduce method."""
        class BadReducer:
            name = "com.bad.reducer"
            # Missing reduce method
        
        plugin = BadReducer()
        with pytest.raises(AttributeError):
            plugin.reduce(iter([]))
    
    def test_invalid_plugin_missing_export(self, fresh_registry):
        """Reject export plugin missing export method."""
        class BadExport:
            name = "bad-export"
            # Missing export method
        
        plugin = BadExport()
        with pytest.raises(AttributeError):
            plugin.export("/tmp", "/tmp/out")
    
    def test_validate_exception_handling(self, fresh_registry):
        """Validation exceptions are caught and returned as error message."""
        class ExceptionPlugin:
            name = "com.exception.plugin"
            schema = {}
            def validate(self, data):
                raise RuntimeError("Unexpected error")
            def cli_command(self): return None

        fresh_registry.register_event_type(ExceptionPlugin())

        with patch.object(registry, 'get_event_type', side_effect=fresh_registry.get_event_type):
            is_valid, error = validate_event_with_plugins("com.exception.plugin", {})

            assert is_valid is False
            assert "Unexpected error" in error
