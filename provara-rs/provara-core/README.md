# provara-core

[![Crates.io](https://img.shields.io/crates/v/provara-core.svg)](https://crates.io/crates/provara-core)
[![Documentation](https://docs.rs/provara-core/badge.svg)](https://docs.rs/provara-core)
[![License](https://img.shields.io/crates/l/provara-core.svg)](https://github.com/provara-protocol/provara/blob/main/LICENSE)

**Provara Protocol v1.0 Core Implementation in Rust**

This crate provides the core cryptographic primitives and data structures for the [Provara Protocol](https://github.com/provara-protocol/provara), including:

- Ed25519 signing and verification (RFC 8032)
- SHA-256 hashing (FIPS 180-4)
- Event creation and validation
- Causal chain verification
- Key ID derivation
- Merkle tree computation

## Installation

```toml
[dependencies]
provara-core = "0.1.0"
```

## Quick Start

### Generate a Keypair

```rust
use provara_core::KeyPair;
use rand::thread_rng;

let mut rng = thread_rng();
let keypair = KeyPair::generate(&mut rng);

println!("Key ID: {}", keypair.key_id().unwrap());
println!("Public Key: {}", hex::encode(keypair.public_key()));
```

### Create a Signed Event

```rust
use provara_core::{create_event, KeyPair};
use serde_json::json;
use rand::thread_rng;

let mut rng = thread_rng();
let keypair = KeyPair::generate(&mut rng);

let event = create_event(
    "OBSERVATION",
    &keypair,
    None, // No previous event (genesis)
    json!({
        "subject": "door",
        "predicate": "state",
        "value": "open"
    }),
).unwrap();

println!("Event ID: {}", event.event_id);
println!("Signature: {:?}", event.signature);
```

### Verify an Event Signature

```rust
use provara_core::{create_event, verify_event_signature, KeyPair};
use serde_json::json;
use rand::thread_rng;

let mut rng = thread_rng();
let keypair = KeyPair::generate(&mut rng);

let event = create_event(
    "OBSERVATION",
    &keypair,
    None,
    json!({"data": "test"}),
).unwrap();

// Verify with the public key
let valid = verify_event_signature(&event, &keypair.public_key()).unwrap();
assert!(valid);
```

### Build a Causal Chain

```rust
use provara_core::{create_event, verify_causal_chain, KeyPair};
use serde_json::json;
use rand::thread_rng;

let mut rng = thread_rng();
let keypair = KeyPair::generate(&mut rng);

// Genesis event
let event1 = create_event(
    "OBSERVATION",
    &keypair,
    None,
    json!({"seq": 1}),
).unwrap();

// Second event (references first)
let event2 = create_event(
    "OBSERVATION",
    &keypair,
    Some(event1.event_id.clone()),
    json!({"seq": 2}),
).unwrap();

// Verify the chain
let events = vec![event1, event2];
verify_causal_chain(&events).unwrap(); // Returns Ok if chain is valid
```

### Compute Merkle Root

```rust
use provara_core::compute_merkle_root;
use serde_json::json;

let entries = vec![
    json!({
        "path": "a.txt",
        "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "size": 0
    }),
    json!({
        "path": "b.txt",
        "sha256": "315f5bdb76d078c43b8ac00c33e22F06d20353842d059013e96196a84f33161",
        "size": 1
    }),
];

let root = compute_merkle_root(&entries).unwrap();
println!("Merkle Root: {}", root);
```

## WASM Usage

Build for WASM:

```bash
cargo install wasm-pack
wasm-pack build --target web
```

Use in JavaScript:

```javascript
import init, { 
    WasmKeyPair, 
    create_event_js, 
    verify_chain_js 
} from 'provara-core';

await init();

// Generate a keypair
const keypair = new WasmKeyPair();
console.log("Key ID:", keypair.key_id);
console.log("Public Key:", keypair.public_key_hex);

// Create an event
const payload = JSON.stringify({ subject: "test", value: "ok" });
const event = create_event_js("OBSERVATION", payload, null);
console.log("Event:", event);

// Verify a chain
const events = JSON.stringify([event]);
const valid = verify_chain_js(events);
console.log("Chain valid:", valid);
```

## API Reference

### Key Management

- `KeyPair::generate(rng: &mut R) -> Self` — Generate a new random keypair
- `KeyPair::from_bytes(seed: &[u8; 32]) -> Result<Self, ProvaraError>` — Create from seed
- `KeyPair::public_key() -> [u8; 32]` — Get public key bytes
- `KeyPair::key_id() -> Result<String, ProvaraError>` — Get Provara key ID (bp1_...)
- `derive_key_id(public_key_bytes: &[u8; 32]) -> Result<String, ProvaraError>` — Derive key ID from public key

### Event Operations

- `create_event(event_type, keypair, prev_event_hash, payload) -> Result<Event, ProvaraError>` — Create signed event
- `derive_event_id(event: &Event) -> Result<String, ProvaraError>` — Compute content-addressed event ID
- `verify_event_signature(event, public_key) -> Result<bool, ProvaraError>` — Verify event signature
- `verify_causal_chain(events: &[Event]) -> Result<(), ProvaraError>` — Verify chain integrity

### Hashing

- `sha256_hash(data: &[u8]) -> [u8; 32]` — Compute SHA-256 hash
- `sha256_hash_hex(data: &[u8]) -> String` — Compute SHA-256 as hex string
- `compute_merkle_root(file_entries: &[Value]) -> Result<String, ProvaraError>` — Compute Merkle root
- `compute_state_hash(state: &Value) -> Result<String, ProvaraError>` — Compute state hash

### Canonical JSON (re-exported from jcs-rs)

- `canonicalize(value: &Value) -> Result<Vec<u8>, CanonicalizeError>`
- `canonical_to_string(value: &Value) -> Result<String, CanonicalizeError>`
- `canonical_hash(value: &Value) -> Result<[u8; 32], CanonicalizeError>`
- `canonical_hash_hex(value: &Value) -> Result<String, CanonicalizeError>`

## Event Types

Provara defines these core event types:

- `OBSERVATION` — Record a sensor reading or observation
- `ATTESTATION` — Attest to the truth of a statement
- `RETRACTION` — Retract a previous attestation
- `GENESIS` — Initialize a new vault
- `KEY_REVOCATION` — Revoke a signing key
- `KEY_PROMOTION` — Promote a new signing key

## Protocol Compliance

This implementation:

- ✅ Passes all 7 test vectors in `test_vectors/vectors.json`
- ✅ Passes the RFC 8785 canonical conformance suite
- ✅ Implements Ed25519 per RFC 8032
- ✅ Implements SHA-256 per FIPS 180-4
- ✅ Implements key ID derivation per Provara spec
- ✅ Implements event ID derivation per Provara spec
- ✅ Implements causal chain verification

## `no_std` Support

To use in a `no_std` environment:

```toml
[dependencies]
provara-core = { version = "0.1.0", default-features = false }
```

Note: Random number generation requires an external RNG source in `no_std` mode.

## Error Handling

All operations return `Result<T, ProvaraError>` with these error variants:

- `ProvaraError::Crypto` — Cryptographic operation failed
- `ProvaraError::InvalidEvent` — Event structure is invalid
- `ProvaraError::ChainValidation` — Causal chain verification failed
- `ProvaraError::KeyDerivation` — Key ID derivation failed
- `ProvaraError::Serialization` — JSON serialization failed
- `ProvaraError::Encoding` — Base64/hex encoding failed

## Testing

```bash
# Run all tests
cargo test

# Run with output
cargo test -- --nocapture

# Run clippy
cargo clippy --all-targets --all-features -- -D warnings
```

## License

Apache 2.0 — See [LICENSE](https://github.com/provara-protocol/provara/blob/main/LICENSE) for details.

## Contributing

Contributions welcome! Please read our [contributing guidelines](https://github.com/provara-protocol/provara/blob/main/CONTRIBUTING.md) first.

## Repository

https://github.com/provara-protocol/provara

## See Also

- [jcs-rs](../jcs-rs) — Standalone RFC 8785 crate
- [Provara Protocol Spec](https://github.com/provara-protocol/provara/blob/main/PROTOCOL_PROFILE.txt)
