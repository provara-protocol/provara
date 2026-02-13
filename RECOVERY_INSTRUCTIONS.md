# Provara v1.0 Recovery Instructions

This document is the last line of defense. If everything else is lost,
confusing, or broken, start here.

---

## What is this system?

This is a self-owned memory vault. It stores events (observations,
decisions, knowledge) in a tamper-proof, cryptographically signed
chain. It does not require any internet connection, any account, or
any company to function.

The vault is a folder on a computer. The folder contains plain text
files (JSON). Anyone with Python 3 and this kit can read, verify,
and extend the vault.

---

## The one file that matters most

```
events/events.ndjson
```

This file is the permanent record. Everything else in the vault —
the state, the manifest, the Merkle root — can be regenerated from
this file. If you have to choose what to save, save this file.

It is plain text. One JSON object per line. You can read it with
any text editor on any operating system.

---

## Recovery scenarios

### 1. You have the vault folder but lost the private keys

**Impact:** You cannot add new events or prove ownership. All existing
data is fully readable and verifiable.

**If you have the quorum (backup) key:**
```bash
cd SNP_Core/bin
PYTHONPATH=. python3 rekey_backpack.py /path/to/vault --compromised root
```
This creates a new root key using the quorum key's authority.
Save the new keys immediately.

**If you lost both keys:**
The vault is now permanently read-only. This is called "identity death."
You can still read everything, but you cannot add to it or transfer
ownership. Create a new vault if you need to continue.

---

### 2. The vault fails integrity checks

Run:
```bash
./check_backpack.sh /path/to/vault
```

**If file hashes don't match:** A file was modified or corrupted.
Restore that file from your most recent verified backup.

**If the Merkle root doesn't match:** The manifest is stale. If you
intentionally modified files, regenerate:
```bash
cd SNP_Core/bin
PYTHONPATH=. python3 manifest_generator.py /path/to/vault
```
Then re-sign the manifest with your private key.

**If phantom files are detected:** There are files in the vault that
aren't tracked. Remove them or regenerate the manifest.

**If the genesis or keys file is corrupted:** These cannot be
regenerated. Restore from backup.

---

### 3. You think someone accessed your private key

**Immediately rotate:**
```bash
cd SNP_Core/bin
PYTHONPATH=. python3 rekey_backpack.py /path/to/vault --compromised root
```
This requires the quorum key. The rotation:
- Revokes the compromised key
- Marks the last trusted event (trust boundary)
- Creates a new key signed by the quorum authority

Then change the password on any system where the old key was stored.

---

### 4. Restoring from a backup

1. Locate your backup (a `.zip` file in the `Backups/` folder)
2. Verify the backup hash:
   ```bash
   shasum -a 256 Backup_YYYY-MM-DD_HHMMSS.zip
   # Compare with the .sha256 file
   ```
3. Extract:
   ```bash
   unzip Backup_YYYY-MM-DD_HHMMSS.zip -d /path/to/restore
   ```
4. Verify the restored vault:
   ```bash
   ./check_backpack.sh /path/to/restore/My_Backpack
   ```
5. If 17/17 pass, you're good.

---

### 5. Verifying this kit itself hasn't been tampered with

Check the kit's own integrity:
```bash
shasum -a 256 -c CHECKSUMS.txt
```

Every file in the kit has a SHA-256 hash recorded in `CHECKSUMS.txt`.
If any hash doesn't match, that file has been modified since the kit
was packaged.

---

### 6. Rebuilding from just the event log

If you have only `events/events.ndjson` and nothing else:

1. Create the directory structure:
   ```
   mkdir -p vault/{identity,events,state,artifacts/cas,policies/ontology}
   cp events.ndjson vault/events/events.ndjson
   ```

2. You will need the genesis.json and keys.json to have a fully
   compliant vault. If these are lost, you can extract the genesis
   event from the log:
   ```bash
   head -1 vault/events/events.ndjson | python3 -m json.tool
   ```
   The first event (type: GENESIS) contains the uid, root_key_id,
   and birth_timestamp.

3. Reconstruct genesis.json manually from that event's payload.

4. keys.json requires the public key. If the event log contains
   signed events, the actor_key_id is recorded but the public key
   material may not be recoverable without the original keys.json.

5. Regenerate state by running the reducer:
   ```bash
   cd SNP_Core/bin
   PYTHONPATH=. python3 -c "
   import json
   from reducer_v0 import SovereignReducerV0
   events = [json.loads(l) for l in open('/path/to/events.ndjson') if l.strip()]
   r = SovereignReducerV0()
   r.apply_events(events)
   print(json.dumps(r.state, indent=2))
   "
   ```

This is the "nuclear option." It works because events are
self-describing and the reducer is deterministic.

---

## What you should back up (priority order)

1. **`my_private_keys.json`** — without this, the vault is read-only
2. **`events/events.ndjson`** — the permanent record (everything derives from this)
3. **`identity/genesis.json`** — the birth certificate
4. **`identity/keys.json`** — the public key registry
5. **The entire vault folder** — everything else is regeneratable

---

## What you should NEVER do

- Store private keys inside the vault folder
- Email private keys
- Store private keys in unencrypted cloud storage
- Delete events/events.ndjson
- Modify events after they've been written (this breaks the causal chain)
- Trust a vault that fails integrity checks without investigating

---

## Verification without this kit

If you have a vault but not this kit, you can still verify it with
any system that has:

- A SHA-256 implementation
- A JSON parser
- An Ed25519 signature verifier

The vault is entirely plain text. No proprietary formats, no binary
blobs, no database files. This is by design.

The protocol profile is in `PROTOCOL_PROFILE.txt`. A competent
programmer can reimplement verification in any language using that
file alone.

---

## Contact

This system was built for long-term private use. There is no company
behind it, no support line, and no cloud dependency. That's the point.

The code is the documentation. The tests are the specification.
If the 17 compliance tests pass, the vault is correct.
