# jcs-rs

[![Crates.io](https://img.shields.io/crates/v/jcs-rs.svg)](https://crates.io/crates/jcs-rs)
[![Documentation](https://docs.rs/jcs-rs/badge.svg)](https://docs.rs/jcs-rs)
[![License](https://img.shields.io/crates/l/jcs-rs.svg)](https://github.com/provara-protocol/provara/blob/main/LICENSE)

**RFC 8785 JSON Canonicalization Scheme implementation in Rust**

This crate provides deterministic JSON serialization according to [RFC 8785](https://www.rfc-editor.org/rfc/rfc8785.html). It is a standalone crate with zero Provara-specific assumptions, suitable for any project requiring canonical JSON.

## Features

- **Lexicographic key ordering** — Object keys sorted by Unicode code point
- **No whitespace** — Minimal output with no spaces between tokens
- **Minimal escapes** — Only necessary escape sequences in strings
- **Canonical numbers** — No leading zeros, no trailing decimal zeros
- **UTF-8 encoding** — Without BOM
- **`no_std` compatible** — Enables embedded and WASM targets
- **WASM bindings** — Ready for browser usage

## Installation

```toml
[dependencies]
jcs-rs = "0.1.0"
```

## Usage

### Basic Canonicalization

```rust
use serde_json::json;
use jcs_rs::{canonicalize, canonical_to_string};

let value = json!({
    "z": null,
    "a": true,
    "b": [1, 2, 3],
    "m": {"inner": 42}
});

// Get canonical bytes
let canonical_bytes = canonicalize(&value).unwrap();

// Or get canonical string
let canonical_str = canonical_to_string(&value).unwrap();
assert_eq!(
    canonical_str,
    r#"{"a":true,"b":[1,2,3],"m":{"inner":42},"z":null}"#
);
```

### Hashing Canonical JSON

```rust
use serde_json::json;
use jcs_rs::{canonical_hash, canonical_hash_hex};

let value = json!({"key": "value"});

// Get SHA-256 hash of canonical JSON
let hash_bytes = canonical_hash(&value).unwrap();
let hash_hex = canonical_hash_hex(&value).unwrap();
```

### Serializable Types

```rust
use serde::Serialize;
use jcs_rs::canonicalize_serializable;

#[derive(Serialize)]
struct Data {
    name: String,
    count: u32,
}

let data = Data {
    name: "test".to_string(),
    count: 42,
};

let canonical = canonicalize_serializable(&data).unwrap();
```

### WASM Usage

```javascript
import init, { canonicalize_js, canonicalize_string_js } from 'jcs-rs';

await init();

const input = JSON.stringify({ z: 1, a: 2, m: 3 });
const canonical = canonicalize_string_js(input);
console.log(canonical); // {"a":2,"m":3,"z":1}
```

## API Reference

### Core Functions

- `canonicalize(value: &Value) -> Result<Vec<u8>, CanonicalizeError>` — Canonicalize to bytes
- `canonical_to_string(value: &Value) -> Result<String, CanonicalizeError>` — Canonicalize to string
- `canonicalize_serializable<T: Serialize>(value: &T) -> Result<Vec<u8>, CanonicalizeError>` — Canonicalize any serializable type
- `canonical_hash(value: &Value) -> Result<[u8; 32], CanonicalizeError>` — SHA-256 hash of canonical JSON
- `canonical_hash_hex(value: &Value) -> Result<String, CanonicalizeError>` — SHA-256 hash as hex string

### WASM Functions

- `canonicalize_js(value: &JsValue) -> Result<Vec<u8>, JsValue>` — Canonicalize from JavaScript
- `canonicalize_string_js(value: &JsValue) -> Result<String, JsValue>` — Canonicalize to string from JavaScript

## Compliance

This implementation passes the Provara RFC 8785 Canonical JSON Conformance Suite, which includes:

- Key ordering (lexicographic by Unicode code point)
- Unicode key sorting
- Empty container preservation
- Nested structure handling
- Null value preservation
- String escape minimization
- Unicode string distinctness (NFC/NFD)
- Number formatting
- Boolean and null handling
- Array mixed types
- Key prefix ordering

## `no_std` Support

To use in a `no_std` environment:

```toml
[dependencies]
jcs-rs = { version = "0.1.0", default-features = false }
```

## License

Apache 2.0 — See [LICENSE](https://github.com/provara-protocol/provara/blob/main/LICENSE) for details.

## Contributing

Contributions welcome! Please read our [contributing guidelines](https://github.com/provara-protocol/provara/blob/main/CONTRIBUTING.md) first.

## Repository

https://github.com/provara-protocol/provara
