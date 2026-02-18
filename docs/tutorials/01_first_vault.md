# Tutorial 1: Your First Vault

**Reading time:** 4 minutes  
**Prerequisites:** Python 3.10+, pip installed

Create your first tamper-evident vault, append three events, and verify the cryptographic chain.

---

## What You'll Build

A Provara vault is an append-only event log where every event is:
- **Signed** with Ed25519 (non-repudiation)
- **Hashed** with SHA-256 (content-addressed)
- **Chained** to previous events (tamper-evident)

By the end, you'll have a working vault with three events and cryptographic proof of integrity.

---

## Step 1: Install Provara

```bash
pip install provara-protocol
```

Verify installation:

```bash
provara --help
```

---

## Step 2: Initialize Your Vault

Create a new vault directory with genesis events:

```bash
provara init my_first_vault --actor "alice" --quorum
```

**What happens:**
- Generates two Ed25519 keypairs (root + quorum for recovery)
- Creates the vault directory structure
- Writes a GENESIS event (the cryptographic beginning)
- Generates a safety policy (L1 by default)

**Expected output:**
```
Initializing Provara Vault at: /path/to/my_first_vault
  [bootstrap] Generating Ed25519 root keypair...
  [bootstrap] Generating Ed25519 quorum keypair...
  [bootstrap] Creating directory structure...
  [bootstrap] Bootstrap complete.

SUCCESS: Vault created and verified.
```

**Save your keys:** The CLI outputs private keys to stdout. In production, save them to a secure file:

```bash
provara init my_first_vault --actor "alice" --quorum --private-keys alice_keys.json
```

---

## Step 3: Inspect the Vault Structure

Your vault contains:

```
my_first_vault/
├── events/
│   └── events.ndjson    # Append-only event log
├── identity/
│   └── keys.json        # Public key registry
├── policies/
│   └── safety_policy.json
├── manifest.json        # File integrity manifest
└── merkle_root.txt      # Merkle tree root hash
```

View the genesis events:

```bash
cat my_first_vault/events/events.ndjson
```

You'll see two events (GENESIS + initial OBSERVATION), each with:
- `event_id`: Content-addressed hash (`evt_...`)
- `actor_key_id`: The signing key (`bp1_...`)
- `sig`: Ed25519 signature
- `prev_event_hash`: Link to previous event (null for genesis)

---

## Step 4: Append Your First Event

Add an observation to the vault:

```bash
provara append my_first_vault \
  --type OBSERVATION \
  --data '{"subject": "system", "predicate": "status", "value": "initialized"}' \
  --keyfile alice_keys.json \
  --actor "alice"
```

**Expected output:**
```
Appended event evt_3f8a2b9c1d4e5f6a7b8c9d0e (type=OBSERVATION)
```

---

## Step 5: Append Two More Events

Add a second observation:

```bash
provara append my_first_vault \
  --type OBSERVATION \
  --data '{"subject": "user_action", "predicate": "login", "value": {"user_id": "bob", "method": "ssh"}}' \
  --keyfile alice_keys.json \
  --actor "alice"
```

Add an assertion (a claim that can be disputed):

```bash
provara append my_first_vault \
  --type ASSERTION \
  --data '{"subject": "system_state", "predicate": "is_healthy", "value": true}' \
  --keyfile alice_keys.json \
  --actor "alice" \
  --confidence 0.95
```

---

## Step 6: Verify the Chain

Run integrity checks:

```bash
provara verify my_first_vault
```

**Expected output:**
```
Verifying vault integrity: /path/to/my_first_vault
PASS: All 17 integrity checks passed.
```

The verifier checks:
- Directory structure matches spec
- All events have valid signatures
- Causal chain is unbroken (prev_event_hash links)
- Manifest matches actual files
- Merkle root is correct

---

## Step 7: Replay the State

See the current derived state:

```bash
provara replay my_first_vault
```

**Expected output:**
```json
{
  "canonical": {
    "uid": "...",
    "root_key_id": "bp1_..."
  },
  "local": {
    "system": {"status": "initialized"},
    "user_action": {"login": {"user_id": "bob"}},
    "system_state": {"is_healthy": true}
  },
  "contested": {},
  "archived": {},
  "state_hash": "a3f8b2c9d1e4f5a6b7c8d9e0f1a2b3c4..."
}
```

The **state_hash** is deterministic: replay the same events on any machine, get the same hash.

---

## What Just Happened

1. **Genesis:** Created a vault with a GENESIS event (the cryptographic beginning of time for this vault)
2. **Key generation:** Generated Ed25519 keypairs for signing events
3. **Append-only:** Added three events, each chained to the previous
4. **Verification:** Confirmed all signatures and hashes are valid
5. **State derivation:** Reduced the event log to a deterministic state

---

## Key Concepts

| Term | Meaning |
|------|---------|
| **Vault** | Append-only event log + cryptographic metadata |
| **Event** | Signed, hashed, chained record (OBSERVATION, ASSERTION, etc.) |
| **actor_key_id** | Ed25519 public key identifier (`bp1_...`) |
| **event_id** | Content-addressed hash (`evt_...`) |
| **prev_event_hash** | Link to this actor's previous event (causal chain) |
| **state_hash** | Deterministic hash of the reduced state |

---

## Common Issues

**"Key file not found"**  
Ensure `--keyfile` points to the JSON file with your private keys.

**"Integrity check failed"**  
Don't manually edit `events.ndjson`. Use `provara append` only.

**"No such command"**  
Ensure you installed with `pip install provara-protocol` and the `provara` command is on your PATH.

---

## Next Steps

- **Tutorial 2:** Multi-Actor Dispute — two actors, conflicting observations, attestation resolution
- **Tutorial 3:** Checkpoint & Query — checkpoint a 1000-event vault, query by actor/date range
- **Tutorial 4:** MCP Integration — connect Provara vault to an AI agent via MCP server
- **Tutorial 5:** Anchor to L2 — timestamp or anchor vault state to external trust anchor

---

**Reference:**  
- [Provara Protocol Spec v1.0](../BACKPACK_PROTOCOL_v1.0.md)  
- [CLI Reference](../api/cli.md)
