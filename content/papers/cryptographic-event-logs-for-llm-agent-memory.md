# Cryptographic Event Logs for LLM Agent Memory

**A Position Paper on Verifiable Memory Substrates for Autonomous Agents**

**Version:** 1.0  
**Date:** 2026-02-17  
**Authors:** The Provara Maintainers  
**License:** Apache 2.0

---

## Abstract

Large language model agents are increasingly deployed for high-stakes decisions: executing trades, managing infrastructure, negotiating contracts, and providing legal or medical guidance. Yet the memory systems powering these agents remain fundamentally unverifiable. Vector databases, RAG systems, and even the emerging MCP Memory Server all share a critical weakness: agent memory is mutable, platform-dependent, and cryptographically unanchored.

This paper argues that LLM agent memory requires the same tamper-evident, non-repudiable guarantees that we demand of financial records, legal evidence, and scientific data. We present Provara—a self-sovereign cryptographic event log protocol—as a memory substrate for AI agents. Provara provides Ed25519-signed observations, SHA-256 hash chains for tamper evidence, RFC 8785 canonical JSON for deterministic replay, and a four-namespace model (canonical, local, contested, archived) for multi-agent dispute resolution.

We demonstrate that cryptographic event logs enable: (1) non-repudiable agent decisions, (2) deterministic replay of agent reasoning, (3) verifiable multi-agent coordination, and (4) 50-year readability independent of any platform or vendor. We provide a working implementation via the Provara MCP Server, enabling any MCP-compatible agent to read and write verifiable memory.

The goal of this paper is to establish a standard for verifiable agent memory before proprietary, non-interoperable systems become entrenched. We invite the AI agent community to adopt cryptographic event logs as the foundation for trustworthy autonomous systems.

---

## 1. The Problem: LLM Agent Memory is Unverifiable

### 1.1 The Current State of Agent Memory

Modern LLM agents rely on external memory systems to overcome context window limitations. The dominant approaches are:

**Vector Databases** (Pinecone, Weaviate, Chroma): Store embeddings of past interactions, retrieved by semantic similarity. Weaknesses: embeddings are lossy, the database is mutable without detection, and there is no cryptographic link between retrieved context and the original observation.

**RAG Systems** (LangChain, LlamaIndex): Retrieve documents from a knowledge base at query time. Weaknesses: documents can be altered post-hoc, there is no signature linking the document to its source, and retrieval is non-deterministic (different queries may produce different "memories" of the same event).

**MCP Memory Server** (Anthropic): A knowledge graph exposed via the Model Context Protocol. Weaknesses: memory is stored as mutable JSON, there are no cryptographic signatures, and multi-agent disputes have no resolution mechanism beyond last-write-wins.

**Plain File Storage**: Agents write memories to JSON or Markdown files. Weaknesses: files can be edited without detection, there is no chain of custody, and temporal ordering relies on filesystem metadata (which is manipulable).

### 1.2 Why This Matters

Consider an AI hedge fund that executes trades based on its memory of market signals. If the memory is mutable:

- A rogue employee could alter the agent's memory to hide unauthorized trades.
- A competitor who gains access could inject false signals.
- In a regulatory investigation, the fund cannot prove what the agent "knew" at the time of each trade.
- The agent itself cannot distinguish between an authentic memory and a fabricated one.

Or consider an AI legal assistant that memorizes case precedents:

- If the memory is altered, the assistant might cite fabricated precedents.
- There is no way to prove which version of a precedent the assistant relied upon.
- Multiple assistants working on the same case cannot resolve conflicting memories.

The core issue is that **mutable memory undermines trust in agent decisions**. If we cannot verify what an agent remembered, we cannot verify why it acted.

### 1.3 Requirements for Verifiable Agent Memory

We propose eight properties that a verifiable agent memory system must satisfy:

| Property | Description | Why It Matters |
|----------|-------------|----------------|
| **R1: Tamper Evidence** | Any alteration of memory is cryptographically detectable | Prevents post-hoc fabrication of memories |
| **R2: Non-Repudiation** | Every memory is signed by its observer | Agents cannot deny what they observed |
| **R3: Deterministic Replay** | Given the same event log, any implementation derives the same state | Enables independent verification of agent reasoning |
| **R4: Multi-Agent Dispute Resolution** | Conflicting observations are tracked and resolved via attestation | Enables coordination among distrustful agents |
| **R5: Context Window Independence** | Memory is stored externally, retrieved as needed | Overcomes LLM context limits |
| **R6: Platform Independence** | Memory format is vendor-neutral, readable without proprietary tools | Prevents lock-in, enables 50-year readability |
| **R7: Temporal Anchoring** | Memories can be anchored to independent time sources | Proves when a memory was created |
| **R8: Selective Disclosure** | Agents can prove specific memories without revealing all | Privacy-preserving verification |

No current agent memory system satisfies all eight properties. Provara satisfies R1–R7 natively; R8 is achievable via zero-knowledge proofs over the event log (future work).

---

## 2. Architecture: Provara as Memory Substrate

### 2.1 Core Cryptographic Primitives

Provara is built on three cryptographic foundations, all specified in `PROTOCOL_PROFILE.txt`:

**Ed25519 Signatures (RFC 8032):** Every observation is signed with the observer's Ed25519 private key. The signature covers the canonical JSON serialization of the event (excluding the `sig` field itself). This provides non-repudiation (R2): only the holder of the private key could have produced the signature.

**SHA-256 Hash Chains (FIPS 180-4):** Each event includes a `prev_event_hash` field pointing to the SHA-256 hash of the previous event by the same actor. This creates a causal chain: altering any event breaks the hash chain, providing tamper evidence (R1).

**RFC 8785 Canonical JSON:** JSON objects are serialized deterministically: keys are sorted lexicographically, no whitespace, minimal escape sequences. This ensures that the same logical object always produces the same bytes, enabling deterministic replay (R3) and cross-implementation compatibility (R6).

### 2.2 Event Structure

A Provara event is a JSON object with the following structure:

```json
{
  "type": "OBSERVATION",
  "namespace": "local",
  "actor": "alice_agent_v1",
  "actor_key_id": "bp1_abc123...",
  "timestamp_utc": "2026-02-17T14:30:00Z",
  "prev_event_hash": "evt_previous...",
  "event_id": "evt_abc123...",
  "payload": {
    "subject": "market_signal",
    "predicate": "observed",
    "value": {...},
    "confidence": 0.75
  },
  "sig": "base64_ed25519_signature..."
}
```

**Key fields:**
- `event_id`: Content-addressed identifier (`evt_` + SHA-256 of event without `event_id` or `sig` fields).
- `prev_event_hash`: Links to the previous event by this actor (null for genesis events).
- `namespace`: One of `canonical`, `local`, `contested`, `archived` (see §2.3).
- `payload.subject` and `payload.predicate`: Define the "key" for the belief (e.g., `market_signal:AAPL`).
- `payload.value`: The actual observation or attestation.
- `payload.confidence`: Numeric confidence score (0.0–1.0).

### 2.3 Four-Namespace Model

Provara agents maintain four namespaces for beliefs:

| Namespace | Purpose | Entry | Exit |
|-----------|---------|-------|------|
| `canonical` | Attested truth | ATTESTATION with confidence ≥0.9 | Superseded by new ATTESTATION → `archived` |
| `local` | Private observations | OBSERVATION events | Promoted to `canonical` or `contested` |
| `contested` | Conflicting evidence | ≥2 OBSERVATIONs with conflicting values | Resolved by authority ATTESTATION → `archived` |
| `archived` | Historical record | Superseded canonical beliefs | Permanent (never deleted) |

This model enables multi-agent dispute resolution (R4). When two agents observe the same event differently, their observations go to `local`. If they conflict (same `subject` and `predicate`, different `value`), the belief moves to `contested`. An authority agent (e.g., an oracle, a human supervisor, or a voting mechanism) can then issue an ATTESTATION that resolves the conflict, moving the belief to `canonical` and archiving the conflicting evidence.

### 2.4 State Derivation via Reducer

The agent's "memory state" is derived by replaying the event log through a deterministic reducer function:

```python
def reduce(events: List[Event]) -> State:
    state = State(canonical={}, local={}, contested={}, archived={})
    for event in events:
        if event.type == "OBSERVATION":
            state.local[key(event)] = event.payload
        elif event.type == "ATTESTATION":
            if event.payload.confidence >= 0.9:
                state.canonical[key(event)] = event.payload
                if key(event) in state.contested:
                    state.archived[key(event)] = state.contested[key(event)]
                    del state.contested[key(event)]
        elif event.type == "RETRACTION":
            if event.payload.subject in state.canonical:
                state.archived[event.payload.subject] = state.canonical[event.payload.subject]
                del state.canonical[event.payload.subject]
    return state
```

The reducer is pure (no side effects, no randomness). Given the same event log, any implementation produces the same state hash. This enables deterministic replay (R3) and independent verification.

---

## 3. Properties Enabled by Cryptographic Event Logs

### 3.1 Non-Repudiable Agent Decisions

When an agent makes a decision, it logs an OBSERVATION event:

```json
{
  "type": "OBSERVATION",
  "namespace": "local",
  "actor": "trading_agent_v1",
  "payload": {
    "subject": "trading_decision",
    "predicate": "executed",
    "value": {
      "action": "SELL",
      "ticker": "AAPL",
      "quantity": 1000,
      "price": 185.50,
      "reasoning": "RSI > 70, MACD bearish crossover"
    },
    "confidence": 0.85
  }
}
```

The event is signed with the agent's private key. Later, if the decision is questioned (e.g., by a regulator), the agent cannot deny having made it. The signature proves the agent (or someone with access to its key) authored the event.

**Contrast with mutable memory:** A vector database can be edited post-hoc. There is no cryptographic link between the decision and the agent that made it.

### 3.2 Deterministic Replay of Agent Reasoning

Given an event log, any party can replay the agent's reasoning:

```bash
provara replay agent_memory_vault
```

The output shows the agent's state at each point in time: what it observed, what it attested to, what conflicts arose, and how they were resolved. This enables:

- **Debugging:** Why did the agent make a bad decision? Replay shows what it knew at the time.
- **Auditing:** Did the agent follow its stated policy? Replay shows the decision chain.
- **Forensics:** Was the agent's memory tampered with? Replay verifies the hash chain.

**Contrast with RAG systems:** RAG retrieval is non-deterministic. Different queries may produce different "memories" of the same event. There is no way to reconstruct what the agent knew at a specific point in time.

### 3.3 Multi-Agent Dispute Resolution

Consider two agents observing the same market signal:

- Alice-Bot: "AAPL broke out above resistance at $185"
- Bob-Bot: "AAPL had a false breakout at $185"

Both observations are logged as OBSERVATION events. The reducer detects the conflict (same `subject` and `predicate`, different `value`) and moves the belief to `contested`. An oracle agent (e.g., a premium data source) then issues an ATTESTATION:

```json
{
  "type": "ATTESTATION",
  "namespace": "canonical",
  "actor": "market_oracle_v1",
  "payload": {
    "subject": "market_signal:AAPL",
    "predicate": "attested",
    "value": {
      "signal_type": "FALSE_BREAKOUT",
      "reasoning": "Volume ratio < 3.0 indicates insufficient conviction"
    },
    "confidence": 0.95
  }
}
```

The belief moves to `canonical`, and the conflicting observations are archived. All agents that sync the vault now share the same canonical truth.

**Contrast with MCP Memory:** The MCP Memory Server has no dispute resolution mechanism. If two agents write conflicting memories, the last write wins silently.

### 3.4 Context Window Independence

LLM context windows are limited (currently ~100K tokens for leading models). Provara memory is stored externally in a vault file. The agent queries memory as needed:

```python
# Query memory before making a decision
events = query_timeline(
    subject="market_signal:AAPL",
    date_range={"start": "2026-02-17", "end": "2026-02-17"}
)
context = format_events_for_prompt(events)
response = llm.generate(prompt=context)
```

The vault can grow arbitrarily large without affecting the agent's context window. Checkpoints enable fast state materialization without replaying the entire log.

**Contrast with in-context memory:** Agents that store memory in the context window are limited by the model's token limit. As the memory grows, older memories are evicted.

### 3.5 Platform Independence

Provara vaults are UTF-8 JSON files. The event schema is specified in `PROTOCOL_PROFILE.txt`. Any implementation in any language can read and verify a Provara vault. This enables:

- **50-year readability:** The vault format does not depend on any vendor or platform.
- **Cross-language interoperability:** A Python agent can read memory written by a Rust agent.
- **Offline operation:** The vault is a file, not a database. It works without network connectivity.

**Contrast with vector databases:** Vector databases are vendor-specific. Migrating from Pinecone to Weaviate requires exporting and re-embedding all data. The embedding model itself may become obsolete.

### 3.6 Temporal Anchoring

Provara vaults can be anchored to RFC 3161 Timestamp Authorities (TSAs):

```bash
provara timestamp agent_memory_vault --tsa https://freetsa.org/tsr
```

The TSA returns a signed timestamp token (TSR) proving the vault state existed at a specific time. This provides:

- **Independent temporal proof:** The TSA is a third party, not controlled by the agent.
- **Legal admissibility:** RFC 3161 timestamps are recognized in many jurisdictions.
- **Long-term verification:** The timestamp proves when the memory was created, even if the agent's clock was manipulated.

**Contrast with system clocks:** System clocks are manipulable. An attacker with root access can backdate events. TSA timestamps are independent of the agent's system.

---

## 4. Comparison with Alternative Approaches

| Property | Provara | Vector DB | RAG | MCP Memory | Plain Files |
|----------|---------|-----------|-----|------------|-------------|
| **Tamper Evidence (R1)** | ✅ Hash chain | ❌ Mutable | ❌ Mutable | ❌ Mutable | ❌ Mutable |
| **Non-Repudiation (R2)** | ✅ Ed25519 | ❌ None | ❌ None | ❌ None | ❌ None |
| **Deterministic Replay (R3)** | ✅ Yes | ❌ Approximate | ❌ Approximate | ❌ Approximate | ⚠️ If structured |
| **Dispute Resolution (R4)** | ✅ 4 namespaces | ❌ LWW | ❌ LWW | ❌ LWW | ❌ Manual |
| **Context Independence (R5)** | ✅ External | ✅ External | ✅ External | ✅ External | ✅ External |
| **Platform Independence (R6)** | ✅ RFC 8785 | ❌ Vendor-specific | ⚠️ Framework-specific | ⚠️ MCP-dependent | ✅ If structured |
| **Temporal Anchoring (R7)** | ✅ RFC 3161 | ❌ System clock | ❌ System clock | ❌ System clock | ❌ System clock |
| **Selective Disclosure (R8)** | 🔜 ZK proofs | ❌ All or nothing | ❌ All or nothing | ❌ All or nothing | ⚠️ Manual redaction |

**Key:** ✅ Satisfied, ⚠️ Partially satisfied, ❌ Not satisfied, 🔜 Future work

### 4.1 Honest Tradeoffs

Provara is not the right choice for every agent memory use case:

**When to use Provara:**
- High-stakes decisions (trading, legal, medical)
- Multi-agent coordination with distrust
- Regulatory compliance requirements
- Long-term memory (50-year readability)

**When NOT to use Provara:**
- High-frequency logging (>1000 events/second)
- Ephemeral session memory
- Purely internal debugging
- When all agents fully trust each other

The overhead of cryptographic signing and hash chain verification is measurable (~1ms per event). For high-frequency trading or real-time control systems, this may be unacceptable. For high-stakes decisions where auditability matters, it is essential.

---

## 5. Implementation: Provara MCP Server

We provide a working implementation of Provara memory for AI agents via the Model Context Protocol.

### 5.1 Setup

```bash
# Start MCP server
python tools/mcp_server/server.py \
  --transport http \
  --host 0.0.0.0 \
  --port 8765 \
  --vault-path ./agent_memory_vault \
  --keyfile agent_keys.json
```

### 5.2 Available Tools

| Tool | Description |
|------|-------------|
| `append_event` | Append an observation or attestation |
| `query_timeline` | Query events by subject, predicate, date range |
| `snapshot_belief` | Get current canonical state for a subject |
| `list_conflicts` | List all contested beliefs |
| `verify_chain` | Verify vault integrity |

### 5.3 Example: Agent with Verifiable Memory

```python
from mcp import ClientSession

async with ClientSession(read, write) as session:
    # Observe a market signal
    await session.call_tool("append_event", arguments={
        "type": "OBSERVATION",
        "namespace": "local",
        "payload": {
            "subject": "market_signal:AAPL",
            "predicate": "observed",
            "value": {
                "signal_type": "BREAKOUT_ABOVE_RESISTANCE",
                "price": 185.50,
                "confidence": 0.75
            }
        }
    })
    
    # Query memory before making a decision
    result = await session.call_tool("query_timeline", arguments={
        "subject": "market_signal:AAPL",
        "date_range": {"start": "2026-02-17"}
    })
    
    # Use memories in reasoning
    context = format_memories(result.events)
    decision = llm.generate(f"Based on these memories: {context}")
```

The full implementation is available at https://github.com/provara-protocol/provara.

---

## 6. Open Questions

### 6.1 Key Rotation for Long-Lived Agents

Agents that run for years will need to rotate their signing keys. Provara supports key rotation via `KEY_REVOCATION` and `KEY_PROMOTION` events, but the UX for agents is not yet polished. How should agents handle in-flight memories signed with old keys? Should there be a grace period?

### 6.2 Memory Compaction

As the event log grows, replay becomes slower. Checkpoints help, but they do not reduce storage size. Should there be a compaction mechanism that archives old events while preserving the hash chain? How do we balance verifiability with storage efficiency?

### 6.3 Cross-Agent Trust Establishment

When two agents meet for the first time, how do they establish trust? Should there be a web-of-trust model? A certificate authority? A decentralized identity system? This is an open research question.

### 6.4 Zero-Knowledge Selective Disclosure

Property R8 (selective disclosure) is not yet implemented. Zero-knowledge proofs over the event log would enable an agent to prove "I observed X at time T" without revealing other memories. This is a promising direction for future work.

---

## 7. Conclusion and Call to Action

LLM agents are increasingly deployed for high-stakes decisions. Yet their memory systems remain fundamentally unverifiable. This is a technical debt that will compound as agents become more autonomous.

We have presented Provara—a cryptographic event log protocol—as a memory substrate for AI agents. Provara provides tamper evidence, non-repudiation, deterministic replay, and multi-agent dispute resolution. It is platform-independent, temporally anchorable, and designed for 50-year readability.

**We call on the AI agent community to:**

1. **Adopt cryptographic event logs** as the foundation for agent memory in high-stakes applications.
2. **Contribute to the Provara specification** via the GitHub repository (https://github.com/provara-protocol/provara).
3. **Build tooling** for ZK selective disclosure, key rotation UX, and memory compaction.
4. **Publish research** on multi-agent trust establishment and dispute resolution mechanisms.

If AI agents are to be trusted partners in human decision-making, their memories must be as verifiable as the decisions they inform. Cryptographic event logs are the foundation for that trust.

---

## References

1. Provara Protocol v1.0 Specification. `PROTOCOL_PROFILE.txt`. https://github.com/provara-protocol/provara
2. RFC 8032: Edwards-Curve Digital Signature Algorithm (EdDSA). https://datatracker.ietf.org/doc/html/rfc8032
3. RFC 8785: JSON Canonicalization Scheme (JCS). https://datatracker.ietf.org/doc/html/rfc8785
4. FIPS 180-4: Secure Hash Standard (SHS). https://csrc.nist.gov/publications/detail/fips/180/4/final
5. RFC 3161: Internet X.509 Public Key Infrastructure Time-Stamp Protocol (TSP). https://datatracker.ietf.org/doc/html/rfc3161
6. Model Context Protocol (MCP) Specification. https://modelcontextprotocol.io
7. Federal Rules of Evidence 901: Authenticating or Identifying Evidence. https://www.law.cornell.edu/rules/fre/rule_901

---

**About Provara:** Provara is an open-source cryptographic event log protocol for self-sovereign, tamper-evident memory. Apache 2.0 licensed. Built by Hunt Information Systems LLC. https://github.com/provara-protocol/provara
