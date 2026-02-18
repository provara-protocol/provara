# `privacy`

privacy.py — Cryptographic Erasure for Provara Vaults

Implements "Crypto-Shredding" to reconcile immutability with GDPR.
- Encrypts sensitive data with ephemeral keys.
- Stores keys in a mutable sidecar (sqlite/json).
- Deletes keys to "erase" data while preserving the chain.

## Classes

### `PrivacyKeyStore`

Mutable sidecar for ephemeral data keys.

#### `PrivacyKeyStore.store_key(self, key_id: str, key_bytes: bytes) -> None`

Persist a generated data-encryption key.

Args:
    key_id: Stable key identifier used in encrypted wrappers.
    key_bytes: Raw AES key bytes.

#### `PrivacyKeyStore.get_key(self, key_id: str) -> Optional[bytes]`

Load key bytes for a wrapper key ID.

Args:
    key_id: Wrapper key identifier.

Returns:
    Optional[bytes]: Key bytes or ``None`` if key was shredded/missing.

#### `PrivacyKeyStore.shred_key(self, key_id: str) -> bool`

The 'Erasure' operation.

### `PrivacyWrapper`

Encrypts/Decrypts payloads using AES-GCM.

#### `PrivacyWrapper.encrypt(self, data: Dict[str, Any]) -> Dict[str, Any]`

Encrypt a payload and persist a one-time key in the sidecar store.

Args:
    data: JSON-serializable dictionary payload.

Returns:
    Dict[str, Any]: Encrypted wrapper containing scheme, key ID, nonce,
    and ciphertext.

Raises:
    TypeError: If payload cannot be serialized.

Example:
    wrapper = PrivacyWrapper(vault).encrypt({"ssn": "redacted"})

#### `PrivacyWrapper.decrypt(self, wrapper: Dict[str, Any]) -> Optional[Dict[str, Any]]`

Decrypt a privacy wrapper payload when key material is still present.

Args:
    wrapper: Encrypted wrapper produced by ``encrypt``.

Returns:
    Optional[Dict[str, Any]]: Decrypted payload, or ``None`` if key was
    shredded or ciphertext is invalid.

Raises:
    ValueError: If wrapper uses an unsupported privacy scheme.

#### `PrivacyWrapper.shred(self, kid: str) -> bool`

Delete a key so wrapped data becomes cryptographically unreadable.

Args:
    kid: Wrapper key ID to shred.

Returns:
    bool: True when a key was deleted, else False.
