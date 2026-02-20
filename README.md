# Provara Protocol

**Self-sovereign cryptographic event logs.**
Ed25519 · SHA-256 · RFC 8785 · Apache 2.0

[Try the Playground](https://provara-protocol.github.io/provara/) ·
[Read the Spec](docs/BACKPACK_PROTOCOL_v1.0.md) ·
[PyPI](https://pypi.org/project/provara-protocol/)

---

## What is Provara?

Provara is an append-only, cryptographically signed event log that anyone can verify and no one can silently rewrite. It preserves memory as evidence: signed observations that can be replayed into state, audited independently, and stored in plain files for long-horizon readability. Built for AI governance, cognitive continuity, and accountable records that outlive platforms.

---

## 60-Second Quickstart

```bash
pip install provara-protocol
```

```bash
# Create a vault
provara init my-vault

# Append a signed event
provara append my-vault --type OBSERVATION --data '{"event":"test"}' --keyfile my-vault/identity/private_keys.json

# Verify integrity
provara verify my-vault
```

---

## Key Features

- Tamper-evident append-only event logs
- Ed25519 signatures, SHA-256 hashing, RFC 8785 canonical JSON
- Per-actor causal chains with cryptographic linkage
- SCITT-compatible event types
- MCP server for AI agent integration
- Browser playground — zero install

---

## Three Implementations

| Language | Status | Tests |
|----------|--------|-------|
| Python | v1.0.1 (reference) | 528+ |
| Rust | Complete | 20 |
| TypeScript | Complete | — |

---

## Documentation

| Resource | Description |
|----------|-------------|
| [Quickstart](docs/QUICKSTART.md) | Install, init, verify in 5 minutes |
| [Tutorials](docs/tutorials/) | Step-by-step guides for common workflows |
| [API Reference](docs/api/) | Module and CLI documentation |
| [Cookbook](docs/cookbook/) | Recipes for AI governance, key rotation, sync |
| [Protocol Spec](docs/BACKPACK_PROTOCOL_v1.0.md) | Normative specification |
| [SOUL.md](SOUL.md) | Design philosophy and principles |

---

## Badges

![PyPI](https://img.shields.io/pypi/v/provara-protocol)
![Python](https://img.shields.io/pypi/pyversions/provara-protocol)
![License](https://img.shields.io/pypi/l/provara-protocol)
![Tests](https://img.shields.io/badge/tests-528%2B%20passing-brightgreen)

---

## Why This Exists

Your memories, your identity, your cognitive continuity should not depend on any company surviving, any server staying online, or any platform deciding to keep your data. Provara is built for people and organizations that need accountable records: families preserving history, AI teams logging model decisions, and regulated operators proving chain-of-custody.

> **Golden Rule:** Truth is not merged. Evidence is merged. Truth is recomputed.

---

## Design Guarantees

| Guarantee | What It Means |
|-----------|---------------|
| **No vendor lock-in** | Plain text JSON events. No proprietary formats. |
| **No internet required** | Works entirely offline. No phone-home, no telemetry. |
| **No accounts** | Your identity lives in your files, not on a server. |
| **Tamper-evident** | Merkle trees, Ed25519 signatures, causal chains detect modification. |
| **Human-readable** | NDJSON event log — open with any text editor. |
| **50-year readable** | JSON, SHA-256, Ed25519 are industry standards. |

---

## Vault Anatomy

```
my-vault/
├── identity/
│   ├── genesis.json              # Birth certificate
│   └── private_keys.json         # Ed25519 keypair (guard this!)
├── events/
│   └── events.ndjson             # Append-only event log
├── policies/
│   ├── safety_policy.json        # L0-L3 kinetic risk tiers
│   ├── retention_policy.json     # Data permanence rules
│   └── sync_contract.json        # Governance + authority ladder
├── manifest.json                 # File inventory with SHA-256 hashes
├── manifest.sig                  # Ed25519 signature over manifest
└── merkle_root.txt               # Integrity anchor
```

---

## MCP Server — AI Agents Write Tamper-Evident Memory

Connect any AI agent that supports the [Model Context Protocol](https://modelcontextprotocol.io/) to a Provara vault:

```json
{
  "mcpServers": {
    "provara": {
      "command": "python",
      "args": ["-m", "provara.mcp", "--transport", "stdio"]
    }
  }
}
```

**Available tools:** `append_event`, `verify_chain`, `snapshot_state`, `query_timeline`, `list_conflicts`, `generate_digest`, `export_markdown`, `checkpoint_vault`

---

## AI Governance Use Cases

| Use Case | How Provara Supports It |
|----------|------------------------|
| **Model evaluation logging** | Signed `OBSERVATION` events with model ID, benchmark, scores |
| **Prompt & test result logging** | Chained events with inputs, outputs, latency — tamper-evident |
| **Policy enforcement decisions** | `ATTESTATION` events record decisions with policy version and reasoning |
| **AI cost & routing oversight** | Token usage, model selection, routing decisions as signed events |
| **Red-team audit records** | Append-only audit trail for adversarial tests and severity assessments |

---

## Testing

```bash
# Run all tests
pytest

# Compliance tests against reference vault
python tests/backpack_compliance_v1.py tests/fixtures/reference_backpack -v
```

| Suite | Tests | Coverage |
|-------|------:|----------|
| Core + adversarial | 400+ | Reducer, sync, crypto, bootstrap, forgery, byzantine |
| Compliance | 17 | Full protocol conformance |
| PSMC | 60 | Application layer |
| MCP Server | 22 | All tools, both transports |
| Test vectors | 8 | Cross-language validation |
| Property-based fuzz | 20+ | Hypothesis-driven invariant testing |
| **Total** | **528+** | |

---

## Reimplementing Provara

The protocol is language-agnostic. To reimplement:

1. Implement SHA-256 (FIPS 180-4), Ed25519 (RFC 8032), RFC 8785 canonical JSON
2. Validate against [`test_vectors/vectors.json`](test_vectors/vectors.json)
3. Build a deterministic reducer for `OBSERVATION`, `ATTESTATION`, `RETRACTION`
4. Run the [17 compliance tests](tests/backpack_compliance_v1.py)

**If state hashes match, your implementation is correct.**

---

## Key Management

Your private keys are the root of sovereignty. Guard them:

- `private_keys.json` should never live on the same drive as your vault
- Store keys in separate physical locations
- Use `--quorum` flag during bootstrap for recovery key
- Compromised keys can be rotated via `KEY_REVOCATION` + `KEY_PROMOTION` events

**Full guide:** [Keys_Info/HOW_TO_STORE_KEYS.md](Keys_Info/HOW_TO_STORE_KEYS.md)

---

## Recovery

| Scenario | Solution |
|----------|----------|
| Lost keys, corrupted vault | [Recovery/WHAT_TO_DO.md](Recovery/WHAT_TO_DO.md) |
| Catastrophic failure | [RECOVERY_INSTRUCTIONS.md](RECOVERY_INSTRUCTIONS.md) |
| Routine backup/restore | `provara backup` / `provara restore` |

---

## FAQ

**What happens if I lose my private keys?**
With `--quorum`, the quorum key can authorize rotation. Without it, the vault is readable but read-only. See [Recovery/WHAT_TO_DO.md](Recovery/WHAT_TO_DO.md).

**Can I read my vault without this software?**
Yes. Events are NDJSON — open `events/events.ndjson` in any text editor.

**What if Python goes away in 20 years?**
JSON, SHA-256, and Ed25519 are industry standards implemented in every major language. The data survives the tooling.

**Can multiple devices share a vault?**
Yes. Sync uses union merge with causal chain verification and fork detection. Event-sourced architecture makes merging safe.

**Is this a blockchain?**
No. It's a Merkle tree over files with per-actor causal chains. Closer to git than Bitcoin. No consensus, no mining, no tokens.

**What does "Truth is not merged. Evidence is merged. Truth is recomputed." mean?**
You merge raw observations, then rerun the deterministic reducer to derive fresh conclusions. No merge conflicts at the belief layer.

---

## Version

```
Protocol            Provara v1.0
Implementation      1.0.1
PyPI                provara-protocol 1.0.1
Tests Passing       528+
```

---

## License

Apache 2.0

Normative specification: [`docs/BACKPACK_PROTOCOL_v1.0.md`](docs/BACKPACK_PROTOCOL_v1.0.md)
