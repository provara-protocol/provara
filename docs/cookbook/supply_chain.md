# Cookbook: Supply Chain Provenance

**Use Case:** Multi-organization product journey tracking  
**Time to Complete:** 30 minutes  
**Difficulty:** Advanced

---

## Problem Statement

### The Supply Chain Challenge

Modern supply chains involve multiple organizations that don't fully trust each other:

| Stakeholder | Pain Point | Current Solution | Provara Solution |
|-------------|------------|------------------|------------------|
| **Manufacturer** | Prove origin/authenticity | Certificates (forgeable) | Cryptographic chain |
| **Distributor** | Prove handling conditions | Paper logs (alterable) | Signed observations |
| **Retailer** | Prove compliance | Audit reports (periodic) | Continuous trail |
| **Consumer** | Verify claims | QR codes (static) | Verifiable chain |
| **Regulator** | Enforce standards | Inspections (sampling) | Full traceability |

**Why Provara:**
- Each organization maintains its own vault with its own keys
- Sync events between organizations at handoff points
- Discrepancies go to `contested` namespace until resolved
- Full chain is verifiable by any party

---

## Multi-Actor Architecture

### Organization Structure

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Manufacturer   │     │   Distributor   │     │    Retailer     │
│  (Org A)        │────▶│   (Org B)       │────▶│    (Org C)      │
│                 │     │                 │     │                 │
│ Vault A         │     │ Vault B         │     │ Vault C         │
│ Key: bp1_mfg    │     │ Key: bp1_dist   │     │ Key: bp1_retail │
└─────────────────┘     └─────────────────┘     └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                        ┌────────▼────────┐
                        │   Shared Sync   │
                        │   Vault         │
                        │                 │
                        │ Key: bp1_sync   │
                        └─────────────────┘
```

### Event Schema: Product Creation

```json
{
  "type": "OBSERVATION",
  "namespace": "local",
  "actor": "manufacturer_org_a",
  "actor_key_id": "bp1_mfg_key_abc123",
  "payload": {
    "subject": "product_lifecycle",
    "predicate": "created",
    "value": {
      "product_id": "PROD-2026-00042",
      "sku": "WIDGET-XL-BLUE",
      "batch_number": "BATCH-2026-02-17-A",
      "manufacturing_location": "Factory A, Shenzhen",
      "manufacturing_timestamp": "2026-02-17T08:00:00Z",
      "quality_certification": "ISO-9001:2015",
      "initial_checksum": "sha256:abc123..."
    },
    "confidence": 1.0
  }
}
```

### Event Schema: Custody Handoff

```json
{
  "type": "ATTESTATION",
  "namespace": "local",
  "actor": "distributor_org_b",
  "payload": {
    "subject": "product_custody",
    "predicate": "received",
    "value": {
      "product_id": "PROD-2026-00042",
      "from_organization": "manufacturer_org_a",
      "to_organization": "distributor_org_b",
      "handoff_location": "Port of Los Angeles",
      "handoff_timestamp": "2026-02-20T14:00:00Z",
      "condition_at_receipt": {
        "temperature_celsius": 22,
        "humidity_percent": 45,
        "packaging_intact": true,
        "seal_number": "SEAL-789456"
      },
      "shipping_document_ref": "BOL-2026-12345"
    },
    "actor_key_id": "bp1_dist_key_def456",
    "confidence": 1.0
  }
}
```

### Event Schema: Condition Monitoring

```json
{
  "type": "OBSERVATION",
  "namespace": "local",
  "actor": "iot_sensor_001",
  "payload": {
    "subject": "product_condition",
    "predicate": "monitored",
    "value": {
      "product_id": "PROD-2026-00042",
      "sensor_type": "TEMPERATURE_HUMIDITY",
      "readings": [
        {"timestamp": "2026-02-20T10:00:00Z", "temp_c": 21, "humidity_pct": 44},
        {"timestamp": "2026-02-20T11:00:00Z", "temp_c": 22, "humidity_pct": 45},
        {"timestamp": "2026-02-20T12:00:00Z", "temp_c": 28, "humidity_pct": 60}
      ],
      "threshold_violations": [
        {"timestamp": "2026-02-20T12:00:00Z", "violation": "TEMPERATURE_EXCEEDED", "limit": 25}
      ]
    },
    "confidence": 0.95
  }
}
```

---

## Implementation Walkthrough

### Step 1: Manufacturer Initializes Vault

```bash
# Manufacturer creates vault
mkdir mfg_vault_org_a
provara init mfg_vault_org_a \
  --actor "manufacturer_org_a" \
  --private-keys mfg_keys.json

# Record product creation
cat > product_creation.json << 'EOF'
{
  "type": "OBSERVATION",
  "namespace": "local",
  "actor": "manufacturer_org_a",
  "payload": {
    "subject": "product_lifecycle",
    "predicate": "created",
    "value": {
      "product_id": "PROD-2026-00042",
      "sku": "WIDGET-XL-BLUE",
      "batch_number": "BATCH-2026-02-17-A",
      "manufacturing_location": "Factory A, Shenzhen",
      "manufacturing_timestamp": "2026-02-17T08:00:00Z",
      "quality_certification": "ISO-9001:2015"
    },
    "confidence": 1.0
  }
}
EOF

provara append mfg_vault_org_a \
  --data-file product_creation.json \
  --keyfile mfg_keys.json

# Anchor to timestamp authority
provara timestamp mfg_vault_org_a \
  --keyfile mfg_keys.json \
  --tsa https://freetsa.org/tsr
```

### Step 2: Distributor Initializes Vault

```bash
# Distributor creates vault
mkdir dist_vault_org_b
provara init dist_vault_org_b \
  --actor "distributor_org_b" \
  --private-keys dist_keys.json

# Record receipt of product
cat > product_receipt.json << 'EOF'
{
  "type": "ATTESTATION",
  "namespace": "local",
  "actor": "distributor_org_b",
  "payload": {
    "subject": "product_custody",
    "predicate": "received",
    "value": {
      "product_id": "PROD-2026-00042",
      "from_organization": "manufacturer_org_a",
      "to_organization": "distributor_org_b",
      "handoff_location": "Port of Los Angeles",
      "handoff_timestamp": "2026-02-20T14:00:00Z",
      "condition_at_receipt": {
        "temperature_celsius": 22,
        "humidity_percent": 45,
        "packaging_intact": true,
        "seal_number": "SEAL-789456"
      },
      "shipping_document_ref": "BOL-2026-12345"
    },
    "actor_key_id": "bp1_dist_key_def456",
    "confidence": 1.0
  }
}
EOF

provara append dist_vault_org_b \
  --data-file product_receipt.json \
  --keyfile dist_keys.json
```

### Step 3: Sync Vaults at Handoff

```bash
# Create shared sync vault
mkdir shared_sync_vault
provara init shared_sync_vault \
  --actor "supply_chain_sync" \
  --private-keys sync_keys.json

# Merge manufacturer's vault
provara merge shared_sync_vault \
  --remote ../mfg_vault_org_a \
  --strategy union

# Merge distributor's vault
provara merge shared_sync_vault \
  --remote ../dist_vault_org_b \
  --strategy union

# Verify combined chain
provara verify shared_sync_vault

# Expected output:
# [verify] Vault integrity: VALID
# [verify] Events verified: 4
# [verify] Actors: 2 (manufacturer_org_a, distributor_org_b)
```

### Step 4: Retailer Receives Product

```bash
# Retailer creates vault
mkdir retail_vault_org_c
provara init retail_vault_org_c \
  --actor "retailer_org_c" \
  --private-keys retail_keys.json

# Record receipt from distributor
cat > retail_receipt.json << 'EOF'
{
  "type": "ATTESTATION",
  "namespace": "local",
  "actor": "retailer_org_c",
  "payload": {
    "subject": "product_custody",
    "predicate": "received",
    "value": {
      "product_id": "PROD-2026-00042",
      "from_organization": "distributor_org_b",
      "to_organization": "retailer_org_c",
      "handoff_location": "Distribution Center, Chicago",
      "handoff_timestamp": "2026-02-25T10:00:00Z",
      "condition_at_receipt": {
        "temperature_celsius": 20,
        "humidity_percent": 42,
        "packaging_intact": true,
        "seal_number": "SEAL-789456"
      },
      "retail_location": "Store #1234, New York"
    },
    "actor_key_id": "bp1_retail_key_ghi789",
    "confidence": 1.0
  }
}
EOF

provara append retail_vault_org_c \
  --data-file retail_receipt.json \
  --keyfile retail_keys.json
```

### Step 5: Consumer Verification

```bash
# Consumer scans QR code linking to vault
# Consumer runs verification

provara verify retail_vault_org_c

# Expected output:
# [verify] Vault integrity: VALID
# [verify] Chain of custody: COMPLETE
# [verify] Organizations: 3 (manufacturer, distributor, retailer)
# [verify] Timestamp anchors: 1

# Consumer can see full journey:
provara replay retail_vault_org_c | jq '.events[] | {actor, payload}'
```

---

## Discrepancy Resolution

### Scenario: Temperature Excursion Dispute

**Manufacturer claims:** Product stored within spec  
**Distributor claims:** Temperature exceeded limits during transit

```bash
# Manufacturer disputes distributor's claim
cat > mfg_dispute.json << 'EOF'
{
  "type": "OBSERVATION",
  "namespace": "contested",
  "actor": "manufacturer_org_a",
  "payload": {
    "subject": "product_condition:PROD-2026-00042",
    "predicate": "disputed",
    "value": {
      "disputed_claim": "Temperature exceeded limits",
      "manufacturer_evidence": {
        "data_logger_serial": "DL-2026-0042",
        "recorded_max_temp": 24,
        "spec_limit": 25,
        "data_integrity": "SHA256_SIGNED"
      },
      "requested_resolution": "INDEPENDENT_AUDIT"
    },
    "confidence": 0.90
  }
}
EOF

provara append shared_sync_vault \
  --data-file mfg_dispute.json \
  --keyfile mfg_keys.json

# Third-party auditor attests
cat > auditor_attestation.json << 'EOF'
{
  "type": "ATTESTATION",
  "namespace": "canonical",
  "actor": "independent_auditor_sgs",
  "payload": {
    "subject": "product_condition:PROD-2026-00042",
    "predicate": "attested",
    "value": {
      "finding": "TEMPERATURE_WITHIN_SPEC",
      "evidence_reviewed": [
        "Manufacturer data logger DL-2026-0042",
        "Distributor sensor readings",
        "Shipping container telemetry"
      ],
      "conclusion": "Maximum recorded temperature: 24°C (spec: 25°C)",
      "certification": "SGS-CERT-2026-789456"
    },
    "actor_key_id": "bp1_auditor_key",
    "confidence": 0.98
  }
}
EOF

provara append shared_sync_vault \
  --data-file auditor_attestation.json \
  --keyfile auditor_keys.json

# Dispute resolved - replay shows canonical truth
provara replay shared_sync_vault | jq '.canonical'
```

---

## Expected Vault State by Organization

### Manufacturer Vault (Org A)
```json
{
  "canonical": {},
  "local": {
    "product_lifecycle:PROD-2026-00042": {
      "value": {"status": "created", "location": "Factory A"},
      "confidence": 1.0
    }
  },
  "contested": {},
  "archived": {}
}
```

### Distributor Vault (Org B)
```json
{
  "canonical": {},
  "local": {
    "product_custody:PROD-2026-00042": {
      "value": {"status": "received", "from": "manufacturer_org_a"},
      "confidence": 1.0
    }
  },
  "contested": {
    "product_condition:PROD-2026-00042": {
      "conflicting_values": [
        {"actor": "manufacturer_org_a", "claim": "within_spec"},
        {"actor": "distributor_org_b", "claim": "exceeded_spec"}
      ]
    }
  },
  "archived": {}
}
```

### Shared Sync Vault (After Resolution)
```json
{
  "canonical": {
    "product_condition:PROD-2026-00042": {
      "value": {"finding": "TEMPERATURE_WITHIN_SPEC"},
      "attested_by": "independent_auditor_sgs",
      "confidence": 0.98
    }
  },
  "local": {},
  "contested": {},
  "archived": {
    "product_condition:PROD-2026-00042": {
      "superseded_values": [
        {"actor": "manufacturer_org_a", "claim": "within_spec"},
        {"actor": "distributor_org_b", "claim": "exceeded_spec"}
      ]
    }
  }
}
```

---

## What Could Go Wrong

### 1. Organization Key Compromise

**Scenario:** Distributor's signing key is stolen.

**Impact:** Attacker can forge custody records.

**Mitigation:**
- Key rotation with `KEY_REVOCATION` events
- Multi-sig for handoff attestations (future)
- Cross-verify with IoT sensor data

**Response:**
```bash
# Revoke compromised key
cat > key_revocation.json << 'EOF'
{
  "type": "KEY_REVOCATION",
  "actor": "distributor_org_b",
  "payload": {
    "revoked_key_id": "bp1_dist_key_def456",
    "reason": "KEY_COMPROMISE_DETECTED",
    "incident_id": "SEC-2026-0099",
    "replacement_key_id": "bp1_dist_key_new789"
  }
}
EOF

provara append dist_vault_org_b \
  --data-file key_revocation.json \
  --keyfile dist_keys.json

# Notify all partners
# (Distribute revocation event to all synced vaults)
```

### 2. Vault Sync Failure

**Scenario:** Network failure prevents vault sync at handoff.

**Impact:** Chain of custody has gaps.

**Mitigation:**
- Offline-first design (sync when connectivity restored)
- QR code handoff (scan to exchange vault state)
- SMS/email fallback for critical handoff notifications

**Recovery:**
```bash
# Sync when connectivity restored
provara merge shared_sync_vault \
  --remote ../dist_vault_org_b \
  --strategy union

# Verify no gaps in chain
provara verify shared_sync_vault
```

### 3. Conflicting Condition Reports

**Scenario:** IoT sensors report different temperatures.

**Impact:** Dispute over product quality.

**Mitigation:**
- Multiple sensors per shipment
- Sensor calibration records in vault
- Third-party auditor attestation

**Resolution:**
```bash
# Record all sensor readings
# Attestation from auditor resolves conflict
# See "Discrepancy Resolution" section above
```

### 4. Regulatory Compliance Gap

**Scenario:** New regulation requires additional tracking fields.

**Impact:** Historical records don't meet new standards.

**Mitigation:**
- Schema versioning in event payloads
- Migration events that map old→new schema
- Regulatory attestation events

**Response:**
```bash
# Schema migration event
cat > schema_migration.json << 'EOF'
{
  "type": "OBSERVATION",
  "payload": {
    "subject": "schema_migration",
    "predicate": "applied",
    "value": {
      "from_schema_version": "1.0",
      "to_schema_version": "1.1",
      "new_required_fields": ["carbon_footprint_kg", "recyclable_percent"],
      "migration_timestamp": "2026-03-01T00:00:00Z"
    },
    "confidence": 1.0
  }
}
EOF

provara append shared_sync_vault \
  --data-file schema_migration.json \
  --keyfile sync_keys.json
```

---

## Compliance Mapping

| Regulation | Provara Feature | Evidence Produced |
|------------|-----------------|-------------------|
| **FDA DSCSA** | Product tracing | Full custody chain |
| **EU MDR** | Device traceability | UDI + event chain |
| **CBAM** | Carbon tracking | Emissions observations |
| **Uyghur Forced Labor** | Origin verification | Manufacturing location + timestamps |
| **FSMA 204** | Food traceability | Temperature + custody log |

---

## Consumer Verification Flow

### QR Code Content

```
https://verify.provera.dev/vault/PROD-2026-00042
```

### Consumer Verification Page

```html
<!-- Consumer scans QR code, sees: -->

Product: WIDGET-XL-BLUE
ID: PROD-2026-00042

Journey:
✅ 2026-02-17: Manufactured (Factory A, Shenzhen)
✅ 2026-02-20: Received by Distributor (Port of Los Angeles)
✅ 2026-02-25: Received by Retailer (Chicago, IL)
✅ 2026-02-28: Available for Sale (Store #1234, New York)

Condition:
✅ Temperature: Always within spec (max 24°C, limit 25°C)
✅ Humidity: Always within spec (max 60%, limit 65%)
✅ Packaging: Intact throughout journey

Verification:
✅ Cryptographic chain: VALID
✅ All signatures: VERIFIED
✅ Timestamp anchors: 3 TSA anchors

Verified by Provara Protocol v1.0
```

---

## Next Steps

1. **Pilot Deployment:**
   - Select one product line for pilot
   - Onboard manufacturer, distributor, retailer
   - Run end-to-end traceability test

2. **Scale-Up:**
   - Integrate with ERP systems
   - Automate event generation
   - Set up monitoring dashboards

3. **Consumer-Facing:**
   - Generate QR codes for products
   - Build verification web app
   - Marketing campaign around transparency

---

**See Also:**
- [SaaS Audit Log Cookbook](./audit_log_saas.md) — Single-org audit trails
- [Legal Discovery Cookbook](./legal_discovery.md) — Evidence chain for legal proceedings
- [AI Agent Memory Cookbook](./ai_agent_memory.md) — Multi-agent dispute resolution
