# Security Policy

Provara takes security seriously. This document outlines our security policy and how to report vulnerabilities.

---

## Reporting a Vulnerability

**Do not open a public issue for security vulnerabilities.**

To report a security issue:

1. **Email:** security@provara.dev
2. **Include:**
   - Description of the vulnerability
   - Steps to reproduce
   - Impact assessment (what can an attacker do?)
   - Suggested fix (if any)
3. **We will respond within 48 hours** with an acknowledgment.
4. **We request 90 days** for patch development before public disclosure.

If you do not receive a response within 48 hours, please follow up.

---

## Scope

### In Scope

The following are considered security vulnerabilities:

| Category | Examples |
|----------|----------|
| **Cryptographic** | Signature bypass, hash collision, key recovery, nonce reuse |
| **Remote Code Execution** | Arbitrary code execution via crafted events or payloads |
| **Data Corruption** | Silent data loss, event tampering without detection |
| **Authentication Bypass** | Unauthorized vault access, key impersonation |
| **Privilege Escalation** | Unauthorized key rotation, policy bypass |

### Out of Scope

The following are **not** considered vulnerabilities in Provara:

| Category | Rationale |
|----------|-----------|
| **Denial of Service** | Availability is user responsibility (see Threat Model) |
| **Information Disclosure** | Provara does not encrypt; confidentiality is out of scope |
| **Social Engineering** | No technical control can prevent user deception |
| **Physical Access Attacks** | If attacker has physical access, all bets are off |
| **Key Loss** | Key management is user responsibility |

If you're unsure whether something is in scope, email us and we'll clarify.

---

## Response Timeline

We commit to the following timeline:

| Milestone | Target |
|-----------|--------|
| Initial response | 48 hours |
| Triage complete | 5 business days |
| Patch developed | 90 days |
| Public disclosure | After patch release |

We will keep you informed of our progress throughout the process.

---

## Disclosure Policy

We follow coordinated disclosure:

1. **Reporter submits vulnerability** to security@provara.dev.
2. **We acknowledge receipt** within 48 hours.
3. **We triage and assess** severity and impact.
4. **We develop and test a patch.**
5. **We notify users** via security advisory (if critical).
6. **We release the patch** and publish a CVE (if applicable).
7. **We credit the reporter** (unless they prefer anonymity).

---

## Security Advisories

Security advisories are published at:

- **GitHub Security Advisories:** https://github.com/provara-protocol/provara/security/advisories
- **Mailing List:** security-announce@provara.dev (subscribe for notifications)

### Advisory Format

Each advisory includes:

- **Summary:** Brief description of the vulnerability.
- **Severity:** CVSS score and rating (Critical/High/Medium/Low).
- **Affected Versions:** Which versions are vulnerable.
- **Patched Versions:** Which versions contain the fix.
- **Workarounds:** Mitigations if upgrading is not immediately possible.
- **References:** Links to related issues, CVEs, or external resources.

---

## Vulnerability Severity

We use CVSS v3.1 for severity scoring:

| Rating | CVSS Score | Response Time |
|--------|------------|---------------|
| **Critical** | 9.0–10.0 | 24 hours |
| **High** | 7.0–8.9 | 7 days |
| **Medium** | 4.0–6.9 | 30 days |
| **Low** | 0.1–3.9 | 90 days |

### Severity Examples

**Critical:**
- Remote code execution via crafted event.
- Signature verification bypass.
- Private key extraction from memory.

**High:**
- Chain integrity check bypass.
- Unauthorized key rotation.
- Event injection without detection.

**Medium:**
- Information disclosure (if encryption is layered).
- Denial of service (if specific conditions met).

**Low:**
- Non-cryptographic hash collision (non-security impact).
- Minor input validation issues.

---

## Security Best Practices

### For Users

1. **Secure your keys:**
   - Store private keys encrypted at rest.
   - Use HSMs or YubiKeys for high-value vaults.
   - Never store keys on the same drive as the vault.

2. **Verify before trusting:**
   - Run `provara verify` before relying on vault state.
   - Check Merkle root and manifest signatures.
   - Verify causal chain integrity.

3. **Maintain backups:**
   - Use the 3-2-1 rule (3 copies, 2 media types, 1 offsite).
   - Test restore procedures regularly.
   - Encrypt backups if confidentiality is required.

4. **Stay updated:**
   - Subscribe to security-announce@provara.dev.
   - Monitor GitHub Security Advisories.
   - Upgrade promptly when patches are released.

### For Developers

1. **Validate all inputs:**
   - Never trust external event data.
   - Validate JSON Schema for custom event types.
   - Check signature before processing events.

2. **Use constant-time comparisons:**
   - Compare signatures in constant time.
   - Avoid timing side-channels.

3. **Handle errors safely:**
   - Don't leak sensitive information in error messages.
   - Log security events for audit.

4. **Follow cryptographic best practices:**
   - Use libraries, don't roll your own crypto.
   - Follow [PROTOCOL_PROFILE.txt](PROTOCOL_PROFILE.txt) exactly.
   - Never modify cryptographic parameters without review.

---

## Security Testing

We employ multiple security testing strategies:

### Automated Testing

- **Unit tests:** 495+ tests covering cryptographic operations.
- **Property-based testing:** Hypothesis fuzzing for edge cases.
- **Integration tests:** End-to-end vault operations.

### Manual Review

- **Code review:** All changes reviewed by maintainers.
- **Security audit:** Third-party audit planned for 2026.
- **Bug bounty:** Under consideration (contact us if interested).

### External Testing

We welcome external security testing:

- **Academic researchers:** Contact us for test vaults and guidance.
- **Security consultants:** We can provide scoped testing environments.
- **Community members:** Report findings via security@provara.dev.

---

## Past Advisories

### 2026

No security advisories issued to date.

---

## Contact

- **Security Email:** security@provara.dev
- **PGP Key:** [Available upon request]
- **Response Time:** 48 hours

For non-security issues, use [GitHub Issues](https://github.com/provara-protocol/provara/issues).

---

## Acknowledgments

We thank security researchers who responsibly disclose vulnerabilities. Contributors will be credited in security advisories (unless they prefer anonymity).

---

## References

- [Threat Model](docs/THREAT_MODEL.md) — Detailed STRIDE analysis
- [PROTOCOL_PROFILE.txt](PROTOCOL_PROFILE.txt) — Cryptographic specification
- [Contributing Guide](CONTRIBUTING.md) — Security guidelines for contributors
