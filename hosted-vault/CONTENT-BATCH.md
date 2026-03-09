# Content Batch — Provara Hosted Vault Launch

**Created:** 2026-03-07  
**Target:** 4 pieces from 1 build  
**Time Box:** 2 hours

---

## 📹 Piece 1: YouTube Video (45 min)

**Title:** I Built Tamper-Evident Memory for AI Agents  
**Length:** 8-12 min  
**Thumbnail:** Vault icon + "AI Audit Trails" text

### Script Outline

**[0:00-0:30] Hook**
> "Your AI agent just made a decision that cost a client $50K. How do you prove what it knew, when it knew it, and why it acted? That's what I built."

**[0:30-2:00] The Problem**
- AI agents make decisions
- Those decisions need audit trails (EU AI Act, liability, debugging)
- Current solutions: databases (mutable), vector stores (no integrity), blockchains (overkill)
- What's missing: cryptographic proof without the complexity

**[2:00-4:00] What is Provara?**
- Append-only event log
- Every event signed (Ed25519) + hashed (SHA-256)
- Tamper-evident: change one byte, break the chain
- Built on file-first principles (readable in 50 years)
- MCP server for AI agents to write memory

**[4:00-7:00] Live Demo**
```bash
# Create vault
curl -X POST https://api.provara.app/api/v1/vaults \
  -H "Authorization: Bearer <token>" \
  -d '{"name": "my-agent"}'

# Append event
curl -X POST https://api.provara.app/api/v1/vaults/:id/events \
  -d '{"event_type": "decision", "data": {"action": "reject_loan", "confidence": 0.94}}'

# Verify integrity
curl https://api.provara.app/api/v1/vaults/:id/events?action=verify
```

**[7:00-9:00] Why This Matters**
- EU AI Act requires audit trails (Article 12)
- High-stakes AI needs accountability
- Your future self needs to know what happened
- Sovereignty: export your data anytime, no lock-in

**[9:00-10:00] CTA**
> "If you're building AI systems that need accountable memory, join the waitlist at provara.app. Free tier gets you started. Link in description."

### Description Template
```
Provara Hosted Vault — Tamper-evident event logging for AI agents.

🔐 Get Early Access: https://provara.app
📚 Docs: https://provara.dev/docs
💻 GitHub: https://github.com/provara-protocol/provara

Timestamps:
0:00 The Problem
2:00 What is Provara?
4:00 Live Demo
7:00 Why This Matters
9:00 Get Started

#AI #AIGovernance #Crypto #OpenSource
```

---

## 📝 Piece 2: Substack Post (30 min)

**Title:** Why I Built a Tamper-Evident Vault for AI Agents  
**Subtitle:** Cryptographic memory isn't optional anymore — it's infrastructure  
**Reading Time:** 5 min

---

**Body:**

Last week I finished something I've been thinking about for two years: Provara Hosted Vault.

It's a simple idea with uncomfortable implications.

### The Idea

AI agents make decisions. Those decisions should be:
1. **Logged** — what happened, when, and why
2. **Tamper-evident** — you can't quietly change the story
3. **Verifiable** — anyone can check the integrity
4. **Portable** — you own the data, not the platform

Provara does this with three cryptographic primitives:
- Ed25519 signatures (who wrote this)
- SHA-256 hash chains (what came before)
- RFC 8785 canonical JSON (deterministic encoding)

The result: an append-only event log where changing a single byte breaks the entire chain. You can't fake history. You can't erase mistakes. You can only add corrections — which are themselves logged.

### Why I Built It

Three reasons:

**1. Regulatory reality**  
The EU AI Act goes into effect soon. Article 12 requires "records of the development process" and "logs of high-risk AI systems." Provara makes compliance automatic — not a bolt-on audit tool, but the actual data layer.

**2. Debugging at scale**  
When your agent does something weird at 3 AM, you need to know: what did it observe, what did it believe, what decision did it make? Not "the agent said X" but "the agent signed Y at timestamp Z with confidence 0.87."

**3. Sovereignty**  
Your cognitive continuity shouldn't depend on a company surviving, a server staying online, or a platform deciding to keep your data. Provara vaults are UTF-8 directories. Open them with a text editor in 2076.

### The Architecture

I made specific choices:

| Choice | Why |
|--------|-----|
| Files over databases | Databases rot. Files are forever. |
| Ed25519 over RSA | Faster, smaller keys, no known weaknesses |
| Vercel + Supabase | Zero ops, scales automatically |
| Free tier | Remove friction for developers |

### What's Next

The protocol is done. The hosted service is built. Now I need:

1. **Early users** — people building AI systems who want accountable memory
2. **Case studies** — real deployments with real constraints
3. **Compliance mappings** — EU AI Act, ISO 42001, NIST AI RMF

If that's you, or you know someone building AI systems that need audit trails:

→ Join the waitlist at [provara.app](https://provara.app)

Free tier: 100 events/month, no credit card.

---

*Chase builds AI infrastructure at Hunt Information Systems LLC. He tweets at @syncshadow7.*

---

## 🐦 Piece 3: Twitter/LinkedIn Thread (15 min)

**Platform:** Twitter (adapt for LinkedIn)  
**Length:** 8-10 tweets

---

**Tweet 1/8**
I built tamper-evident memory for AI agents.

Your AI makes decisions. Those decisions need audit trails — not just logs, but cryptographic proof of what happened, when, and why.

Here's what I learned building Provara Hosted Vault 🧵

**Tweet 2/8**
The problem:

AI agents are going into production. They're making loan decisions, medical triage, legal research.

When something goes wrong, how do you prove:
- What the agent observed?
- What it believed?
- Why it acted?

Current answer: vibes.

**Tweet 3/8**
What's needed:

1. Append-only logs (can't erase mistakes)
2. Cryptographic signatures (can't fake authorship)
3. Hash chains (can't insert fake history)
4. Export capability (no vendor lock-in)

This isn't "nice to have." EU AI Act requires it.

**Tweet 4/8**
The architecture:

Every event is:
- Signed with Ed25519 (who wrote it)
- Hashed with SHA-256 (what it contains)
- Chained to previous event (what came before)

Change one byte → break the entire chain.

Tamper-evidence by design.

**Tweet 5/8**
The stack:

- Vercel (serverless API)
- Supabase (Postgres + Storage)
- Clerk (JWT auth)
- Stripe (billing)

Deploy time: ~45 minutes.
Cost at scale: ~$70/mo + transaction fees.

Zero ops. Scales automatically.

**Tweet 6/8**
The pricing:

Free: 100 events/month
Developer: $29/mo (10K events)
Team: $99/mo (100K events)

Free tier is intentional. Remove friction. Let developers try it. Charge when it's mission-critical.

**Tweet 7/8**
What's next:

- Early users (join waitlist)
- Case studies (real deployments)
- Compliance mappings (EU AI Act, ISO 42001)

This is infrastructure. It needs to work for 50+ years.

**Tweet 8/8**
Try it:

→ provara.app (waitlist)
→ github.com/provara-protocol/provara (open source)

Built on cryptographic first principles. Files over databases. Sovereignty over convenience.

Questions? Drop them below. 👇

---

## 📰 Piece 4: Hacker News Show Post (10 min)

**Title:** Show HN: Provara – Tamper-evident event logging for AI agents (no blockchain)  
**URL:** https://provara.app  
**Comments:** (seed with technical details)

---

**Comment to post after submission:**

Hey HN! Chase here, builder of Provara.

A few technical details for the curious:

**What it does:** Append-only event log with Ed25519 signatures and SHA-256 hash chains. Every event is cryptographically signed and linked to its predecessor. Change one byte, break the chain.

**Why it exists:** AI agents need accountable memory. When your agent makes a high-stakes decision, you need to prove what it knew, when it knew it, and why it acted. Databases are mutable. Vector stores have no integrity. Blockchains are overkill. Provara is the middle ground.

**Architecture:**
- Python core (single dependency: `cryptography`)
- Vercel serverless API
- Supabase Postgres + Storage
- Clerk for JWT auth
- Stripe for billing

**Design constraints:**
1. Single external dependency (cryptography library)
2. UTF-8 plaintext events (readable with `cat` in 50 years)
3. No infrastructure required (files on disk)
4. Export anytime (no vendor lock-in)

**Compliance angle:** EU AI Act Article 12 requires audit trails for high-risk AI. Provara makes this automatic — not a bolt-on tool, but the actual data layer.

Happy to answer questions about:
- Cryptographic design choices
- Protocol spec (it's like git + Sigstore had a file-first child)
- AI governance use cases
- Why I didn't use SQLite / Git / blockchain

---

## ⏰ Publishing Schedule

| Piece | Platform | When |
|-------|----------|------|
| Substack | Email + web | Monday 8am ET |
| YouTube | Video | Monday 12pm ET |
| Twitter/LinkedIn | Thread | Monday 2pm ET |
| Hacker News | Show HN | Tuesday 8am ET |

**Cross-promotion:**
- Substack links to YouTube
- YouTube description links to Substack + waitlist
- Twitter thread links to both
- HN post = waitlist + GitHub

---

## 📊 Success Metrics (Week 1)

| Metric | Target |
|--------|--------|
| Waitlist signups | 50 |
| GitHub stars | 100 |
| YouTube views | 500 |
| Substack subscribers | 30 |
| HN upvotes | 100+ |
| Early user conversations | 5 |

---

*Content batch template v0.1 | 2026-03-07*
