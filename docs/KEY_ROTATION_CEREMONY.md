# Provara Key Rotation Ceremony

**Version:** 1.0  
**Date:** 2026-02-18  
**Status:** Normative Specification  
**Protocol Version:** 1.0 (Profile A)

---

## 1. Overview

Key rotation is the process of replacing an existing cryptographic key with a new one while maintaining the integrity and continuity of the Provara event log. This ceremony ensures that the transition is authorized, tamper-evident, and cryptographically linked to the preceding chain of evidence.

Per **PROTOCOL_PROFILE.txt**, Provara uses a two-event rotation model:
1.  **KEY_REVOCATION**: Marks the old key as invalid.
2.  **KEY_PROMOTION**: Introduces the new key and assigns its roles.

**Critical Rule:** A new key MUST NOT authorize its own promotion. The rotation events must be signed by a **surviving trusted authority**.

---

## 2. Prerequisites

- A Provara vault with at least two active keys (e.g., a `root` key and a `quorum` key) OR an external authority defined in the `degradation_ladder`.
- The private key of the surviving authority.
- Access to the Provara CLI.

---

## 3. Step-by-Step Ceremony

### Step 1: Generate New Keypair
Generate a new Ed25519 keypair. The private key MUST be stored securely (e.g., HSM, hardware wallet, or encrypted vault) and NEVER enter the Provara vault.

### Step 2: Prepare Revocation
Identify the `key_id` to be revoked and determine the `trust_boundary_event_id`. This is the ID of the last event signed by the old key that is considered legitimate.

### Step 3: Append KEY_REVOCATION Event
The surviving authority signs an event marking the old key as revoked.

**Payload Structure:**
```json
{
  "revoked_key_id": "bp1_oldkeyid12345",
  "reason": "scheduled_rotation",
  "trust_boundary_event_id": "evt_lastgoodlink67890",
  "revoked_at_utc": "2026-02-18T12:00:00Z"
}
```

### Step 4: Append KEY_PROMOTION Event
The same (or another) surviving authority signs an event promoting the new public key.

**Payload Structure:**
```json
{
  "new_key_id": "bp1_newkeyidabcde",
  "new_public_key_b64": "SGVsbG8gV29ybGQh...",
  "algorithm": "Ed25519",
  "roles": ["root", "attestation"],
  "promoted_by": "bp1_survivingkey999",
  "replaces_key_id": "bp1_oldkeyid12345",
  "promoted_at_utc": "2026-02-18T12:05:00Z"
}
```

### Step 5: Update Local Identity
Update the vault's `identity/keys.json` to reflect the change.
- Change the status of the old key to `revoked`.
- Add the new key entry with status `active`.

### Step 6: Regenerate Manifest and Merkle Root
Since `identity/keys.json` and the event log have changed, the manifest must be regenerated and resigned.

### Step 7: Verify Continuity
Run `provara verify` to ensure the chain remains valid and the rotation is recognized.

---

## 4. CLI Workflow

Assuming `bp1_root_key` is being rotated and `bp1_quorum_key` is the surviving authority.

```bash
# 1. Generate new key (handled internally by rotate command or manually)
# For now, we assume a combined command exists or is performed via script:

# 2. Perform rotation
# (Note: Current CLI requires implementation of 'rotate' command)
provara rotate <vault_path> 
  --revoke bp1_root_key 
  --with-authority bp1_quorum_key 
  --keyfile path/to/quorum_private.json 
  --trust-boundary evt_final_valid_event

# 3. Verify
provara verify <vault_path>
```

---

## 5. Edge Cases

### 5.1 Single-Key Vaults (No Surviving Authority)
If a vault has only one key and it must be rotated, there is no surviving internal authority.
- **Protocol:** Fallback to the `degradation_ladder`.
- **Ceremony:** An out-of-band authority (e.g., `designated_human`) must provide a signature or a new `GENESIS` event that references the previous manifest's Merkle root as a "parent" anchor. This is a **Hard Reset** rather than a rotation.

### 5.2 Compromised Old Key
If the old key is already compromised, the `trust_boundary_event_id` is critical. Any events signed by the compromised key *after* this event ID are considered "contested" and must be re-attested by the new key (see `KEY_COMPROMISE_RECOVERY.md`).

---

## 6. Safety Tiers & Timelines

- **L3 Operations:** All L3 (Critical) operations are strictly BLOCKED during the rotation window until the `KEY_PROMOTION` event is synced and verified by all peers.
- **Rotation Frequency:** 
  - **Root Keys:** Every 2 years or upon hardware upgrade.
  - **Operational/Agent Keys:** Every 90 days.
  - **Trigger Events:** Staff turnover, device loss, or detection of anomalous signing patterns.

---

## 7. Test Vector: Rotation Sequence

| Sequence | Event Type | Actor | signer_key_id | prev_event_hash | Notes |
|----------|------------|-------|---------------|-----------------|-------|
| 100 | OBSERVATION | user | bp1_old_root | evt_99 | Last legitimate event |
| 101 | KEY_REVOCATION | authority | bp1_quorum | evt_100 | Revokes old_root |
| 102 | KEY_PROMOTION | authority | bp1_quorum | evt_101 | Promotes new_root |
| 103 | OBSERVATION | user | bp1_new_root | evt_102 | First event with new key |

---

## 8. Spec Gaps & Open Decisions

1.  **Automated Rotation CLI:** The `provara rotate` command needs a normative implementation in `cli.py` to match the ceremony logic.
2.  **Cross-Vault Rotation:** How to propagate rotation events to sync peers without a central registry. (See `docs/OPEN_DECISIONS.md`).
