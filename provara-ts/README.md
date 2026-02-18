# provara-ts

TypeScript implementation of the **Provara Protocol v1.0** — tamper-evident,
append-only event log using Ed25519 + SHA-256 + RFC 8785 canonical JSON.

## Overview

This package is byte-compatible with the Python reference implementation.
Events signed by Python can be verified by TypeScript and vice versa.

## Modules

| Module | Purpose |
|--------|---------|
| `jcs.ts` | RFC 8785 JSON Canonicalization Scheme — custom tokenizer preserving int/float distinction |
| `crypto.ts` | Ed25519 + SHA-256 via Node.js `node:crypto` |
| `event.ts` | Event creation, signing, and signature verification |
| `chain.ts` | Per-actor causal chain validation |
| `merkle.ts` | Binary SHA-256 Merkle tree |
| `reducer.ts` | Deterministic state reducer (port of `SovereignReducerV0`) |
| `vault.ts` | Vault read and signature verification |

## Requirements

- Node.js 18+
- No runtime dependencies

## Setup

```sh
npm install
```

## Build and Test

```sh
npm test        # build + run all tests
npm run build   # compile TypeScript only
npm run typecheck  # type-check without emitting
```

## Cross-implementation compatibility

Python serializes integer-valued floats as `1.0` (not `1`). JavaScript's
`JSON.parse` discards this distinction. The custom tokenizer in `jcs.ts`
preserves the original number representation from raw JSON text, making
`verifyEventSignatureRaw(rawLine, publicKeyB64)` produce the same canonical
bytes as the Python signer.

```typescript
import { verifyEventSignatureRaw, loadRawEvents, loadKeysRegistry } from "provara";

const lines    = loadRawEvents("path/to/events.ndjson");
const registry = loadKeysRegistry("path/to/identity/keys.json");

for (const line of lines) {
  const keyId    = /"actor_key_id":"([^"]+)"/.exec(line)![1];
  const pubKey   = registry[keyId].public_key_b64;
  const ok       = verifyEventSignatureRaw(line, pubKey);
  console.log(ok ? "✓" : "✗", keyId);
}
```

## Key ID format

```
bp1_<first-16-hex-chars-of-SHA-256(raw-32-byte-pubkey)>
```

## Test results

52 tests pass, including:
- 12 RFC 8785 conformance vectors (including `minus_zero` via custom tokenizer)
- 6 of 7 Provara test vectors (one has a pre-existing signature defect)
- Cross-implementation verification of the Python-created reference backpack
