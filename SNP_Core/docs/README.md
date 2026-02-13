# Provara v1.0 — Provara Protocol

**Version:** 1.0.0-rc1  
**Status:** Reference Implementation (Python)  
**Tests:** 58 passing (41 unit + 17 compliance)  
**Dependencies:** Python 3.10+, `cryptography` >= 41.0  
**License:** Apache 2.0 — Hunt Information Systems

---

## What This Is

A vendor-agnostic, event-sourced cognitive continuity system designed to persist
for 20+ years, support multi-agent collaboration, and facilitate seamless
migration across embodied robotic systems.

The protocol treats identity as a verifiable chain of evidence — not a model
checkpoint, not a vendor export, not a database dump. Any compliant
implementation can reconstruct the agent's beliefs from the event log alone.

**Golden Rule:** Truth is not merged. Evidence is merged. Truth is recomputed.

---

## Release Manifest

```
provara_v1_release/
├── bin/                              # Operational code (7 modules, 2,016 lines)
│   ├── canonical_json.py             #   RFC 8785-like deterministic JSON
│   ├── backpack_integrity.py         #   Merkle tree, path safety, SHA-256
│   ├── reducer_v0.py                 #   Deterministic belief reducer v0.2.0
│   ├── manifest_generator.py         #   Manifest + Merkle root generator
│   ├── backpack_signing.py           #   Ed25519 signing layer
│   ├── rekey_backpack.py             #   Key rotation protocol
│   └── bootstrap_v0.py              #   Sovereign birth (nothing → compliant node)
│
├── test/                             # Test suites (4 suites, 2,037 lines)
│   ├── test_reducer_v0.py            #   23 reducer invariant tests
│   ├── test_rekey.py                 #   18 signing + rotation tests
│   ├── test_bootstrap.py             #   16 bootstrap + integration tests
│   └── backpack_compliance_v1.py     #   17 protocol compliance tests
│
├── deploy/templates/                 # Reference policy files
│   ├── safety_policy.json            #   L0-L3 kinetic risk tiers
│   ├── sync_contract.json            #   Governance + authority ladder
│   └── retention_policy.json         #   Data permanence rules
│
├── examples/
│   └── reference_backpack/           # Known-good backpack (passes all 17 compliance tests)
│
└── docs/
    └── README.md                     # This file
```

---

## Quick Start

### Bootstrap a New Node

```bash
# Birth a sovereign backpack with root + quorum keys, run self-test
cd bin && python bootstrap_v0.py /path/to/new_backpack --quorum --self-test

# Private keys print to stdout — pipe to a secure file
python bootstrap_v0.py /path/to/backpack --quorum --private-keys /secure/keys.json --self-test
```

### Run All Tests

```bash
# Unit tests (reducer + signing + rotation + bootstrap)
cd test && PYTHONPATH=../bin python -m unittest test_reducer_v0 test_rekey test_bootstrap -v

# Compliance tests (against reference backpack)
cd test && PYTHONPATH=../bin python backpack_compliance_v1.py ../examples/reference_backpack -v
```

### Verify an Existing Backpack

```bash
cd test && PYTHONPATH=../bin python backpack_compliance_v1.py /path/to/backpack -v
```

### Generate a Manifest

```bash
cd bin && python manifest_generator.py /path/to/backpack --write
```

### Verify Key Rotation History

```bash
cd bin && python rekey_backpack.py verify /path/to/backpack
```

---

## Architecture

### Three-Lane Event Model

| Lane | Content | Merge Strategy |
|------|---------|---------------|
| **Episodic Events** | Append-only observation log | Union by `event_id` |
| **Beliefs** | Derived view from events | Recomputed by reducer (never merged directly) |
| **Policies** | Governance, safety, sync rules | Versioned with ratchet constraints |

### Four-Namespace Belief Model

| Namespace | Meaning | Promotion Rule |
|-----------|---------|---------------|
| `canonical/` | Institutionally attested truth | Requires ATTESTATION event |
| `local/` | Node-local observations | Auto-promotes on no conflict |
| `contested/` | Conflicting high-confidence evidence | Requires resolution event |
| `archived/` | Superseded canonical beliefs | Automatic on supersession |

### Safety Envelope (L0–L3)

| Tier | Risk Level | Offline Allowed | Gate |
|------|-----------|----------------|------|
| L0 | Data-only, reversible | Yes | Local reducer |
| L1 | Low-kinetic | Yes (log for review) | Reducer + policy |
| L2 | High-kinetic | Lease window only | Multi-sensor + signed policy |
| L3 | Critical/irreversible | No | Human MFA / remote signature |

**Merge Ratchet:** Safety constraints only tighten automatically. Loosening
requires signed POLICY_UPDATE by top authority.

### Cryptographic Primitives

| Function | Algorithm | Specification |
|----------|-----------|--------------|
| Hashing | SHA-256 | FIPS 180-4 |
| Signing | Ed25519 | RFC 8032 (mandatory-to-implement) |
| Canonical JSON | JCS-subset | RFC 8785 (sorted keys, no whitespace, UTF-8) |
| Key IDs | `bp1_` + SHA-256(pubkey)[:16hex] | Backpack v1 format |

---

## Module Reference

### `canonical_json.py`
Deterministic JSON serialization. All hashing and signing operations use this
as the canonical form. Sorted keys, compact separators, UTF-8, no NaN/Infinity.

### `reducer_v0.py` — SovereignReducerV0
Deterministic belief reducer. Takes an event stream, produces a belief state
with byte-identical state hash across any replay. Handles OBSERVATION,
ATTESTATION, REDUCER_EPOCH, and unknown event types gracefully.

**Invariant:** `f(events) → state` where identical events always produce
identical `metadata.state_hash`.

### `backpack_integrity.py`
Shared primitives for Merkle tree computation, path traversal protection,
SHA-256 file hashing, and spec constants. Used by both manifest generator
and compliance verifier.

### `manifest_generator.py`
Generates `manifest.json` and `merkle_root.txt` for a backpack directory.
Symlink-safe, path-validated, excludes meta files from the hash tree.

### `backpack_signing.py`
Ed25519 signing layer. Keypair generation, event signing/verification,
manifest signing/verification, key registry management.

### `rekey_backpack.py`
Key rotation protocol. Two-event model (KEY_REVOCATION + KEY_PROMOTION).
Rotation events must be signed by a surviving trusted authority — the
compromised key cannot authorize its own replacement.

### `bootstrap_v0.py`
Sovereign birth script. Creates a fully compliant, cryptographically signed
backpack from nothing. Generates Ed25519 keypairs, genesis event, seed
policies, manifest, and Merkle root. Output passes all 17 compliance tests
on first breath. Supports `--self-test` flag for built-in verification.

---

## What's Not Yet Implemented

| Component | Purpose | Status |
|-----------|---------|--------|
| `sync_v0.py` | Union merge + chain verification + fencing tokens | Pending |
| `BACKPACK_PROTOCOL_v1.0.md` | Formal canonical specification | Pending |
| Checkpoint system | Signed state materializations | Designed, not coded |
| Perception tiering | T0-T3 sensor data hierarchy | Designed, not coded |

---

## Design Principles

1. **Truth over Comfort:** Never merge beliefs. Merge evidence. Recompute.
2. **Stability over Speed:** Causal integrity before low-latency ingestion.
3. **Fail Safe, Not Silent:** Merkle failure or reducer hang → hardware lockout.
4. **Reversibility by Default:** Destructive actions require explicit authority.
5. **Evidence is Permanent:** Events are never deleted, only superseded.

---

© 2026 Hunt Information Systems. All rights reserved.
