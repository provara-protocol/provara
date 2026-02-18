# RFC 3161 Trusted Timestamping in Provara

## Overview
Trusted timestamping (RFC 3161) provides independent, third-party proof that a specific piece of data existed at a certain point in time. While Provara vaults provide an internal causal ordering of events, an external Time Stamping Authority (TSA) provides a "temporal anchor" that is indispensable for legal admissibility and long-term non-repudiation.

## How it works
1.  **Event Generation:** A Provara event is created, signed, and appended to the vault.
2.  **Hashing:** The SHA-256 hash of the full signed event is computed.
3.  **Request:** The hash is sent to an RFC 3161 compliant TSA. **The TSA never sees the event content, only its hash.**
4.  **Token Issuance:** The TSA signs the hash alongside its own high-precision clock time and returns a DER-encoded TimeStampToken.
5.  **Storage:** The token is stored in the vault's auxiliary evidence directory: `timestamps/{event_id}.tst`.

## Trust Model
-   **Privacy-Preserving:** Only the event hash is shared with the TSA.
-   **Independent Proof:** Even if the vault's keys are compromised later, the TSA's signature proves the state of the event at the time of timestamping.
-   **Chain Integrity:** Timestamps are auxiliary evidence. They do not modify the normative hash chain of the vault.

## Legal Standing
RFC 3161 timestamps are recognized under various international standards and regulations, including:
-   **eIDAS (EU):** Qualified electronic time stamps.
-   **ESIGN / UETA (USA):** Legal recognition of electronic records.
-   **ANSI X9.95:** Trusted Time Stamp Management.

## Usage

### CLI Integration
Append an event and request a timestamp:
```bash
provara append my-vault --type OBSERVATION --data '{"status": "ok"}' --keyfile keys.json --timestamp
```

Verify all timestamps in a vault:
```bash
provara verify-timestamps my-vault
```

Timestamp an existing event:
```bash
provara timestamp my-vault evt_12345...
```

### Supported TSAs
You can specify a custom TSA via the `--tsa-url` flag. Default options include:
-   **DigiCert:** http://timestamp.digicert.com (Free, high reliability)
-   **FreeTSA:** https://freetsa.org/tsr (Privacy-focused)
-   **Sectigo:** http://timestamp.sectigo.com

## Limitations
-   **Connectivity:** Requesting a timestamp requires an active internet connection to reach the TSA.
-   **TSA Availability:** If the TSA is offline, the timestamp operation will fail gracefully with a warning.
-   **TSA Trust:** The value of the timestamp is tied to the reliability and certificate authority of the TSA.
