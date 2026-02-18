# Sigstore Transparency Log Anchoring

**Status:** Optional integration (requires `pip install 'provara-protocol[sigstore]'`)

---

## What Is Sigstore?

[Sigstore](https://www.sigstore.dev) is an open-source project that provides free, public, tamper-evident infrastructure for software supply-chain transparency. Its key component for Provara integration is **Rekor** — a transparency log that creates immutable, publicly verifiable records of when specific content was committed.

Unlike X.509 certificate authorities or commercial TSAs, Sigstore requires no registration, no paid subscription, and no key management. Any CI/CD pipeline or developer can anchor content to the Rekor log and anyone can verify it — including third parties with no prior relationship.

---

## Why It Complements RFC 3161

Provara already supports [RFC 3161 timestamps](https://datatracker.ietf.org/doc/html/rfc3161) for cryptographic timestamping. Sigstore adds a complementary layer:

| Property | RFC 3161 (TSA) | Sigstore (Rekor) |
|----------|----------------|------------------|
| **Trust model** | Trust the TSA certificate chain | Trust the append-only transparency log |
| **Verification** | Requires TSA root certificate | Public log — anyone can verify |
| **Registration** | Often requires account or payment | Free, no registration |
| **Proof type** | Private timestamping | Public inclusion proof |
| **CI integration** | Requires TSA URL configuration | Automatic in GitHub Actions (ambient OIDC) |
| **Revocation** | TSA can be compromised/revoked | Log entries are permanent |
| **Auditability** | Depends on TSA's audit policy | All entries are publicly auditable |

**Use RFC 3161 when:** You need a private timestamping proof compliant with specific legal or regulatory standards (eIDAS, etc.).

**Use Sigstore when:** You want a public proof that doesn't require trusting any single entity, or when you want the anchoring to be visible in Sigstore's public transparency log.

**Use both:** Maximum assurance — private TSA proof + public Rekor proof.

---

## Trust Model

The Sigstore transparency model works as follows:

1. **You anchor** a vault Merkle root (SHA-256 hash) to Rekor.
2. **Rekor records** the hash with a server-signed timestamp, creating a log entry with a globally unique `log_index`.
3. **Anyone can verify** by fetching the log entry from `rekor.sigstore.dev` and confirming the inclusion proof.
4. **No single party** can retroactively remove or modify an entry — the Rekor log is append-only and monitored by witnesses.

In GitHub Actions, Sigstore uses **keyless signing with OIDC**:
- GitHub provides a short-lived OIDC token bound to the workflow identity.
- The signed certificate embeds the repository, workflow, and ref in the Subject Alternative Name (SAN).
- No long-lived private keys to manage or rotate.

This means the Rekor entry proves not just *when* the vault state was anchored, but *which GitHub Actions workflow* anchored it — providing identity attribution with no key infrastructure.
---

## Installation

```bash
pip install 'provara-protocol[sigstore]'
```

---

## CLI Usage

### Anchor the current vault state

```bash
# Anchor the current Merkle root to Sigstore
provara anchor ./my-vault

# Anchor a specific event's canonical hash
provara anchor ./my-vault --event evt_abc123...

# Use Sigstore staging (for testing)
provara anchor ./my-vault --staging
```

**Output:**

```
[anchor] Signing vault Merkle root with Sigstore...
[anchor] Log index:    42
[anchor] Log ID:       c0d23d6ad406973f9559f3ba2d1ca01f84147d8ffc5b8445c224f98b9591801d
[anchor] Integrated:   2026-02-18T12:00:00+00:00
[anchor] Verify at:    https://search.sigstore.dev/?logIndex=42
[anchor] Saved to:     my-vault/anchors/20260218T120000Z_42.json
```

### Verify an existing anchor

```bash
provara verify-anchor ./my-vault --anchor ./my-vault/anchors/20260218T120000Z_42.json
```

**Output on success:**

```
[verify-anchor] PASS — Sigstore anchor is valid
  Log index: 42
  Merkle root: abc123...
  Anchored: 2026-02-18T12:00:00+00:00
```

**Output on failure:**

```
[verify-anchor] FAIL — Sigstore bundle verification failed
```
---

## Anchor Storage

Anchor files are stored at:

```
vault_path/
  anchors/
    20260218T120000Z_42.json     ← timestamp_logindex.json
    20260225T094512Z_1337.json
    ...
```

Each anchor file contains:

```json
{
  "format": "provara-sigstore-anchor-v1",
  "event_id": null,
  "merkle_root": "sha256:abc123...",
  "vault_event_count": 42,
  "anchor_timestamp": "2026-02-18T12:00:00+00:00",
  "log_index": 42,
  "log_id": "c0d23d6a...",
  "integrated_time": "2026-02-18T12:00:01+00:00",
  "verification_url": "https://search.sigstore.dev/?logIndex=42",
  "sigstore_bundle": { ... }
}
```

- `event_id` is `null` when anchoring the full Merkle root, or an `evt_...` ID when anchoring a specific event.
- `sigstore_bundle` is the full Sigstore bundle (Rekor log entry + certificate + signature).
- `anchor_timestamp` is when Provara wrote the file; `integrated_time` is when Rekor accepted the entry.

---

## GitHub Actions Integration

The `provara-verify` action automatically integrates Sigstore anchoring with your CI/CD pipeline. See [.github/actions/provara-verify](../.github/actions/provara-verify/README.md).

For custom workflows, you can call the Provara CLI directly:

```yaml
- name: Anchor vault to Sigstore
  run: provara anchor ./my-vault
  env:
    # GitHub provides SIGSTORE_ID_TOKEN automatically in Actions
    SIGSTORE_ID_TOKEN: ${{ secrets.SIGSTORE_ID_TOKEN }}
```
---

## Python API

```python
from pathlib import Path
from provara.sigstore_anchor import anchor_to_sigstore, verify_sigstore_anchor, list_anchors

vault = Path("./my-vault")

# Anchor the current state
result = anchor_to_sigstore(vault)
print(f"Anchored at log index {result.log_index}")
print(f"Verify: {result.verification_url}")

# Anchor a specific event
result = anchor_to_sigstore(vault, event_id="evt_abc123...")

# Verify an anchor
is_valid = verify_sigstore_anchor(vault, result.anchor_path)

# List all anchors
anchors = list_anchors(vault)
for a in anchors:
    print(a["anchor_timestamp"], a["log_index"])
```

---

## Security Considerations

- **Rekor entries are permanent.** Once a Merkle root or event hash is anchored, it is publicly visible forever. Do not anchor vaults containing sensitive metadata in the Merkle root.
- **Sigstore is public.** The log entry and the signing certificate (including the GitHub Actions workflow identity) are visible to anyone with the log index.
- **Anchoring is not signing.** Rekor proves the hash existed at a time; it does not prove ownership or authorize actions on the vault.
- **Offline verification.** The Sigstore bundle in the anchor file contains an inclusion proof — you can verify offline once you have the bundle, without contacting Rekor. The `verify-anchor` CLI command supports this.

---

## See Also

- [Rekor transparency log](https://rekor.sigstore.dev)
- [Sigstore Python library](https://github.com/sigstore/sigstore-python)
- [Sigstore log search](https://search.sigstore.dev)
- [RFC 3161 Timestamping](https://datatracker.ietf.org/doc/html/rfc3161)