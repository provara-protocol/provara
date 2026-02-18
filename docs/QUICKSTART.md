# Provara 60-Second Quickstart

**Goal:** From zero to verified vault in under 60 seconds.

**Prerequisites:**
- Python 3.10+
- `pip install provara-protocol`

---

## The Fast Path

```bash
# 1. Install (10 seconds)
pip install provara-protocol

# 2. Create vault (5 seconds)
provara init my_vault --actor "alice"

# 3. Append first event (10 seconds)
provara append my_vault \
  --type OBSERVATION \
  --data '{"subject": "hello", "predicate": "world", "value": "first event"}' \
  --keyfile my_vault/identity/private_keys.json

# 4. Verify (5 seconds)
provara verify my_vault

# 5. See state (5 seconds)
provara replay my_vault
```

**Done.** You now have a tamper-evident vault with:
- Ed25519-signed events
- SHA-256 hash chain
- RFC 8785 canonical JSON
- Verifiable integrity

---

## Expected Output

### Step 2: Init
```
Initializing Provara Vault at: /path/to/my_vault
[bootstrap] Generating Ed25519 root keypair...
[bootstrap] Creating directory structure...
[bootstrap] Writing genesis.json...
[bootstrap] Writing keys.json...
[bootstrap] Bootstrap complete. UID=<unique_id>
[bootstrap] Root key: bp1_abc123...

SUCCESS: Vault created and verified.
```

### Step 3: Append
```
[append] Event appended successfully
[append] Event ID: evt_abc123...
[append] Actor: alice
[append] Type: OBSERVATION
```

### Step 4: Verify
```
[verify] Checking causal chains...
[verify] Checking signatures...
[verify] Checking Merkle root...
[verify] Vault integrity: VALID
[verify] Events verified: 2
```

### Step 5: Replay
```json
{
  "canonical": {},
  "local": {
    "hello:world": {
      "value": "first event",
      "confidence": 1.0,
      "actor": "alice"
    }
  },
  "contested": {},
  "archived": {},
  "metadata": {
    "state_hash": "abc123...",
    "event_count": 2
  }
}
```

---

## What You Built

```
my_vault/
├── identity/
│   ├── keys.json          # Public key registry
│   ├── genesis.json       # Genesis event
│   └── private_keys.json  # Your private keys (guard this!)
├── events/
│   └── events.ndjson      # Append-only event log
├── state/
│   └── state.json         # Current derived state
└── manifest.json          # Merkle root + signatures
```

---

## Next Steps

### Add More Events
```bash
provara append my_vault \
  --type OBSERVATION \
  --data '{"subject": "temperature", "predicate": "reading", "value": 22.5}' \
  --keyfile my_vault/identity/private_keys.json
```

### Create Checkpoint
```bash
provara checkpoint my_vault \
  --keyfile my_vault/identity/private_keys.json
```

### Make Backup
```bash
provara backup my_vault --to ./backups
```

### Anchor to Timestamp Authority
```bash
provara timestamp my_vault \
  --keyfile my_vault/identity/private_keys.json \
  --tsa https://freetsa.org/tsr
```

---

## Troubleshooting

### "Command not found: provara"
```bash
# Ensure pip installed to PATH
pip show provara-protocol
```

### "Private keys file not found"
```bash
# Keys are saved in vault/identity/private_keys.json
# Use that path for --keyfile
```

### "Invalid signature"
```bash
# Ensure you're using the correct keyfile
# Keys are actor-specific
```

---

## Learn More

- **Full Documentation:** https://provara.dev/docs
- **Cookbook:** [`docs/cookbook/`](./docs/cookbook/) — Real-world recipes
- **Protocol Spec:** [`PROTOCOL_PROFILE.txt`](./PROTOCOL_PROFILE.txt) — Cryptographic details
- **GitHub:** https://github.com/provara-protocol/provara

---

**That's it.** You've created your first tamper-evident vault. Everything you append is now cryptographically anchored and verifiable for the next 50 years.

*"Truth is not merged. Evidence is merged. Truth is recomputed."*
