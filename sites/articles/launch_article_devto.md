---
title: I Built a Cryptographic Memory Vault -- Here's the Protocol
published: false
description: Provara is an open-source, tamper-evident, offline-first memory protocol that serves both human digital vaults and AI agent cognitive continuity -- using Ed25519, SHA-256, and a single dependency.
tags: ai, cryptography, opensource, python
---

# I Built a Cryptographic Memory Vault -- Here's the Protocol

Every AI agent framework shipping today has a memory problem. Not a "we need more context window" problem -- a trust problem. Mem0, Zep, LangChain memory, whatever your stack uses -- it all lives on someone else's servers, in someone else's format, behind someone else's API key. When that company pivots, gets acquired, or shuts down, your agent's memory goes with it. No export. No verification. No proof that what you get back is what you put in.

Now zoom out. The same problem exists for humans. Your photos are on iCloud. Your documents are on Google Drive. Your notes are in Notion. Your family records are scattered across a dozen services, each with its own terms of service, its own export format, and zero cryptographic guarantees that the data hasn't been modified. Try inheriting someone's digital life. Try proving what was there before something was deleted. You can't.

I spent the last several months building an open protocol to solve this. It's called **[Provara](https://provara.dev)**, and it's a sovereign, tamper-evident, offline-first memory system that works for both humans and AI agents using the same underlying architecture. Seven Python modules. Seventy-four tests. One dependency. Here's how it works.

---

## The Problem, Clearly Stated

AI memory systems today are cloud-dependent by default. Mem0 stores your agent's memory on their infrastructure. Zep runs a server you have to maintain. Every major agent framework treats memory as a hosted service -- which means your agent's cognitive continuity is a subscription payment away from disappearing.

For humans, the picture is worse. Your digital legacy -- decades of photos, documents, messages, records -- sits fragmented across services that owe you nothing beyond their current terms of service. None of it is cryptographically verifiable. None of it is inheritable in any meaningful technical sense. When you die, your family gets a patchwork of account recovery processes, not a coherent, tamper-proof record.

The gap is clear: there is no open protocol for tamper-evident, offline-first, sovereign memory that serves both humans and AI agents. No standard format that a family can hand down for generations, or that an AI agent can carry across embodiments without trusting a third party.

What if your memory system outlasted the company that built it?

---

## Design Constraints

Before writing any code, I locked down what the system had to guarantee:

- **Must work fully offline.** Air-gapped operations. No phone-home, no telemetry, no cloud dependency after initial setup.
- **Must be tamper-evident.** Every event is cryptographically signed and hash-chained. Any modification -- even a single flipped bit -- is detectable.
- **Must be deterministic.** Same events fed into the same reducer produce byte-identical state on any machine, any time, forever.
- **Must be readable in 50 years.** The data format uses JSON, SHA-256, and Ed25519 -- industry standards that will outlive any company, any framework, any platform.
- **Must have one external dependency.** The only package the system imports outside the standard library is `cryptography` (>= 41.0). That's it.
- **Must serve both humans and AI agents** with the same protocol, not two products duct-taped together.
- **No blockchain.** Provara provides real cryptographic guarantees without consensus mechanisms, gas fees, or network dependency. More on this below.

These constraints shaped every architectural decision that followed.

---

## How It Works

### Event-Sourced Architecture

Provara is built on event sourcing. The source of truth is an append-only NDJSON file -- one JSON object per line, in `events/events.ndjson`. Events are never modified and never deleted. Corrections are new events. The current state of the system is always derived by replaying the event log through a deterministic reducer.

This is the golden rule: **Truth is not merged. Evidence is merged. Truth is recomputed.**

When two devices sync, you don't merge their beliefs or conclusions. You merge their raw event logs (union by `event_id`), then replay the full combined log through the reducer. Fresh conclusions emerge from all available evidence. No last-write-wins heuristics. No merge conflicts at the belief layer.

### Three-Lane Model

Events flow into three lanes:

| Lane | Content | Merge Strategy |
|------|---------|----------------|
| **Episodic Events** | Append-only observation log | Union by `event_id` |
| **Beliefs** | Derived view from events | Recomputed by reducer (never merged directly) |
| **Policies** | Governance, safety, sync rules | Versioned with ratchet constraints |

### Event Structure

Here's what a real event looks like in the log:

```json
{
  "type": "OBSERVATION",
  "namespace": "local",
  "actor": "robot_a",
  "actor_key_id": "bp1_a3f8c9d2e1b07654",
  "ts_logical": 1,
  "prev_event_hash": null,
  "timestamp_utc": "2026-02-12T19:30:00Z",
  "payload": {
    "subject": "door_01",
    "predicate": "opens",
    "value": "inward",
    "confidence": 0.9
  },
  "event_id": "evt_7a3b9c1d4e5f6071829a3b",
  "sig": "R0xPQkFMX1NJR05BVFVSRV9CQVNFNjQ..."
}
```

Every event carries its actor identity, a logical timestamp, a causal chain link (`prev_event_hash`), a structured payload, a content-addressed ID (SHA-256 of the canonical form), and an Ed25519 signature. The `event_id` is derived from the event content itself -- if any field changes, the ID changes, and the causal chain breaks.

### Cryptographic Primitives

| Function | Algorithm | Specification |
|----------|-----------|---------------|
| Hashing | SHA-256 | FIPS 180-4 |
| Signing | Ed25519 | RFC 8032 |
| Canonical JSON | JCS-subset | RFC 8785 |
| Key IDs | `bp1_` + SHA-256(pubkey)[:16 hex] | Backpack v1 format |

All hashing and signing operations go through a canonical JSON serializer that implements RFC 8785 -- sorted keys, compact separators, UTF-8 encoding, no NaN or Infinity. This is the critical piece for determinism: two implementations in different languages, on different machines, must produce byte-identical canonical bytes for the same logical object.

```python
def canonical_dumps(obj: Any) -> str:
    """Canonical JSON: sorted keys, no whitespace, UTF-8."""
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )

def canonical_hash(obj: Any) -> str:
    """SHA-256 hex digest of canonical JSON bytes."""
    return hashlib.sha256(
        canonical_dumps(obj).encode("utf-8")
    ).hexdigest()
```

### Four-Namespace Belief Model

The reducer maintains four namespaces for beliefs:

| Namespace | Meaning | Promotion Rule |
|-----------|---------|----------------|
| `canonical/` | Institutionally attested truth | Requires `ATTESTATION` event |
| `local/` | Node-local observations | Auto-promotes when no conflict exists |
| `contested/` | Conflicting high-confidence evidence | Requires explicit resolution event |
| `archived/` | Superseded canonical beliefs | Automatic on supersession |

When Robot A observes a door opening inward with 0.9 confidence, and Robot B observes it opening outward with 0.95 confidence, the reducer detects the conflict and moves the belief into `contested/` with all evidence preserved. It doesn't pick a winner -- it surfaces the disagreement and waits for an `ATTESTATION` event from a trusted authority. When a canonical belief is superseded by a new attestation, the old belief is archived, not deleted. The full evidentiary history is always available.

### Causal Chain

Events form a per-actor linked list via `prev_event_hash`. Each actor's first event has `prev_event_hash: null`. Every subsequent event by that actor links back to their previous event's `event_id`. An event must never reference another actor's chain. This creates an unforgeable causal ordering -- if event E claims to follow event P, then P must exist, must precede E, and must belong to the same actor. Any gap or forgery breaks the chain and fails compliance.

### Merkle Tree

Every file in the vault is hashed with SHA-256 and assembled into a Merkle tree. The root hash is written to `merkle_root.txt`, and the entire manifest is signed with Ed25519. This seals the vault state: you can verify the integrity of every file with a single signature check, and detect any modification -- additions, deletions, or changes -- against the signed root.

### Key Rotation

Keys can be compromised. The protocol handles this with a two-event model:

1. **KEY_REVOCATION** -- signed by a surviving trusted authority, marks the compromised key as revoked and establishes a trust boundary (the last event by that key that's considered trustworthy).
2. **KEY_PROMOTION** -- signed by the same surviving authority, introduces the new public key with roles and scopes.

The critical security constraint: the compromised key cannot authorize its own replacement. The signing authority must be a different, non-revoked key. If an attacker could generate a new keypair and self-authorize, the trust chain would be meaningless.

### Safety Envelope

Policies include a four-tier safety model (L0-L3) designed for AI agents operating in the physical world:

| Tier | Risk Level | Offline Allowed | Gate |
|------|------------|-----------------|------|
| L0 | Data-only, reversible | Yes | Local reducer |
| L1 | Low-kinetic | Yes (logged for review) | Reducer + policy |
| L2 | High-kinetic | Lease window only | Multi-sensor + signed policy |
| L3 | Critical / irreversible | No | Human MFA or remote signature |

The merge ratchet ensures safety constraints only tighten automatically during sync. Loosening requires a signed `POLICY_UPDATE` from the top authority. This is designed for robotic systems where an agent might go offline -- the degradation is always toward more caution, never less.

---

## What I Built

Here are the numbers:

```
Operational Code    7 Python modules          ~2,016 lines
Test Code           4 test suites             ~2,037 lines
Tests Passing       74 total                  57 unit + 17 compliance
External Deps       1                         cryptography >= 41.0
Python Version      3.10+
Platforms           Windows, macOS, Linux
Data Format         NDJSON events + JSON      Readable forever
```

The seven modules:

- **`canonical_json.py`** -- RFC 8785 deterministic JSON serialization
- **`backpack_integrity.py`** -- Merkle tree computation, path safety, SHA-256 file hashing
- **`reducer_v0.py`** -- Deterministic belief reducer with four namespaces
- **`manifest_generator.py`** -- Manifest and Merkle root generation
- **`backpack_signing.py`** -- Ed25519 signing layer for events and manifests
- **`rekey_backpack.py`** -- Key rotation protocol (revocation + promotion)
- **`bootstrap_v0.py`** -- Sovereign birth: creates a fully compliant vault from nothing

Bootstrap a complete vault in one command:

```bash
python bootstrap_v0.py /path/to/my_vault --quorum --self-test
```

This generates Ed25519 keypairs (root + quorum), creates the genesis event, builds policy files, generates the manifest and Merkle root, signs everything, and then runs all 17 compliance tests against its own output. If the tests fail, the bootstrap has a bug. The output is a cryptographically signed, self-verifying vault from first breath.

The compliance test suite is designed to be run against any implementation. If you reimplement Provara in Rust, Go, or JavaScript, your output must pass the same 17 tests: directory structure, identity schema, event format, causal chain integrity, Merkle verification, safety policy structure, sync contract validity, reducer determinism, and retention permanence. Same events, same reducer, same state hash. If the hashes match, your implementation is correct.

---

## The Dual-Audience Insight

Here's the thing that surprised me most during the design process: the same protocol naturally serves two very different audiences.

**For families**, Provara is a digital vault. Tamper-proof records that can be passed down for generations. No cloud accounts to expire. No services to sunset. No export formats to rot. Open the event log in a text editor in 2076 and it reads exactly the same as it does today. Key management supports a quorum model -- root and recovery keys stored in separate physical locations -- so that inheritance is a key handoff, not a password guessing game.

**For AI agents**, Provara is cognitive continuity infrastructure. An autonomous agent's memory -- its observations, beliefs, and policy constraints -- lives in a verifiable chain of evidence that migrates across embodiments without vendor lock-in. Swap the robot's body. Change the inference engine. Move to a new cloud provider. The memory persists, verifiable and intact.

This isn't two products sharing a name. It's one protocol with two use cases. The event-sourced architecture, the cryptographic primitives, the deterministic reducer -- all of it is the same system. A family vault and a robot's cognitive log differ in what events they record, not in how those events are stored, signed, chained, or verified.

The best infrastructure serves multiple audiences without compromise.

---

## Why Not Blockchain?

I know this will come up, so let me address it directly.

Provara provides the same guarantees people associate with blockchain: tamper evidence, hash chains, cryptographic signatures, append-only logs. But it does this without consensus mechanisms, without gas fees, without network dependency, and without requiring anyone to run a node.

A blockchain solves the problem of distributed consensus among mutually distrusting parties. That's not the problem here. A family vault has one owner. An AI agent has one operator (or a known, small trust group). The trust model is local, not global. You don't need proof of work to verify your own memory -- you need a hash chain, a signature, and a Merkle tree.

Provara works offline. It works air-gapped. It works on a USB drive in a safe deposit box. It works on a robot in a warehouse with no internet connection. No nodes to run. No chain to sync. No tokens to buy.

We use the math without the overhead.

---

## What's Next

Provara is open source under **Apache 2.0**.

The protocol spec is frozen at v1.0. The reference implementation passes 74 tests. The compliance suite is ready for any reimplementation to validate against.

What's coming:

- **Sync layer** (`sync_v0.py`) -- multi-device event merging with fencing tokens and lease-based conflict prevention
- **Family Vault desktop app** -- a GUI wrapper so non-technical users can create, browse, and back up vaults without touching a command line
- **Formal specification document** -- the full normative protocol spec for cross-language implementation
- **Consulting** -- if you're building autonomous agents and need verifiable cognitive continuity, I'd be glad to help design the memory architecture

The repo is here: **[github.com/hunt-os/provara](https://github.com/hunt-os/provara)**

```bash
git clone https://github.com/hunt-os/provara.git
cd provara
python -m pytest
```

If you're building AI agents with long-term memory requirements, if you're thinking about digital legacy for your family, or if you just appreciate well-built cryptographic systems -- take a look. Clone it. Run the compliance tests. Read the event log in a text editor. Break it if you can.

---

## Closing

We're entering a period where both humans and AI agents will need memory systems that are sovereign, verifiable, and built to last. Not memory as a service. Not memory locked behind an API. Memory as infrastructure -- something you own, something you can prove, something that outlasts the tools that created it.

Provara is my answer to that. It's not the only answer, but it's an honest one: real cryptography, real tests, real code you can read in an afternoon. No magic. No hand-waving. Just Ed25519, SHA-256, and the discipline to build something that works the same way on every machine, every time, for the next fifty years.

The repo is open. The protocol is frozen. The compliance tests are waiting.

**[github.com/hunt-os/provara](https://github.com/hunt-os/provara)**

*[Hunt Information Systems](https://huntinfosystems.com) -- we build systems that remember.*
