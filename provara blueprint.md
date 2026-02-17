# PROVARA PROTOCOL — THE ULTIMATE BLUEPRINT

**Provara · February 2026 · v1.0 FINAL**

*"Truth is not merged. Evidence is merged. Truth is recomputed."*

---

## 0. What This Document Is (and Isn't)

This blueprint synthesizes six prior drafts into one canonical strategy. Where the drafts disagreed, this document makes a decision and states it. Where they were vague, this document gets specific. Where they repeated each other, this document cuts. Read this. Burn the rest.

---

## 1. THE ONE-LINE THESIS

**Provara is the integrity layer for memory that outlives you.**

Not a database. Not a blockchain. Not "just logging." Provara is the cryptographic proof layer that makes *any* digital record tamper-evident, sovereign, and auditable for 50+ years — with zero infrastructure.

**The positioning line:**

> "Provara is what happens when Git history and Sigstore logs have a file-first, zero-infrastructure child — and it grows up to become the audit backbone for AI governance."

---

## 2. STRATEGIC POSITIONING — MAKE THE CATEGORY, DON'T JOIN ONE

### The Category: *Cryptographic Evidence Substrate*

Every prior draft compared Provara to Git, blockchains, event sourcing, and Sigstore. That's necessary but insufficient. The real strategic move is **category creation**:

Provara doesn't compete in "logging" or "version control" or "blockchain." It defines **sovereign evidence** — the ability to prove what happened, when, under which keys, without asking anyone's permission or running anyone's server.

### The Competitive Cheat Sheet

| Dimension | Git | Blockchain | EventStore/Axon | Sigstore/Rekor | **Provara** |
|---|---|---|---|---|---|
| **What it proves** | File change sequence | Global consensus on state | Application event order | Artifact signatures | **Belief evolution & decision provenance** |
| **Infra required** | Minimal | Nodes + gas + P2P | DB server | Hosted Merkle log | **None. Files on disk.** |
| **Mutability** | Rebase/force-push rewrites history | Immutable by consensus | Append-only (DB-enforced) | Append-only (server-enforced) | **Append-only by cryptographic chaining** |
| **Identity model** | SSH/GPG keys (optional, bolted on) | Wallet addresses | None built-in | Ephemeral OIDC certs | **Ed25519 key ladders with rotation** |
| **Fork detection** | Merge conflicts (manual) | N/A (consensus prevents) | N/A (single-writer) | N/A (centralized) | **Automatic causal fork detection** |
| **50-year readability** | Likely (but binary packfiles) | Uncertain (chain dependencies) | No (server dependency) | No (server dependency) | **Yes. UTF-8 JSON + cat/jq.** |
| **Offline-first** | Yes | No | No | No | **Yes** |

### The 30-Second "Why Not Git?" Rebuttal

"Git tracks file changes. Provara tracks beliefs. Git has no concept of cryptographic identity binding, event semantics, causal fork detection, key rotation, or deterministic state derivation. You wouldn't store an AI's decision history as Git diffs any more than you'd store a financial ledger as Git diffs."

Then show: two devices appending events offline → sync → fork detection → causal resolution. Git literally cannot do this.

### The Moat

**The moat is the spec, not the code.** If the canonical spec + compliance tests are widely adopted before a competitor enters, then competitors build *Provara-compatible implementations* rather than alternatives. This is the TCP/IP play. Own the standard. Let others build on it.

Three reinforcing layers:
1. **Spec + compliance tests** — low-friction conformance path creates network effects across languages
2. **Zero-infra portability** — vaults are UTF-8 directories, inspectable with `cat` and `jq`, archivable forever
3. **Single-dependency surface** — minimal supply chain risk makes Provara credible for high-assurance deployments

---

## 3. TECHNICAL ROADMAP

### Governing Constraints (Non-Negotiable)

These never change. Every feature proposal is tested against them:

1. **Single external dependency** (`cryptography`). No exceptions.
2. **Spec-first.** If the spec doesn't support it, change the spec first, then the code.
3. **File-first.** Any proposal requiring a server or DB is a separate project, not core.
4. **UTF-8 plaintext.** Events must be readable with `cat`, verifiable with commodity tools.
5. **Append-only.** The log is additive. Deletion is an event, not an erasure.

### Phase 0: Ship and Unblock (Months 0–3)

**Goal: Credibility.** A protocol nobody can use is a protocol nobody cares about.

| Priority | Deliverable | Definition of Done |
|---|---|---|
| P0 | CI/CD unblocked | GitHub Actions billing resolved, 12-job matrix green on every commit |
| P0 | `provara-protocol` v1.0.0 on PyPI | Stable release, not RC. pip install provara-protocol works. |
| P0 | `provara.dev` deployed | Cloudflare Pages. Three-tier docs: Protocol Spec / Python API / PSMC CLI |
| P1 | PROTOCOL_PROFILE.txt frozen | Normative spec, versioned, with explicit stability guarantees |
| P1 | Compliance test runner packaged | `provara-compliance` CLI, language-agnostic harness |
| P2 | Show HN post shipped | Tuesday/Wednesday 8–9am ET. "Show HN: Tamper-evident audit trails — no server, no blockchain, just signed JSON files." |

### Phase 1: Cross-Language Credibility (Months 3–6)

**Goal: Prove the protocol is real, not just Python.**

| Priority | Deliverable | Rationale |
|---|---|---|
| P0 | **Rust port** (`provara-rs`) passing all 17 compliance tests | Rust = performance baseline, FFI target for Go/TS/Python bindings, strong signal to security community |
| P1 | **Checkpoint system v1** | Signed snapshots: Merkle root + event index + reducer state digest. Stored as `checkpoints/NNNNNNNNNN.chk`. Replay from last verified checkpoint. Target: 100K events → sub-100ms load. |
| P1 | **PSMC CLI v1.1** | PSMC (Personal Sovereign Memory Container) is already integrated at `tools/psmc/` as the first Provara app layer — 480 LOC, 52 tests, imports Provara primitives. v1.1 adds: `--provara` flag for native event emission, reducer integration, checkpoint support. Polished, documented, demo-ready. |
| P2 | **TypeScript compliance tests** | Port the test suite first (not the implementation). This lets community contributors build the TS impl against a known target. |

**Decision point (resolved):** Rust before Go. Prior drafts disagreed. Rust is correct because: (a) Rust FFI enables Go/TS/Python bindings from a single codebase, (b) Rust has stronger traction in security/crypto communities, (c) a Rust core defines the performance ceiling. Go comes next in Phase 2.

### Phase 2: Integration Layer (Months 6–12)

**Goal: Make Provara trivially embeddable in AI systems and pipelines.**

| Priority | Deliverable | Rationale |
|---|---|---|
| P0 | **MCP Server v1** | Model Context Protocol server: `append_event`, `query_timeline`, `list_conflicts`, `snapshot_belief`, `export_digest`. Any MCP-compatible agent (Claude, GPT, local models) can write to a Provara vault. **This is the distribution hack.** |
| P0 | **TypeScript/Node SDK** | Wrap Rust core via N-API or WASM. Browser verification (read-only) + Node.js full implementation. Critical for developer tooling, VS Code extensions, agent UIs. |
| P1 | **Go port** | Cloud-native infra teams. Docker/K8s ecosystem. `provara-go` module passing compliance tests. |
| P1 | **Encryption at rest** (optional layer) | XChaCha20-Poly1305 envelope encryption using `cryptography` primitives (no new deps). Key management external. Rotation is append-only. Clear tradeoff docs: encrypted vaults break `cat`/`jq` inspection but preserve tamper evidence. |
| P2 | **Performance benchmarks published** | "Provara can verify 1M events in X seconds on a Raspberry Pi." Target: 100K events with checkpoint in <2s. Full 1M replay <60s streaming. |
| P2 | `provara-action` GitHub Action | Drop-in CI integration: verify vault integrity on every commit, append build events automatically. |

### Phase 3: Institutional Grade (Months 12–24)

**Goal: Make Provara a recognized primitive in governance and compliance.**

| Priority | Deliverable | Rationale |
|---|---|---|
| P0 | **Post-quantum dual-signing** | Ed25519 + ML-DSA (Dilithium). New events support multiple signatures. Authority ladder extended to PQ keys. "PQ upgrade" events cross-sign old→new. Published cryptographic longevity roadmap. |
| P0 | **Provara Compliance Toolkit** | Pre-built schemas for EU AI Act Article 12, ISO 42001 logging. Ready-made reducers that emit regulator-formatted reports. "AI Logging Readiness" assessment playbook. |
| P1 | **Formal verification sketch** | Collaborate with formal methods folks. Model core properties (append-only, fork detection, reducer determinism) in Tamarin or equivalent. Publish practitioner-oriented security proof sketch + threat model. |
| P1 | **Cross-vault anchoring** (optional) | Periodically anchor a vault's Merkle root into Rekor or another transparency log. Provara stays offline-first; anchoring is opt-in for high-assurance deployments. |
| P2 | **Rich query helpers** | Non-normative sidecar index files (SQLite or JSON). Tooling generates them; they're never part of the evidence chain. |
| P2 | **Provara Verify** web tool | Static site with WASM verifier. Upload a vault, get cryptographic verification results in-browser. Zero backend. |

---

## 4. PRODUCT & REVENUE — THE OPEN RAILROAD, PAID TRAINS MODEL

### The Philosophy

The protocol is the railroad — open, free, Apache 2.0, forever. Revenue comes from the trains: convenience, compliance packaging, SLAs, and consulting. PSMC (already shipped as `tools/psmc/`, 52 tests) validates this model: a 480-line personal vault CLI built entirely on Provara primitives, proving the protocol supports application layers without modification.

**Pricing principle:** Charge for *reduced regulatory and operational risk*, not for storage or events. "If an AI incident costs you millions in fines or reputation, a few thousand per month to make your logs provably immutable is cheap insurance."

### Three Customer Segments (Priority Order)

**Segment 1: AI Labs & Model Evaluation Teams**
- *Need:* Reproducible context, red-team logs, model evaluation provenance
- *Aha moment:* "We can prove to auditors that every high-risk AI decision is logged immutably with a cryptographic chain, and we can replay the system's belief state at any point."
- *Entry point:* MCP server integration → agent memory → audit artifacts

**Segment 2: Compliance & Governance Teams at Regulated Enterprises**
- *Need:* Immutable evidence for EU AI Act Article 12, ISO 42001, NIST AI RMF conformity assessments
- *Aha moment:* "We hand auditors a vault directory that proves training data lineage and evaluation logs. Our audit took 10 minutes."
- *Entry point:* Compliance consulting → Toolkit license → Enterprise support

**Segment 3: Sovereign Infrastructure Builders (The Long Tail)**
- *Need:* Personal/team audit trails, portable PSMC vaults, platform-lock-in-proof memory
- *Aha moment:* "My entire research archive is cryptographically linked in plain files. I can sync across machines and still detect any tampering."
- *Entry point:* PSMC CLI → word of mouth → community advocacy

### Free vs. Paid

**Open-source forever (Apache 2.0):**
- Core protocol spec + compliance tests
- Python, Rust, TypeScript, Go implementations
- PSMC CLI + base SDKs
- MCP server (self-hosted)

**Commercial (Months 9–24):**

| Tier | What | Price Range | Timeline |
|---|---|---|---|
| **Consulting** | Architecture review, integration design, compliance mapping | $5K–$50K/engagement | Month 3+ |
| **Enterprise Toolkit** | Governance schemas, SIEM connectors, compliance reducers, priority support, SLA | $2K–$10K/mo | Month 12+ |
| **Provara Verify** (hosted) | Managed verification mirror, long-term archival, organizational dashboards | $500–$2K/mo (SMB), $5K–$20K/mo (enterprise) | Month 18+ |
| **Certification & Training** | "Provara-Ready" vendor certification, engineer training courses | $1K–$5K/cert | Month 18+ |

### Revenue Trajectory

| Milestone | Target | How |
|---|---|---|
| **First dollar** (Month 3–4) | $5K–$10K | Fixed-fee consulting engagement with an AI governance or compliance vendor. Source from launch content + LinkedIn outreach. |
| **$5K MRR** (Month 8–10) | Recurring | 2–3 consulting clients ($3K/mo blended) + Provara Verify early adopters ($2K/mo from 15–20 teams) |
| **$10K MRR** (Month 12–14) | Recurring | 5–10 enterprise teams at $1K–$2K/mo for Toolkit + support + quarterly architecture reviews |
| **$25K–$50K MRR** (Month 24) | Scaling | Enterprise Toolkit licenses + hosted Verify + consulting pipeline + first certification revenue |

---

## 5. GO-TO-MARKET — SEED DEVELOPERS, HARVEST ENTERPRISES

### Launch Sequence (90-Day Sprint)

**Weeks 1–2: Developer soft launch**
1. **Hacker News** — "Show HN: Provara — Tamper-evident audit trails with no infrastructure, no blockchain, just signed JSON files." Tuesday/Wednesday, 8–9am ET. Have the "Why Not Git?" comparison table ready.
2. **Dev.to** — Long-form: "Why I Built a Cryptographic Event Log That Works Without a Server"
3. **Reddit** — r/programming (technical impl), r/cryptography (crypto design choices), r/selfhosted (sovereignty story)

**Weeks 3–4: AI/ML community**
4. **LinkedIn** — "The Missing Infrastructure for AI Audit Trails." Tag compliance/AI safety professionals. Post from Provara brand.
5. **AI communities** — Simon Willison's blog (file-first alignment), LangChain Discord (MCP angle), Anthropic dev community

**Weeks 5–12: Sustained cadence**
6. Bi-weekly blog posts on provara.dev
7. GitHub README optimization: badges, <30s quickstart, architecture diagram, comparison section
8. Begin consulting lead outreach (EU AI Act angle)

### Developer Adoption Funnel

```
DISCOVER              TRY                  INTEGRATE              ADVOCATE
─────────────         ──────────           ────────────           ──────────
HN / Dev.to /     →   pip install       →  MCP server in      →  Blog post,
Reddit / LinkedIn     5-line quickstart     their AI agent         conference talk,
                                            OR vault in their      PR, case study,
                                            CI pipeline            "Powered by Provara"
```

**Friction killers:**
- Discovery → Try: README has a working example in <5 lines. Zero config preamble.
- Try → Integrate: MCP server installable in one command. SDK is `pip`/`npm` installable with typed interfaces.
- Integrate → Advocate: "Powered by Provara" badge. Blog template for "How I Use Provara" posts.

### Conference Strategy (Months 3–24)

| Event Type | Targets | Talk Angle |
|---|---|---|
| AI/ML engineering | AI Engineer Summit, NeurIPS, ICML | "Cryptographic Memory for AI Agents" |
| Security/DevSecOps | RSA, Black Hat, KubeCon | "Immutable AI Logs Without Blockchains" |
| Compliance/RegTech | GovTech, AI Policy Summit, EU AI Act events | "Audit Trails That Outlast Your Vendor" |
| OSS/Developer | PyCon, RustConf, FOSDEM, All Things Open | "Single-Dependency Constraint: What It Cost and What It Bought" |

Strategy: Submit under "Provara team." Focus on the problem space, not the product. Let the protocol sell itself.

### Content Strategy

| Type | Frequency | Channel | Purpose |
|---|---|---|---|
| Protocol design rationale | Monthly | provara.dev/blog | Thought leadership, SEO |
| Compliance mapping guides | Quarterly | provara.dev/docs | Lead gen for consulting |
| Quickstart tutorials | Per-language port | GitHub + provara.dev | Adoption |
| "How we use Provara" case studies | As available | provara.dev/stories | Social proof |
| Comparison deep-dives (vs Git, etc.) | Quarterly | Dev.to + provara.dev | SEO, positioning |
| Benchmark results | Per milestone | GitHub + provara.dev | Credibility |

**SEO targets:** "tamper-evident logs," "AI audit trail," "EU AI Act Article 12 compliance," "zero-infrastructure transparency log," "cryptographic event log"

---

## 6. COMMUNITY & ECOSYSTEM

### Platform Decision: GitHub Discussions, Not Discord

**Why not Discord:** Ephemeral, unsearchable by Google, creates real-time response expectations a one-person team can't sustain. Also philosophically incoherent — conversations about a 50-year protocol should themselves be durable.

**Why GitHub Discussions:** Threaded, indexed by search engines, co-located with code, contributors already there. Categories: "Protocol Design," "Show & Tell," "Help," "Compliance & Governance."

**Escalation path:** If community exceeds ~200 active participants (month 12+), add a Matrix/Element server. Matrix is self-hostable with archival properties.

### Contributor Strategy (Phased)

**Phase 1 (Months 0–6): Curated contributions**
- "Good first issue" labels for docs, examples, test improvements
- Language port bounties: "Help us port compliance tests to [Rust/Go/TS]" — co-authorship credit
- Explicit CONTRIBUTING.md with the spec-first constraint: "If the spec doesn't support it, we change the spec first, then the code"

**Phase 2 (Months 6–12): Ecosystem enablement**
- Integration grants ($500–$2K) for building Provara + LangChain, MLflow, DVC, W&B connectors
- "Provara Conformant" certification badge for third-party implementations passing compliance tests
- Publish "Porting Provara" guide: how to read the spec, pass compliance, get listed

**Phase 3 (Months 12–24): Governance formalization**
- RFC process for spec changes (modeled on Rust RFCs)
- Technical steering committee (3–5 members) if adoption warrants
- Consider CNCF or foundation membership if enterprise traction justifies

### Strategic Partnerships

| Partner Type | Specific Targets | Value Exchange |
|---|---|---|
| **AI safety orgs** | MIRI, ARC, Anthropic safety, Partnership on AI | Provara as reference audit trail; they get free tooling, Provara gets credibility |
| **Compliance platforms** | Vanta, Drata, OneTrust, Secureframe | Integration: vaults as evidence source for their dashboards; they get differentiated feature, Provara gets distribution |
| **MLOps platforms** | W&B, MLflow, DVC, Hugging Face Hub | Plugin: log model training decisions to Provara vault; they get governance story, Provara gets embedded in workflows |
| **AI agent frameworks** | LangChain, CrewAI, AutoGen, LlamaIndex | MCP integration; they get audit capability, Provara gets baked into developer workflows |
| **Transparency log projects** | Sigstore, Rekor, Trillian | Cross-integration for optional public audit mirrors; mutual credibility boost |
| **Standards/compliance orgs** | ISO 42001 implementers, NIST AI RMF, IETF SCITT WG | Alignment and joint guidance; potential standards-track submission |

---

## 7. RISKS & MITIGATIONS (RANKED)

### Risk 1: Bus Factor = 1 (CRITICAL)

**Probability:** Certain. **Impact:** Project death on founder incapacitation.

**Mitigation stack (layered, not either/or):**
1. **Immediate:** Dead man's switch document — all credentials, keys, DNS config, operational knowledge encrypted with recovery instructions for a trusted party
2. **Month 3:** `OPERATIONS.md` in private repo: release process, PyPI/npm credentials, CI billing, DNS configuration
3. **Month 6:** Recruit 1–2 co-maintainers (not co-founders) — trusted contributors with merge access + release capability
4. **Month 12:** If traction warrants, establish formal governance document designating succession
5. **Structural mitigation:** The spec-first, compliance-test-driven architecture *is itself* a mitigation. Any competent developer can rebuild from the spec and tests. The protocol is in `PROTOCOL_PROFILE.txt`, not in the founder's head.

### Risk 2: "Why Not Just Use Git?" (HIGH)

**Probability:** High (the #1 objection from every developer).
**Impact:** Adoption stall if the answer isn't crisp.

**Mitigation:**
- **30-second answer:** Memorized. Rehearsed. In the README. (See Section 2.)
- **Technical answer:** Detailed comparison at `provara.dev/docs/provara-vs-git` with concrete code examples
- **Demo answer:** Show a use case Git literally cannot do — two devices, offline append, sync, fork detection, causal resolution

### Risk 3: Adoption Stall — New Protocol, No Network Effects (HIGH)

**Probability:** High (most protocols die in obscurity).
**Impact:** Project irrelevance.

**Mitigation — four reinforcing strategies:**
1. **MCP server as distribution hack.** Users don't need to "adopt Provara" — their AI agent just writes to it. Piggyback on the agentic AI explosion.
2. **Compliance pull.** Regulation creates demand. Companies adopt audit protocols because regulators require provable records. Time outreach to EU AI Act enforcement dates.
3. **Integrations over standalone adoption.** Provara as a library inside W&B, MLflow, or LangChain reaches more users than Provara as a standalone tool.
4. **"Powered by Provara" badge.** Trivially easy to signal use. Social proof compounds.

### Risk 4: Cryptographic Algorithm Obsolescence (MEDIUM, long-term)

**Probability:** Low in 5 years, medium in 10, near-certain in 20+.
**Impact:** Vault integrity guarantees degraded.

**Mitigation:**
- Phase 3 dual-signing (Ed25519 + ML-DSA) is the technical answer
- `algorithm` field in event metadata supports agility by design
- Published "Cryptographic Longevity" document on provara.dev (marketing + engineering)
- Monitor NIST PQC standardization and adjust timeline accordingly

### Risk 5: Big Player Builds Similar (MEDIUM)

**Probability:** Medium (Google, AWS, or a compliance vendor could build this).
**Impact:** Provara gets outspent and out-distributed.

**Mitigation:**
- **Philosophy mismatch is the shield.** A big player's version will be cloud-hosted, vendor-locked, proprietary. Provara's entire value is sovereignty and portability. Fundamentally incompatible.
- **Spec becomes the standard.** If adopted before a competitor enters, their offering becomes "a Provara-compatible service." TCP/IP play.
- **Apache 2.0 is strategic.** Permissive licensing means big players can *embed* Provara rather than compete with it. Better inside their product than opposed to it.

---

## 8. BOLD BETS

### Bold Bet 1: "Provara Inside" for AI Agent Frameworks (Months 3–6)

**The bet:** Get Provara adopted as the default audit trail for at least one major AI agent framework (LangChain, CrewAI, or AutoGen) via the MCP server — no code changes required on their side.

**Why it's bold:** Framework maintainers are conservative about dependencies.

**Why it could work:** MCP sidesteps the dependency problem entirely. Ship a flawless MCP server, write a tutorial showing it with LangChain + Claude, and let developers pull the framework maintainers forward.

**Payoff:** Thousands of AI agents writing to Provara vaults within months. "Provara vault" becomes a standard artifact alongside "log file" and "database."

### Bold Bet 2: IETF SCITT Working Group Submission (Month 12)

**The bet:** Submit the Provara event log format as an Internet-Draft to IETF, targeting the SCITT (Supply Chain Integrity, Transparency, and Trust) working group.

**Why it's bold:** Standards bodies are slow, political, and dominated by big companies.

**Why it could work:** SCITT is actively seeking tamper-evident log formats. Provara's spec-first design is already written like a standard. Anonymous founder constraint actually helps — the spec speaks for itself. Apache 2.0 with zero patent claims is standards-body-friendly.

**Payoff:** "IETF-track" transforms Provara from "some OSS project" to "an emerging standard." Enterprise adoption accelerates dramatically.

### Bold Bet 3: EU AI Act Compliance Backbone (Months 6–18)

**The bet:** Position Provara as the reference implementation for Article 12 (record-keeping) and Article 14 (human oversight logging).

**Why it's bold:** Regulatory capture normally requires lobbying, relationships, and presence in Brussels.

**Why it could work:** Regulators need open, auditable, vendor-neutral solutions. The key vector is compliance consultancies (Deloitte, PwC, EY AI practices). If one Big 4 firm recommends Provara-based audit trails, that's worth more than any marketing budget.

**Approach:** Free downloadable compliance mapping whitepaper → SEO optimize for "EU AI Act audit trail" → speak at RegTech conferences → direct outreach to consultants building AI governance practices.

**Payoff:** De facto standard for AI audit trails in the EU. Consulting revenue. Enterprise licenses. Near-impenetrable regulatory moat.

### Bold Bet 4: The "50-Year Vault" Bounty

**The bet:** Offer a bounty/trust to maintain a Provara vault for 50 years, publicly, as a living proof of the file-first durability thesis.

**Why it's bold:** It's a stunt. But it's a stunt that perfectly embodies the value proposition.

**Payoff:** PR, credibility, and an unforgettable talking point in every pitch, talk, and blog post.

### Bold Bet 5: Zero-Knowledge Evidence (Months 18–24, exploratory)

**The bet:** Research ZK-Proofs for Provara events — prove "I have evidence of X happening at time Y" without revealing the content of X.

**Why it's bold:** ZK + file-first is uncharted territory. Research risk is high.

**Payoff:** Opens the door to privacy-preserving compliance and selective disclosure. Massive differentiator if achievable.

---

## 9. KEY METRICS

| Metric | Month 6 | Month 12 | Month 24 |
|---|---|---|---|
| GitHub stars | 200 | 500 | 2,000 |
| PyPI monthly downloads | 500 | 2,000 | 10,000 |
| npm monthly downloads | — | 1,000 | 5,000 |
| Conformant implementations | 2 (Python + Rust) | 4 (+ TS, Go) | 6+ (community) |
| Third-party integrations | 0 | 3 | 10 |
| MRR | $0 | $5–10K | $25–50K |
| Consulting engagements | 1–2 | 5–8 | 10+ |
| Conference talks given | 1 | 3–5 | 8+ |
| Blog posts published | 6 | 15 | 30+ |
| Contributors (non-founder) | 3 | 10 | 25+ |

---

## 10. 90-DAY SPRINT PLAN (IMMEDIATE EXECUTION)

| Week | Action | Owner |
|---|---|---|
| 1 | Unblock CI/CD (resolve billing or self-hosted runner) | Founder |
| 1 | Fix Windows CRLF compliance (`test_09`) via `.gitattributes` — blocker for stable release | AI agents |
| 2 | Ship v1.0.0 stable to PyPI (all 17 compliance tests green on all 3 OS) | Founder + AI agents |
| 2 | Deploy provara.dev (Cloudflare Pages, three-tier docs: Protocol Spec / Python API / PSMC CLI) | Founder |
| 3 | Publish Show HN post | Founder |
| 3 | Begin Rust compliance test port (`provara-rs/tests/`) — per decision log: Rust before TS | AI agents |
| 4 | Publish Dev.to launch article | Founder |
| 4 | Begin MCP server library (`provara-mcp`) — library-first, importable into any Python process; daemon wrapper is optional convenience | AI agents |
| 5–6 | Reddit posts (r/programming, r/cryptography, r/selfhosted) | Founder |
| 5–6 | Rust core implementation: canonical_json + signing + chain verification | AI agents |
| 7–8 | LinkedIn article + AI community outreach | Founder |
| 7–8 | Alpha MCP server + demo video (Provara vault as Claude agent memory) | AI agents + Founder |
| 9–10 | Rust port v0.1 passing all 17 compliance tests | AI agents |
| 9–10 | First consulting lead outreach (EU AI Act angle) | Founder |
| 11–12 | MCP server v1.0 release + begin TypeScript compliance test port | AI agents |
| 11–12 | Conference talk proposals submitted (2–3 events) | Founder |

---

## 11. DECISION LOG — RESOLVED CONTRADICTIONS FROM PRIOR DRAFTS

These are places where the six drafts disagreed. This section records the final decision and rationale.

| Question | Decision | Rationale |
|---|---|---|
| Rust or Go first? | **Rust** | FFI to Go/TS/Python, security community traction, performance baseline. Go comes in Phase 2. |
| Discord or GitHub Discussions? | **GitHub Discussions** | Durable, searchable, philosophically consistent. Discord only if community >200 active (unlikely before month 12). |
| Encryption: separate tool or protocol layer? | **Optional protocol envelope layer** | Using `cryptography` primitives (no new dep). External key management. Separate tool approach creates fragmentation. |
| MCP: local daemon or library? | **Library-first, daemon optional** | Library embeds into any Python/Rust/Node process. Daemon is a convenience wrapper, not a requirement. |
| First revenue: consulting or product? | **Consulting** | Faster to first dollar. Validates market. Informs product design. Product SaaS revenue follows in months 12+. |
| "Enterprise Vault Manager" SaaS? | **Deferred to Month 18+** | Building hosted infra contradicts zero-infra ethos if done too early. Focus on protocol adoption first. Hosted offerings must be explicitly opt-in and clearly separated. |
| Foundation or LLC? | **LLC now, foundation if warranted** | Don't create governance overhead prematurely. If adoption justifies it (month 12+), evaluate CNCF or similar. |
| Checkpoint format: separate file or event type? | **Separate file** (`checkpoints/NNNNNNNNNN.chk`) | Checkpoints are verifier optimizations, not evidence. They don't belong in the event log. *(Supersedes prior "checkpoints go IN the log" decision from early drafts — that conflated optimization with evidence.)* |
| Post-quantum: v2 spec or spec extension? | **Spec extension** (`PROTOCOL_PROFILE_PQ.txt`) | Don't break v1 adoption momentum. PQ is additive. Dual-signing during transition period. |

---

## APPENDIX: THE PROVARA IDENTITY

**Brand architecture:**
- `provara.dev` → Protocol specification, docs, blog (developer-facing)
- `provara.app` → Commercial products (when ready)
- `huntinformationsystems.com` → Corporate/legal entity
- GitHub org: `provara-protocol` → All open-source repositories

**Voice:** Technical but not academic. Opinionated but not preachy. The tone of a senior engineer who's thought deeply about this problem and built something they believe in.

**Taglines (use contextually):**
- "The sovereign evidence layer for AI and institutions"
- "Git for verifiable history. Rekor for everything. No servers required."
- "Prove what happened. Prove when. Prove under which keys. No infrastructure needed."

**The mantra:**

> *"Truth is not merged. Evidence is merged. Truth is recomputed."*

---

*This document is the canonical blueprint. All prior drafts are superseded. Execute from here.*
