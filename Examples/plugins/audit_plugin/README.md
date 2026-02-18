# Provara Audit Plugin

Example plugin demonstrating the Provara Plugin API.

## Features

### Event Type: `com.example.audit.login`

Custom event type for audit logging with schema validation:

```json
{
  "user_id": "alice",
  "success": true,
  "ip_address": "192.168.1.1",
  "user_agent": "Mozilla/5.0...",
  "session_id": "sess_abc123"
}
```

**Required fields:** `user_id`, `success`, `ip_address`

### Reducer: `com.example.audit.login_counter`

Aggregates login statistics per actor:

```json
{
  "reducer": "com.example.audit.login_counter",
  "version": "1.0.0",
  "actors": {
    "alice": {
      "total": 10,
      "successful": 8,
      "failed": 2,
      "unique_users": ["alice"]
    }
  }
}
```

### Export Format: `csv`

Exports vault events to CSV for spreadsheet analysis.

## Installation

```bash
# From the audit_plugin directory
pip install -e .
```

## Usage

### List installed plugins

```bash
provara plugins list
```

Expected output:
```
Installed Provara Plugins
=========================

Event Types:
  - com.example.audit.login (provara-audit-plugin v1.0.0)

Reducers:
  - com.example.audit.login_counter (provara-audit-plugin v1.0.0)

Export Formats:
  - csv (provara-audit-plugin v1.0.0)
```

### Append a login event

```bash
provara append my-vault --type com.example.audit.login \
  --data '{"user_id":"alice","success":true,"ip_address":"192.168.1.1"}'
```

### Run the login counter reducer

```bash
provara reduce my-vault --plugin com.example.audit.login_counter
```

### Export vault to CSV

```bash
provara export my-vault --format csv --output vault-export.csv
```

## Development

### Run tests

```bash
pytest tests/
```

### Build package

```bash
pip install build
python -m build
```

### Publish to PyPI

```bash
pip install twine
twine upload dist/*
```

## License

Apache 2.0
