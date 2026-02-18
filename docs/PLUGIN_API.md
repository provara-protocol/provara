# Provara Plugin API Specification

**Version:** 1.0
**Date:** 2026-02-18
**Status:** Draft

---

## Overview

The Provara Plugin API enables third-party extensions without forking core. Plugins can define custom event types, custom reducers, and custom export formats. The plugin system uses Python entry points for automatic discovery and zero-config installation.

**Design Goals:**
- **Zero runtime overhead** — Plugins are opt-in; core performance is unaffected
- **No new dependencies** — Core does not depend on any plugin
- **Type-safe** — Protocols define required interfaces
- **Discoverable** — `provara plugins list` shows installed plugins
- **Validated** — Custom event types enforce JSON Schema validation

---

## Extension Points

### 1. Custom Event Types

Plugins can register new event types with schema validation.

**Use Cases:**
- Domain-specific events (e.g., `com.acme.audit.login`)
- Industry standards mapping (e.g., `org.hl7.fhir.observation`)
- Research instrumentation (e.g., `edu.mit.experiment.sensor_read`)

**Requirements:**
- Type name MUST use reverse-domain notation (per EXTENSION_REGISTRY.md)
- Type name MUST NOT collide with reserved core types
- Plugin MUST provide JSON Schema for validation
- Plugin MAY provide CLI subcommand for easy event creation

**Reserved Core Types:**
`GENESIS`, `OBSERVATION`, `ASSERTION`, `ATTESTATION`, `RETRACTION`, `KEY_REVOCATION`, `KEY_PROMOTION`, `REDUCER_EPOCH`, `SIGNED_STATEMENT`, `RECEIPT`

**Example:**
```python
from provara.plugins import EventTypePlugin

class LoginEventPlugin:
    name = "com.acme.audit.login"
    schema = {
        "type": "object",
        "required": ["user_id", "success", "ip_address"],
        "properties": {
            "user_id": {"type": "string"},
            "success": {"type": "boolean"},
            "ip_address": {"type": "string", "format": "ipv4"},
            "user_agent": {"type": "string"}
        }
    }
    
    def validate(self, data: dict) -> bool:
        import jsonschema
        jsonschema.validate(data, self.schema)
        return True
    
    def cli_command(self) -> str | None:
        return "login"  # Enables: provara append --type login ...
```

---

### 2. Custom Reducers

Plugins can register reducer functions that process events and produce derived state.

**Use Cases:**
- Compliance monitoring (flag policy violations)
- Metrics aggregation (count events, compute statistics)
- Custom belief derivation (domain-specific state machines)

**Requirements:**
- Reducer MUST be a pure function (no side effects)
- Reducer MUST be deterministic (same events → same output)
- Reducer MUST NOT modify input events
- Reducer output MUST be JSON-serializable

**Example:**
```python
from provara.plugins import ReducerPlugin
from typing import Iterator, Any

class ComplianceReducer:
    name = "com.acme.compliance.monitor"
    
    def reduce(self, events: Iterator[dict]) -> dict[str, Any]:
        violations = []
        for event in events:
            if event.get("type") == "com.acme.audit.login":
                if not event.get("payload", {}).get("success"):
                    violations.append({
                        "event_id": event["event_id"],
                        "violation": "failed_login",
                        "timestamp": event["timestamp_utc"]
                    })
        return {
            "compliance_version": "1.0",
            "total_violations": len(violations),
            "violations": violations
        }
```

---

### 3. Custom Export Formats

Plugins can register new export formats for `provara export --format <name>`.

**Use Cases:**
- CSV export for spreadsheet analysis
- SIEM integration (Splunk, QRadar, Sentinel)
- Legal discovery bundles
- Custom JSON structures

**Requirements:**
- Export function MUST accept vault path and output path
- Export function MUST NOT modify vault contents
- Export function SHOULD provide progress feedback for large vaults

**Example:**
```python
from provara.plugins import ExportPlugin
from pathlib import Path
import csv

class CSVExportPlugin:
    name = "csv"
    
    def export(self, vault_path: str, output_path: str) -> None:
        from provara.sync_v0 import load_events
        events = load_events(Path(vault_path) / "events" / "events.ndjson")
        
        with open(output_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["event_id", "type", "timestamp_utc", "actor", "payload"])
            writer.writeheader()
            for event in events:
                writer.writerow({
                    "event_id": event["event_id"],
                    "type": event["type"],
                    "timestamp_utc": event["timestamp_utc"],
                    "actor": event["actor"],
                    "payload": str(event.get("payload", {}))
                })
```

---

## Plugin Registration

### Via Entry Points (Recommended)

Plugins are discovered automatically via setuptools entry points.

**pyproject.toml:**
```toml
[project]
name = "acme-provara-plugins"
version = "1.0.0"
dependencies = ["provara-protocol>=1.0.0"]

[project.entry-points."provara.plugins"]
audit_plugin = "acme_provara_plugins:LoginEventPlugin"
compliance_reducer = "acme_provara_plugins:ComplianceReducer"
csv_export = "acme_provara_plugins:CSVExportPlugin"
```

**Installation:**
```bash
pip install acme-provara-plugins
provara plugins list  # Plugin appears automatically
```

### Via Python API (Advanced)

Plugins can be registered programmatically:

```python
from provara.plugins import registry

registry.register_event_type(LoginEventPlugin())
registry.register_reducer(ComplianceReducer())
registry.register_export(CSVExportPlugin())
```

---

## Plugin Discovery

Plugins are discovered in this order:

1. **Entry points** — `importlib.metadata.entry_points()` for group `provara.plugins`
2. **Explicit registration** — Via `registry.register_*()` calls
3. **Environment variable** — `PROVARA_PLUGINS` can specify module paths

**Discovery happens:**
- On CLI invocation (`provara <command>`)
- On import of `provara.plugins` module

**Caching:**
- Discovered plugins are cached for the lifetime of the process
- Re-discovery requires process restart or explicit `registry.reload()`

---

## CLI Commands

### `provara plugins list`

Lists all discovered plugins.

**Output:**
```
Installed Provara Plugins
=========================

Event Types:
  - com.acme.audit.login (acme-provara-plugins v1.0.0)
  - com.acme.audit.logout (acme-provara-plugins v1.0.0)

Reducers:
  - com.acme.compliance.monitor (acme-provara-plugins v1.0.0)

Export Formats:
  - csv (acme-provara-plugins v1.0.0)
  - siem-splunk (acme-provara-plugins v1.0.0)
```

### `provara append --type <custom-type>`

Custom event types appear alongside built-in types.

```bash
provara append my-vault --type com.acme.audit.login \
  --data '{"user_id":"alice","success":true,"ip_address":"192.168.1.1"}'
```

### `provara reduce --plugin <reducer-name>`

Run custom reducers alongside built-in reducers.

```bash
provara reduce my-vault --plugin com.acme.compliance.monitor
```

### `provara export --format <format-name>`

Use custom export formats.

```bash
provara export my-vault --format csv --output vault-export.csv
```

---

## Error Handling

### Invalid Plugin (Missing Methods)

```
ERROR: Plugin 'bad_plugin' is invalid.
  Missing required method: 'reduce'
  Plugin class: BadReducer
  Source: bad-plugin-package v0.1.0
Fix: Implement all required protocol methods.
```

### Name Collision

```
ERROR: Plugin name collision for 'csv'.
  Existing: provara.plugins.builtin.CSVExporter
  New: acme_provara_plugins.CSVExportPlugin
Fix: Use a unique name (reverse-domain notation recommended).
```

### Schema Validation Failure

```
ERROR: Event validation failed for type 'com.acme.audit.login'.
  Field: 'ip_address'
  Error: '192.168.1' is not a valid IPv4 address
  Schema: com.acme.audit.login v1.0
Fix: Correct the payload to match the schema.
```

---

## Security Considerations

### Trust Model

| Component | Trust Level | Mitigation |
|-----------|-------------|------------|
| Core Provara | Trusted | Code review, audits, signing |
| Third-party plugins | Untrusted | Sandboxed execution, explicit install |
| Plugin entry points | Untrusted | User must `pip install` explicitly |

### Recommendations

1. **Audit plugins before install** — Review source code, check signatures
2. **Pin plugin versions** — Use `plugin==1.2.3` in requirements
3. **Monitor plugin updates** — Subscribe to release notifications
4. **Isolate high-value vaults** — Run untrusted plugins in containers/VMs

### Out of Scope

- Plugin sandboxing (plugins run with user's privileges)
- Plugin signing (future extension)
- Plugin reputation system (future extension)

---

## Testing Plugins

### Unit Tests

```python
import pytest
from provara.plugins import registry
from my_plugin import LoginEventPlugin

def test_login_event_validation():
    plugin = LoginEventPlugin()
    assert plugin.validate({"user_id": "alice", "success": True, "ip_address": "192.168.1.1"})
    
    with pytest.raises(Exception):
        plugin.validate({"user_id": "alice"})  # Missing required fields
```

### Integration Tests

```python
def test_plugin_end_to_end(tmp_path):
    # Create vault
    run_command(f"provara init {tmp_path}/vault")
    
    # Append custom event
    run_command(f"provara append {tmp_path}/vault --type com.acme.audit.login --data '{{...}}'")
    
    # Verify vault
    result = run_command(f"provara verify {tmp_path}/vault")
    assert result.returncode == 0
```

---

## Publishing Plugins

### Package Structure

```
acme-provara-plugins/
├── pyproject.toml
├── README.md
├── acme_provara_plugins/
│   ├── __init__.py
│   ├── login_event.py
│   ├── compliance_reducer.py
│   └── csv_export.py
└── tests/
    ├── test_login.py
    ├── test_compliance.py
    └── test_export.py
```

### pyproject.toml Template

```toml
[project]
name = "acme-provara-plugins"
version = "1.0.0"
description = "ACME plugins for Provara Protocol"
readme = "README.md"
requires-python = ">=3.10"
dependencies = ["provara-protocol>=1.0.0"]

[project.entry-points."provara.plugins"]
login_event = "acme_provara_plugins:LoginEventPlugin"
compliance_reducer = "acme_provara_plugins:ComplianceReducer"
csv_export = "acme_provara_plugins:CSVExportPlugin"

[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.build_meta"
```

### Publishing to PyPI

```bash
pip install build twine
python -m build
twine upload dist/*
```

---

## Versioning

### Plugin API Stability

| Version | Stability |
|---------|-----------|
| 1.0 | Stable — no breaking changes in 1.x |
| 2.0 | Breaking changes allowed |

### Plugin Versioning

Plugins SHOULD follow semantic versioning:

- **MAJOR** — Breaking changes to plugin API or behavior
- **MINOR** — New features, backward compatible
- **PATCH** — Bug fixes, backward compatible

### Core Compatibility

Plugins SHOULD specify compatible Provara versions:

```toml
dependencies = ["provara-protocol>=1.0.0,<2.0.0"]
```

---

## FAQ

**Q: Can plugins modify core behavior?**

A: No. Plugins extend; they do not modify. Core behavior is immutable.

**Q: Can plugins access private keys?**

A: No. Plugins have no access to `private_keys.json`. Signing is handled by core.

**Q: Can plugins store state?**

A: Yes, but only in application memory or plugin-managed files. Core does not persist plugin state.

**Q: What happens if a plugin is uninstalled?**

A: Custom events remain in the vault (they are standard JSON). Custom reducers and exports become unavailable.

**Q: Can I use plugins with the MCP server?**

A: Yes. Plugins registered in the core are available to MCP server tools.

---

## References

- [EXTENSION_REGISTRY.md](./EXTENSION_REGISTRY.md) — Event type registration process
- [PROTOCOL_PROFILE.txt](../PROTOCOL_PROFILE.txt) — Core protocol specification
- [setuptools entry points](https://setuptools.pypa.io/en/latest/userguide/entry_point.html)

---

*This specification is part of Provara v1.0. For changes or extensions, open a GitHub issue.*
