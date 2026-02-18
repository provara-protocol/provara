# Provara Data Residency and Jurisdictional Guidance

## 1. Introduction
Provara is a decentralized, self-sovereign protocol. Unlike traditional cloud services where data residency is managed by a central provider, Provara users are responsible for determining where their vaults reside and ensuring compliance with local data protection laws (e.g., GDPR, CCPA).

## 2. Where Does a Vault Live?
A Provara vault is a directory on a filesystem. Common residency patterns include:

- **Local Filesystem**: Highest sovereignty. Data remains on the user's device.
- **Cloud Storage (Sync)**: Vaults synced via Dropbox, iCloud, or S3 reside in the jurisdictions governed by those providers.
- **Removable Media**: USB drives or encrypted external disks allow for physical data residency control.

## 3. Jurisdictional Questions
Provara vaults often contain events from multiple actors. This creates complex jurisdictional scenarios:

- **Multi-Actor Vaults**: If a vault contains observations from an actor in the EU (GDPR) and an actor in the US, the vault may be subject to multiple overlapping legal frameworks.
- **Vault as a Data Export**: Under GDPR, sharing a Provara vault with a peer in another country may constitute a cross-border data transfer.

## 4. GDPR and the Right to Erasure
Provara's append-only nature is in natural tension with GDPR Article 17.

### 4.1 Deletion vs. Erasure
In Provara, "Deletion is an event, not an erasure." When a user requests erasure:
1.  **Redaction**: Use `provara redact` to replace sensitive content with a cryptographic tombstone.
2.  **Crypto-Shredding**: For highly sensitive data, use the `privacy.py` module to encrypt payloads with ephemeral keys. Deleting the key effectively erases the data while preserving the chain.

### 4.2 Multi-Jurisdiction Compliance
If a vault contains data subject to GDPR, the **entire vault** should be managed according to the most restrictive requirements (the "Merge Ratchet" philosophy applied to policy).

## 5. Encryption at Rest
Provara **does not encrypt data by default** to ensure 50-year readability and third-party verifiability. 

**Recommendations:**
- Use OS-level encryption (FileVault, BitLocker, LUKS).
- Use encrypted containers (VeraCrypt) for portable vaults.
- For sensitive beliefs, use the `PrivacyWrapper` in `src/provara/privacy.py`.

## 6. Practical Guidance for EU Users
1.  **Actor Sovereignty**: Ensure each actor manages their own private keys.
2.  **Redaction Policy**: Establish a clear `com.provara.redaction` workflow for processing erasure requests.
3.  **Transparency**: Document the use of Provara in your Privacy Policy, specifically noting the append-only cryptographic nature of the event log.
4.  **Local First**: Prefer local residency with encrypted sync over direct cloud residency.
