# Provara API Documentation

Welcome to the Provara Protocol API reference. This documentation covers the Python reference implementation — a complete, production-grade SDK for building tamper-evident, self-sovereign event logs.

## Quick Links

- **[Protocol Specification](https://provara.dev/spec/)** — Normative specification (RFC-style)
- **[Getting Started](./getting-started.md)** — Installation and basic usage
- **[GitHub Repository](https://github.com/provara-protocol/provara)** — Source code and issues

## Core Modules

The reference implementation consists of 8 core cryptographic and operational modules:

### Cryptographic Foundation

- **[canonical_json](./modules/canonical_json.md)** — RFC 8785 deterministic JSON serialization
- **[backpack_signing](./modules/backpack_signing.md)** — Ed25519 signing and verification
- **[backpack_integrity](./modules/backpack_integrity.md)** — SHA-256 hashing, Merkle trees, path validation

### Event Processing

- **[reducer_v0](./modules/reducer_v0.md)** — Deterministic belief reducer (OBSERVATION → state)
- **[sync_v0](./modules/sync_v0.md)** — Union merge, causal chain verification, fencing tokens
- **[manifest_generator](./modules/manifest_generator.md)** — Manifest + Merkle root generation

### Vault Lifecycle

- **[bootstrap_v0](./modules/bootstrap_v0.md)** — Genesis vault creation
- **[rekey_backpack](./modules/rekey_backpack.md)** — Key rotation protocol

## Utilities & Extensions

- **[checkpoint_v0](./modules/checkpoint_v0.md)** — Signed state snapshots for fast replay
- **[perception_v0](./modules/perception_v0.md)** — Sensor data hierarchy (T0–T3)
- **[CLI](./modules/cli.md)** — Command-line interface

## Integration Points

- **[MCP Server](./integration/mcp.md)** — Model Context Protocol for AI agents
- **[PSMC](./integration/psmc.md)** — Personal Sovereign Memory Container

## One External Dependency

```python
cryptography >= 41.0
```

That's it. No frameworks, no ORM, no build complexity. Just cryptographic primitives and stdlib.

## Key Design Principles

1. **Determinism** — Same events always produce the same state hash on any machine.
2. **Append-only** — Events are never modified or deleted. New evidence supersedes old.
3. **Tamper-evident** — Merkle trees, signatures, and causal chains detect any modification.
4. **Replayable** — The complete event log is preserved. Auditors can verify conclusions.
5. **50-year readable** — JSON, SHA-256, and Ed25519 are industry standards.

## Module Dependency Graph

```
bootstrap_v0 ──→ backpack_signing ──→ canonical_json
     │                  │
     ▼                  ▼
reducer_v0      backpack_integrity
     │                  │
     ▼                  ▼
sync_v0 ◄──── manifest_generator
     │
     ▼
rekey_backpack ──→ backpack_signing
```

All modules import from stdlib + `cryptography` only. No circular dependencies.

## Development

### Running Tests

```bash
# All unit tests (125)
python -m pytest tests/ -v

# Compliance tests (17)
python tests/backpack_compliance_v1.py tests/fixtures/reference_backpack -v

# Full suite (232 tests)
make test
```

### Type Checking

```bash
# Already passing --strict
python -m mypy --strict --ignore-missing-imports src/provara/
```

## License

Apache 2.0. See [LICENSE](https://github.com/provara-protocol/provara/blob/main/LICENSE) in the repository.

## Questions?

- Open an issue on [GitHub](https://github.com/provara-protocol/provara/issues)
- Read the [protocol specification](https://provara.dev/spec/)
- Check the [threat model](https://provara.dev/threat-model/)
