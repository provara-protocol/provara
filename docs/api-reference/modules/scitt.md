# `scitt`

scitt.py — SCITT Phase 1 compatibility for Provara

Adds two event types that bridge Provara vaults to the IETF SCITT architecture:

  com.ietf.scitt.signed_statement — wraps a SCITT Signed Statement as a
      Provara event, storing the statement hash, content type, subject, issuer,
      and (optionally) a Base64-encoded COSE Sign1 envelope.

  com.ietf.scitt.receipt — wraps a SCITT Receipt as a Provara event,
      referencing the originating signed_statement event and embedding the
      transparency service's inclusion proof.

Both types are OPTIONAL — core vault operations are not affected.
No new dependencies are introduced; all serialization uses stdlib.

Reference: https://datatracker.ietf.org/wg/scitt/about/
Mapping:   docs/SCITT_MAPPING.md

## Functions

### `record_scitt_statement(vault_path: Path, keyfile_path: Path, statement_hash: str, content_type: str, subject: str, issuer: str, cose_envelope_b64: Optional[str] = None, actor: str = 'scitt_agent') -> Dict[str, Any]`

Append a SCITT signed statement event to a vault.

Args:
    vault_path: Path to the Provara vault directory.
    keyfile_path: Path to the private keys JSON file.
    statement_hash: SHA-256 digest hex of the signed statement.
    content_type: Statement MIME type (for example ``application/json``).
    subject: Subject identifier of the statement.
    issuer: Issuer identifier (DID, key ID, or label).
    cose_envelope_b64: Optional Base64 COSE Sign1 payload.
    actor: Actor label recorded in the event envelope.

Returns:
    Dict[str, Any]: Signed event object written to ``events.ndjson``.

Raises:
    ValueError: If required payload fields are missing or malformed.
    OSError: If vault files cannot be read or written.

Example:
    record_scitt_statement(vault, keys, stmt_hash, "application/json", "pkg:a", "issuer:1")

### `record_scitt_receipt(vault_path: Path, keyfile_path: Path, statement_event_id: str, transparency_service: str, inclusion_proof: Any, receipt_b64: Optional[str] = None, actor: str = 'scitt_agent') -> Dict[str, Any]`

Append a SCITT receipt event to a vault.

Args:
    vault_path: Path to the Provara vault directory.
    keyfile_path: Path to the private keys JSON file.
    statement_event_id: Provara event ID of the source statement.
    transparency_service: Transparency service URL or identifier.
    inclusion_proof: Inclusion proof payload from the transparency service.
    receipt_b64: Optional Base64-encoded receipt bytes.
    actor: Actor label recorded in the event envelope.

Returns:
    Dict[str, Any]: Signed event object written to ``events.ndjson``.

Raises:
    ValueError: If required payload fields are missing or malformed.
    OSError: If vault files cannot be read or written.

Example:
    record_scitt_receipt(vault, keys, "evt_abcd", "ts.example", {"root": "..."})
