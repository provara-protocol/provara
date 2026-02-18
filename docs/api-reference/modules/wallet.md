# `wallet`

wallet.py — Provara Economic Bridge

Enables interoperability between Provara Identity Keys and Crypto Wallets.
Currently supports:
- Solana (Ed25519): Native compatibility.
  Provara Key <-> Solana CLI Keypair (id.json)

Dependencies: None (uses stdlib + cryptography)

## Functions

### `export_to_solana(private_key_b64: str) -> List[int]`

Convert a Provara private key to Solana CLI ``id.json`` byte-array format.

Args:
    private_key_b64: Base64 Ed25519 private key bytes (32-byte seed).

Returns:
    List[int]: 64-byte Solana keypair array ``[priv32 + pub32]``.

Raises:
    ValueError: If the private key cannot be decoded.

Example:
    arr = export_to_solana(private_key_b64)

### `import_from_solana(solana_keypair: List[int]) -> Dict[str, str]`

Convert Solana CLI ``id.json`` bytes into Provara key format.

Args:
    solana_keypair: Solana keypair list of 64 integer bytes.

Returns:
    Dict[str, str]: ``{"key_id": ..., "private_key_b64": ...}``.

Raises:
    ValueError: If keypair length is not exactly 64 bytes.

Example:
    key = import_from_solana(json.loads(Path("id.json").read_text()))
