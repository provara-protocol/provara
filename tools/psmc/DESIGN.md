# Personal Sovereign Memory Container (PSMC)
## Design Document v1.0

**Built on [Provara Protocol](https://github.com/provara-protocol/provara) primitives.**

---

## Provara Integration

PSMC is the first application built on the Provara Protocol's cryptographic foundation. Rather than reimplementing crypto primitives, PSMC imports directly from `SNP_Core/bin/`:

| PSMC Function | Provara Primitive | Module |
|---------------|-------------------|--------|
| Canonical JSON serialization | `canonical_dumps()` | `canonical_json.py` |
| Event hashing | `canonical_hash()` | `canonical_json.py` |
| Key fingerprints | `key_id_from_public_bytes()` | `backpack_signing.py` |

**Key ID format:** PSMC uses Provara's `bp1_` prefix scheme (`bp1_` + first 16 hex chars of SHA-256 of raw public key bytes), ensuring cross-compatibility between PSMC vaults and Provara backpacks.

**What PSMC keeps separate:**
- Vault layout (simpler than a full Provara backpack)
- Event types (human-friendly: decision, belief, reflection, etc.)
- PEM key storage (vs. Provara's base64 raw keys)
- Chain file architecture (signatures in chain.ndjson, not embedded in events)

---

## Directory Structure

```
vault/
├── psmc.json              # Vault metadata (version, creation date, key fingerprint)
├── README.txt             # Human-readable explanation for future readers
├── keys/
│   ├── active.pem         # Ed25519 private key (PEM, 0600 permissions)
│   ├── active.pub.pem     # Ed25519 public key (PEM, shareable)
│   └── retired/           # Rotated keys with timestamp prefix
│       ├── 20260101T120000Z_private.pem
│       └── 20260101T120000Z_public.pub.pem
├── events/
│   └── events.ndjson      # Append-only event log (one JSON per line)
├── chain/
│   └── chain.ndjson       # Hash chain entries (parallel to events)
├── digests/
│   └── 2025-W24.md        # Human-readable weekly summaries
└── export.md              # Full Markdown export (optional)
```

**Why this layout:**
- Every file is UTF-8 text. No binary blobs except PEM keys (which are base64 text).
- A human with `cat`, `grep`, and `python3` can read everything.
- The separation of events and chain allows independent verification tooling.

---

## Event Schema (NDJSON)

Each line in `events.ndjson` is a self-contained JSON object:

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "seq": 0,
  "type": "identity",
  "timestamp": "2025-06-15T14:30:00+00:00",
  "prev_hash": "0000000000000000000000000000000000000000000000000000000000000000",
  "data": {
    "name": "Alice",
    "values": ["truth", "durability"]
  },
  "tags": ["personal", "foundational"],
  "hash": "a3f2b8c1d4e5f6..."
}
```

| Field       | Type     | Description                                      |
|-------------|----------|--------------------------------------------------|
| `id`        | UUID v4  | Globally unique event identifier                 |
| `seq`       | integer  | Zero-indexed sequence number (monotonic)         |
| `type`      | string   | One of the valid event types (see below)         |
| `timestamp` | ISO 8601 | UTC creation time                                |
| `prev_hash` | hex      | SHA-256 hash of the previous event (chain link)  |
| `data`      | object   | Arbitrary JSON payload (type-specific)           |
| `tags`      | string[] | Optional classification tags                     |
| `hash`      | hex      | SHA-256 of the canonical form of this event      |

**Valid event types:** `identity`, `decision`, `belief`, `promotion`, `note`, `milestone`, `reflection`, `correction`, `migration`

**Canonical JSON:** All hashing uses RFC 8785-style canonical JSON (sorted keys, no extra whitespace, `separators=(",",":")`) via Provara's `canonical_json.py` to ensure deterministic hashing across platforms and languages.

---

## Hash Chain Design

```
┌─────────────────────────────────────────────────────────────┐
│ EVENT 0                                                     │
│ prev_hash: 000000...  (genesis)                             │
│ hash: SHA256(canonical_json(event_without_hash_field))      │
│                                              │              │
│ CHAIN 0                                      │              │
│ hash: (same) ────────────────────────────────┘              │
│ sig: Ed25519(hash)                                          │
│ key_fp: bp1_ fingerprint of signing key                     │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼ prev_hash
┌─────────────────────────────────────────────────────────────┐
│ EVENT 1                                                     │
│ prev_hash: (hash of event 0)                                │
│ hash: SHA256(canonical_json(event_without_hash_field))      │
│                                              │              │
│ CHAIN 1                                      │              │
│ hash: (same) ────────────────────────────────┘              │
│ sig: Ed25519(hash)                                          │
│ key_fp: bp1_ fingerprint of signing key                     │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼ prev_hash
                          ...
```

### How Integrity Works

**Three layers of protection:**

1. **Content hashing:** Each event's hash is computed over its canonical JSON representation (all fields except `hash` itself). If any byte of the event changes, the hash changes.

2. **Hash chain linkage:** Each event embeds the hash of the previous event in its `prev_hash` field. This creates a linked chain: modifying any event breaks the chain for all subsequent events. An attacker would need to recompute and re-sign every subsequent event.

3. **Cryptographic signatures:** Each hash is signed with the vault owner's Ed25519 private key. The signature proves the event was created by the key holder. Without the private key, forged events can't be signed.

**Verification algorithm:**
```
for each (event, chain_entry) at index i:
    1. Check event.prev_hash == hash of event[i-1]  (or genesis if i==0)
    2. Recompute SHA-256 of canonical_json(event minus hash field)
    3. Confirm recomputed hash == event.hash == chain_entry.hash
    4. Look up public key by chain_entry.key_fp
    5. Verify Ed25519 signature over the hash
    6. Confirm event.seq == i
```

If any check fails, the chain is broken at that point.

---

## CLI Reference

```bash
# Initialize a new vault
python psmc.py --vault ./my-vault init

# Append events
python psmc.py append --type identity --data '{"name":"Alice"}'
python psmc.py append --type decision --data '{"title":"Use NDJSON","reason":"simplicity"}' --tags architecture foundational
python psmc.py append --type belief --data '{"statement":"Simplicity wins","confidence":0.9}'
python psmc.py append --type note --data '{"content":"Random thought at 3am"}'

# Verify entire chain
python psmc.py verify
python psmc.py verify --verbose

# Browse events
python psmc.py show
python psmc.py show --last 5
python psmc.py show --type decision

# Generate weekly digest
python psmc.py digest --weeks 1
python psmc.py digest --weeks 4

# Export full vault as Markdown
python psmc.py export --format markdown

# Rotate signing key
python psmc.py rotate-key

# Seed example entries
python psmc.py seed
```

---

## Example Entries

### Identity
```json
{
  "name": "Alice Nakamoto",
  "born": "1990-03-15",
  "summary": "Founder, systems architect, sovereign tech builder",
  "values": ["truth", "durability", "sovereignty", "simplicity"]
}
```

### Decision
```json
{
  "title": "Adopt append-only architecture for memory system",
  "context": "Evaluated relational DB, flat files, and event log approaches",
  "choice": "NDJSON event log with hash chain",
  "reason": "Maximum durability, portability, and simplicity.",
  "alternatives_rejected": ["SQLite", "PostgreSQL", "custom binary format"],
  "reversible": false
}
```

### Belief Snapshot
```json
{
  "domain": "technology",
  "statement": "Cryptographic integrity is more important than encryption for personal records",
  "confidence": 0.85,
  "evidence": "Encryption keys get lost over decades; tamper-evidence preserves trust",
  "last_reviewed": "2025-01-15"
}
```

### Promotion Event
```json
{
  "title": "Senior Systems Architect",
  "organization": "Sovereign Systems Inc.",
  "effective_date": "2025-06-01",
  "summary": "Promoted to lead all infrastructure and protocol development",
  "prior_role": "Systems Engineer"
}
```

---

## Weekly Digest

The `digest` command generates a Markdown summary grouped by event type, with a chain integrity footer. Example output:

```markdown
# Memory Digest: 2025-W24
Generated: 2025-06-15T14:30:00+00:00
Period: 2025-06-08 to 2025-06-15
Events: 6

## Decision (1)
- **2025-06-10** — Adopt append-only architecture for memory system

## Belief (1)
- **2025-06-11** — Cryptographic integrity is more important than encryption...

---
Chain head: `a3f2b8c1d4e5f6a7...`
Total events in vault: 42
```

Digests are saved to `digests/YYYY-WNN.md` for archival.

---

## Migration Path for Cryptographic Upgrades

**Problem:** SHA-256 and Ed25519 are strong today but may weaken over decades.

**Strategy: Epoch-based migration**

1. **Current epoch (v1):** SHA-256 + Ed25519. Sufficient through ~2040+ at minimum.

2. **Migration trigger:** When a stronger algorithm becomes standard (e.g., post-quantum), perform a key rotation that also logs the algorithm transition:

```json
{
  "type": "migration",
  "data": {
    "action": "algorithm_upgrade",
    "old_hash_algo": "sha256",
    "new_hash_algo": "sha3-256",
    "old_sig_algo": "ed25519",
    "new_sig_algo": "dilithium3",
    "epoch": 2,
    "bridging_hash": "<sha256 of last event, also hashed with new algo>",
    "reason": "Post-quantum migration per NIST PQC standardization"
  }
}
```

3. **Bridge event:** The migration event is signed with BOTH the old and new keys, creating a cryptographic bridge. The old chain remains verifiable with old keys; new events use new algorithms.

4. **Vault metadata update:** `psmc.json` gets `"hash_algo"` and `"sig_algo"` fields updated. Verification code checks the epoch and uses the appropriate algorithm.

5. **Backward compatibility:** Old events always remain verifiable because:
   - The old public keys are preserved in `keys/retired/`
   - The old hash algorithm is recorded in the migration event
   - NDJSON is self-describing — each chain entry can specify its algorithm

**Key rotation** (without algorithm change) is already supported via `rotate-key`. The retired keys are preserved for verification of historical events.

---

## Tradeoffs

| Choice | Benefit | Cost |
|--------|---------|------|
| NDJSON over SQLite | Human-readable, no tooling needed, survives decades | No indexing, O(n) scans for queries |
| Single file over sharded | Simplicity, easy backup | File size limit (~2GB practical), no parallel writes |
| Ed25519 over RSA | Small keys (32 bytes), fast, modern | Less ubiquitous in legacy systems |
| SHA-256 over SHA-3 | Universal support, battle-tested | Not post-quantum (but neither is Ed25519) |
| Append-only over mutable | Tamper-evident, audit trail | Can't fix typos — must append corrections |
| No encryption at rest | Readable without key management | Private data visible to filesystem access |
| Canonical JSON over CBOR | Human-readable, debuggable | Slightly larger, slower to parse |
| `cryptography` as sole dep | Minimal attack surface | Must be installed; no pure-Python fallback |
| Sequential seq numbers | Simple verification | Reveals operation count to anyone with file access |
| Provara primitives | Battle-tested crypto, shared maintenance | Import path coupling to SNP_Core |

---

## Failure Modes

### 1. Private key compromise
**Impact:** Attacker can sign forged events.
**Mitigation:** Keep `active.pem` on encrypted storage. Rotate keys regularly. If compromised, rotate immediately — the migration event creates a trust boundary.
**Detection:** Events you don't recognize in the log.

### 2. File corruption (disk failure, bad copy)
**Impact:** Verification fails at the corrupted event.
**Mitigation:** Regular backups (the entire vault is a plain directory — `cp -r` or `rsync`). Verify after every backup.
**Detection:** `psmc.py verify` catches any corruption.

### 3. Truncation (partial write during crash)
**Impact:** Last event may be incomplete JSON. Chain still valid up to the last complete event.
**Mitigation:** fsync after every append. The incomplete line can be detected (invalid JSON) and removed.
**Recovery:** Delete the last incomplete line from both `events.ndjson` and `chain.ndjson`.

### 4. Clock manipulation
**Impact:** Timestamps can be forged (they're self-reported).
**Mitigation:** Timestamps are informational, not authoritative. The sequence number and hash chain establish ordering regardless of clock.
**Note:** If you need trusted timestamps, append a hash to an external timestamping service (RFC 3161) periodically.

### 5. Loss of private key
**Impact:** Cannot sign new events. Cannot prove authorship of future events.
**Mitigation:** Back up `active.pem` securely. Old events remain verifiable via `active.pub.pem`.
**Recovery:** Generate new key via `rotate-key`. Old events verifiable with retired public key.

### 6. NDJSON grows very large
**Impact:** Slow verification, large backups.
**Mitigation:** At ~100K events (~500MB), consider epoch rotation: archive the old file, start a new one with a migration event pointing to the archive hash.
**Note:** 1 event/day = 36,500 events over 100 years. Realistically not a problem.

### 7. Algorithm obsolescence
**Impact:** SHA-256 or Ed25519 broken by quantum computers.
**Mitigation:** Migration path documented above. Post-quantum algorithms (ML-DSA/Dilithium) are standardized. The `migration` event type exists specifically for this.
**Timeline:** NIST estimates SHA-256 remains safe through 2030s+. Ed25519 is the weaker link (vulnerable to sufficiently large quantum computers). Monitor NIST PQC guidance.

### 8. Software loss
**Impact:** Can't run `psmc.py` in 2046.
**Mitigation:** The code is <500 lines of Python. The format is documented in `README.txt`. A competent programmer can rewrite verification in any language in a day. The data is just JSON lines — `cat` and `jq` work fine.

---

## AI CLI Integration

This vault is designed for use by AI coding tools:

```bash
# AI agents can append programmatically:
python psmc.py append --type note --data '{"content":"AI-generated insight","source":"claude"}'

# Or read the log for context:
python psmc.py show --last 20 --type decision

# Verify before trusting the log:
python psmc.py verify
```

The JSON-in, JSON-out design means any tool that can shell out and parse JSON can interact with the vault. No API server needed.

---

## Quick Start

```bash
pip install cryptography
cd tools/psmc
python psmc.py init
python psmc.py seed          # populate example entries
python psmc.py verify -v     # confirm integrity
python psmc.py show          # browse all events
python psmc.py digest        # generate weekly summary
```

Total code: ~480 lines of Python. Single dependency. No database. No cloud. No blockchain. Readable in 2046.
