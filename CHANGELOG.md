# Changelog — Provara Protocol

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.3] — 2026-03-08

### Added
- **Managed Vault Support:** Initial implementation of Provara SaaS backend (FastAPI + Docker) for remote, verifiable memory logging.
- **SaaS Bridge in MCP:** The MCP server now supports `saas://` URIs, enabling AI agents to use managed vaults on Provara Cloud.
- **Waitlist & B2B Site:** Re-architected `provara.app` as an AI audit trail developer platform.

### Fixed
- Version parity across SDK, CLI, and Forensic Export modules.
- Updated `mcp.py` to handle missing dependencies gracefully for non-SaaS users.

## [1.0.2] — 2026-03-07

### Fixed
- `provara verify` and `provara backup` no longer depend on test-only modules (`backpack_compliance_v1`) in pip installs.
- Added package-internal integrity checks for manifest content, Merkle root, causal chains, and event signatures.
- Removed `verify` side effects that created `identity/privacy_keys.db` during read-only checks.

## [1.0.1] — 2026-03-07

### Added
- **Full Compliance Suite:** Integrated `backpack_compliance_v1.py` with 18 automated protocol verification tests.
- **Parallel Verification Engine:** Highly optimized event signature verification for large logs.
- **Stability Classifiers:** Updated `pyproject.toml` to "Development Status :: 5 - Production/Stable".
- **Documentation:** Prepared foundations for `provara.dev` via `mkdocs-material`.

### Fixed
- Fixed edge cases in `verify_sovereign_events()` where detached actors could skip validation.
- Improved error handling for malformed NDJSON lines during sync.
- Corrected Merkle root recomputation logic in the manifest verification layer.

## [1.0.0] — 2026-02-26

### Added
- **Official Protocol Release:** Canonical implementation of the Provara Ed25519-signed NDJSON event log.
- **The Reducer:** Deterministic state machine for replaying event logs into queryable snapshots.
- **PSMC CLI:** The Provara Sovereign Memory Controller for vault management.
- **Sync Engine:** Robust union-merge implementation for offline-first data synchronization.
- **Key Rotation:** Secure authority transfer and key revocation logic.
- **Sovereign Digital Blueprint:** Foundational design patterns for cryptographic memory.

---
## 0.x — Development Alpha

- Initial POC of the signed NDJSON chain.
- Hypothesis-based fuzz testing for collision detection.
- Merkle manifest prototyping.
