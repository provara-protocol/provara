# Cookbook: Legal Discovery Evidence Chain

**Use Case:** Chain of custody for digital evidence in legal proceedings  
**Time to Complete:** 20 minutes  
**Difficulty:** Advanced

---

## Problem Statement

### The Challenge of Digital Evidence

In legal proceedings, digital evidence faces three critical challenges:

1. **Authenticity:** How do you prove the evidence hasn't been altered?
2. **Chain of Custody:** Who handled the evidence and when?
3. **Temporal Proof:** When was the evidence created/captured?

Traditional approaches rely on:
- Witness testimony (fallible, contestable)
- System logs (mutable, platform-dependent)
- Notarization (expensive, slow, geographic constraints)

### Why Provara?

| Requirement | Traditional Approach | Provara Solution |
|-------------|---------------------|------------------|
| **Authenticity** | Hash stored separately (can be swapped) | Hash chained to every event, signed |
| **Chain of Custody** | Manual log (trust-based) | Cryptographic event chain |
| **Temporal Proof** | System clock (manipulable) | RFC 3161 TSA (independent) |
| **Verification** | Expert testimony required | Anyone can run `provara verify` |
| **Longevity** | Proprietary formats | RFC 8785 JSON, 50-year readability |

**Legal Framework Alignment:**
- **Federal Rules of Evidence 901(b)(9)** — Electronic records authentication
- **Uniform Rules of Evidence** — Self-authenticating records
- **eDiscovery** — ESI (Electronically Stored Information) handling

---

## Evidence Intake Workflow

### Event Schema: Evidence Intake

```json
{
  "type": "OBSERVATION",
  "namespace": "local",
  "actor": "evidence_intake_system",
  "actor_key_id": "bp1_intake_key...",
  "timestamp_utc": "2026-02-17T10:00:00Z",
  "prev_event_hash": null,
  "payload": {
    "subject": "evidence_item",
    "predicate": "received",
    "value": {
      "evidence_id": "EV-2026-00042",
      "case_number": "CV-2026-12345",
      "item_type": "EMAIL_EXPORT",
      "source_system": "Microsoft 365",
      "source_account": "john.doe@example.com",
      "collection_method": "ADMIN_EXPORT",
      "collection_timestamp": "2026-02-17T09:45:00Z",
      "collector_id": "admin_001",
      "file_hash_sha256": "a1b2c3d4e5f6...",
      "file_size_bytes": 1048576,
      "chain_of_custody_initiated": true
    },
    "confidence": 1.0
  }
}
```

### Event Schema: Custody Transfer

```json
{
  "type": "OBSERVATION",
  "namespace": "local",
  "actor": "custody_tracker",
  "payload": {
    "subject": "evidence_custody",
    "predicate": "transferred",
    "value": {
      "evidence_id": "EV-2026-00042",
      "from_custodian": "admin_001",
      "to_custodian": "legal_reviewer_003",
      "transfer_reason": "LEGAL_REVIEW",
      "transfer_timestamp": "2026-02-17T14:00:00Z",
      "authorization_ticket": "AUTH-2026-789"
    },
    "confidence": 1.0
  }
}
```

### Event Schema: Forensic Analysis

```json
{
  "type": "ATTESTATION",
  "namespace": "local",
  "actor": "forensic_analyst_001",
  "payload": {
    "subject": "evidence_analysis",
    "predicate": "attested",
    "value": {
      "evidence_id": "EV-2026-00042",
      "analysis_type": "HASH_VERIFICATION",
      "analysis_tool": "sha256sum v8.32",
      "computed_hash": "a1b2c3d4e5f6...",
      "expected_hash": "a1b2c3d4e5f6...",
      "hash_match": true,
      "analyst_certification": "CFCE-2024-567"
    },
    "actor_key_id": "bp1_analyst_key...",
    "confidence": 1.0
  }
}
```

---

## Implementation Walkthrough

### Step 1: Initialize Legal Evidence Vault

```bash
# Create evidence vault
mkdir evidence_vault_CV-2026-12345

# Initialize with legal entity identity
provara init evidence_vault_CV-2026-12345 \
  --actor "hunt_legal_evidence_system" \
  --private-keys evidence_keys.json

# Output:
# [bootstrap] Root key: bp1_7f3a9c2e8b1d4056
# [bootstrap] Bootstrap complete. UID=evidence_CV-2026-12345
```

### Step 2: Record Evidence Intake

```bash
# Create intake event
cat > evidence_intake_001.json << 'EOF'
{
  "type": "OBSERVATION",
  "namespace": "local",
  "actor": "evidence_intake_system",
  "payload": {
    "subject": "evidence_item",
    "predicate": "received",
    "value": {
      "evidence_id": "EV-2026-00042",
      "case_number": "CV-2026-12345",
      "item_type": "EMAIL_EXPORT",
      "source_system": "Microsoft 365",
      "source_account": "john.doe@example.com",
      "collection_method": "ADMIN_EXPORT",
      "collection_timestamp": "2026-02-17T09:45:00Z",
      "collector_id": "admin_001",
      "file_hash_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
      "file_size_bytes": 1048576,
      "chain_of_custody_initiated": true
    },
    "confidence": 1.0
  }
}
EOF

# Append to vault
provara append evidence_vault_CV-2026-12345 \
  --data-file evidence_intake_001.json \
  --keyfile evidence_keys.json

# Expected output:
# [append] Event appended successfully
# [append] Event ID: evt_2a8f9c3e1b7d4056
```

### Step 3: Anchor to RFC 3161 Timestamp Authority

```bash
# Anchor vault state to external TSA
provara timestamp evidence_vault_CV-2026-12345 \
  --keyfile evidence_keys.json \
  --tsa https://freetsa.org/tsr

# Expected output:
# [timestamp] Computing vault state hash...
# [timestamp] Requesting timestamp from TSA...
# [timestamp] Timestamp received: 2026-02-17T10:05:32Z
# [timestamp] TSA: FreeTSA.org
# [timestamp] TSR saved to: evidence_vault_CV-2026-12345/timestamps/tsr_001.tsr
# [timestamp] Event appended: com.provara.timestamp_anchor
```

**What This Proves:**
- The vault state existed at the timestamp time
- An independent third party (TSA) attests to the time
- The timestamp is cryptographically bound to the vault state

### Step 4: Record Custody Transfer

```bash
# Custody transfer event
cat > custody_transfer_001.json << 'EOF'
{
  "type": "OBSERVATION",
  "namespace": "local",
  "actor": "custody_tracker",
  "payload": {
    "subject": "evidence_custody",
    "predicate": "transferred",
    "value": {
      "evidence_id": "EV-2026-00042",
      "from_custodian": "admin_001",
      "to_custodian": "legal_reviewer_003",
      "transfer_reason": "LEGAL_REVIEW",
      "transfer_timestamp": "2026-02-17T14:00:00Z",
      "authorization_ticket": "AUTH-2026-789"
    },
    "confidence": 1.0
  }
}
EOF

# Append transfer
provara append evidence_vault_CV-2026-12345 \
  --data-file custody_transfer_001.json \
  --keyfile evidence_keys.json
```

### Step 5: Forensic Verification

```bash
# Verify entire chain
provara verify evidence_vault_CV-2026-12345

# Expected output:
# [verify] Checking causal chains...
# [verify] Checking signatures...
# [verify] Checking Merkle root...
# [verify] Checking RFC 3161 timestamps...
# [verify] Vault integrity: VALID
# [verify] Events verified: 4
# [verify] Timestamps verified: 1
# [verify] Chain integrity: OK
```

---

## Forensic Export for Legal Submission

### Generate Evidence Bundle

```bash
# Create checkpoint
provara checkpoint evidence_vault_CV-2026-12345 \
  --keyfile evidence_keys.json

# Generate manifest
provara manifest evidence_vault_CV-2026-12345

# Create verified backup
provara backup evidence_vault_CV-2026-12345 \
  --output evidence_bundle_CV-2026-12345.zip
```

### Generate Verification Report

```bash
# Replay to show current state
provara replay evidence_vault_CV-2026-12345 > evidence_state_report.json

# The report includes:
# - All events in causal order
# - All custody transfers
# - All timestamps
# - Current state hash
# - Merkle root
# - All actor public keys
```

### Expert Witness Verification Script

Provide this to opposing counsel's expert:

```bash
#!/bin/bash
# evidence_verification.sh
# Run this to independently verify the evidence chain

VAULT_ZIP="$1"

if [ -z "$VAULT_ZIP" ]; then
    echo "Usage: $0 <evidence_bundle.zip>"
    exit 1
fi

echo "=== Evidence Verification Report ==="
echo "Bundle: $VAULT_ZIP"
echo "Date: $(date -u)"
echo ""

# Extract
TEMP_DIR=$(mktemp -d)
unzip -q "$VAULT_ZIP" -d "$TEMP_DIR"

# Verify
echo "Running cryptographic verification..."
provara verify "$TEMP_DIR"

if [ $? -eq 0 ]; then
    echo ""
    echo "VERIFICATION RESULT: PASS"
    echo "The evidence chain is cryptographically sound."
else
    echo ""
    echo "VERIFICATION RESULT: FAIL"
    echo "The evidence chain has integrity issues."
    exit 1
fi

# Show state
echo ""
echo "=== Evidence State ==="
provara replay "$TEMP_DIR"

# Cleanup
rm -rf "$TEMP_DIR"
```

---

## Expected Vault State Timeline

| Step | Events | Actors | Timestamps | State |
|------|--------|--------|------------|-------|
| Init | 1 (genesis) | 1 | 0 | Initial state |
| Intake | 2 | 1 | 0 | Evidence recorded |
| TSA Anchor | 3 | 1 | 1 | Temporally anchored |
| Custody Transfer | 4 | 2 | 1 | Custody tracked |
| Forensic Analysis | 5 | 3 | 1 | Analysis attested |

---

## What Could Go Wrong

### 1. TSA Unavailability

**Scenario:** FreeTSA.org is down when you need to timestamp.

**Impact:** Cannot obtain independent temporal proof.

**Mitigation:**
- Use multiple TSAs (FreeTSA, UniversalTS, custom TSA)
- Retry logic with exponential backoff
- Document TSA unavailability in custody log

**Recovery:**
```bash
# Try alternative TSA
provara timestamp evidence_vault \
  --tsa https://www.universaltimestamp.com/tsa
```

### 2. Key Compromise During Litigation

**Scenario:** Opposing party claims evidence system key was compromised.

**Impact:** Evidence authenticity challenged.

**Mitigation:**
- Key rotation with `KEY_REVOCATION` events
- Multi-sig for evidence operations (future)
- TSA timestamps prove key was valid at time of signing

**Response:**
```bash
# Show key was valid at timestamp time
provara replay evidence_vault | grep -A5 "timestamp_anchor"

# The TSA timestamp proves the key was uncompromised at that time.
```

### 3. File Corruption

**Scenario:** Storage media corruption damages `events.ndjson`.

**Impact:** Evidence chain broken.

**Mitigation:**
- Frequent backups to multiple locations
- Checksum verification on backup restoration
- TSA timestamps on each backup

**Detection:**
```bash
# Verify backup integrity
provara verify evidence_backup_20260217.zip

# If verification fails, restore from previous backup
```

### 4. Chain of Custody Gap

**Scenario:** Custody transfer not recorded for 48 hours.

**Impact:** Evidence admissibility challenged.

**Mitigation:**
- Automated custody tracking (badge swipes, access logs)
- Alerting for custody gaps >24 hours
- Supervisor attestation for gaps

**Response:**
```bash
# Record belated custody transfer with explanation
cat > custody_gap_explanation.json << 'EOF'
{
  "type": "OBSERVATION",
  "payload": {
    "subject": "custody_gap",
    "predicate": "explained",
    "value": {
      "evidence_id": "EV-2026-00042",
      "gap_start": "2026-02-17T18:00:00Z",
      "gap_end": "2026-02-19T09:00:00Z",
      "explanation": "Weekend - evidence in secure storage",
      "attesting_supervisor": "supervisor_001"
    },
    "confidence": 1.0
  }
}
EOF

provara append evidence_vault \
  --data-file custody_gap_explanation.json \
  --keyfile evidence_keys.json
```

---

## Legal Admissibility Checklist

| Requirement | Provara Feature | Verification Command |
|-------------|-----------------|---------------------|
| **Authenticity** | Ed25519 signatures | `provara verify` |
| **Chain of Custody** | Causal event chain | `provara replay` |
| **Temporal Proof** | RFC 3161 TSA | TSA certificate |
| **Integrity** | SHA-256 hash chain | `provara verify` |
| **Reproducibility** | Deterministic replay | `provara replay` |
| **Expert Testimony** | Anyone can verify | `provara verify` |

---

## Expert Witness Preparation

### What the Expert Will Testify To

1. **System Design:**
   - "Provara uses Ed25519 signatures per RFC 8032"
   - "SHA-256 hashing per FIPS 180-4"
   - "RFC 8785 canonical JSON for deterministic serialization"

2. **Verification Process:**
   - "I ran `provara verify` on the evidence bundle"
   - "All 47 events verified successfully"
   - "All 3 TSA timestamps verified successfully"

3. **Independence:**
   - "The verification tool is open-source (Apache 2.0)"
   - "I compiled it myself from source"
   - "Anyone can independently verify using the same commands"

### Sample Direct Examination Questions

**Q:** What is Provara?  
**A:** Provara is an open-source cryptographic event log protocol that creates tamper-evident records using industry-standard cryptography.

**Q:** How does it ensure tamper-evidence?  
**A:** Each event is signed with Ed25519, and events are chained together using SHA-256 hashes. If you modify any event, the hash chain breaks and the signature fails.

**Q:** Can the system administrator alter the evidence?  
**A:** No. The administrator's key is recorded in the vault. Any event they sign is attributable to them. If they try to modify past events, the hash chain breaks.

**Q:** How do you know the evidence existed at the claimed time?  
**A:** The vault is anchored to an RFC 3161 Timestamp Authority. The TSA is an independent third party that certifies the vault state existed at a specific time.

**Q:** Could you have fabricated this evidence?  
**A:** No. I received the evidence bundle from opposing counsel. I ran the verification commands, which are part of the open-source Provara tool. Anyone can download the tool and verify the same results.

---

## Next Steps

1. **Pre-Litigation Preparation:**
   - Establish evidence intake procedures
   - Train staff on custody tracking
   - Set up TSA anchoring schedule

2. **During Litigation:**
   - Record all evidence handling
   - Anchor to TSA daily
   - Generate weekly verification reports

3. **Trial Preparation:**
   - Prepare expert witness
   - Generate evidence bundle for court
   - Prepare verification script for opposing counsel

---

**See Also:**
- [SaaS Audit Log Cookbook](./audit_log_saas.md) — Compliance audit trails
- [RFC 3161 Guide](../docs/RFC3161_GUIDE.md) — Timestamp authority integration
- [Federal Rules of Evidence 901](https://www.law.cornell.edu/rules/fre/rule_901) — Authentication requirements
