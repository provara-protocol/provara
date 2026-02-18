# `timestamp`

timestamp.py — RFC 3161 Trusted Timestamping for Provara

Allows anchoring vault state hashes to an external Trust Anchor (TSA)
for legal admissibility and independent temporal proof.

## Functions

### `get_rfc3161_timestamp(data_hash_hex: str, tsa_url: str = DEFAULT_TSA_URL) -> bytes`

Request an RFC 3161 timestamp response (TSR) for a SHA-256 digest.

Args:
    data_hash_hex: SHA-256 digest in lowercase or uppercase hex.
    tsa_url: RFC 3161 timestamp authority endpoint URL.

Returns:
    bytes: Raw TSR bytes returned by the timestamp authority.

Raises:
    RuntimeError: If TSA responds with a non-200 HTTP status.
    ValueError: If ``data_hash_hex`` is invalid hex.
    urllib.error.URLError: If request/connection fails.

Example:
    tsr = get_rfc3161_timestamp("ab" * 32)

### `record_timestamp_anchor(vault_path: Path, keyfile_path: Path, tsa_url: str = DEFAULT_TSA_URL, actor: str = 'timestamp_authority') -> Dict[str, Any]`

Anchor current reducer state hash to an external timestamp authority.

Args:
    vault_path: Target vault directory.
    keyfile_path: Path to private key file used for event signing.
    tsa_url: RFC 3161 authority endpoint URL.
    actor: Actor label for the timestamp event.

Returns:
    Dict[str, Any]: Signed timestamp anchor event appended to the vault.

Raises:
    FileNotFoundError: If required vault files are missing.
    KeyError: If reducer metadata does not include ``state_hash``.
    OSError: If vault files cannot be read or written.

Example:
    event = record_timestamp_anchor(Path("My_Backpack"), Path("keys.json"))
