# What To Do When Things Go Wrong

This document covers every realistic failure scenario for your Memory Vault.
Read it now so you know where to find it later.

---

## Scenario 1: I lost my private key

**What this means:** You can no longer add new memories to your vault or
prove that it's yours. All existing memories are still readable.

**What to do:**

If your vault has a **quorum key** (it does if you used the default setup):
1. Find your `my_private_keys.json` file — it has both a "root" key and
   a "quorum" key
2. If you still have the quorum key, you can rotate your root key:
   ```
   cd SNP_Core/bin
   python rekey_backpack.py /path/to/My_Backpack --compromised root
   ```
3. This revokes the lost key and creates a new one
4. **Save the new key immediately**

If you've lost **both** keys:
- Your vault is now read-only. You can still see everything in it,
  but you cannot add to it or prove ownership.
- This is called "identity death." It is permanent.
- You can create a new vault and start fresh, but the old vault's
  chain of trust is broken.

**How to prevent this:**
- Store keys in at least 2 separate, secure places
- A password manager + a printed copy in a safe
- Never store keys inside the vault folder

---

## Scenario 2: My vault won't pass integrity checks

**What this means:** Something in the vault has been changed, corrupted,
or a file is missing.

**What to do:**

1. Run the check script and read the error carefully:
   ```
   ./check_backpack.sh /path/to/My_Backpack
   ```

2. **If a file hash doesn't match:** The file was modified (corruption
   or tampering). Restore that specific file from a backup.

3. **If the Merkle root doesn't match:** The manifest is out of date.
   If you intentionally added files, regenerate the manifest:
   ```
   cd SNP_Core/bin
   python manifest_generator.py /path/to/My_Backpack
   ```
   Then re-sign it with your private key.

4. **If a phantom file is detected:** There's a file in the vault that
   isn't in the manifest. Either remove it or regenerate the manifest.

5. **If the genesis or keys file is corrupted:** Restore from backup.
   These files cannot be regenerated.

**How to prevent this:**
- Back up your vault monthly (or after major additions)
- Use the check script after restoring from backup
- Keep backups on a separate physical device

---

## Scenario 3: I think someone accessed my private key

**What this means:** Someone may be able to add events to your vault
pretending to be you.

**What to do immediately:**

1. Rotate your compromised key:
   ```
   cd SNP_Core/bin
   python rekey_backpack.py /path/to/My_Backpack --compromised root
   ```
   This requires your quorum key (the second key in `my_private_keys.json`).

2. The rotation creates a "trust boundary" — any events signed by the
   old key after the compromise point are flagged as untrusted.

3. Generate a new private key file and secure it.

4. **Change the password** on any password manager or account where
   the old key was stored.

**If both keys are compromised:**
- Create a new vault (new identity)
- Your old vault should be treated as untrusted from the compromise point forward
- All events before the compromise are still valid and verifiable

---

## Scenario 4: I want to pass my vault to someone else

This is called **custody transfer**. The vault system was designed for this.

**Steps:**

1. Give them a copy of the vault folder
2. Give them the private keys (securely — in person, or via encrypted channel)
3. They should immediately rotate the keys:
   ```
   cd SNP_Core/bin
   python rekey_backpack.py /path/to/Backpack --rotate-all
   ```
4. This creates new keys under their control while preserving the full
   history and chain of trust

**What they receive:**
- The complete, verifiable history of the vault
- A new set of keys that only they control
- The ability to continue adding to the vault

**What you should do after transfer:**
- Delete your copy of the private keys
- Optionally keep a read-only backup of the vault

---

## Scenario 5: The check script itself is missing or broken

The vault is designed to be self-describing. The most important file is:

```
events/events.ndjson
```

This is plain text (JSON, one line per event). Any programmer — or any
future AI system — can read it without any special tools. The format is:

```json
{"event_id": "...", "type": "OBSERVATION", "actor": "...", "payload": {...}, ...}
```

Even if every script in this kit disappears, the data survives because:
- It's plain text (UTF-8 JSON)
- Each event is self-contained
- The format is documented in `SNP_Core/docs/README.md`
- Any SHA-256 implementation can verify the integrity hashes

This is the "50-year test": can someone read this with no internet,
no special software, and no knowledge of the system? Yes.

---

## Scenario 6: I'm starting over

If you want to create a fresh vault:

1. Keep your old vault as an archive (rename the folder)
2. Run `init_backpack.sh` or `init_backpack.bat` again
3. Secure the new private keys
4. The new vault has no connection to the old one — it's a new identity

---

## Key Concepts Reference

| Term | What it means |
|------|--------------|
| **Private key** | The secret that proves you own this vault. Never share it. |
| **Root key** | The primary key. Can do everything. |
| **Quorum key** | The backup key. Can rotate the root key if it's compromised. |
| **Key rotation** | Replacing a compromised key with a new one. |
| **Identity death** | All keys lost. Vault becomes read-only. Permanent. |
| **Merkle root** | A single number that proves nothing in the vault has changed. |
| **Events** | Your permanent record. Append-only. Never deleted. |
| **Compliance check** | 17 tests that verify everything is correct. |
