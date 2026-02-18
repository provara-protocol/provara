# jcs-rs

**RFC 8785 JSON Canonicalization Scheme (JCS) for Rust**

Pure Rust implementation of [RFC 8785](https://www.rfc-editor.org/rfc/rfc8785),
the JSON Canonicalization Scheme. Produces deterministic, byte-identical
JSON output for any semantically equivalent input.

## Usage
```rust
use jcs_rs::canonicalize;
use serde_json::json;

let value = json!({"b": 2, "a": 1});
let canonical = canonicalize(&value).unwrap();
assert_eq!(canonical, b"{\"a\":1,\"b\":2}");
```

## Why JCS?
Deterministic JSON is required when signatures, hashes, and Merkle proofs depend on exact bytes. Standard JSON serializers may vary key order or float formatting across implementations. RFC 8785 gives a stable encoding so cryptographic verification remains portable.

## Conformance
Passes all 12 Provara canonical conformance vectors and additional RFC-aligned edge-case tests. Part of the Provara Protocol ecosystem.

## API
- `canonicalize(&serde_json::Value) -> Result<Vec<u8>, Error>`
- `canonicalize_str(&str) -> Result<Vec<u8>, Error>`
- `is_canonical(&[u8]) -> bool`

## License
Apache-2.0
