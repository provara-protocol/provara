# Provara + AgentGuard Integration Study

**Date:** 2026-02-18  
**Status:** Integration proposal  
**Related:** [AgentGuard Repository](https://github.com/Sagar-Gogineni/agentguard)

---

## Executive Summary

AgentGuard is an EU AI Act compliance middleware that provides audit logging for AI agents. Provara is a self-sovereign cryptographic event log protocol with tamper-evident audit trails.

**Integration value:** AgentGuard + Provara = tamper-evident EU AI Act compliance. Same audit events, cryptographic proof they haven't been altered.

---

## 1. What AgentGuard Does

### 1.1 Overview

AgentGuard ([GitHub](https://github.com/Sagar-Gogineni/agentguard)) is a compliance middleware for AI agents, designed to satisfy EU AI Act requirements:

| EU AI Act Article | Requirement | AgentGuard Coverage |
|-------------------|-------------|---------------------|
| **Article 12** | Record-keeping | ✅ Audit event logging |
| **Article 14** | Human oversight | ✅ Decision logging |
| **Article 16** | Accuracy, robustness, cybersecurity | ✅ Security monitoring |
| **Article 50** | Transparency obligations | ✅ Disclosure logging |

### 1.2 Architecture

```
AI Agent → AgentGuard Middleware → SQLite/JSONL Backend
```

**AgentGuard captures:**
- Decision events (what action was taken)
- Rationale (why the action was chosen)
- Risk assessments (safety tier evaluation)
- Human interventions (oversight events)
- System state (context at decision time)

### 1.3 Current Backend

AgentGuard uses:
- **SQLite** for structured event storage
- **JSONL** for log export

**Limitations:**
- SQLite is mutable (rows can be modified without detection)
- JSONL has no integrity chain (lines can be inserted/deleted)
- No cryptographic signatures (events are not author-attributed)
- No tamper evidence (modifications leave no trace)

---

## 2. Why Provara is a Better Backend

### 2.1 Cryptographic Guarantees

| Property | SQLite/JSONL | Provara |
|----------|--------------|---------|
| **Tamper evidence** | ❌ No | ✅ Hash chain + Merkle tree |
| **Author attribution** | ❌ No | ✅ Ed25519 signatures |
| **Append-only** | ⚠️ By convention | ✅ By cryptography |
| **Content addressing** | ❌ No | ✅ Event IDs are content hashes |
| **Long-term integrity** | ⚠️ Depends on operator | ✅ Self-verifying |
| **Cross-party verification** | ❌ Requires trust | ✅ Trustless verification |

### 2.2 Compliance Benefits

**EU AI Act Article 12 (Record-keeping):**
- Provara provides **cryptographically signed** records
- Records are **self-verifying** (no trusted operator required)
- **50-year readability** guarantee (plain text NDJSON)

**EU AI Act Article 14 (Human Oversight):**
- Human interventions are **signed events** (non-repudiable)
- Oversight decisions are **timestamped** and **chained**
- **Audit trail** cannot be silently modified

**EU AI Act Article 50 (Transparency):**
- AI-generated content decisions are **cryptographically attributed**
- Disclosure logs are **tamper-evident**
- Third parties can **independently verify** compliance

---

## 3. Integration Architecture

### 3.1 High-Level Design

```
┌─────────────────────────────────────────────────────────────┐
│  AI Agent                                                   │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  AgentGuard Middleware                                      │
│  - EU AI Act compliance logic                               │
│  - Risk assessment                                          │
│  - Human oversight routing                                  │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  Provara Vault Backend                                      │
│  - Ed25519 signed events                                    │
│  - Per-actor causal chains                                  │
│  - Tamper-evident audit log                                 │
│  - Merkle tree integrity                                    │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 Event Mapping

| AgentGuard Event | Provara Event Type | Payload Fields |
|------------------|-------------------|----------------|
| `decision_made` | `agentguard.decision` | `action`, `rationale`, `risk_level` |
| `human_intervention` | `agentguard.oversight` | `intervention_type`, `operator_id`, `outcome` |
| `risk_assessment` | `agentguard.risk_eval` | `risk_score`, `factors`, `mitigation` |
| `transparency_disclosure` | `agentguard.disclosure` | `disclosure_type`, `recipient`, `content` |

---

## 4. Provara as an AgentGuard Backend

### 4.1 Interface Requirements

AgentGuard expects a backend implementing:

```python
class AuditBackend(Protocol):
    def log_event(self, event_type: str, payload: dict) -> str:
        """Log an audit event. Returns event ID."""
        ...

    def query_events(
        self,
        event_type: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> List[dict]:
        """Query events by type and time range."""
        ...

    def export_audit_trail(self, output_path: str) -> None:
        """Export full audit trail for compliance review."""
        ...

    def verify_integrity(self) -> bool:
        """Verify audit trail integrity."""
        ...
```

### 4.2 Provara Adapter Implementation

```python
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Dict, Any

from provara.bootstrap_v0 import bootstrap_backpack
from provara.crypto_shred import create_encrypted_vault, create_encrypted_payload
from provara.sync_v0 import load_events, write_events
from provara.backpack_signing import load_private_key_b64, sign_event
from provara.canonical_json import canonical_hash
from provara.crypto_shred import PrivacyKeyStore


class ProvaraAuditBackend:
    """Provara backend for AgentGuard compliance logging."""

    def __init__(
        self,
        vault_path: Path,
        keyfile_path: Path,
        actor_name: str,
        encrypted: bool = False,
    ):
        self.vault_path = vault_path
        self.keyfile_path = keyfile_path
        self.actor_name = actor_name
        self.encrypted = encrypted

        # Initialize vault if needed
        if not vault_path.exists():
            if encrypted:
                create_encrypted_vault(vault_path, actor_name)
            bootstrap_backpack(vault_path, actor=actor_name, quiet=True)

        # Load signing keys
        self.keys_data = self._load_keys()
        self.key_id = list(self.keys_data.keys())[0]
        self.private_key = load_private_key_b64(self.keys_data[self.key_id])

        # Initialize privacy store if encrypted
        self.key_store = PrivacyKeyStore(vault_path) if encrypted else None

    def _load_keys(self) -> Dict[str, str]:
        """Load private keys from file."""
        import json
        data = json.loads(self.keyfile_path.read_text())
        if "keys" in data and isinstance(data["keys"], list):
            return {k["key_id"]: k["private_key_b64"] for k in data["keys"]}
        return {k: v for k, v in data.items() if k != "WARNING"}

    def log_event(self, event_type: str, payload: dict) -> str:
        """Log an audit event with cryptographic signature."""
        events_path = self.vault_path / "events" / "events.ndjson"
        all_events = load_events(events_path)

        # Get prev_event_hash for this actor
        actor_events = [e for e in all_events if e.get("actor") == self.actor_name]
        prev_hash = actor_events[-1]["event_id"] if actor_events else None

        # Prepare event
        event = {
            "type": f"agentguard.{event_type}",
            "actor": self.actor_name,
            "prev_event_hash": prev_hash,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "payload": payload,
        }

        # Encrypt payload if vault is encrypted
        if self.encrypted and self.key_store:
            event["data_encrypted"] = True
            event["payload"] = create_encrypted_payload(
                payload, self.key_store, self.actor_name
            )

        # Compute event_id and sign
        eid_hash = canonical_hash(event)
        event["event_id"] = f"evt_{eid_hash[:24]}"
        signed_event = sign_event(event, self.private_key, self.key_id)

        # Append to log
        all_events.append(signed_event)
        write_events(events_path, all_events)

        return signed_event["event_id"]

    def query_events(
        self,
        event_type: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> List[dict]:
        """Query events by type and time range."""
        events_path = self.vault_path / "events" / "events.ndjson"
        all_events = load_events(events_path)

        results = []
        for event in all_events:
            # Filter by type
            if event_type and not event.get("type", "").startswith(f"agentguard.{event_type}"):
                continue

            # Filter by time
            event_time = datetime.fromisoformat(event.get("timestamp_utc", ""))
            if start_time and event_time < start_time:
                continue
            if end_time and event_time > end_time:
                continue

            results.append(event)

        return results

    def export_audit_trail(self, output_path: str) -> None:
        """Export full audit trail for compliance review."""
        from provara.export import export_vault_scitt_compat

        export_vault_scitt_compat(
            vault_path=self.vault_path,
            output_dir=Path(output_path),
        )

    def verify_integrity(self) -> bool:
        """Verify audit trail integrity."""
        import sys
        sys.path.insert(0, str(self.vault_path.parent / "tests"))
        from backpack_compliance_v1 import TestBackpackComplianceV1
        import unittest

        TestBackpackComplianceV1.backpack_path = str(self.vault_path)
        suite = unittest.TestLoader().loadTestsFromTestCase(TestBackpackComplianceV1)
        runner = unittest.TextTestRunner(verbosity=0)
        result = runner.run(suite)

        return result.wasSuccessful()
```

### 4.3 Usage Example

```python
from pathlib import Path
from agentguard import AgentGuardMiddleware
from provara_adapter import ProvaraAuditBackend

# Initialize Provara backend
backend = ProvaraAuditBackend(
    vault_path=Path("/var/agentguard/vault"),
    keyfile_path=Path("/var/agentguard/keys.json"),
    actor_name="agent_001",
    encrypted=True,  # GDPR-compliant crypto-shredding
)

# Initialize AgentGuard with Provara backend
middleware = AgentGuardMiddleware(
    audit_backend=backend,
    risk_threshold=0.7,
    require_human_oversight=True,
)

# Use in AI agent
@middleware.intercept
async def agent_decision(context):
    # Agent logic here
    # Events are automatically logged to Provara vault
    return action
```

---

## 5. Benefits of Integration

### 5.1 For AI Developers

- **Drop-in replacement:** Same interface as SQLite backend
- **Stronger compliance:** Cryptographic proof of audit integrity
- **GDPR compliance:** Crypto-shredding for right to erasure
- **Long-term preservation:** 50-year readability guarantee

### 5.2 For Auditors

- **Trustless verification:** Verify compliance without trusting operator
- **Tamper evidence:** Any modification is cryptographically detectable
- **Complete history:** Append-only log preserves full audit trail
- **Third-party attestation:** Events are signed by agent/operator

### 5.3 For Regulators

- **Standardized format:** NDJSON + cryptographic signatures
- **Cross-jurisdiction:** Provara is language-agnostic and portable
- **Self-verifying:** No need to trust the audited entity
- **Legal admissibility:** Cryptographic signatures support non-repudiation

---

## 6. Implementation Roadmap

### Phase 1: Core Integration (Week 1-2)

- [ ] Implement `ProvaraAuditBackend` adapter
- [ ] Add AgentGuard event type mappings
- [ ] Write integration tests
- [ ] Document setup process

### Phase 2: Encryption Support (Week 3-4)

- [ ] Enable encrypted vaults for GDPR compliance
- [ ] Implement crypto-shredding workflow
- [ ] Add key management documentation
- [ ] Test GDPR erasure requests

### Phase 3: Production Hardening (Week 5-6)

- [ ] Performance optimization (batch signing, async I/O)
- [ ] Monitoring and alerting integration
- [ ] Backup and recovery procedures
- [ ] Security audit

### Phase 4: Certification (Week 7-8)

- [ ] EU AI Act compliance assessment
- [ ] Third-party security audit
- [ ] Documentation for auditors
- [ ] Reference deployment

---

## 7. Pitch

**AgentGuard + Provara = Tamper-Evident EU AI Act Compliance**

AgentGuard provides the compliance logic. Provara provides the cryptographic audit trail. Together, they offer:

- **Same audit events** that AgentGuard already defines
- **Cryptographic proof** that events haven't been altered
- **GDPR compliance** via crypto-shredding
- **50-year preservation** in plain text format
- **Trustless verification** for third-party auditors

**No more "trust us, the logs are accurate."** Now you can prove it.

---

## 8. References

- [AgentGuard Repository](https://github.com/Sagar-Gogineni/agentguard)
- [EU AI Act Text](https://artificialintelligenceact.eu/)
- [Provara Protocol](https://github.com/provara-protocol/provara)
- [Crypto-Shredding Spec](../docs/CRYPTO_SHREDDING.md)
- [IETF Internet-Draft](../docs/draft-hunt-provara-protocol-00.md)

---

*This integration study is part of Provara v1.0. For implementation questions, open a GitHub issue.*
