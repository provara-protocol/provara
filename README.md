<pre>
  ____  _   _ ____    _                                  _  ___ _
 / ___|| \ | |  _ \  | |    ___  __ _  __ _  ___ _   _  | |/ (_) |_
 \___ \|  \| | |_) | | |   / _ \/ _` |/ _` |/ __| | | | | ' /| | __|
  ___) | |\  |  __/  | |__|  __/ (_| | (_| | (__| |_| | | . \| | |_
 |____/|_| \_|_|     |_____\___|\__, |\__,_|\___|\__, | |_|\_\_|\__|
                                |___/            |___/
         Provara Protocol v1.0 — Reference Implementation
</pre>

**Your memory belongs to you. Prove it.**

![Protocol](https://img.shields.io/badge/Protocol-Provara_v1.0-blue)
![Tests](https://img.shields.io/badge/Tests-110_passing-brightgreen)
![Python](https://img.shields.io/badge/Python-3.10%2B-yellow)
![Status](https://img.shields.io/badge/Status-Reference_Implementation-orange)
![License](https://img.shields.io/badge/License-Apache_2.0-blue)

---

## Table of Contents

- [Why This Exists](#why-this-exists)
- [Design Guarantees](#design-guarantees)
- [At a Glance](#at-a-glance)
- [Quick Start](#quick-start)
  - [Prerequisites](#prerequisites)
  - [Create Your Vault](#create-your-vault)
  - [Verify Your Vault](#verify-your-vault)
  - [Back Up Your Vault](#back-up-your-vault)
- [For Developers](#for-developers)
- [Architecture](#architecture)
  - [Three-Lane Event Model](#three-lane-event-model)
  - [Four-Namespace Belief Model](#four-namespace-belief-model)
  - [Safety Envelope (L0--L3)](#safety-envelope-l0--l3)
  - [Cryptographic Primitives](#cryptographic-primitives)
  - [Vault Anatomy](#vault-anatomy)
  - [Causal Chain](#causal-chain)
- [Module Reference](#module-reference)
- [Testing](#testing)
  - [Compliance Breakdown](#compliance-breakdown)
- [Design Principles](#design-principles)
- [Project Map](#project-map)
- [Roadmap](#roadmap)
- [Reimplementing Provara](#reimplementing-provara)
- [Key Management](#key-management)
- [Recovery](#recovery)
- [FAQ](#faq)
- [Version](#version)
- [License](#license)

---

## Why This Exists

Your memories, your identity, your cognitive continuity should not depend on any company surviving, any server staying online, or any platform deciding to keep your data. Every cloud service is a promise that can be broken. Every proprietary export is a format that can be abandoned. Every account is a dependency on someone else's infrastructure.

The Provara Legacy Kit is a self-sovereign, cryptographically-signed event log that anyone can verify, no one can silently tamper with, and that can be read with nothing but Python and a text editor for the next 50 years. It treats identity not as a model checkpoint or a database dump, but as a verifiable chain of evidence.

> **Golden Rule:** Truth is not merged. Evidence is merged. Truth is recomputed.

This system is built for individuals preserving family records, AI agents maintaining cognitive continuity across embodied robotic systems, organizations requiring tamper-evident audit trails, and anyone who needs to prove what they knew, when they knew it, with cryptographic certainty. If your memories matter, they deserve better than a terms-of-service agreement.

---

## Design Guarantees

| Guarantee | What It Means |
|-----------|---------------|
| **No vendor lock-in** | Everything is plain text: JSON events, Python scripts. No proprietary formats. |
| **No internet required** | Works entirely offline after initial setup. No phone-home, no telemetry, no cloud. |
| **No accounts** | Your identity lives in your files, not on a server. No signup, no login, no password. |
| **Tamper-evident** | Merkle trees, Ed25519 signatures, and causal chains detect any modification. |
| **Human-readable** | The event log is NDJSON — open it with any text editor and read it. |
| **50-year readable** | JSON, SHA-256, and Ed25519 are industry standards. They will outlive any company or platform. |

---

## At a Glance

```
Operational Code    7 Python modules          ~2,016 lines
Test Code           4 test suites             ~2,037 lines
Tests Passing       110 total                 93 unit + 17 compliance
External Deps       1                         cryptography >= 41.0
Crypto Stack        Ed25519 + SHA-256         RFC 8032 + FIPS 180-4
Serialization       Canonical JSON            RFC 8785 (JCS)
Platforms           Windows, macOS, Linux     Shell + Python
Data Format         NDJSON events + JSON      Readable forever
```

---

> ### Not Technical?
>
> Start here: **[Family_Guide/START_HERE.md](Family_Guide/START_HERE.md)**
>
> Then run `init_backpack.bat` (Windows) or `./init_backpack.sh` (Mac/Linux) to create your vault. That's it.

---

## Quick Start

### Prerequisites

- **Python 3.10 or later** — [python.org](https://python.org)
- The `cryptography` package (>= 41.0) — installed automatically by the init scripts
- No internet connection required after initial setup

### Create Your Vault

```bash
# Mac / Linux
./init_backpack.sh

# Windows
init_backpack.bat
```

This will:
1. Generate Ed25519 keypairs (root authority)
2. Create the genesis event (your vault's birth certificate)
3. Build policy files (safety, retention, sync governance)
4. Generate the manifest and Merkle root
5. Run all 17 compliance tests automatically

**Output:**
- `my_private_keys.json` — **Guard this with your life.** See [Key Management](#key-management).
- `My_Backpack/` — Your vault. Back it up early and often.

### Verify Your Vault

```bash
# Mac / Linux
./check_backpack.sh My_Backpack

# Windows
check_backpack.bat My_Backpack
```

Runs 17 compliance tests: directory structure, identity schema, event integrity, Merkle verification, safety policy, sync contract, reducer determinism, and retention permanence.

### Back Up Your Vault

```bash
# Mac / Linux
./backup_vault.sh My_Backpack

# Windows
backup_vault.bat My_Backpack
```

Creates a timestamped, integrity-verified ZIP with a SHA-256 hash file. Automatically prunes to keep the last 12 backups.

---

## For Developers

```bash
# Bootstrap with dual-key authority (root + quorum)
cd SNP_Core/bin && python bootstrap_v0.py /path/to/backpack --quorum --self-test

# Pipe private keys to a secure file
python bootstrap_v0.py /path/to/backpack --quorum --private-keys /secure/keys.json --self-test

# Run full unit test suite (57 tests)
cd SNP_Core/test && PYTHONPATH=../bin python -m unittest test_reducer_v0 test_rekey test_bootstrap -v

# Run compliance tests (17 tests)
cd SNP_Core/test && PYTHONPATH=../bin python backpack_compliance_v1.py ../examples/reference_backpack -v

# Generate / regenerate manifest
cd SNP_Core/bin && python manifest_generator.py /path/to/backpack --write

# Verify key rotation history
cd SNP_Core/bin && python rekey_backpack.py verify /path/to/backpack
```

---

## Architecture

```
                            PROVARA PROTOCOL
                            ================

  +-----------------+       +---------------------+       +------------------+
  |                 |       |                     |       |                  |
  |  EVENTS         |  -->  |  REDUCER            |  -->  |  BELIEF STATE    |
  |  (append-only   |       |  (deterministic,    |       |  (derived view,  |
  |   NDJSON log)   |       |   replayable)       |       |   never merged)  |
  |                 |       |                     |       |                  |
  +-----------------+       +---------------------+       +------------------+
                                                                  |
                                                                  v
                                                          +------------------+
                                                          |  MANIFEST        |
                                                          |  + Merkle Root   |
                                                          |  + Ed25519 Sig   |
                                                          +------------------+

  Events flow in. The reducer processes them deterministically. Beliefs emerge.
  The manifest seals the vault state with a Merkle tree and cryptographic signature.

  Same events --> same reducer --> same state hash. Always. On any machine. Forever.
```

### Three-Lane Event Model

| Lane | Content | Merge Strategy |
|------|---------|----------------|
| **Episodic Events** | Append-only observation log | Union by `event_id` |
| **Beliefs** | Derived view from events | Recomputed by reducer (never merged directly) |
| **Policies** | Governance, safety, sync rules | Versioned with ratchet constraints |

### Four-Namespace Belief Model

| Namespace | Meaning | Promotion Rule |
|-----------|---------|----------------|
| `canonical/` | Institutionally attested truth | Requires `ATTESTATION` event |
| `local/` | Node-local observations | Auto-promotes when no conflict exists |
| `contested/` | Conflicting high-confidence evidence | Requires explicit resolution event |
| `archived/` | Superseded canonical beliefs | Automatic on supersession |

### Safety Envelope (L0--L3)

| Tier | Risk Level | Offline Allowed | Gate |
|------|------------|-----------------|------|
| **L0** | Data-only, reversible | Yes | Local reducer |
| **L1** | Low-kinetic | Yes (logged for review) | Reducer + policy |
| **L2** | High-kinetic | Lease window only | Multi-sensor + signed policy |
| **L3** | Critical / irreversible | No | Human MFA or remote signature |

**Merge Ratchet:** Safety constraints only tighten automatically. Loosening requires a signed `POLICY_UPDATE` by a key with L3 clearance.

### Cryptographic Primitives

| Function | Algorithm | Specification |
|----------|-----------|---------------|
| Hashing | SHA-256 | FIPS 180-4 |
| Signing | Ed25519 | RFC 8032 |
| Canonical JSON | JCS-subset | RFC 8785 |
| Key IDs | `bp1_` + SHA-256(pubkey)[:16 hex] | Backpack v1 format |

The full normative specification is in [`PROTOCOL_PROFILE.txt`](PROTOCOL_PROFILE.txt) — immutable after distribution.

### Vault Anatomy

```
My_Backpack/
├── identity/
│   ├── genesis.json              # Birth certificate — who, when, why
│   └── keys.json                 # Public key registry
├── events/
│   └── events.ndjson             # THE source of truth (append-only)
├── policies/
│   ├── safety_policy.json        # L0-L3 kinetic risk tiers
│   ├── retention_policy.json     # Data permanence rules
│   ├── sync_contract.json        # Governance + authority ladder
│   └── ontology/
│       └── perception_ontology_v1.json
├── state/                        # Regeneratable from events (cache)
├── artifacts/
│   └── cas/                      # Content-addressed storage
├── manifest.json                 # File inventory with SHA-256 hashes
├── manifest.sig                  # Ed25519 signature over manifest
└── merkle_root.txt               # Integrity anchor (single hex string)
```

### Causal Chain

Events form a per-actor linked list via `prev_event_hash`:

- **First event** by an actor: `prev_event_hash` is `null`
- **Subsequent events**: `prev_event_hash` equals the `event_id` of that actor's immediately preceding event
- **Cross-actor**: an event must never reference another actor's events

This creates an unforgeable causal ordering. If event E claims to follow event P, then P must exist, and P must belong to the same actor. Any gap or forgery breaks the chain and fails compliance.

---

<details>
<summary><strong>Module Reference</strong> (click to expand)</summary>

## Module Reference

### `canonical_json.py`

Deterministic JSON serialization per RFC 8785. All hashing and signing operations use this as the canonical form. Keys sorted lexicographically, compact separators, UTF-8 encoding, no NaN or Infinity.

### `backpack_integrity.py`

Shared primitives for Merkle tree computation, path traversal protection, SHA-256 file hashing, and spec constants. Used by both the manifest generator and the compliance verifier.

### `reducer_v0.py` — `SovereignReducerV0`

Deterministic belief reducer. Takes an event stream, produces a belief state with byte-identical `state_hash` across any replay on any machine. Handles `OBSERVATION`, `ATTESTATION`, `REDUCER_EPOCH`, and gracefully preserves unknown event types.

**Core invariant:** `f(events) -> state` where identical events always produce identical `metadata.state_hash`.

### `manifest_generator.py`

Generates `manifest.json` and `merkle_root.txt` for a backpack directory. Symlink-safe, path-validated, excludes meta files from the hash tree.

### `backpack_signing.py`

Ed25519 signing layer. Keypair generation, event signing and verification, manifest signing and verification, key registry management.

### `rekey_backpack.py`

Key rotation protocol using a two-event model: `KEY_REVOCATION` followed by `KEY_PROMOTION`. The revoking/promoting signer must be a surviving trusted authority — the compromised key cannot authorize its own replacement.

### `bootstrap_v0.py`

Sovereign birth. Creates a fully compliant, cryptographically signed backpack from nothing. Generates Ed25519 keypairs, genesis event, seed policies, manifest, and Merkle root. The output passes all 17 compliance tests on first breath. Supports `--self-test` for built-in verification.

</details>

---

## Testing

### Test Matrix

| Suite | Tests | Coverage |
|-------|------:|----------|
| `test_reducer_v0.py` | 23 | Reducer determinism, evidence handling, namespace transitions, conflict resolution, state hashing |
| `test_rekey.py` | 18 | Key generation, event signing/verification, rotation protocol, trust boundary validation |
| test_bootstrap.py | 16 | End-to-end bootstrap, directory structure, genesis validation, manifest generation, self-test |
| test_sync_v0.py | 36 | Union merge, causal chain verification, deduplication, fork detection, fencing tokens |
| `backpack_compliance_v1.py` | 17 | Full protocol compliance (see breakdown below) |
| **Total** | **110** | |

### Running Tests

```bash
# All unit tests
cd SNP_Core/test && PYTHONPATH=../bin python -m unittest test_reducer_v0 test_rekey test_bootstrap -v

# Compliance tests against reference backpack
cd SNP_Core/test && PYTHONPATH=../bin python backpack_compliance_v1.py ../examples/reference_backpack -v

# Compliance tests against your own vault
cd SNP_Core/test && PYTHONPATH=../bin python backpack_compliance_v1.py /path/to/your/backpack -v
```

<details>
<summary><strong>Compliance Breakdown</strong> (click to expand)</summary>

### Compliance Breakdown

The 17 compliance tests are the minimum bar for any Provara v1.0 implementation:

| Category | Tests | What's Verified |
|----------|------:|-----------------|
| Directory structure | 2 | Required folders and files exist |
| Identity schema | 2 | Genesis event and key registry validity |
| Event schema + causal chain | 3 | Event format, uniqueness, and causal ordering |
| Manifest + Merkle tree | 5 | File hashes, Merkle computation, no phantoms, path safety |
| Safety policy | 2 | L0-L3 structure and ratchet constraints |
| Sync contract | 1 | Governance schema validity |
| Reducer determinism | 1 | Same events produce identical state hash |
| Retention permanence | 1 | Events are never deleted |

</details>

---

## Design Principles

1. **Truth over Comfort.** Never merge beliefs. Merge evidence. Recompute truth from the full record. If the evidence is uncomfortable, the truth is uncomfortable.

2. **Stability over Speed.** Causal integrity comes before low-latency ingestion. A correct answer later beats a wrong answer now.

3. **Fail Safe, Not Silent.** Merkle failure or reducer hang triggers a hardware lockout, not a quiet log entry. Integrity violations are never swallowed.

4. **Reversibility by Default.** Destructive actions require explicit, signed authority. The default is always the action that can be undone.

5. **Evidence is Permanent.** Events are never deleted, only superseded by newer evidence. The complete history is always available for re-evaluation.

---

<details>
<summary><strong>Project Map</strong> (click to expand)</summary>

## Project Map

```
Provara_Legacy_Kit/
│
├── README.md                       # You are here
├── PROTOCOL_PROFILE.txt            # Normative crypto spec (IMMUTABLE after distribution)
├── CHECKSUMS.txt                   # SHA-256 of every file in this kit
├── RECOVERY_INSTRUCTIONS.md        # Catastrophic recovery doctrine
│
├── Family_Guide/
│   └── START_HERE.md               # Non-technical user guide
│
├── Keys_Info/
│   └── HOW_TO_STORE_KEYS.md        # Key storage best practices
│
├── Recovery/
│   └── WHAT_TO_DO.md               # Lost keys? Corrupted vault? Start here.
│
├── Examples/
│   ├── README.md                   # About the demo
│   └── Demo_Backpack/              # A working vault you can explore and verify
│
├── SNP_Core/                       # The reference implementation
│   ├── bin/                        # 7 Python modules (~2,016 lines)
│   ├── test/                       # 4 test suites, 74 tests (~2,037 lines)
│   ├── deploy/templates/           # Policy templates (safety, retention, sync)
│   ├── examples/reference_backpack/# Known-good test fixture
│   └── docs/README.md              # Technical architecture documentation
│
├── init_backpack.sh / .bat         # Create your vault
├── check_backpack.sh / .bat        # Verify vault integrity
└── backup_vault.sh / .bat / .ps1   # Automated backup with verification
```

</details>

---

## Roadmap

| Component | Purpose | Status |
|-----------|---------|--------|
| `sync_v0.py` | Union merge + chain verification + fencing tokens | Pending |
| `BACKPACK_PROTOCOL_v1.0.md` | Formal canonical specification document | Pending |
| Checkpoint system | Signed state materializations for fast replay | Designed, not coded |
| Perception tiering | T0-T3 sensor data hierarchy | Designed, not coded |

---

<details>
<summary><strong>Reimplementing Provara</strong> (click to expand)</summary>

## Reimplementing Provara

The protocol is designed to be reimplemented in any language. The Python reference is canonical for resolving ambiguity, but the specification is language-agnostic.

**Steps:**

1. Implement SHA-256 (FIPS 180-4), Ed25519 (RFC 8032), and RFC 8785 canonical JSON
2. Validate against `test_vectors/vectors.json` (7 test vectors)
3. Build a reducer that processes `OBSERVATION`, `ATTESTATION`, and `RETRACTION` events
4. Verify your reducer produces the same `state_hash` as the Python reference for the test vector event sequence
5. Run the 17 compliance tests against your output

**If the state hashes match, your implementation is correct.** If they diverge, the canonical JSON or hash computation has a bug. The full specification is in [`PROTOCOL_PROFILE.txt`](PROTOCOL_PROFILE.txt).

</details>

---

## Key Management

Your private keys are the root of your sovereignty. If they are compromised, your identity is compromised. If they are lost without a quorum key, your vault becomes read-only forever.

**Read the full guide:** [Keys_Info/HOW_TO_STORE_KEYS.md](Keys_Info/HOW_TO_STORE_KEYS.md)

**Critical rules:**
- `my_private_keys.json` should never live on the same drive as your vault
- Use the `--quorum` flag during bootstrap to generate a recovery key pair
- Store root and quorum keys in separate physical locations
- If a key is compromised, use `rekey_backpack.py` to rotate — the compromised key cannot authorize its own replacement

---

## Recovery

Things break. Keys get lost. Drives fail. The kit is designed for this.

| Scenario | Resource |
|----------|----------|
| Catastrophic failure, total loss | [RECOVERY_INSTRUCTIONS.md](RECOVERY_INSTRUCTIONS.md) |
| Lost keys, corrupted files, common issues | [Recovery/WHAT_TO_DO.md](Recovery/WHAT_TO_DO.md) |
| Routine backup and restore | `backup_vault.sh` / `backup_vault.bat` |

Every backup is integrity-verified with SHA-256 before being written. The backup system verifies the source vault before copying and verifies the backup after creation.

---

## FAQ

**What happens if I lose my private keys?**
If you bootstrapped with `--quorum`, the quorum key can authorize a key rotation. If you only have a root key and it's gone, the vault is still readable — the data is plain JSON — but you can no longer sign new events. See [Recovery/WHAT_TO_DO.md](Recovery/WHAT_TO_DO.md).

**Can I read my vault without this software?**
Yes. Events are stored as NDJSON (one JSON object per line). Open `events/events.ndjson` with any text editor. The format was chosen specifically to remain human-readable for 50+ years.

**What if Python goes away in 20 years?**
The data format is language-agnostic. JSON, SHA-256, and Ed25519 are industry standards implemented in every major programming language. The protocol profile is a complete specification for reimplementation. The data survives the tooling.

**Can multiple devices share a vault?**
`sync_v0.py` is on the roadmap. The event-sourced architecture makes merging fundamentally safe — you merge the raw events, then recompute beliefs. No conflict resolution heuristics. No last-write-wins.

**Is this a blockchain?**
No. It is a Merkle tree over files combined with a causal event chain per actor. There is no consensus mechanism, no mining, no network, no tokens. It is closer to git than to Bitcoin.

**What's the difference between root and quorum keys?**
The root key is the primary signing authority. The quorum key is a recovery key stored in a separate physical location. Together they enable key rotation if either key is compromised. Neither key alone can be permanently locked out.

**How do I know my vault hasn't been tampered with?**
Run `check_backpack`. It verifies the Merkle root, manifest signatures, causal chain integrity, file hashes, and all 17 compliance tests. Any silent modification — even a single flipped bit — will fail verification.

**Can I use this for an AI agent's memory?**
Yes. The protocol was designed for cognitive continuity across embodied robotic systems. Events map to sensor observations, beliefs map to working memory, policies map to behavioral constraints. The reducer is the agent's epistemological engine.

**What does "Truth is not merged. Evidence is merged. Truth is recomputed." mean?**
When combining data from multiple sources, you never directly merge conclusions. You merge the raw observations (evidence), then rerun the deterministic reducer to derive fresh conclusions from all available evidence. This eliminates merge conflicts at the belief layer entirely.

**How large can a vault get?**
Events are append-only NDJSON — the practical limit is disk space. State is always regeneratable from events and can be cached or evicted freely. Old perception data follows configurable retention policies with oldest-first eviction.

---

## Version

```
Protocol            Provara v1.0
Profile             PROVARA-1.0_PROFILE_A
Implementation      1.0.0-rc1
Kit Date            2026-02-13
Tests Passing       74 (57 unit + 17 compliance)
```

---

## License

Apache 2.0 — Hunt Information Services. All rights reserved.

See [`PROTOCOL_PROFILE.txt`](PROTOCOL_PROFILE.txt) for the normative specification.

---

(c) 2026 Hunt Information Services

