# Show HN Launch Content

**Date:** 2026-02-18  
**Target:** news.ycombinator.com  
**Author:** Provara Team

---

## Title Options (Pick 3)

### Option 1 (Recommended)
**Show HN: Provara – Cryptographic event logs for AI agent memory**

Why this works:
- Clear "Show HN" prefix
- Technical description
- Mentions AI (timely) without being hypey

### Option 2
**Show HN: Provara – Tamper-evident audit trails for distributed systems**

Why this works:
- Appeals to security/infrastructure crowd
- "Tamper-evident" is a strong technical differentiator
- Broader than just AI

### Option 3
**Show HN: Provara – Append-only cryptographic logs with 50-year readability**

Why this works:
- "50-year readability" is a unique hook
- Technical audience appreciates long-term thinking
- Differentiates from blockchain solutions

---

## Post Body (Max 300 Words)

**What it is:** Provara is a protocol for append-only cryptographic event logs—think of it as a tamper-evident audit trail that any AI agent or distributed system can use for verifiable memory.

**The problem:** AI agents store memory in databases controlled by vendors, logs that can be silently modified, or proprietary formats that become unreadable when companies fail. Your agent's memory depends on the continued existence and good faith of specific organizations.

**How it works:** Every event is signed with Ed25519, linked via SHA-256 hash chains, and integrity-verified via Merkle trees. Events are stored as plain text NDJSON—open them with any text editor in 2076. The protocol uses RFC 8785 canonical JSON for cross-platform determinism, so the same event log produces byte-identical state on any machine.

**What's technically interesting:**
- Per-actor causal chains (not global ordering like blockchain)
- Streaming reducer processes 51K events/second with bounded memory
- Crypto-shredding for GDPR Article 17 compliance (encrypt at write, destroy key to erase)
- Three implementations (Python, Rust, TypeScript) validated against cross-language test vectors
- IETF Internet-Draft submitted for standards track

**Try it:**
```bash
pip install provara-protocol
provara init my-vault
provara append my-vault --type OBSERVATION --data '{"key":"value"}'
provara verify my-vault
```

**Links:**
- [GitHub](https://github.com/provara-protocol/provara)
- [PyPI](https://pypi.org/project/provara-protocol/)
- [Browser Playground](https://provara-protocol.github.io/provara/)
- [IETF Internet-Draft](https://datatracker.ietf.org/doc/draft-hunt-provara-protocol/)

Happy to answer questions about the protocol design, cryptographic choices, or performance tradeoffs!

---

## Comments to Seed Discussion

### Comment 1: Performance Numbers

> For those asking about performance:
> 
> - Vault creation: 171K events/second
> - Chain verification: 188K events/second  
> - Streaming reducer: 51K events/second (bounded at 56MB memory)
> - Checkpoint resume: 1.7-2.0x speedup over full replay
> 
> Benchmarks run on AMD Ryzen 7 7700X, Python 3.12. Full results in `tools/benchmarks/results.json`.
> 
> The streaming reducer (v1) is 80x faster than the full reducer (v0) at 100K events—happy to explain the optimization if anyone's interested.

### Comment 2: Why Not Blockchain

> This comes up a lot! Provara is closer to git than Bitcoin:
> 
> - No consensus mechanism (per-actor chains, not global ordering)
> - No tokens or mining
> - No energy cost
> - Faster by orders of magnitude (171K events/s vs Bitcoin's 7 tx/s)
> 
> The hash chain provides tamper evidence without the overhead of decentralized consensus. If you control the vault, you don't need proof-of-work.

### Comment 3: GDPR Compliance

> For the privacy folks: Provara supports crypto-shredding for GDPR Article 17.
> 
> Events are encrypted with AES-256-GCM at write time. To "erase" data, you destroy the encryption key. The ciphertext remains in the log (preserving hash chain integrity), but the content is cryptographically unrecoverable.
> 
> Spec is in `docs/CRYPTO_SHREDDING.md`. This is the same approach as VCP (draft-kamimura-scitt-vcp-01).

---

## Follow-up Actions

1. **Post at 11:30 AM PT** — Optimal HN traffic
2. **Monitor for 4 hours** — Respond to comments quickly
3. **Pin top comment** — Performance numbers or FAQ
4. **Update post** — Add links to any relevant discussions

---

*This launch content is part of Provara v1.0. For media inquiries, contact press@provara.dev.*
