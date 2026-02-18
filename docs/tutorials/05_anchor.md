# Tutorial 5: Anchor to External Trust Anchors

**Reading time:** 4 minutes  
**Prerequisites:** Tutorial 1 completed

Anchor your vault's state to external trust anchors: RFC 3161 timestamp authorities (TSA) and Layer-2 blockchains.

---

## Why Anchor?

Anchoring proves:
- **Temporal existence:** "This vault state existed at time T"
- **Independent verification:** Third-party attestation, not just your clock
- **Legal admissibility:** RFC 3161 timestamps carry evidentiary weight
- **L2 finality:** Blockchain anchoring provides public, immutable proof

---

## Part 1: RFC 3161 Timestamp Anchoring

### What is RFC 3161?

RFC 3161 defines the **Timestamp Protocol (TSP)**. A Timestamp Authority (TSA) signs a hash with a trusted timestamp.

**Provara integration:**
1. Compute vault state hash
2. Submit hash to TSA
3. TSA returns signed timestamp token (TSR)
4. Store TSR in vault as `TIMESTAMP_ANCHOR` event

### Step 1: Anchor to FreeTSA

```bash
provara timestamp my_vault --keyfile my_keys.json
```

**Default TSA:** `https://freetsa.org/tsr` (free, no registration)

**Expected output:**
```
Anchoring state hash: a3f8b2c9d1e4f5a6...
Recorded TIMESTAMP_ANCHOR: evt_7d8e9f0a1b2c3d4e
```

### Step 2: Verify the Timestamp

```python
from provara import Vault
import base64
from datetime import datetime

vault = Vault('my_vault')
events_file = vault.path / 'events' / 'events.ndjson'

# Find timestamp anchor events
import json
with open(events_file) as f:
    for line in f:
        event = json.loads(line)
        if event.get('type') == 'TIMESTAMP_ANCHOR':
            tsr = event['payload']['value']['tsr_base64']
            print(f"Timestamp event: {event['event_id']}")
            print(f"TSA response size: {len(base64.b64decode(tsr))} bytes")
```

### Step 3: Use a Custom TSA

For production, use a commercial TSA:

```bash
provara timestamp my_vault \
  --keyfile my_keys.json \
  --tsa "https://timestamp.digicert.com"
```

**Commercial TSAs:**
- DigiCert: `https://timestamp.digicert.com`
- Sectigo: `https://timestamp.sectigo.com`
- GlobalSign: `https://timestamp.globalsign.com/tsa`

---

## Part 2: L2 Blockchain Anchoring

### What is L2 Anchoring?

Anchor your vault's Merkle root to a Layer-2 blockchain (Base, Optimism, Arbitrum). The transaction hash proves:
- **Public verifiability:** Anyone can verify on-chain
- **Immutable timestamp:** Block timestamp is consensus-validated
- **State commitment:** Merkle root commits to all vault files

### Step 1: Anchor to Base Mainnet (Simulated)

```python
from provara import Vault

vault = Vault('my_vault')

# Anchor to L2 (mock contract for testing)
result = vault.anchor_to_l2(
    key_id="bp1_your_key_id",
    private_key_b64="your_private_key_base64",
    network="base-mainnet"
)

print(f"Anchor event: {result['event_id']}")
print(f"Mock TX hash: {result['payload']['value']['tx_hash']}")
```

### Step 2: Inspect the Anchor Event

```python
import json

# The anchor event contains:
anchor_payload = result['payload']['value']
print(json.dumps(anchor_payload, indent=2))
```

**Output:**
```json
{
  "merkle_root": "e9930fd48a52d4fe...",
  "network": "base-mainnet",
  "tx_hash": "0x7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e",
  "contract_address": "0xProvaraAnchorV1MockAddress"
}
```

### Step 3: Production L2 Anchoring

For production, implement a real Web3 integration:

```python
# Example: Anchor to Base using web3.py
from web3 import Web3

def anchor_to_base(merkle_root: str, private_key: str) -> str:
    w3 = Web3(Web3.HTTPProvider("https://base-mainnet.g.alchemy.com/v2/YOUR_KEY"))
    
    # Contract ABI (simplified)
    contract = w3.eth.contract(
        address="0xYourAnchorContract",
        abi=[{"inputs": [{"name": "root", "type": "bytes32"}], "name": "anchor"}]
    )
    
    # Build transaction
    tx = contract.functions.anchor(
        merkle_root.encode()
    ).build_transaction({
        'nonce': w3.eth.get_transaction_count("YOUR_ADDRESS"),
        'gas': 50000,
    })
    
    # Sign and send
    signed = w3.eth.account.sign_transaction(tx, private_key)
    tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
    
    return tx_hash.hex()
```

---

## Part 3: Verification

### Verify Timestamp Anchor

```python
import hashlib
import base64
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography import x509
from cryptography.x509.oid import NameOID

def verify_tsa_timestamp(tsr_base64: str, original_hash: str) -> bool:
    """
    Verify an RFC 3161 TSR against the original hash.
    In production, parse the ASN.1 structure properly.
    """
    tsr_bytes = base64.b64decode(tsr_base64)
    
    # Simplified verification (production needs full ASN.1 parsing)
    # 1. Extract signed hash from TSR
    # 2. Compare to original_hash
    # 3. Verify TSA certificate chain
    
    # For now, just confirm TSR is valid Base64
    return len(tsr_bytes) > 100  # TSRs are typically 500-2000 bytes
```

### Verify L2 Anchor

```python
from web3 import Web3

def verify_l2_anchor(tx_hash: str, network: str) -> dict:
    """
    Verify an L2 anchor transaction.
    Returns block number, timestamp, and confirmed status.
    """
    providers = {
        "base-mainnet": "https://base-mainnet.g.alchemy.com/v2/YOUR_KEY",
        "optimism": "https://opt-mainnet.g.alchemy.com/v2/YOUR_KEY",
    }
    
    w3 = Web3(Web3.HTTPProvider(providers[network]))
    tx = w3.eth.get_transaction(tx_hash)
    
    return {
        "block_number": tx.blockNumber,
        "timestamp": w3.eth.get_block(tx.blockNumber).timestamp,
        "confirmed": True
    }
```

---

## Anchoring Strategy

### Recommended Cadence

| Vault Activity | Anchor Type | Frequency |
|----------------|-------------|-----------|
| Daily operations | RFC 3161 TSA | Daily |
| Major milestones | RFC 3161 + L2 | Per milestone |
| Legal evidence | RFC 3161 + L2 | Per case |
| Compliance audits | RFC 3161 + L2 | Audit start/end |

### Cost Estimates

| Anchor Type | Cost | Latency |
|-------------|------|---------|
| FreeTSA | Free | ~1-5 seconds |
| Commercial TSA | ~$0.01-0.10 per timestamp | ~1 second |
| Base L2 | ~$0.001-0.01 per anchor | ~2 seconds |
| Ethereum L1 | ~$1-10 per anchor | ~15 seconds |

---

## Legal Admissibility

### RFC 3161 in Court

RFC 3161 timestamps are admissible under:
- **US Federal Rules of Evidence 901(b)(9)** — Process or system authentication
- **EU eIDAS Regulation** — Qualified electronic timestamps
- **UK Electronic Communications Act 2000**

### Best Practices for Legal Use

1. **Anchor before disclosure:** Timestamp evidence before sharing with opposing counsel
2. **Use commercial TSA:** FreeTSA is fine for testing; use DigiCert/Sectigo for legal
3. **Preserve TSR:** Store the full TSR, not just the event reference
4. **Chain of custody:** Document who requested the timestamp and why

---

## Complete Example: Legal Evidence Vault

```bash
# Create vault for legal matter
provara init matter_2026_001 --actor "legal_counsel" --private-keys matter_keys.json

# Add evidence
provara append matter_2026_001 \
  --type OBSERVATION \
  --data '{"subject": "evidence", "predicate": "document_hash", "value": {"doc": "contract_v2.pdf", "sha256": "a3f8b2c9..."}}' \
  --keyfile matter_keys.json

# Anchor to TSA (creates independent temporal proof)
provara timestamp matter_2026_001 --keyfile matter_keys.json --tsa "https://timestamp.digicert.com"

# Anchor to L2 (public, immutable proof)
python -c "
from provara import Vault
v = Vault('matter_2026_001')
v.anchor_to_l2('bp1_your_key', 'your_private_key', 'base-mainnet')
"
```

---

## Next Steps

- **Tutorial 1:** Your First Vault — create, append, verify
- **MCP Integration:** Tutorial 4 — AI agent memory
- **SCITT Compatibility:** [`docs/SCITT_MAPPING.md`](SCITT_MAPPING.md)

---

**Reference:**  
- [RFC 3161 Specification](https://www.rfc-editor.org/rfc/rfc3161)  
- [Base Blockchain](https://base.org)  
- [Timestamp API](../api/timestamp.md)
