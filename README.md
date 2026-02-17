<pre>
  ____  _   _ ____    _                                  _  ___ _
 / ___|| \ | |  _ \  | |    ___  __ _  __ _  ___ _   _  | |/ (_) |_
 \___ \|  \| | |_) | | |   / _ \/ _` |/ _` |/ __| | | | | ' /| | __|
  ___) | |\  |  __/  | |__|  __/ (_| | (_| | (__| |_| | | . \| | |_
 |____/|_| \_|_|     |_____\___|\__, |\__,_|\___|\__, | |_|\_\_|\__|
                                |___/            |___/
         Provara Protocol v1.0 — Reference Implementation
</pre>

**A protocol for preserving signed evidence with deterministic replay across humans, agents, and institutions.**

![Protocol](https://img.shields.io/badge/Protocol-Provara_v1.0-blue)
![Tests](https://img.shields.io/badge/Tests-232_passing-brightgreen)
![Python](https://img.shields.io/badge/Python-3.10%2B-yellow)
![PyPI](https://img.shields.io/badge/PyPI-provara--protocol_1.0.0-blue)
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
- [Development Workflow](#development-workflow)
- [Architecture](#architecture)
  - [Three-Lane Event Model](#three-lane-event-model)
  - [Four-Namespace Belief Model](#four-namespace-belief-model)
  - [Safety Envelope (L0--L3)](#safety-envelope-l0--l3)
  - [Cryptographic Primitives](#cryptographic-primitives)
  - [Vault Anatomy](#vault-anatomy)
  - [Causal Chain](#causal-chain)
- [AI Governance Use Cases](#ai-governance-use-cases)
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

Provara is an append-only, cryptographically signed event log that anyone can verify and no one can silently rewrite. It treats memory as evidence first: signed observations that can be replayed into state, audited independently, and preserved in plain files for long-horizon readability.

> **Golden Rule:** Truth is not merged. Evidence is merged. Truth is recomputed.

This system is built for people and organizations that need accountable records: families preserving history, AI teams logging model decisions, and regulated operators proving chain-of-custody. Provara does not claim truth. It preserves evidence so truth can be recomputed.

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
Operational Code    9 Python modules          ~3,500 lines
Test Suites         7 suites                  232 tests passing
External Deps       1                         cryptography >= 41.0
Crypto Stack        Ed25519 + SHA-256         RFC 8032 + FIPS 180-4
Serialization       Canonical JSON            RFC 8785 (JCS)
MCP Server          8 tools, SSE + stdio      Works with Claude, GPT, etc.
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
# Install
pip install provara-protocol

# Or clone and run directly
git clone https://github.com/provara-protocol/provara

# Create a vault
provara init /path/to/vault

# Verify integrity
provara verify /path/to/vault

# Run tests
python -m pytest tests/
PYTHONPATH=src python tests/backpack_compliance_v1.py tests/fixtures/reference_backpack -v
python -m pytest tools/psmc/test_psmc.py tools/mcp_server/test_server.py -v

# MCP server (connect any AI agent to a Provara vault)
python tools/mcp_server/server.py --transport stdio    # Claude Code / Cursor
python tools/mcp_server/server.py --transport http --port 8765  # SSE/HTTP
```

**Cross-language implementors:** see the triad in `docs/`:
- [`CHAIN_VALIDATION.md`](docs/CHAIN_VALIDATION.md) — step-numbered validation algorithm
- [`ERROR_CODES.md`](docs/ERROR_CODES.md) — 29 normative error codes
- [`test_vectors/vectors.json`](test_vectors/vectors.json) — 8 cross-language test vectors

---

## Development Workflow

This project uses AI-assisted development. Automated coding tools handle backend implementation, test expansion, refactoring, and security audits. The maintainer retains final approval on all changes.

| Scope | Approach |
|-------|----------|
| Backend code (`SNP_Core/bin/`) | AI-assisted implementation and refactoring |
| Test coverage (`SNP_Core/test/`) | AI-assisted expansion and edge-case generation |
| Protocol compliance | Automated verification via 17-test compliance suite |
| Documentation | AI-assisted drafting, human review |
| Websites and deployment (`sites/`) | Manual |
| Business operations | Manual |

Project context files (`CLAUDE.md`, `GEMINI.md`, `CODEX.md`) provide standing instructions for AI coding tools. These are analogous to `.editorconfig` or linter configs — tooling configuration, not documentation.

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

## MCP Server — Any AI Agent Writes Tamper-Evident Memory

The Provara MCP server exposes the full vault API to any AI agent that supports the [Model Context Protocol](https://modelcontextprotocol.io/).

**Claude Code / Cursor** — add to `.mcp.json`:
```json
{
  "mcpServers": {
    "provara": {
      "command": "python",
      "args": ["path/to/tools/mcp_server/server.py", "--transport", "stdio"]
    }
  }
}
```

**HTTP/SSE** (Claude.ai, OpenAI, etc.):
```bash
python tools/mcp_server/server.py --transport http --port 8765
# Connect to: http://localhost:8765/sse
```

**Available tools:**

| Tool | Description |
|------|-------------|
| `append_event` | Write a signed, chained event to the vault |
| `verify_chain` | Verify causal chain + signature integrity |
| `snapshot_state` | Get deterministic state hash |
| `query_timeline` | Filter events by type or time range |
| `list_conflicts` | Show contested beliefs awaiting resolution |
| `generate_digest` | Weekly markdown digest of memory events |
| `export_markdown` | Full vault history as formatted Markdown |
| `checkpoint_vault` | Create signed state snapshot for fast replay |

Once connected, the agent writes tamper-evident, cryptographically-signed memory that outlives any session, platform, or provider.

---

## AI Governance Use Cases

Provara's append-only event log, deterministic reducer, and Ed25519 signature chain make it a natural substrate for AI governance and control plane systems. The same properties that guarantee cognitive continuity for autonomous agents guarantee auditability and non-repudiation for AI oversight frameworks.

| Use Case | How Provara Supports It |
|----------|------------------------|
| **Model evaluation logging** | Each evaluation run is a signed `OBSERVATION` event with model ID, benchmark, and scores. Results are tamper-evident and reproducible. |
| **Prompt & test result logging** | Prompt inputs, model outputs, and latency metrics are recorded as chained events. Any after-the-fact alteration breaks the causal chain. |
| **Policy enforcement decisions** | When a governance policy permits or denies an AI action, the decision, the policy version, and the reasoning are recorded as an `ATTESTATION`. Auditors can replay the full decision history. |
| **AI cost & routing oversight** | Token usage, model selection, routing decisions, and cost data are logged as signed events. Spend anomalies surface through reducer-computed aggregates. |
| **Red-team audit records** | Adversarial test cases, model responses, and severity assessments form a signed, append-only audit trail. Results cannot be silently retracted or amended. |

**Why this works:**

- **Append-only guarantees** mean no record can be deleted or modified after the fact — a hard requirement for regulatory compliance.
- **Deterministic reducers** mean any auditor can replay the event log and independently verify every derived conclusion.
- **Ed25519 signatures** bind every event to a specific key holder, providing non-repudiation.
- **Causal chains** provide total ordering per actor, making it impossible to insert, reorder, or remove events without detection.

> For a detailed treatment, see [`docs/GOVERNANCE_ALIGNMENT.md`](docs/GOVERNANCE_ALIGNMENT.md).
>
> For example event schemas, see [`examples/ai_governance_events/`](examples/ai_governance_events/).

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
| `test_bootstrap.py` | 16 | End-to-end bootstrap, directory structure, genesis validation, manifest generation, self-test |
| `test_sync_v0.py` | 36 | Union merge, causal chain verification, deduplication, fork detection, fencing tokens, delta export/import |
| `test_vectors.py` | 8 | Cross-language normative vectors (canonical JSON, SHA-256, Ed25519, event_id, key_id, Merkle, reducer) |
| `backpack_compliance_v1.py` | 17 | Full protocol compliance |
| `test_psmc.py` | 60 | PSMC application layer (Personal Sovereign Memory Container) |
| `test_server.py` | 22 | MCP server — all 8 tools, SSE and stdio transports |
| `test_checkpoint_v0.py` | 3 | Checkpoint create, verify, tamper-detection |
| `test_perception_v0.py` | 3 | Perception payload generation |
| **Total** | **206** | *(215 including compliance; 7 compliance fail on Windows CRLF — known pre-existing)* |

### Running Tests

```bash
# Core unit tests (125)
cd SNP_Core/test && PYTHONPATH=../bin python -m unittest test_reducer_v0 test_rekey test_bootstrap test_sync_v0 -v

# All pytest suites
python -m pytest tools/psmc/test_psmc.py tools/mcp_server/test_server.py SNP_Core/test/test_vectors.py -v

# Compliance tests against reference backpack
cd SNP_Core/test && PYTHONPATH=../bin python backpack_compliance_v1.py ../examples/reference_backpack -v
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
├── src/provara/                    # The reference implementation package
│   ├── cli.py                      # CLI entry point
│   └── ...                         # Core modules (crypto, reducer, sync)
│
├── tests/                          # Test suites (unit, compliance, integration)
│   ├── fixtures/reference_backpack/# Known-good test fixture
│   └── ...
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
| Core protocol (7 modules) | Ed25519 + SHA-256 + canonical JSON + reducer | ✅ Complete |
| `BACKPACK_PROTOCOL_v1.0.md` | Human-readable protocol spec | ✅ Complete |
| `docs/spec/v1.0/` | Static HTML spec for provara.dev/spec/v1.0 | ✅ Complete |
| `CHAIN_VALIDATION.md` | Language-agnostic validation pseudocode | ✅ Complete |
| `errors.json` | 29 normative error codes | ✅ Complete |
| Checkpoint system | Signed state snapshots for fast replay | ✅ Complete |
| Perception tiering | T0-T3 sensor data hierarchy | ✅ Complete |
| PSMC | Personal Sovereign Memory Container app layer | ✅ Complete |
| MCP server | 8-tool server (SSE + stdio) for any AI agent | ✅ Complete |
| Unified CLI | `provara init/verify/backup/checkpoint/replay` | ✅ Complete |
| Rust port | `provara-rs` — performance + FFI | 🔜 Next |
| TypeScript port | Browser + Node | 🔜 |
| IETF SCITT draft | Internet-Draft submission | 🔜 Month 12 |

---

<details>
<summary><strong>Reimplementing Provara</strong> (click to expand)</summary>

## Reimplementing Provara

The protocol is designed to be reimplemented in any language. The Python reference is canonical for resolving ambiguity, but the specification is language-agnostic.

**Steps:**

1. Implement SHA-256 (FIPS 180-4), Ed25519 (RFC 8032), and RFC 8785 canonical JSON
2. Validate against `test_vectors/vectors.json` (8 test vectors)
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
Yes. `sync_v0.py` implements union merge with causal chain verification, fork detection, and fencing tokens. The event-sourced architecture makes merging fundamentally safe — you merge the raw events, then recompute beliefs. No conflict resolution heuristics. No last-write-wins.

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
Implementation      1.0.0
PyPI                provara-protocol 1.0.0
Kit Date            2026-02-13
Tests Passing       232 (125 unit + 8 vector + 17 compliance + 60 PSMC + 22 MCP)
```

---

## License

Apache 2.0. See [`LICENSE`](LICENSE) for details.

Normative specification: [`PROTOCOL_PROFILE.txt`](PROTOCOL_PROFILE.txt) (immutable after distribution).
Canonical spec URL: [`https://provara.dev/spec/v1.0`](https://provara.dev/spec/v1.0).
Human-readable spec source: [`docs/spec/v1.0/provara-v1.0-spec.txt`](docs/spec/v1.0/provara-v1.0-spec.txt).
Static spec HTML source: [`docs/spec/v1.0/index.html`](docs/spec/v1.0/index.html).



