"""
Audit Plugin for Provara Protocol

Provides:
- com.example.audit.login event type
- Login counter reducer
- CSV export format

Usage:
    pip install -e .
    provara plugins list  # Should show audit plugins
"""

from typing import Any, Iterator
from pathlib import Path
import csv


# ---------------------------------------------------------------------------
# Event Type Plugin: Login Event
# ---------------------------------------------------------------------------

class LoginEventPlugin:
    """Custom event type for audit login events."""
    
    name = "com.example.audit.login"
    schema = {
        "type": "object",
        "required": ["user_id", "success", "ip_address"],
        "properties": {
            "user_id": {"type": "string", "description": "User identifier"},
            "success": {"type": "boolean", "description": "Whether login succeeded"},
            "ip_address": {"type": "string", "description": "Client IP address"},
            "user_agent": {"type": "string", "description": "Browser user agent"},
            "session_id": {"type": "string", "description": "Session identifier"}
        },
        "additionalProperties": True
    }
    
    def validate(self, data: dict[str, Any]) -> bool:
        """Validate login event data against schema."""
        # Simple validation without jsonschema dependency
        required = ["user_id", "success", "ip_address"]
        for field in required:
            if field not in data:
                raise ValueError(f"Missing required field: '{field}'")
        
        if not isinstance(data["user_id"], str):
            raise ValueError(f"Field 'user_id' must be a string")
        if not isinstance(data["success"], bool):
            raise ValueError(f"Field 'success' must be a boolean")
        if not isinstance(data["ip_address"], str):
            raise ValueError(f"Field 'ip_address' must be a string")
        
        # Optional field validation
        if "user_agent" in data and not isinstance(data["user_agent"], str):
            raise ValueError(f"Field 'user_agent' must be a string")
        if "session_id" in data and not isinstance(data["session_id"], str):
            raise ValueError(f"Field 'session_id' must be a string")
        
        return True
    
    def cli_command(self) -> str | None:
        """CLI subcommand name."""
        return "login"


# ---------------------------------------------------------------------------
# Reducer Plugin: Login Counter
# ---------------------------------------------------------------------------

class LoginCounterReducer:
    """Reducer that counts logins per actor and tracks success/failure."""
    
    name = "com.example.audit.login_counter"
    
    def reduce(self, events: Iterator[dict]) -> dict[str, Any]:
        """Process event stream and return login statistics."""
        stats: dict[str, dict[str, Any]] = {}
        
        for event in events:
            if event.get("type") != "com.example.audit.login":
                continue
            
            actor = event.get("actor", "unknown")
            payload = event.get("payload", {})
            success = payload.get("success", False)
            user_id = payload.get("user_id", "unknown")
            
            if actor not in stats:
                stats[actor] = {
                    "total": 0,
                    "successful": 0,
                    "failed": 0,
                    "users": set()
                }
            
            stats[actor]["total"] += 1
            stats[actor]["users"].add(user_id)
            if success:
                stats[actor]["successful"] += 1
            else:
                stats[actor]["failed"] += 1
        
        # Convert sets to lists for JSON serialization
        result = {}
        for actor, data in stats.items():
            result[actor] = {
                "total": data["total"],
                "successful": data["successful"],
                "failed": data["failed"],
                "unique_users": sorted(list(data["users"]))
            }
        
        return {
            "reducer": self.name,
            "version": "1.0.0",
            "actors": result
        }


# ---------------------------------------------------------------------------
# Export Plugin: CSV Export
# ---------------------------------------------------------------------------

class CSVExportPlugin:
    """Export vault events to CSV format."""
    
    name = "csv"
    
    def export(self, vault_path: str, output_path: str) -> None:
        """Export vault events to CSV file."""
        # Import here to avoid circular dependency
        from provara.sync_v0 import load_events
        
        events_file = Path(vault_path) / "events" / "events.ndjson"
        
        if not events_file.exists():
            raise FileNotFoundError(f"Events file not found: {events_file}")
        
        events = load_events(events_file)
        
        if not events:
            # Write empty CSV with headers
            with open(output_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["event_id", "type", "timestamp_utc", "actor", "payload"])
            return
        
        # Determine all unique payload keys for columns
        payload_keys = set()
        for event in events:
            payload = event.get("payload", {})
            if isinstance(payload, dict):
                payload_keys.update(payload.keys())
        
        # Build field names
        base_fields = ["event_id", "type", "timestamp_utc", "actor"]
        fieldnames = base_fields + sorted(payload_keys)
        
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            
            for event in events:
                row = {
                    "event_id": event.get("event_id", ""),
                    "type": event.get("type", ""),
                    "timestamp_utc": event.get("timestamp_utc", ""),
                    "actor": event.get("actor", "")
                }
                
                payload = event.get("payload", {})
                if isinstance(payload, dict):
                    for key in payload_keys:
                        if key in payload:
                            row[key] = str(payload[key])
                
                writer.writerow(row)


# ---------------------------------------------------------------------------
# Plugin instances for entry point registration
# ---------------------------------------------------------------------------

# These are instantiated when the entry point is loaded
login_event_plugin = LoginEventPlugin
login_counter_reducer = LoginCounterReducer
csv_export_plugin = CSVExportPlugin
