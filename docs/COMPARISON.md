# Provara vs. Alternative Approaches

**Honest comparison of Provara against Git, Blockchain, EventStore, and Sigstore.**

Each tool solves a subset of the same problem: "How do I maintain a verifiable record of events?" But they optimize for different use cases.

---

## Comparison Matrix

| Feature | Provara | Git | Blockchain | EventStore | Sigstore/CT |
|---------|---------|-----|------------|------------|-------------|
| **Primary use case** | AI agent memory, dispute resolution | Source code versioning | Decentralized consensus | Event sourcing (CQRS) | Code transparency, supply chain |
| **Data model** | Append-only NDJSON events | Snapshots + deltas (trees) | Append-only transaction log | Append-only event stream | Append-only certificate log |
| **Integrity** | SHA-256 hash chains + Ed25519 signatures | SHA-1/SHA-256 hash chains | Merkle trees + consensus | Checksums (optional) | Merkle trees + SCT signatures |
| **Non-repudiation** | ✅ Ed25519 per-event signatures | ❌ Committer identity is not cryptographically verified | ✅ Account-based signatures | ❌ Optional, not core | ✅ Signed certificate timestamps |
| **Conflict detection** | ✅ Automatic (contested namespace) | ⚠️ Manual merge resolution | ❌ Consensus prevents conflicts | ❌ Last-write-wins or application logic | ❌ Not applicable |
| **Dispute resolution** | ✅ Attestation events, epistemic hierarchy | ❌ Not supported | ⚠️ Fork choice rules (not semantic) | ❌ Application-specific | ❌ Not applicable |
| **Deterministic state** | ✅ Reducer produces identical state_hash | ❌ Working tree is not deterministic | ✅ State root is deterministic | ❌ Projections are application-specific | ❌ Not applicable |
| **Temporal anchoring** | ✅ RFC 3161 TSA, L2 blockchain | ❌ System clock (untrusted) | ✅ Block timestamps (consensus) | ❌ System clock | ✅ SCT timestamps (trusted) |
| **Query capability** | ⚠️ Full replay or checkpoint | ✅ Fast tree traversal | ⚠️ Full replay or index | ✅ Native query engine | ⚠️ Binary search (Merkle path) |
| **Storage format** | NDJSON (50-year readability) | Packfiles (binary, compressed) | Varies (often binary) | Binary or JSON | Binary (Merkle tree) |
| **Dependencies** | 1 (`cryptography`) | Many (C, zlib, etc.) | Many (consensus, crypto, networking) | Many (database, serialization) | Many (crypto, ASN.1, HTTP) |
| **Offline-first** | ✅ Designed for disconnected operation | ✅ Fully offline | ❌ Requires network/consensus | ⚠️ Possible but not optimized | ❌ Requires network (SCT) |
| **Multi-actor** | ✅ Per-actor causal chains, key registry | ⚠️ Single-author branches | ✅ Account-based | ⚠️ Application-specific | ❌ Single-issuer model |
| **Legal admissibility** | ✅ RFC 3161 + signatures | ⚠️ Weak (clock spoofing) | ✅ Consensus timestamps | ❌ Application-specific | ✅ SCT + Merkle audit paths |

---

## Deep Dive: Each Alternative

### Git

**What Git does well:**
- Branching and merging (three-way merge, rebase)
- Deltas and compression (packfiles)
- Fast history traversal (commit graph)
- Massive ecosystem (GitHub, GitLab, tooling)

**Where Git falls short for Provara use cases:**
- **Identity is not cryptographic:** `git commit --author="alice@example.com"` is not signed by default. Even with GPG, verification is optional and not enforced.
- **History rewriting:** `git rebase`, `git commit --amend`, and `git push --force` break the append-only guarantee. Provara events are permanent.
- **No conflict semantics:** Git detects merge conflicts syntactically (same line, different content). Provara detects *semantic* conflicts (same subject:predicate, different value) and provides a resolution mechanism (attestation).
- **Clock spoofing:** Commit timestamps are system time. Provara anchors to RFC 3161 TSAs for independent temporal proof.

**When to use Git:**
- Source code versioning (obviously)
- Configuration files, documentation
- Any workflow where history rewriting is acceptable

**When to use Provara instead:**
- Audit logs that must be immutable
- Multi-agent systems with dispute resolution
- Legal evidence chains requiring non-repudiation
- AI agent memory with verifiable integrity

---

### Blockchain (Ethereum, Base, etc.)

**What Blockchain does well:**
- Decentralized consensus (no trusted party)
- Public verifiability (anyone can verify the chain)
- Smart contracts (programmable state transitions)
- Native economic incentives (staking, slashing)

**Where Blockchain falls short for Provara use cases:**
- **Consensus overhead:** Every node must agree on every transaction. Provara is single-authority (or multi-authority with explicit trust) — no consensus needed.
- **Cost:** Every write costs gas ($0.001–$10+ depending on L2/L1). Provara writes are free (local storage).
- **Throughput:** L1: ~15 TPS (Ethereum). L2: ~100–1000 TPS. Provara: ~10,000+ events/second (local SSD).
- **Privacy:** Public blockchains expose all data. Provara vaults are private by default (local files).
- **Complexity:** Running a node, managing gas, key management at scale. Provara: `pip install provara-protocol`.

**When to use Blockchain:**
- Decentralized applications (no trusted operator)
- Token transfers, DeFi, NFTs
- Public accountability (anyone can audit)

**When to use Provara instead:**
- Private audit logs (enterprise, legal)
- AI agent memory (high throughput, low latency)
- Multi-actor systems with known participants
- Cost-sensitive applications (no gas fees)

**Hybrid approach:**
Use Provara for high-throughput event logging, then periodically anchor the Merkle root to an L2 blockchain. Best of both worlds: fast, private, cheap + public, immutable, timestamped.

---

### EventStore (Event Sourcing Databases)

**What EventStore does well:**
- High-performance event storage (millions of events/second)
- Projections (real-time derived views)
- Stream subscriptions (push-based event processing)
- Built-in query language (SQL-like)

**Where EventStore falls short for Provara use cases:**
- **No cryptographic integrity:** Checksums are optional and not end-to-end. Provara verifies every event signature and hash chain.
- **No non-repudiation:** Events are not signed by the actor. Provara requires Ed25519 signatures.
- **Vendor lock-in:** EventStoreDB is a proprietary database. Provara is NDJSON files (readable in 50 years with any text editor).
- **No dispute resolution:** Conflicts are application-specific. Provara has built-in conflict detection (contested namespace) and resolution (attestation).

**When to use EventStore:**
- CQRS/ES architectures (command/query separation)
- High-throughput event streaming
- Real-time dashboards, projections

**When to use Provara instead:**
- Tamper-evident audit logs
- Legal/regulatory compliance (non-repudiation)
- Multi-actor systems with disputes
- Long-term archival (50-year readability)

---

### Sigstore / Certificate Transparency

**What Sigstore/CT does well:**
- Code signing transparency (detect misissued certificates)
- Supply chain integrity (verify build artifacts)
- Public audit log (Merkle tree, anyone can verify)
- Short-lived signing keys (no long-term key management)

**Where Sigstore/CT falls short for Provara use cases:**
- **Narrow scope:** Designed for code signing, not general event logging.
- **No state machine:** CT logs certificates, but there's no reducer producing derived state. Provara's reducer produces canonical/local/contested/archived namespaces.
- **No dispute resolution:** CT doesn't handle conflicting claims. Provara has attestation-based resolution.
- **Public only:** CT logs are public. Provara vaults can be private.

**When to use Sigstore/CT:**
- Code signing transparency
- Supply chain integrity (SLSA, in-toto)
- Certificate audit logs

**When to use Provara instead:**
- General-purpose event logging
- Multi-actor dispute resolution
- Private vaults (enterprise, legal)
- AI agent memory

---

## Decision Tree: When to Use Provara

```
Do you need to maintain a verifiable record of events?
│
├─ No → Use a regular database (PostgreSQL, SQLite)
│
└─ Yes
   │
   ├─ Is the data source code?
   │  └─ Yes → Use Git
   │
   ├─ Do you need decentralized consensus (no trusted party)?
   │  ├─ Yes → Use Blockchain (Ethereum, Base)
   │  │
   │  └─ No (you trust the operator or participants)
   │     │
   │     ├─ Is it for code signing / supply chain?
   │     │  └─ Yes → Use Sigstore / Certificate Transparency
   │     │
   │     ├─ Do you need high-throughput event streaming with projections?
   │     │  ├─ Yes → Use EventStore (but add Provara for integrity)
   │     │  │
   │     │  └─ No
   │     │     │
   │     │     ├─ Do you need tamper-evidence + non-repudiation?
   │     │     │  ├─ Yes → Use Provara ✅
   │     │     │  │
   │     │     │  └─ No → Use a regular database
   │     │     │
   │     │     └─ Do you need multi-actor dispute resolution?
   │     │        ├─ Yes → Use Provara ✅
   │     │        │
   │     │        └─ No → Use a regular database
   │     │
   │     └─ Do you need AI agent memory with verifiable integrity?
   │        └─ Yes → Use Provara ✅
   │
   └─ Is it for legal/regulatory compliance?
      └─ Yes → Use Provara (with RFC 3161 anchoring) ✅
```

---

## Honest Tradeoffs

**What Provara does NOT do well:**

1. **Branching/Merging:** Git's three-way merge is far more sophisticated. Provara sync is union-merge with conflict detection — not suitable for code.

2. **Query Performance:** EventStore has a native query engine. Provara requires full replay or external indexing (SQLite sidecar).

3. **Decentralization:** Provara assumes trusted actors (signed events). It does not solve Byzantine consensus like blockchain.

4. **Compression:** Git packfiles are highly compressed. Provara NDJSON is verbose (intentionally — 50-year readability).

5. **Ecosystem:** Git has 15+ years of tooling. Provara is new. You're early.

---

## Summary

| Use Case | Best Choice |
|----------|-------------|
| Source code versioning | Git |
| Decentralized apps (no trusted party) | Blockchain |
| High-throughput event streaming | EventStore |
| Code signing transparency | Sigstore/CT |
| **Tamper-evident audit logs** | **Provara** |
| **Multi-actor dispute resolution** | **Provara** |
| **AI agent verifiable memory** | **Provara** |
| **Legal evidence chains** | **Provara** |
| **Long-term archival (50 years)** | **Provara** |

---

**Next:** Read the [Provara Protocol Spec](BACKPACK_PROTOCOL_v1.0.md) for technical details.
