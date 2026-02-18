# Cookbook: AI Agent Memory with Dispute Resolution

**Use Case:** Verifiable memory for LLM agents with multi-agent dispute resolution  
**Time to Complete:** 25 minutes  
**Difficulty:** Advanced

---

## Problem Statement

### The LLM Memory Problem

Current LLM agent memory systems have critical weaknesses:

| Property | Vector DB | RAG System | MCP Memory | Provara Vault |
|----------|-----------|------------|------------|---------------|
| **Tamper Evidence** | ❌ Mutable | ❌ Mutable | ❌ Mutable | ✅ Cryptographic |
| **Non-Repudiation** | ❌ No signatures | ❌ No signatures | ❌ No signatures | ✅ Ed25519 |
| **Deterministic Replay** | ❌ Approximate | ❌ Approximate | ❌ Approximate | ✅ Exact |
| **Multi-Agent Dispute** | ❌ No resolution | ❌ No resolution | ❌ No resolution | ✅ ATTESTATION |
| **Platform Independence** | ❌ Vendor-specific | ❌ Vendor-specific | ⚠️ MCP-dependent | ✅ File-based |

**The Core Issue:** LLM agent memory is currently **mutable, unverifiable, and platform-dependent**. If an agent's memory can be altered without detection, the agent's decisions cannot be trusted.

### Why Provara for Agent Memory?

1. **Cryptographic Event Logs:** Every observation, decision, and action is signed and chained
2. **Multi-Agent Dispute Resolution:** Conflicting observations go to `contested` namespace until attested
3. **Deterministic Replay:** Given the same event log, any agent derives the same state
4. **MCP Integration:** AI agents can read/write memory via standard MCP tools

---

## Architecture Overview

### Four-Namespace Model

```
┌─────────────────────────────────────────────────────────┐
│                    Sovereign State                       │
├─────────────┬─────────────┬──────────────┬──────────────┤
│  canonical  │    local    │   contested  │   archived   │
│             │             │              │              │
│ Attested    | Unverified  │ Conflicting  │ Superseded   │
│ Truth       | Observations│ Evidence     | Beliefs      │
└─────────────┴─────────────┴──────────────┴──────────────┘
```

| Namespace | Purpose | Entry Criteria | Exit Criteria |
|-----------|---------|----------------|---------------|
| `canonical` | Accepted truth | ATTESTATION with confidence ≥0.9 | Superseded by new ATTESTATION |
| `local` | Private observations | OBSERVATION events | Promoted to canonical or contested |
| `contested` | Conflicting evidence | ≥2 OBSERVATIONs with conflicting values | Resolved by authority ATTESTATION |
| `archived` | Historical record | Superseded canonical beliefs | Permanent (never deleted) |

### Event Types for Agent Memory

| Event Type | Purpose | Payload Schema |
|------------|---------|----------------|
| `OBSERVATION` | Agent perceives something | `{subject, predicate, value, confidence}` |
| `ATTESTATION` | Agent attests to a belief | `{subject, predicate, value, actor_key_id, confidence}` |
| `RETRACTION` | Agent retracts a belief | `{subject, reason}` |
| `com.provara.timestamp_anchor` | Vault anchored to TSA | `{target_state_hash, rfc3161_tsr_b64}` |

---

## Implementation Walkthrough

### Step 1: Initialize Agent Memory Vault

```bash
# Create agent memory vault
mkdir agent_memory_vault

# Initialize with agent identity
provara init agent_memory_vault \
  --actor "alice_agent_v1" \
  --private-keys alice_agent_keys.json

# Output:
# [bootstrap] Root key: bp1_alice_key_abc123
# [bootstrap] Bootstrap complete. UID=alice_agent_memory
```

### Step 2: Agent Makes an Observation

**Scenario:** Alice-Bot observes a stock price signal.

```bash
# Observation event
cat > alice_observation_001.json << 'EOF'
{
  "type": "OBSERVATION",
  "namespace": "local",
  "actor": "alice_agent_v1",
  "payload": {
    "subject": "market_signal",
    "predicate": "observed",
    "value": {
      "ticker": "AAPL",
      "signal_type": "BREAKOUT_ABOVE_RESISTANCE",
      "price_at_signal": 185.50,
      "resistance_level": 185.00,
      "volume_ratio": 2.3,
      "confidence": 0.75,
      "data_source": "polygon.io",
      "timestamp_logical": "2026-02-17T14:30:00Z"
    },
    "confidence": 0.75
  }
}
EOF

# Append to vault
provara append agent_memory_vault \
  --data-file alice_observation_001.json \
  --keyfile alice_agent_keys.json

# Expected output:
# [append] Event appended successfully
# [append] Event ID: evt_alice_obs_001
# [append] Namespace: local
```

### Step 3: Second Agent Makes Conflicting Observation

**Scenario:** Bob-Bot observes the same market but reaches a different conclusion.

```bash
# Initialize Bob's agent vault (separate identity)
provara init bob_agent_memory \
  --actor "bob_agent_v1" \
  --private-keys bob_agent_keys.json

# Bob's conflicting observation
cat > bob_observation_001.json << 'EOF'
{
  "type": "OBSERVATION",
  "namespace": "local",
  "actor": "bob_agent_v1",
  "payload": {
    "subject": "market_signal",
    "predicate": "observed",
    "value": {
      "ticker": "AAPL",
      "signal_type": "FALSE_BREAKOUT",
      "price_at_signal": 185.50,
      "resistance_level": 185.00,
      "volume_ratio": 2.3,
      "confidence": 0.80,
      "data_source": "alpaca.markets",
      "timestamp_logical": "2026-02-17T14:30:00Z",
      "reasoning": "Volume insufficient for confirmed breakout"
    },
    "confidence": 0.80
  }
}
EOF

# Append to Bob's vault
provara append bob_agent_memory \
  --data-file bob_observation_001.json \
  --keyfile bob_agent_keys.json
```

### Step 4: Sync Vaults to Detect Conflict

```bash
# Create shared vault for multi-agent memory
mkdir shared_memory_vault
provara init shared_memory_vault \
  --actor "shared_memory_coordinator" \
  --private-keys shared_keys.json

# Merge Alice's observations
provara merge shared_memory_vault \
  --remote ../alice_agent_memory \
  --strategy union

# Merge Bob's observations
provara merge shared_memory_vault \
  --remote ../bob_agent_memory \
  --strategy union

# Replay to see derived state
provara replay shared_memory_vault
```

**Expected State:**
```json
{
  "canonical": {},
  "local": {
    "market_signal:AAPL:alice_agent_v1": {
      "value": {"signal_type": "BREAKOUT_ABOVE_RESISTANCE"},
      "confidence": 0.75,
      "actor": "alice_agent_v1"
    },
    "market_signal:AAPL:bob_agent_v1": {
      "value": {"signal_type": "FALSE_BREAKOUT"},
      "confidence": 0.80,
      "actor": "bob_agent_v1"
    }
  },
  "contested": {
    "market_signal:AAPL": {
      "conflicting_values": [
        {"actor": "alice_agent_v1", "value": "BREAKOUT_ABOVE_RESISTANCE"},
        {"actor": "bob_agent_v1", "value": "FALSE_BREAKOUT"}
      ],
      "resolution_status": "UNRESOLVED"
    }
  },
  "archived": {}
}
```

### Step 5: Oracle Attestation Resolves Conflict

**Scenario:** A trusted oracle (e.g., premium data source) attests to the correct interpretation.

```bash
# Initialize oracle identity
provara init oracle_memory \
  --actor "market_oracle_v1" \
  --private-keys oracle_keys.json

# Oracle attestation
cat > oracle_attestation_001.json << 'EOF'
{
  "type": "ATTESTATION",
  "namespace": "canonical",
  "actor": "market_oracle_v1",
  "payload": {
    "subject": "market_signal:AAPL",
    "predicate": "attested",
    "value": {
      "signal_type": "FALSE_BREAKOUT",
      "reasoning": "Volume ratio < 3.0 indicates insufficient conviction",
      "supporting_data": {
        "avg_volume_20d": 50000000,
        "signal_volume": 65000000,
        "required_ratio": 3.0,
        "actual_ratio": 1.3
      }
    },
    "actor_key_id": "bp1_oracle_key_xyz789",
    "confidence": 0.95
  }
}
EOF

# Append attestation to shared vault
provara append shared_memory_vault \
  --data-file oracle_attestation_001.json \
  --keyfile oracle_keys.json

# Replay to see resolved state
provara replay shared_memory_vault
```

**Expected State After Resolution:**
```json
{
  "canonical": {
    "market_signal:AAPL": {
      "value": {"signal_type": "FALSE_BREAKOUT"},
      "confidence": 0.95,
      "attested_by": "market_oracle_v1"
    }
  },
  "local": {},
  "contested": {},
  "archived": {
    "market_signal:AAPL": {
      "superseded_values": [
        {"actor": "alice_agent_v1", "value": "BREAKOUT_ABOVE_RESISTANCE"},
        {"actor": "bob_agent_v1", "value": "FALSE_BREAKOUT"}
      ],
      "superseded_at": "2026-02-17T15:00:00Z"
    }
  }
}
```

---

## MCP Server Integration

### Setup Provara MCP Server

```bash
# Start MCP server with SSE transport
python tools/mcp_server/server.py \
  --transport http \
  --host 0.0.0.0 \
  --port 8765 \
  --vault-path ./agent_memory_vault \
  --keyfile alice_agent_keys.json
```

### Claude Desktop Configuration

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "provara-memory": {
      "type": "http",
      "url": "http://localhost:8765/sse"
    }
  }
}
```

### Available MCP Tools

| Tool | Description | Input Schema |
|------|-------------|--------------|
| `append_event` | Append event to vault | `{type, namespace, payload}` |
| `query_timeline` | Query events by criteria | `{subject, predicate, date_range}` |
| `snapshot_belief` | Get current canonical state | `{subject}` |
| `list_conflicts` | List contested beliefs | `{}` |
| `verify_chain` | Verify vault integrity | `{}` |

### Example: Agent Queries Its Memory

```python
# Agent queries its memory before making a decision
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async with stdio_client(server_params) as (read, write):
    async with ClientSession(read, write) as session:
        # Query past observations about AAPL
        result = await session.call_tool(
            "query_timeline",
            arguments={
                "subject": "market_signal:AAPL",
                "date_range": {"start": "2026-02-17", "end": "2026-02-17"}
            }
        )
        
        # Result: List of observations with confidence scores
        for obs in result.content:
            print(f"Observation: {obs['value']}")
            print(f"Confidence: {obs['confidence']}")
            print(f"Actor: {obs['actor']}")
```

---

## Expected Vault State Evolution

| Step | Events | canonical | local | contested | archived |
|------|--------|-----------|-------|-----------|----------|
| Init | 1 | {} | {} | {} | {} |
| Alice observes | 2 | {} | {AAPL: breakout} | {} | {} |
| Bob observes | 3 | {} | {AAPL: breakout, AAPL: false} | {AAPL} | {} |
| Oracle attests | 4 | {AAPL: false} | {} | {} | {AAPL: conflicting} |

---

## What Could Go Wrong

### 1. Rogue Agent Injection

**Scenario:** Malicious agent injects false observations.

**Impact:** Contaminates shared memory.

**Mitigation:**
- Require attestation from trusted oracles for canonical beliefs
- Confidence thresholds (e.g., canonical requires ≥0.9)
- Reputation system for actors (future extension)

**Detection:**
```bash
# List all contested beliefs
provara replay shared_memory_vault | jq '.contested'

# Review conflicting actors
provara replay shared_memory_vault | jq '.contested[].conflicting_values[].actor'
```

### 2. Memory Bloat

**Scenario:** Agent accumulates millions of observations.

**Impact:** Replay becomes slow, storage costs increase.

**Mitigation:**
- Checkpoint system for fast state materialization
- Archive old observations (keep hash chain, compress payload)
- TTL-based retention policy

**Recovery:**
```bash
# Create checkpoint for fast replay
provara checkpoint agent_memory_vault --keyfile keys.json

# Future replays start from checkpoint
```

### 3. Key Compromise

**Scenario:** Agent's private key is stolen.

**Impact:** Attacker can forge observations from that agent.

**Mitigation:**
- Key rotation with `KEY_REVOCATION` + `KEY_PROMOTION` events
- Hardware security modules for key storage
- Multi-sig for high-stakes attestations (future)

**Response:**
```bash
# Revoke compromised key
cat > key_revocation.json << 'EOF'
{
  "type": "KEY_REVOCATION",
  "actor": "alice_agent_v1",
  "payload": {
    "revoked_key_id": "bp1_compromised_key",
    "reason": "KEY_COMPROMISE_DETECTED",
    "incident_id": "SEC-2026-0042"
  }
}
EOF

provara append agent_memory_vault \
  --data-file key_revocation.json \
  --keyfile alice_agent_keys.json
```

### 4. Context Window Independence

**Scenario:** Agent's context window is limited, but vault is large.

**Impact:** Agent cannot access full memory in single prompt.

**Mitigation:**
- Query-based retrieval (RAG over Provara vault)
- Summarization checkpoints (periodic state summaries)
- Hierarchical memory (recent events detailed, old events summarized)

---

## Comparison: Provara vs Alternatives

| Property | Provara | Vector DB | MCP Memory | Plain Files |
|----------|---------|-----------|------------|-------------|
| **Tamper Evidence** | ✅ Hash chain | ❌ Mutable | ❌ Mutable | ❌ Mutable |
| **Signatures** | ✅ Ed25519 | ❌ None | ❌ None | ❌ None |
| **Dispute Resolution** | ✅ 4 namespaces | ❌ Last-write-wins | ❌ Last-write-wins | ❌ Manual |
| **Deterministic Replay** | ✅ Yes | ❌ Approximate | ❌ Approximate | ⚠️ If structured |
| **Multi-Agent** | ✅ Built-in | ⚠️ Custom logic | ⚠️ Custom logic | ❌ Manual |
| **Offline** | ✅ File-based | ⚠️ DB required | ❌ Server required | ✅ Yes |
| **50-Year Readability** | ✅ RFC 8785 JSON | ❌ Vendor-specific | ⚠️ MCP-dependent | ⚠️ If structured |

---

## Next Steps

1. **Production Deployment:**
   - Set up MCP server for your agent framework
   - Implement observation schemas for your domain
   - Configure checkpoint schedule

2. **Advanced Patterns:**
   - Multi-agent governance (voting on contested beliefs)
   - Cross-vault sync (agents on different devices)
   - Oracle network (multiple attesters)

3. **Research Directions:**
   - Confidence aggregation algorithms
   - Reputation systems for actors
   - Memory compaction strategies

---

**See Also:**
- [SaaS Audit Log Cookbook](./audit_log_saas.md) — Compliance use cases
- [Supply Chain Cookbook](./supply_chain.md) — Multi-organization patterns
- [MCP Server Guide](../docs/MCP_SERVER.md) — MCP integration details
- [Provara Protocol Spec](../PROTOCOL_PROFILE.txt) — Cryptographic foundations
