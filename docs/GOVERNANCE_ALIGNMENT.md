# Provara Protocol — AI Governance Alignment

**Version:** 1.0
**Status:** Living document
**Protocol:** Provara v1.0
**License:** Apache 2.0

---

## Purpose

This document explains how the Provara Protocol supports AI governance, regulatory compliance, and auditable decision provenance. Provara is a general-purpose, sovereign memory substrate — not an AI governance product. However, its cryptographic guarantees make it a natural foundation for systems that require tamper-evident records of AI behavior, policy enforcement, and operational oversight.

---

## How Provara Supports AI Governance

### 1. Append-Only Logs Enable Regulatory Compliance

Provara vaults are append-only by design. Events are never deleted, only superseded by newer evidence. This property directly supports regulatory frameworks that require:

- **Complete audit trails** — Every AI decision, model evaluation, and policy action is recorded as a signed event. Regulators can request the full event log and independently verify its integrity.
- **Retention guarantees** — The retention policy enforces event permanence. There is no "delete" operation. Archival and supersession are explicit, signed acts that preserve the original evidence.
- **Chain of custody** — Each event is signed by a specific key holder (`actor_key_id`) and linked to its predecessor via `prev_event_hash`. This creates a per-actor causal chain that cannot be broken without detection.

Compliance frameworks such as the EU AI Act, NIST AI RMF, and ISO/IEC 42001 emphasize traceability and record-keeping. Provara's event log satisfies these requirements at the infrastructure layer, independent of any specific regulatory framework.

### 2. Deterministic Reducers Support Reproducible Audits

The Provara reducer is a pure function: given the same event log, it produces the same belief state with a byte-identical `state_hash` on any machine, at any time, in any compliant implementation.

This means:

- **Independent verification** — An auditor does not need to trust the system that produced the state. They can take the raw event log, run the reducer, and verify the output independently.
- **Reproducible conclusions** — If a governance system derived a risk score, compliance status, or policy decision from Provara events, that derivation can be replayed deterministically. The same inputs always produce the same outputs.
- **No hidden state** — The reducer has no side effects, no randomness, and no dependence on system state. The event log is the complete input. Nothing is hidden.

This is particularly relevant for AI model evaluation, where reproducibility of benchmark results and risk assessments is a regulatory and institutional requirement.

### 3. Ed25519 Signatures Support Non-Repudiation

Every event in a Provara vault is signed with Ed25519 (RFC 8032). The signature binds the event content to a specific cryptographic key, providing:

- **Non-repudiation** — The signer cannot deny having produced the event. The signature is a mathematical proof of authorship.
- **Tamper evidence** — Any modification to a signed event invalidates the signature. Silent alteration is impossible.
- **Key authority tracking** — The protocol tracks which key was active at the time of signing, and enforces that revoked or future keys cannot produce valid events. Key rotation is itself a signed, two-event protocol (`KEY_REVOCATION` + `KEY_PROMOTION`).

For AI governance, this means that when a policy engine records a decision, that decision is cryptographically bound to the engine's identity. When a red-team records a vulnerability finding, that finding cannot be silently retracted.

### 4. "Evidence Is Merged. Truth Is Recomputed." — Why This Matters for AI Systems

The Provara Golden Rule is not a slogan — it is a technical constraint with direct governance implications.

In conventional systems, conclusions (beliefs, scores, compliance statuses) are stored as mutable state. When new information arrives, the state is updated in place. The old state is gone. There is no way to ask: *"What did the system believe at time T, given only the evidence available at time T?"*

Provara inverts this. Conclusions are never stored — they are derived by replaying evidence through the deterministic reducer. The event log is the permanent record. Beliefs are ephemeral, recomputable views.

**For AI governance, this means:**

- **Point-in-time reconstruction** — Regulators can ask "What was the compliance status of model X on date Y?" and get a deterministic, verifiable answer by replaying events up to that point.
- **Evidence discovery** — New evidence (e.g., a previously unknown model vulnerability) can be added to the event log, and the reducer will recompute all derived conclusions incorporating the new evidence. No manual state patching required.
- **Conflict transparency** — When two governance actors produce conflicting assessments, both are preserved in the event log. The four-namespace belief model (`canonical`, `local`, `contested`, `archived`) makes disagreements explicit rather than silently overwriting one conclusion with another.
- **No retroactive falsification** — Because events are append-only and signed, it is impossible to go back and change what the system "knew" at a prior point in time. The historical record is immutable.

---

## Governance Event Patterns

The following patterns demonstrate how AI governance data maps to Provara's existing event type system. No protocol modifications are required — the standard `OBSERVATION` and `ATTESTATION` types accommodate governance use cases natively.

### Model Evaluation

A model evaluation is an `OBSERVATION` — a node records the outcome of running a model against a benchmark.

```
actor:         "eval_pipeline_01"
type:          OBSERVATION
payload:
  subject:     "model/gpt-4o-2025-03"
  predicate:   "benchmark_score"
  value:       { benchmark: "MMLU", score: 0.871, ... }
  confidence:  1.0
```

### Policy Enforcement Decision

A policy decision by an institutional authority is an `ATTESTATION` — a signed, authoritative determination.

```
actor:         "policy_engine_prod"
type:          ATTESTATION
payload:
  subject:     "deployment/customer-support-bot-v3"
  predicate:   "deployment_authorized"
  value:       { decision: "PERMIT", policy_version: "gov-2026-02-01", ... }
```

### Red-Team Audit Record

A red-team finding is an `OBSERVATION` — the tester observes model behavior under adversarial conditions.

```
actor:         "redteam_agent_alpha"
type:          OBSERVATION
payload:
  subject:     "model/internal-llm-v2"
  predicate:   "adversarial_response"
  value:       { attack_vector: "jailbreak_v3", severity: "HIGH", ... }
  confidence:  0.95
```

### Cost & Routing Record

An AI cost event is an `OBSERVATION` — the routing system records what it did and what it cost.

```
actor:         "router_prod_east"
type:          OBSERVATION
payload:
  subject:     "request/req_abc123"
  predicate:   "routing_decision"
  value:       { model: "claude-sonnet-4-5-20250929", tokens_in: 1500, tokens_out: 800, cost_usd: 0.0234, ... }
  confidence:  1.0
```

> Full NDJSON examples are available in [`examples/ai_governance_events/`](../examples/ai_governance_events/).

---

## What Provara Is Not

Provara is not an AI governance product, a compliance dashboard, or a policy engine. It is the **memory layer** beneath those systems — the cryptographic substrate that makes their records tamper-evident, reproducible, and independently verifiable.

Governance products are built *on top of* Provara. Provara provides the guarantees. The product provides the interface.

---

## Related Resources

| Resource | Description |
|----------|-------------|
| [`PROTOCOL_PROFILE.txt`](../PROTOCOL_PROFILE.txt) | Frozen normative specification (immutable) |
| [`README.md`](../README.md) | Primary documentation with AI governance use case summary |
| [`examples/ai_governance_events/`](../examples/ai_governance_events/) | Example NDJSON events for governance scenarios |
| [`SNP_Core/deploy/templates/`](../SNP_Core/deploy/templates/) | Reference policy files (safety, retention, sync) |

---

(c) 2026 Hunt Information Services
