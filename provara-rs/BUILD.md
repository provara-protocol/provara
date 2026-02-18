# provara-rs Build and Test Instructions

## Prerequisites

### Install Rust

**Windows (PowerShell):**
```powershell
winget install Rustlang.Rustup
# OR
choco install rust
# OR download from https://rustup.rs/
```

**macOS/Linux:**
```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
```

### Verify Installation

```bash
rustc --version    # Should show rustc 1.70.0 or later
cargo --version    # Should show cargo 1.70.0 or later
```

## Building

### Build All Crates

```bash
cd provara-rs
cargo build
```

### Build in Release Mode

```bash
cargo build --release
```

### Build with All Features (including WASM)

```bash
cargo build --all-features
```

## Testing

### Run All Tests

```bash
cargo test
```

### Run Tests with Output

```bash
cargo test -- --nocapture
```

### Run Specific Test

```bash
cargo test test_vectors::tests::test_load_and_run_vectors -- --nocapture
cargo test conformance::tests::test_run_conformance_suite -- --nocapture
```

### Run Tests for Specific Crate

```bash
cargo test -p jcs-rs
cargo test -p provara-core
```

## Linting

### Run Clippy

```bash
cargo clippy --all-targets --all-features -- -D warnings
```

### Format Code

```bash
cargo fmt --all -- --check
```

## WASM Build

### Install wasm-pack

```bash
cargo install wasm-pack
```

### Build for WASM

```bash
# For web usage
wasm-pack build --target web

# For Node.js
wasm-pack build --target nodejs

# For bundlers (webpack, etc.)
wasm-pack build --target bundler
```

### Test WASM Build

```bash
wasm-pack test --headless --firefox
wasm-pack test --headless --chrome
```

## Expected Test Output

When all tests pass, you should see:

```
running N tests
test tests::test_name ... ok
test test_vectors::tests::test_load_and_run_vectors ... ok
test conformance::tests::test_run_conformance_suite ... ok

test result: ok. M passed; 0 failed; 0 ignored; 0 measured; 0 filtered out

Test Vector Results:
  ✓ canonical_json_01: ...
  ✓ sha256_hash_01: ...
  ✓ event_id_derivation_01: ...
  ✓ key_id_derivation_01: ...
  ✓ ed25519_sign_verify_01: ...
  ✓ merkle_root_01: ...
  ✓ reducer_determinism_01: ...

Passed: 7/7

Canonical Conformance Suite Results:
  ✓ key_ordering_01
  ✓ key_ordering_unicode
  ✓ empty_containers_01
  ...

Passed: 12/12
```

## Troubleshooting

### "cargo: command not found"

Rust is not installed or not in your PATH. Install Rust using the instructions above, then restart your terminal.

### "rustc 1.XX is not compatible"

Upgrade Rust to version 1.70 or later:

```bash
rustup update
```

### WASM Build Fails

Ensure you have the wasm32 target installed:

```bash
rustup target add wasm32-unknown-unknown
```

### Test Vectors Not Found

Make sure you're running tests from the `provara-rs` directory. The test vectors are loaded from `../test_vectors/`.

## Publishing to crates.io

### jcs-rs

```bash
cd jcs-rs
cargo publish --dry-run  # Verify before publishing
cargo publish
```

### provara-core

```bash
cd provara-core
cargo publish --dry-run  # Verify before publishing
cargo publish
```

**Note:** Publish jcs-rs first, as provara-core depends on it.

## Minimum Supported Rust Version (MSRV)

The minimum supported Rust version is **1.70.0**.

## License

Apache 2.0 — See [LICENSE](../../LICENSE) for details.
