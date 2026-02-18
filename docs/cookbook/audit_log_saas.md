# Cookbook: SaaS Audit Log with Provara

**Use Case:** Tamper-evident audit trail for a SaaS application  
**Time to Complete:** 15 minutes  
**Difficulty:** Intermediate

---

## Problem Statement

### Why Provara Instead of a Database Audit Table?

Traditional database audit tables have critical weaknesses:

| Property | Database Audit Table | Provara Vault |
|----------|---------------------|---------------|
| **Tamper Evidence** | Admin can modify/delete rows silently | Cryptographically impossible without detection |
| **Chain of Custody** | Relies on trust in DBA | SHA-256 hash chain proves continuity |
| **Non-Repudiation** | No cryptographic signatures | Ed25519 signatures on every event |
| **Offline Operation** | Requires DB connection | File-based, works offline |
| **50-Year Readability** | Schema migrations, vendor lock-in | UTF-8 JSON, open spec |
| **Multi-Party Verification** | Single point of trust | Any party can independently verify |

**When to use Provara:**
- Compliance requirements (SOC 2, HIPAA, GDPR accountability)
- High-stakes actions (financial transactions, access control changes)
- Multi-tenant systems where tenants don't trust each other
- Legal discovery preparedness

**When NOT to use Provara:**
- High-frequency logging (>1000 events/second)
- Internal debugging logs
- Temporary/ephemeral state tracking

---

## Event Schema

### Core Event Types

```json
{
  "type": "OBSERVATION",
  "namespace": "local",
  "actor": "app_server_01",
  "actor_key_id": "bp1_abc123...",
  "timestamp_utc": "2026-02-17T14:30:00Z",
  "prev_event_hash": "evt_previous...",
  "payload": {
    "subject": "user_action",
    "predicate": "performed",
    "value": {
      "user_id": "user_12345",
      "action": "UPDATE_RECORD",
      "resource_type": "customer_profile",
      "resource_id": "cust_67890",
      "fields_modified": ["email", "phone"],
      "ip_address": "192.168.1.100",
      "user_agent": "Mozilla/5.0..."
    },
    "confidence": 1.0
  }
}
```

### Event Type Catalog

| Event Type | Use Case | Payload Structure |
|------------|----------|-------------------|
| `OBSERVATION` | User actions, system events | `{subject, predicate, value, confidence}` |
| `ATTESTATION` | Manager approval, compliance sign-off | `{subject, predicate, value, actor_key_id, confidence}` |
| `KEY_PROMOTION` | Key rotation (new admin key) | `{public_key, prev_key_id}` |
| `KEY_REVOCATION` | Key compromise, employee departure | `{revoked_key_id, reason}` |

---

## Implementation Walkthrough

### Step 1: Initialize the Audit Vault

```bash
# Create vault directory
mkdir audit_vault

# Initialize with app identity
provara init audit_vault \
  --actor "acme_corp_audit_system" \
  --private-keys audit_keys.json

# Output:
# [bootstrap] Generating Ed25519 root keypair...
# [bootstrap] Creating directory structure...
# [bootstrap] Writing genesis.json...
# [bootstrap] Writing keys.json...
# [bootstrap] Bootstrap complete. UID=<unique_id>
# [bootstrap] Root key: bp1_2a8f9c3e1b7d4056
```

**Vault Structure Created:**
```
audit_vault/
├── identity/
│   ├── keys.json          # Public keys registry
│   ├── genesis.json       # Genesis event
│   └── policy/
│       ├── safety.ndjson  # Safety constraints
│       └── retention.ndjson
├── events/
│   └── events.ndjson      # Append-only event log
├── state/
│   └── state.json         # Current derived state
└── manifest.json          # Merkle root + signatures
```

### Step 2: Integrate with Application Write Path

**Python Integration Example:**

```python
import json
import subprocess
from pathlib import Path
from datetime import datetime, timezone

class ProvaraAuditLogger:
    def __init__(self, vault_path: str, keyfile: str, actor: str):
        self.vault_path = Path(vault_path)
        self.keyfile = Path(keyfile)
        self.actor = actor
    
    def log_action(self, user_id: str, action: str, resource_type: str, 
                   resource_id: str, fields_modified: list, 
                   ip_address: str, user_agent: str) -> str:
        """
        Log a user action to the Provara vault.
        Returns the event_id for reference.
        """
        event_payload = {
            "type": "OBSERVATION",
            "namespace": "local",
            "actor": self.actor,
            "payload": {
                "subject": "user_action",
                "predicate": "performed",
                "value": {
                    "user_id": user_id,
                    "action": action,
                    "resource_type": resource_type,
                    "resource_id": resource_id,
                    "fields_modified": fields_modified,
                    "ip_address": ip_address,
                    "user_agent": user_agent
                },
                "confidence": 1.0
            }
        }
        
        # Write event to temp file
        event_file = Path("/tmp/audit_event.json")
        with open(event_file, "w") as f:
            json.dump(event_payload, f, indent=2)
        
        # Append to vault
        result = subprocess.run([
            "provara", "append", str(self.vault_path),
            "--data-file", str(event_file),
            "--keyfile", str(self.keyfile)
        ], capture_output=True, text=True)
        
        if result.returncode != 0:
            raise Exception(f"Append failed: {result.stderr}")
        
        # Extract event_id from output
        for line in result.stdout.split("\n"):
            if "Event ID:" in line:
                return line.split("Event ID:")[1].strip()
        
        return None

# Usage in your application
audit = ProvaraAuditLogger(
    vault_path="audit_vault",
    keyfile="audit_keys.json",
    actor="app_server_01"
)

# Log a critical action
event_id = audit.log_action(
    user_id="user_12345",
    action="UPDATE_RECORD",
    resource_type="customer_profile",
    resource_id="cust_67890",
    fields_modified=["email", "phone"],
    ip_address="192.168.1.100",
    user_agent="Mozilla/5.0..."
)
print(f"Audit event logged: {event_id}")
```

### Step 3: Append Events via CLI

```bash
# Create event JSON file
cat > user_action.json << 'EOF'
{
  "type": "OBSERVATION",
  "namespace": "local",
  "actor": "app_server_01",
  "payload": {
    "subject": "user_action",
    "predicate": "performed",
    "value": {
      "user_id": "user_12345",
      "action": "DELETE_RECORD",
      "resource_type": "customer_profile",
      "resource_id": "cust_67890",
      "deleted_by": "admin_001",
      "reason": "GDPR erasure request",
      "erasure_request_id": "gdpr_2026_0042"
    },
    "confidence": 1.0
  }
}
EOF

# Append to vault
provara append audit_vault \
  --data-file user_action.json \
  --keyfile audit_keys.json

# Expected output:
# [append] Event appended successfully
# [append] Event ID: evt_8a3f2c1b9e7d4056
# [append] Actor: app_server_01
# [append] Type: OBSERVATION
# [append] Vault events: 2
```

### Step 4: Add Compliance Attestation

For high-stakes actions, require manager attestation:

```bash
# Manager attestation event
cat > manager_attestation.json << 'EOF'
{
  "type": "ATTESTATION",
  "namespace": "local",
  "actor": "compliance_manager_01",
  "payload": {
    "subject": "user_action",
    "predicate": "attested",
    "value": {
      "attested_event_id": "evt_8a3f2c1b9e7d4056",
      "attestation_type": "GDPR_ERASURE_APPROVED",
      "approver_id": "manager_789",
      "approval_timestamp": "2026-02-17T15:00:00Z"
    },
    "actor_key_id": "bp1_manager_key...",
    "confidence": 1.0
  }
}
EOF

# Append attestation
provara append audit_vault \
  --data-file manager_attestation.json \
  --keyfile audit_keys.json
```

### Step 5: Verify Chain Integrity

```bash
# Verify entire vault
provara verify audit_vault

# Expected output:
# [verify] Checking causal chains...
# [verify] Checking signatures...
# [verify] Checking Merkle root...
# [verify] Vault integrity: VALID
# [verify] Events verified: 3
# [verify] Actors: 2
# [verify] Chain integrity: OK
```

---

## Compliance Export

### Generate Forensic Bundle

```bash
# Create checkpoint (state snapshot)
provara checkpoint audit_vault \
  --keyfile audit_keys.json

# Generate manifest
provara manifest audit_vault

# Create backup with verification
provara backup audit_vault \
  --output audit_vault_backup_$(date +%Y%m%d).zip

# Verify backup
provara verify audit_vault_backup_$(date +%Y%m%d).zip
```

### Export for Auditor

```bash
# Replay to show current state
provara replay audit_vault > audit_state_$(date +%Y%m%d).json

# The output includes:
# - All events in causal order
# - Current state hash
# - Merkle root
# - All actor public keys
```

**Auditor Verification Commands:**

```bash
# Auditor receives: audit_vault_backup_20260217.zip
# They run:

provara verify audit_vault_backup_20260217.zip
provara replay audit_vault_backup_20260217.zip

# If both pass, the audit trail is cryptographically sound.
```

---

## Expected Vault State

### After Step 1 (Init)
```
Events: 1 (genesis)
Actors: 1 (acme_corp_audit_system)
State Hash: <computed>
Merkle Root: <computed>
```

### After Step 3 (First User Action)
```
Events: 2 (genesis + 1 action)
Actors: 1
State Hash: <updated>
Merkle Root: <updated>
```

### After Step 4 (Attestation)
```
Events: 3 (genesis + 1 action + 1 attestation)
Actors: 2 (app_server_01, compliance_manager_01)
State Hash: <updated>
Merkle Root: <updated>
```

---

## What Could Go Wrong

### 1. Key Compromise

**Scenario:** An employee steals the audit system's private key.

**Impact:** They can forge audit events that appear legitimate.

**Mitigation:**
- Store keys in HSM or secure enclave
- Implement key rotation (`KEY_REVOCATION` + `KEY_PROMOTION` events)
- Require multi-sig for critical actions (future extension)

**Detection:**
- Monitor for unusual event patterns
- Cross-reference with application logs
- Use RFC 3161 timestamps for independent temporal proof

### 2. Vault File Deletion

**Scenario:** Attacker deletes `events.ndjson` to hide their tracks.

**Impact:** Audit trail is lost.

**Mitigation:**
- Frequent backups to immutable storage (S3 Object Lock, WORM media)
- Replicate vault to multiple locations
- Anchor Merkle roots to external timestamp authorities

**Detection:**
- Backup verification will fail
- Missing events create gaps in hash chain

### 3. Clock Skew Attack

**Scenario:** Attacker manipulates system clock to backdate events.

**Impact:** Temporal ordering becomes unreliable.

**Mitigation:**
- Use `ts_logical` field with NTP-synchronized time
- Anchor to RFC 3161 TSA for independent timestamps
- Monitor for clock anomalies in event stream

### 4. Performance Bottleneck

**Scenario:** High-volume logging (>1000 events/sec) causes latency.

**Impact:** Application performance degrades.

**Mitigation:**
- Batch events (aggregate multiple actions into single event)
- Async logging (queue events, append in batches)
- Use Provara only for high-stakes actions, not debug logs

---

## Compliance Mapping

| Regulation | Provara Feature | Evidence Produced |
|------------|-----------------|-------------------|
| **SOC 2 CC6.1** | Logical access controls | Event log of all access changes |
| **SOC 2 CC7.2** | System monitoring | Tamper-evident audit trail |
| **HIPAA 164.312(b)** | Audit controls | Cryptographic chain of custody |
| **GDPR Art. 30** | Processing records | Immutable processing log |
| **PCI DSS 10.2** | Audit trails | Non-repudiable event signatures |

---

## Next Steps

1. **Production Deployment:**
   - Set up automated backups to immutable storage
   - Configure monitoring for vault integrity checks
   - Implement key rotation policy

2. **Advanced Patterns:**
   - Multi-region vault replication
   - Cross-organization audit sharing
   - Integration with SIEM systems

3. **Legal Preparedness:**
   - Document chain of custody procedures
   - Train legal team on verification commands
   - Establish relationship with forensic experts

---

**See Also:**
- [Legal Discovery Cookbook](./legal_discovery.md) — Evidence chain for legal proceedings
- [AI Agent Memory Cookbook](./ai_agent_memory.md) — Multi-agent dispute resolution
- [RFC 3161 Timestamping](../docs/RFC3161_GUIDE.md) — Independent temporal proof
