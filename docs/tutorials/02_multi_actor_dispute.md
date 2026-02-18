# Tutorial 2: Multi-Actor Dispute Resolution

**Reading time:** 5 minutes  
**Prerequisites:** Tutorial 1 completed (or existing vault with keys)

Simulate a dispute between two actors with conflicting observations, then resolve it through attestation.

---

## The Scenario

Two actors observe the same system but report different states:
- **Alice** observes: `system.status = "healthy"`
- **Bob** observes: `system.status = "degraded"`

The Provara reducer detects the conflict and moves it to the `contested` namespace. A third actor (oracle) attests to the truth, resolving the dispute.

---

## Step 1: Set Up Two Actors

Create a vault with two actors:

```bash
# Initialize vault with Alice as root
provara init dispute_vault --actor "alice" --private-keys alice_keys.json

# Bob needs his own keypair
# In production, Bob generates this independently
python -c "
from provara import BackpackKeypair
import json
kp = BackpackKeypair.generate()
print(json.dumps({kp.key_id: kp.private_key_b64}, indent=2))
" > bob_keys.json
```

Register Bob's public key in the vault (optional but recommended):

```bash
# Add Bob's key to the vault's key registry
python -c "
import json
from pathlib import Path

# Load Bob's key
bob = json.loads(Path('bob_keys.json').read_text())
key_id = list(bob.keys())[0]

# Load vault registry
registry_path = Path('dispute_vault/identity/keys.json')
registry = json.loads(registry_path.read_text())

# Add Bob (you need his public key - derive from private)
from provara import load_public_key_b64
pub_b64 = load_public_key_b64(bob[key_id])
registry[key_id] = {
    'public_key_b64': pub_b64,
    'actor': 'bob',
    'added_at': '2026-02-18T00:00:00Z'
}

registry_path.write_text(json.dumps(registry, indent=2))
"
```

---

## Step 2: Alice's Observation

Alice observes the system as healthy:

```bash
provara append dispute_vault \
  --type OBSERVATION \
  --data '{"subject": "system", "predicate": "status", "value": "healthy"}' \
  --keyfile alice_keys.json \
  --actor "alice" \
  --confidence 1.0
```

---

## Step 3: Bob's Conflicting Observation

Bob observes the same system as degraded:

```bash
provara append dispute_vault \
  --type OBSERVATION \
  --data '{"subject": "system", "predicate": "status", "value": "degraded"}' \
  --keyfile bob_keys.json \
  --actor "bob" \
  --confidence 0.9
```

---

## Step 4: Detect the Conflict

Replay the state to see the conflict:

```bash
provara replay dispute_vault
```

**Expected output:**
```json
{
  "canonical": {},
  "local": {},
  "contested": {
    "system:status": {
      "status": "AWAITING_RESOLUTION",
      "reason": "conflicts_with_local",
      "evidence_by_value": {
        "\"healthy\"": [...],
        "\"degraded\"": [...]
      }
    }
  },
  "archived": {},
  "metadata": {
    "state_hash": "..."
  }
}
```

The conflict is now in `contested` — neither value is accepted as canonical truth.

---

## Step 5: Oracle Attestation

A trusted oracle (or governance process) investigates and attests to the truth:

```bash
# Oracle needs keys too
python -c "
from provara import BackpackKeypair
import json
kp = BackpackKeypair.generate()
print(json.dumps({kp.key_id: kp.private_key_b64}, indent=2))
" > oracle_keys.json

# Oracle attests to the true state
provara append dispute_vault \
  --type ATTESTATION \
  --data '{
    "subject": "dispute:system:status",
    "predicate": "resolved",
    "value": {
      "true_value": "degraded",
      "reason": "Oracle verified: database latency spike at 14:32 UTC",
      "evidence_ref": "monitoring_log_2026_02_18"
    }
  }' \
  --keyfile oracle_keys.json \
  --actor "oracle_node" \
  --confidence 1.0
```

---

## Step 6: Replay After Resolution

```bash
provara replay dispute_vault
```

The reducer processes the ATTESTATION and moves the resolved value to `canonical`:

```json
{
  "canonical": {
    "system:status": "degraded"
  },
  "contested": {},
  "metadata": {
    "state_hash": "a3f8b2c9..."
  }
}
```

---

## What Just Happened

1. **Conflict Detection:** The reducer detected two OBSERVATIONs with the same subject:predicate but different values
2. **Namespace Shift:** Conflicting claims moved from `local` to `contested`
3. **Attestation Resolution:** An ATTESTATION event (higher epistemic status) resolved the dispute
4. **State Update:** The attested value became canonical truth

---

## Key Concepts

| Namespace | Purpose |
|-----------|---------|
| **canonical** | Accepted institutional truth |
| **local** | Uncontested observations |
| **contested** | Conflicting claims awaiting resolution |
| **archived** | Superseded or retracted claims |

**Epistemic Hierarchy:**
```
ATTESTATION > OBSERVATION
```

An ATTESTATION from a trusted authority can resolve OBSERVATION conflicts.

---

## Real-World Use Cases

- **Supply Chain:** Two sensors report different temperatures → quality oracle attests
- **Financial Data:** Conflicting price feeds → exchange oracle resolves
- **AI Agents:** Two agents disagree on state → governance vote attests
- **Legal Evidence:** Conflicting witness statements → judge's ruling attests

---

## Next Steps

- **Tutorial 3:** Checkpoint & Query — checkpoint a 1000-event vault, query by actor/date range
- **Tutorial 4:** MCP Integration — connect Provara vault to an AI agent via MCP server
- **Tutorial 5:** Anchor to L2 — timestamp or anchor vault state to external trust anchor

---

**Reference:**  
- [Provara Protocol Spec v1.0](../BACKPACK_PROTOCOL_v1.0.md) — §8.3 Conflict Resolution  
- [Event Types](../spec/event_types.md) — ATTESTATION semantics
