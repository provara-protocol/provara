# Demo Backpack

This is a working example of a Memory Vault. It was created to show you
what a vault looks like inside. You can explore it freely — it's not
connected to any real identity.

## What's in it

This demo vault contains 5 events:

1. **GENESIS** — The birth of this vault
2. **OBSERVATION** — System initialized
3. **OBSERVATION** — Grandma's favorite recipe (chocolate chip cookies)
4. **OBSERVATION** — Family home address
5. **OBSERVATION** — Dad's advice ("always back up your data")

## Try it

Run the integrity check to see what "17 tests passing" looks like:

```bash
# From the Legacy Kit root:
./check_backpack.sh Examples/Demo_Backpack
```

Look at the event log (it's plain text):
```bash
cat Examples/Demo_Backpack/events/events.ndjson
```

Each line is one event. You can read it with any text editor.

## This is NOT your vault

This demo has no private keys included. It's read-only by design.
When you create your own vault using `init_backpack.sh`, you'll get
your own identity, your own keys, and an empty event log ready for
your memories.
