# Keeping Your Keys Safe

Your Memory Vault uses two keys to prove ownership. This document explains
what they are, where to put them, and what happens if you lose them.

---

## What are the keys?

When you create a vault, you get a file called `my_private_keys.json`.
It contains two keys:

- **Root key** — The master key. It can sign everything.
- **Quorum key** — The backup key. It can replace the root key if
  the root key is lost or stolen.

Together, they're like having a house key and a spare house key held
by a trusted neighbor.

---

## Where to store them

You need **at least two copies** in **different places**. Here are
the options, ranked from most to least secure:

### Option A: Password Manager (recommended for most people)

1. Open your password manager (1Password, Bitwarden, KeePass, etc.)
2. Create a new entry called "Memory Vault Keys"
3. Paste the entire contents of `my_private_keys.json` into the notes field
4. Save it
5. Delete the original `my_private_keys.json` file

**Pros:** Encrypted, backed up, searchable.
**Cons:** If you lose access to the password manager, you lose the keys.

### Option B: Printed Paper (recommended as backup)

1. Open `my_private_keys.json` in any text editor
2. Print it
3. Put the printout in a sealed envelope
4. Label it: "Memory Vault Recovery Keys — DO NOT OPEN unless needed"
5. Store in a safe, safety deposit box, or with a trusted person
6. Delete the digital file

**Pros:** Works without electricity. Survives account lockouts.
**Cons:** Can be physically stolen or destroyed.

### Option C: Encrypted USB Drive

1. Copy `my_private_keys.json` to a USB drive
2. Encrypt the drive (BitLocker on Windows, FileVault on Mac, LUKS on Linux)
3. Store the USB in a different physical location from your computer
4. Delete the original file

**Pros:** Portable, encrypted.
**Cons:** USB drives can fail. Use a quality brand and test yearly.

---

## What NOT to do

- **Never** keep the keys inside the vault folder
- **Never** email them to yourself or anyone
- **Never** paste them in a chat message, text, or social media
- **Never** store them in an unencrypted cloud folder (Google Drive,
  Dropbox, iCloud without additional encryption)
- **Never** take a screenshot of them

---

## The "sealed envelope" method

This is for people who want a dead-simple physical backup:

1. Print the keys
2. Put the printout in an envelope
3. Seal it and sign across the seal (so you'd know if it was opened)
4. Write on the outside:
   ```
   PRIVATE — Memory Vault Recovery Keys
   Owner: [your name]
   Date sealed: [date]
   Instructions: Do not open unless [your name] requests it,
   or in the event of [your name]'s death or incapacitation.
   ```
5. Give it to someone you trust, or put it in a safe

---

## For families: who should hold the keys?

If multiple family members use the vault system:

- Each person should have their **own** vault with their **own** keys
- No one needs anyone else's keys for normal use
- Designate one trusted person as the "key holder of last resort"
- That person holds sealed envelopes for each family member

This way:
- Everyone controls their own vault
- If someone loses their keys, the key holder can help
- If someone passes away, the key holder can transfer the vault

---

## Testing your backup

Once a year, verify you can still access your keys:

1. Open your password manager (or retrieve your printed copy)
2. Confirm the key file is readable and not corrupted
3. Optionally: run `check_backpack.sh` to verify your vault is healthy

If you can't find your keys, create new ones immediately:
```
cd SNP_Core/bin
python rekey_backpack.py /path/to/My_Backpack --rotate-all
```

---

## Summary

| Storage Method | Security | Durability | Convenience |
|---------------|----------|------------|-------------|
| Password manager | High | High (if backed up) | High |
| Printed paper in safe | High | Very high | Low |
| Encrypted USB | High | Medium | Medium |
| Unencrypted file on desktop | **None** | Low | High |

Use at least two methods. The goal is: no single point of failure.
