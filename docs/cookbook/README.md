# Provara Cookbook

Real-world recipes for using Provara in production systems.

---

## Available Recipes

| Recipe | Use Case | Time | Difficulty |
|--------|----------|------|------------|
| **[SaaS Audit Log](./audit_log_saas.md)** | Tamper-evident audit trail for SaaS applications | 15 min | Intermediate |
| **[Legal Discovery](./legal_discovery.md)** | Evidence chain for legal proceedings | 20 min | Advanced |
| **[AI Agent Memory](./ai_agent_memory.md)** | Verifiable memory with dispute resolution | 25 min | Advanced |
| **[Supply Chain Provenance](./supply_chain.md)** | Multi-organization product journey tracking | 30 min | Advanced |

---

## Common Patterns

All recipes follow these patterns:

### 1. Initialize Vault

```bash
provara init <vault_path> \
  --actor "<actor_name>" \
  --private-keys <keyfile>.json
```

### 2. Append Events

```bash
provara append <vault_path> \
  --data-file <event>.json \
  --keyfile <keyfile>.json
```

### 3. Verify Integrity

```bash
provara verify <vault_path>
```

### 4. Replay State

```bash
provara replay <vault_path>
```

---

## Event Schema Reference

### OBSERVATION Event

```json
{
  "type": "OBSERVATION",
  "namespace": "local",
  "actor": "<actor_name>",
  "payload": {
    "subject": "<subject>",
    "predicate": "<predicate>",
    "value": {...},
    "confidence": 0.0-1.0
  }
}
```

### ATTESTATION Event

```json
{
  "type": "ATTESTATION",
  "namespace": "canonical",
  "actor": "<actor_name>",
  "payload": {
    "subject": "<subject>",
    "predicate": "attested",
    "value": {...},
    "actor_key_id": "bp1_...",
    "confidence": 0.9-1.0
  }
}
```

---

## Namespace Model

| Namespace | Purpose | Entry Criteria | Exit Criteria |
|-----------|---------|----------------|---------------|
| `canonical` | Attested truth | ATTESTATION ≥0.9 confidence | Superseded → `archived` |
| `local` | Private observations | OBSERVATION events | Promoted or contested |
| `contested` | Conflicting evidence | ≥2 conflicting OBSERVATIONs | Resolved → `archived` |
| `archived` | Historical record | Superseded beliefs | Permanent |

---

## Best Practices

### 1. Key Management

- Store private keys in secure enclave or HSM
- Rotate keys periodically via `KEY_REVOCATION` + `KEY_PROMOTION`
- Export backup keys to offline storage

### 2. Timestamp Anchoring

```bash
# Anchor vault state to independent TSA
provara timestamp <vault_path> \
  --keyfile <keyfile>.json \
  --tsa https://freetsa.org/tsr
```

### 3. Checkpointing

```bash
# Create state snapshot for fast replay
provara checkpoint <vault_path> \
  --keyfile <keyfile>.json
```

### 4. Backup

```bash
# Create verified backup
provara backup <vault_path> \
  --output backup_$(date +%Y%m%d).zip
```

---

## Troubleshooting

### "Invalid signature" Error

**Cause:** Wrong key or tampered event  
**Fix:** Verify you're using the correct keyfile. Check event was not modified after signing.

### "Broken causal chain" Error

**Cause:** Events out of order or `prev_event_hash` mismatch  
**Fix:** Ensure events are appended in causal order. Do not manually edit `events.ndjson`.

### "Key not found in registry" Error

**Cause:** Signing with a key not in `keys.json`  
**Fix:** Register the key via `KEY_PROMOTION` event or use the correct keyfile.

---

## Getting Help

- **Documentation:** https://provara.dev/docs
- **GitHub Issues:** https://github.com/provara-protocol/provara/issues
- **Protocol Spec:** [`PROTOCOL_PROFILE.txt`](../PROTOCOL_PROFILE.txt)

---

**See Also:**
- [Provara Quickstart](../QUICKSTART.md)
- [MCP Server Guide](../docs/MCP_SERVER.md)
- [Position Paper: Cryptographic Event Logs for LLM Agent Memory](../content/papers/cryptographic-event-logs-for-llm-agent-memory.md)
