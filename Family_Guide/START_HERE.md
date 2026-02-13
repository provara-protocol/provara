# Welcome to Your Memory Vault

This is a system for keeping a permanent, private record of what matters to you.

Think of it as a journal that can never be edited after the fact, can never be
locked away by a company, and can be passed down to people you trust.

It's not an app. It's not a service. It's a folder on your computer that
holds your memories in a format that will still be readable in 50 years.

---

## What's Inside

Your Memory Vault (we call it a "Backpack") is a folder containing:

- **Your identity** — a unique ID and a set of keys that prove it's yours
- **Your events** — everything you record, in the order it happened
- **Your policies** — rules about what's allowed and who you trust
- **A tamper seal** — a mathematical proof that nothing has been changed

You don't need to understand how any of this works. You just need to know
three things.

---

## The Three Rules

### 1. Keep your private key safe

When you create your vault, you'll get a file called `my_private_keys.json`.

This is the only thing that proves you own your vault. If someone else gets
it, they can pretend to be you. If you lose it, you lose the ability to
add new memories.

**What to do with it:**
- Save it in your password manager (1Password, Bitwarden, etc.)
- Print a copy and keep it in a safe, a safety deposit box, or a sealed
  envelope with someone you trust
- **Never** put it inside the vault folder itself
- **Never** email it, text it, or upload it anywhere

### 2. Back up your vault regularly

Your vault is just a folder. The easiest way is to use the included
backup script — just run `backup_vault.sh` (Mac/Linux) or double-click
`backup_vault.bat` (Windows). It verifies your vault, creates a
timestamped zip, verifies the zip, and cleans up old backups.

You can also copy the vault manually:
- To an external hard drive or USB stick
- To a second computer
- To encrypted cloud storage if you trust the provider

The vault checks itself for tampering every time you use it. If a copy
gets corrupted, you'll know.

### 3. Don't delete the events file

Everything in your vault can be regenerated from one file:
`events/events.ndjson`. This is your permanent record. The rest is
derived from it. If you lose everything else, this file alone can
reconstruct your entire vault.

---

## Getting Started

### First time? Create your vault.

**On Mac or Linux**, open Terminal and run:
```
./init_backpack.sh
```

**On Windows**, double-click:
```
init_backpack.bat
```

This will:
1. Create a new vault in a folder called `My_Backpack`
2. Generate your identity and keys
3. Save your private keys to `my_private_keys.json`
4. Run a self-check to make sure everything is correct

You'll see a message like:
```
✓ Your Memory Vault has been created.
✓ All 17 integrity checks passed.

⚠ IMPORTANT: Move my_private_keys.json to a safe location NOW.
  Then delete it from this folder.
```

### Back up your vault

**On Mac or Linux:**
```
./backup_vault.sh
```

**On Windows**, double-click:
```
backup_vault.bat
```

This will:
1. Verify your vault hasn't been tampered with
2. Create a timestamped zip file in a `Backups/` folder
3. Verify the backup itself is valid
4. Write a hash file so you can check it later
5. Automatically delete backups older than 3 months

You can also set it to run automatically every week. Instructions are
inside the script files.

### Already have a vault? Check it.

```
./check_backpack.sh
```
or on Windows:
```
check_backpack.bat
```

This runs the same 17 integrity checks. If anything has been tampered
with or corrupted, it will tell you exactly what's wrong.

---

## What Can I Do With This?

Right now, the vault is a foundation. It's the part that guarantees your
data is yours, is tamper-proof, and will survive regardless of what
happens to any company or technology.

What you build on top of it is up to you:
- A private AI journal that remembers your conversations
- A family knowledge base that gets passed down
- A personal record that no company can lock you out of
- A system that can one day connect to physical devices you own

The important thing is that the foundation exists, is provably correct,
and belongs to you — not to any service provider.

---

## If Something Goes Wrong

See the `Recovery/` folder for instructions on:
- What to do if you lose your private key
- What to do if your vault gets corrupted
- What to do if you think someone accessed your key
- How to pass your vault to someone else

---

## Questions?

This system was built by someone who cares about your right to own your
own memories. If you're reading this and you're confused, that's okay.
The vault works whether or not you understand the details. Just follow
the three rules above and you'll be fine.

The technical documentation is in `SNP_Core/docs/` if you ever want
to understand what's under the hood. But you never have to.
