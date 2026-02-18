# Twitter/X Launch Thread

**Date:** 2026-02-18  
**Platform:** Twitter/X (also adapts to Mastodon, LinkedIn)  
**Character limit:** 280 characters per tweet

---

## Thread (10 Tweets)

### Tweet 1: Announcement + Link

🚀 Introducing Provara: Cryptographic event logs for AI agent memory.

Your AI agent's memory shouldn't depend on any company surviving or any server staying online. Provara provides tamper-evident, append-only event logs with 50-year readability.

Try it: https://provara-protocol.github.io/provara/

---

### Tweet 2: Problem Statement

The problem: AI agents store memory in databases controlled by vendors, logs that can be silently modified, or proprietary formats that become unreadable.

Your agent's memory depends on the continued existence and good faith of specific organizations.

That's a single point of failure.

---

### Tweet 3: How It Works (with Diagram Description)

How it works:

Every event is signed with Ed25519, linked via SHA-256 hash chains, and sealed with Merkle trees.

[Diagram: Event → Ed25519 Sign → SHA-256 Hash Chain → Merkle Root → Verification]

Events are stored as plain text NDJSON—open them with any text editor in 2076.

---

### Tweet 4: MCP Integration Angle

🤖 AI agents can use Provara via the Model Context Protocol (MCP).

Add to your claude_desktop_config.json:
```json
{
  "mcpServers": {
    "provara": {
      "command": "python",
      "args": ["-m", "provara.mcp"]
    }
  }
}
```

Now Claude has cryptographically verified memory. Every interaction is signed and tamper-evident.

---

### Tweet 5: GDPR Compliance Angle

🇪🇺 GDPR Article 17 (Right to Erasure) vs append-only logs?

Provara uses crypto-shredding:
1. Encrypt events with AES-256-GCM at write time
2. To erase, destroy the encryption key
3. Ciphertext remains (preserving hash chain)
4. Content is cryptographically unrecoverable

Same approach as IETF SCITT VCP.

---

### Tweet 6: Performance Numbers

⚡ Performance (AMD Ryzen 7 7700X, Python 3.12):

- Vault creation: 171K events/second
- Chain verification: 188K events/second
- Streaming reducer: 51K events/second (bounded at 56MB memory)
- Checkpoint resume: 1.7-2.0x speedup

Full benchmarks: https://github.com/provara-protocol/provara/tree/main/tools/benchmarks

---

### Tweet 7: Three Implementations

🌐 Three implementations, one protocol:

- Python: v1.0.0 (reference, 495 tests)
- Rust: Complete (20 tests)
- TypeScript: Complete (browser playground)

All validated against cross-language test vectors. Same event log → byte-identical state hash on any machine.

Reimplement in your language!

---

### Tweet 8: Playground Link

🎮 Try it in your browser:

https://provara-protocol.github.io/provara/

Zero install. Runs entirely client-side via WebCrypto. Create vaults, append events, verify chains—no data leaves your machine.

Self-sovereign means self-hosted, even in the browser.

---

### Tweet 9: IETF Submission Note

📜 IETF Internet-Draft submitted:

draft-hunt-provara-protocol-00

"Provara: A Self-Sovereign Cryptographic Event Log Protocol"

Even if it doesn't become an RFC, the I-D process forces spec clarity and gives the standards community visibility.

Read it: https://datatracker.ietf.org/doc/draft-hunt-provara-protocol/

---

### Tweet 10: Call to Action

👋 We'd love your feedback!

- Star the repo: https://github.com/provara-protocol/provara
- Read the spec: https://provara-protocol.github.io/provara/
- Try the playground: https://provara-protocol.github.io/provara/
- Install: `pip install provara-protocol`

Questions? Drop them below or open an issue. RTs appreciated! 🙏

---

## Hashtags

Use 2-3 per tweet max:

- #AI
- #Cryptography
- #OpenSource
- #MCP
- #GDPR
- #ShowHN (on launch day)

---

## Visual Assets

### Tweet 3 Diagram

Create a simple ASCII or graphic:

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Event     │ ──→ │ Ed25519 Sign │ ──→ │ SHA-256     │
│  (JSON)     │     │  (Signature) │     │ Hash Chain  │
└─────────────┘     └──────────────┘     └─────────────┘
                                                 │
                                                 ↓
                                        ┌──────────────┐
                                        │  Merkle Root │
                                        │  (Integrity) │
                                        └──────────────┘
```

### Tweet 6 Performance Chart

Bar chart showing throughput:
- Vault creation: ████████████████████ 171K/s
- Chain verification: █████████████████████ 188K/s
- Streaming reducer: ██████ 51K/s

### Tweet 8 Screenshot

Screenshot of the playground in action:
- Browser window showing vault creation
- Event appended with signature visible
- Verification status "PASS"

---

## Posting Schedule

| Tweet | Time (PT) | Notes |
|-------|-----------|-------|
| 1-3 | 11:30 AM | Initial announcement |
| 4-6 | 11:35 AM | Technical deep dive |
| 7-10 | 11:40 AM | Community + CTA |

Space tweets 1-2 minutes apart for maximum visibility.

---

## Engagement Strategy

1. **Reply to all comments** in first 2 hours
2. **Quote tweet** with additional context if needed
3. **Pin the thread** to your profile
4. **Retweet** positive responses
5. **Follow up** with a "thank you" thread after 24 hours

---

*This thread is part of Provara v1.0 launch content. For media inquiries, contact press@provara.dev.*
