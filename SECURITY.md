# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 1.0.x   | Yes       |

## Reporting a Vulnerability

If you discover a security vulnerability in the Provara Protocol or its reference implementation, **do not open a public issue.**

Instead, report via one of these channels:

1. **GitHub Private Vulnerability Reporting** (preferred): Use the [Security Advisories](https://github.com/provara-protocol/provara/security/advisories/new) feature on this repository to report privately.
2. **Email**: **security@huntinformationsystems.com**

Include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

We will acknowledge receipt within 48 hours and provide a detailed response within 7 days.

## Scope

The following are in scope for security reports:

- Cryptographic weaknesses (signature bypass, hash collisions, key leakage)
- Event log tampering that passes verification
- Manifest integrity bypass
- Key rotation vulnerabilities
- Causal chain manipulation

The following are out of scope:

- Bugs in the `cryptography` library (report upstream)
- Social engineering attacks
- Physical access attacks (key theft from unencrypted storage)

## Cryptographic Primitives

Provara v1.0 uses:
- **Ed25519** (RFC 8032) for signatures
- **SHA-256** (FIPS 180-4) for hashing
- **RFC 8785** for canonical JSON serialization

If a vulnerability is found in any of these primitives, we will issue an advisory and migration plan.
