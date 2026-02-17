# Provara Event Schemas

JSON Schema definitions for Provara Protocol v1.0 events.

## Files

- **event_types.json** - JSON Schema draft-07 definitions for all 7 core event types
- **validate_event.py** - CLI validator script  
- **test_schemas.py** - Unit tests for schema validation

## Usage

### Validate an event file
```bash
python validate_event.py event.json
```

### Validate from stdin
```bash
echo '{"event_id":"evt_...","type":"OBSERVATION",...}' | python validate_event.py -
```

### Run tests
```bash
python test_schemas.py -v
```

## Event Types

All events share these core fields:
- `event_id` (required): `evt_` + 24 hex chars
- `type` (required): Event type (GENESIS, OBSERVATION, etc.)
- `namespace` (required): canonical | local | contested | archived
- `actor` (required): Actor identifier
- `payload` (required): Event-specific data

Optional common fields:
- `actor_key_id`: Backpack v1 key ID (`bp1_` + 16 hex chars)
- `ts_logical`: Monotonic logical timestamp
- `prev_event_hash`: Previous event ID in actor's chain (null for first event)
- `timestamp_utc`: ISO 8601 timestamp
- `sig`: Base64-encoded Ed25519 signature (86 base64 chars + `==`)

## Notes

- Schema uses inline definitions rather than `$ref` base for better validator compatibility
- Some validators struggle with `oneOf` + `allOf` + `$ref` patterns
- Test events include all optional fields; real events may omit them
- Unknown fields MUST be preserved (forward compatibility per spec §7.5)

## Limitations

Current schema does NOT enforce:
- Causal chain integrity (prev_event_hash references)
- Signature verification
- Event ID computation correctness  
- Key authority verification

These require runtime validation in the reducer.
