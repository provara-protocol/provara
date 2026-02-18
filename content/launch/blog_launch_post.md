# Introducing Provara: Why Your AI Agent's Memory Needs Cryptographic Proof

**Published:** 2026-02-18  
**Author:** Provara Team  
**Reading time:** 5 minutes

---

## The Problem

Your AI agent's memory is stored in a database controlled by a vendor, logs that can be silently modified, or proprietary formats that become unreadable when companies fail. This creates a fundamental vulnerability: the record of your agent's behavior depends on the continued existence and good faith of specific organizations.

What happens when that vendor goes out of business? What if an employee modifies the logs? What if you need to prove what your agent did (or didn't do) in a legal proceeding?

Today, we're introducing Provara—a protocol for self-sovereign cryptographic event logs that solve these problems.

---

## What is Provara?

Provara is an append-only, cryptographically signed event log that anyone can verify and no one can silently rewrite. It preserves memory as evidence: signed observations that can be replayed into state, audited independently, and stored in plain files for 50-year readability.

Think of it as a tamper-evident audit trail for AI agents, distributed systems, or any application requiring accountable records.

---

## How It Works

Every event in Provara is:

1. **Signed with Ed25519** — Each event is cryptographically signed by its author, providing non-repudiation.
2. **Linked via SHA-256 hash chains** — Events form a per-actor causal chain. Any modification breaks the chain.
3. **Sealed with Merkle trees** — A Merkle root over all vault files provides integrity verification.
4. **Stored as plain text NDJSON** — Open your event log with any text editor. It will be readable in 2076.

Here's what an event looks like:

```json
{
  "event_id": "evt_a1b2c3d4e5f6789012345678",
  "type": "OBSERVATION",
  "actor": "alice",
  "timestamp_utc": "2026-02-18T12:00:00Z",
  "payload": {
    "observation": "System initialized",
    "confidence": 0.95
  },
  "prev_event_hash": null,
  "signature": "MEUCIQDv...64-byte-Base64...AA==",
  "public_key": "MCowBQYDK2VwAyEAg...32-byte-Base64...==",
  "key_id": "bp1_27a6549d43046062"
}
```

The `prev_event_hash` field links each event to the actor's previous event, forming a per-actor linked list. Unlike blockchains that enforce global ordering, Provara maintains separate chains per actor—enabling concurrency without coordination.

---

## Getting Started

Install Provara:

```bash
pip install provara-protocol
```

Create a vault:

```bash
provara init my-vault
```

Append a signed event:

```bash
provara append my-vault \
  --type OBSERVATION \
  --data '{"event":"test"}' \
  --keyfile my-vault/identity/private_keys.json
```

Verify integrity:

```bash
provara verify my-vault
```

Output:

```
Verifying vault integrity: /path/to/my-vault
PASS: All 17 integrity checks passed.
```

---

## Key Features

### Tamper-Evident

Any modification to the record is cryptographically detectable. Change a single bit, and the hash chain breaks, the Merkle root mismatches, and the signature fails verification.

### Self-Sovereign

No accounts, no internet required, no vendor lock-in. Your identity lives in your files, not on a server.

### 50-Year Readability

JSON, SHA-256, and Ed25519 are industry standards that will remain readable for decades. No proprietary formats, no phone-home, no telemetry.

### GDPR Compliant

Provara supports crypto-shredding for GDPR Article 17 (Right to Erasure). Events are encrypted with AES-256-GCM at write time. To erase, destroy the encryption key. The ciphertext remains (preserving hash chain integrity), but the content is cryptographically unrecoverable.

### MCP Integration

AI agents can use Provara via the Model Context Protocol (MCP). Add to your `claude_desktop_config.json`:

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

Now Claude has cryptographically verified memory. Every interaction is signed and tamper-evident.

---

## Performance

Benchmarks (AMD Ryzen 7 7700X, Python 3.12):

| Operation | Events | Time | Throughput |
|-----------|--------|------|------------|
| Vault creation | 100K | 0.58s | 171K events/s |
| Chain verification | 100K | 0.53s | 188K events/s |
| Streaming reducer | 100K | 1.96s | 51K events/s |

The streaming reducer processes 51,000 events per second with bounded memory (56MB). Checkpoint resume provides 1.7-2.0x speedup over full replay.

---

## Three Implementations

Provara is implemented in three languages:

- **Python:** v1.0.0 (reference, 495 tests)
- **Rust:** Complete (20 tests)
- **TypeScript:** Complete (browser playground)

All three implementations are validated against cross-language test vectors. The same event log produces byte-identical state hash on any machine.

---

## Standards Track

We've submitted an IETF Internet-Draft:

**draft-hunt-provara-protocol-00** — "Provara: A Self-Sovereign Cryptographic Event Log Protocol"

Even if it doesn't become an RFC, the I-D process forces spec clarity and gives the standards community visibility. Read it at https://datatracker.ietf.org/doc/draft-hunt-provara-protocol/.

---

## Try It Now

**Browser Playground:** https://provara-protocol.github.io/provara/

Zero install. Runs entirely client-side via WebCrypto. Create vaults, append events, verify chains—no data leaves your machine.

**GitHub:** https://github.com/provara-protocol/provara

**PyPI:** https://pypi.org/project/provara-protocol/

---

## What's Next

- **Post-quantum migration:** Adding ML-DSA dual-signing for quantum resistance (2027)
- **Multi-sig vaults:** Threshold signatures for high-security deployments
- **Hardware security module integration:** Native YubiKey/HSM support
- **Streaming sync:** Real-time multi-device synchronization

---

## Acknowledgments

Provara builds on decades of cryptographic research. We're grateful to the authors of RFC 8785 (JSON Canonicalization), RFC 8032 (Ed25519), FIPS 180-4 (SHA-256), and the IETF SCITT working group.

The protocol is available under Apache 2.0. We invite the community to audit, extend, and reimplement it.

---

**Questions?** Open a GitHub issue or join the discussion on Hacker News.

**Security issues?** Email security@provara.dev (not public issues).

**Want to contribute?** Read our [CONTRIBUTING.md](https://github.com/provara-protocol/provara/blob/main/CONTRIBUTING.md).

---

*Provara v1.0.1 — Self-sovereign cryptographic event logs.*
