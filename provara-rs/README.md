# provara-rs

**Rust implementation of the Provara Protocol v1.0**

This workspace contains two crates:

- **[jcs-rs](./jcs-rs)** — Standalone RFC 8785 JSON Canonicalization Scheme
- **[provara-core](./provara-core)** — Provara Protocol core (Ed25519, SHA-256, events, chain validation)

## Quick Start

```bash
# Build both crates
cargo build

# Run all tests
cargo test

# Run clippy
cargo clippy --all-targets --all-features
```

See [BUILD.md](./BUILD.md) for detailed build instructions.

## Crates

### jcs-rs

[![Crates.io](https://img.shields.io/crates/v/jcs-rs.svg)](https://crates.io/crates/jcs-rs)

RFC 8785 canonical JSON implementation. This is a standalone crate suitable for any project requiring deterministic JSON serialization.

**Features:**
- Lexicographic key ordering
- Minimal whitespace and escapes
- `no_std` compatible
- WASM bindings

[→ jcs-rs Documentation](./jcs-rs/README.md)

### provara-core

[![Crates.io](https://img.shields.io/crates/v/provara-core.svg)](https://crates.io/crates/provara-core)

Core Provara Protocol implementation with cryptographic primitives.

**Features:**
- Ed25519 signing/verification (RFC 8032)
- SHA-256 hashing (FIPS 180-4)
- Event creation and validation
- Causal chain verification
- Key ID derivation (bp1_...)
- Merkle tree computation
- `no_std` compatible
- WASM bindings

[→ provara-core Documentation](./provara-core/README.md)

## Compliance

This implementation passes:

- ✅ 7/7 test vectors from `test_vectors/vectors.json`
- ✅ 12/12 canonical conformance tests from `test_vectors/canonical_conformance.json`
- ✅ Provara Protocol v1.0 specification requirements

## Architecture

```
provara-rs/
├── Cargo.toml              # Workspace configuration
├── jcs-rs/
│   ├── Cargo.toml          # jcs-rs crate config
│   ├── src/
│   │   └── lib.rs          # RFC 8785 implementation
│   └── README.md
├── provara-core/
│   ├── Cargo.toml          # provara-core crate config
│   ├── src/
│   │   ├── lib.rs          # Main module
│   │   ├── test_vectors.rs # Test vector validation
│   │   └── conformance.rs  # Conformance suite
│   ├── package.json        # WASM package config
│   └── README.md
└── BUILD.md                # Build instructions
```

## Dependencies

### jcs-rs

- `serde` — Serialization framework
- `serde_json` — JSON parsing
- `thiserror` — Error handling
- `sha2` — SHA-256 (for hash functions)
- `hex` — Hex encoding

### provara-core

- `jcs-rs` — Canonical JSON (this workspace)
- `ed25519-dalek` — Ed25519 signatures (RustCrypto)
- `sha2` — SHA-256 (RustCrypto)
- `signature` — Signature traits
- `serde` / `serde_json` — JSON handling
- `base64` — Base64 encoding
- `hex` — Hex encoding
- `rand_core` — Random number generation

## WASM Support

Both crates support WASM compilation:

```bash
# Install wasm-pack
cargo install wasm-pack

# Build provara-core for WASM
cd provara-core
wasm-pack build --target web
```

WASM exports:
- `WasmKeyPair` — Keypair generation and management
- `create_event_js` — Create signed events from JavaScript
- `verify_chain_js` — Verify causal chains from JavaScript
- `canonicalize_js` — Canonicalize JSON from JavaScript

## Example Usage

### Rust

```rust
use provara_core::{KeyPair, create_event, verify_causal_chain};
use serde_json::json;
use rand::thread_rng;

// Generate keypair
let mut rng = thread_rng();
let keypair = KeyPair::generate(&mut rng);

// Create events
let event1 = create_event(
    "OBSERVATION",
    &keypair,
    None,
    json!({"subject": "test", "value": "ok"}),
).unwrap();

let event2 = create_event(
    "OBSERVATION",
    &keypair,
    Some(event1.event_id.clone()),
    json!({"subject": "test", "value": "updated"}),
).unwrap();

// Verify chain
verify_causal_chain(&[event1, event2]).unwrap();
```

### JavaScript (WASM)

```javascript
import init, { WasmKeyPair, create_event_js, verify_chain_js } from 'provara-core';

await init();

// Generate keypair
const keypair = new WasmKeyPair();
console.log("Key ID:", keypair.key_id);

// Create event
const event = create_event_js(
    "OBSERVATION",
    JSON.stringify({ subject: "test", value: "ok" }),
    null
);

// Verify chain
const valid = verify_chain_js(JSON.stringify([event]));
console.log("Chain valid:", valid);
```

## Testing

```bash
# All tests
cargo test

# With output
cargo test -- --nocapture

# Specific crate
cargo test -p jcs-rs
cargo test -p provara-core

# WASM tests
wasm-pack test --headless --firefox
```

## Publish jcs-rs

```bash
cargo publish --dry-run -p jcs-rs
# then, when ready:
# cargo publish -p jcs-rs
```

## License

Apache 2.0 — See [LICENSE](../LICENSE) for details.

## Contributing

Contributions welcome! Please read our [contributing guidelines](../CONTRIBUTING.md) first.

## Repository

https://github.com/provara-protocol/provara

## See Also

- [Provara Protocol Specification](../PROTOCOL_PROFILE.txt)
- [Python Reference Implementation](../src/provara/)
- [Test Vectors](../test_vectors/)
