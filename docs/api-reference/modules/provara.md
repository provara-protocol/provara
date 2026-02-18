# `provara`

Provara Python SDK public API.

This module exposes the high-level ``Vault`` facade and stable top-level imports
for signing, replay, sync, checkpointing, and integration helpers.

Example:
    from provara import Vault

    vault = Vault.create("My_Backpack")
    state = vault.replay_state()
    print(state["metadata"]["state_hash"])

## Functions

### `check_safety(vault_path: str | Path, action_type: str) -> Dict[str, Any]`

Compatibility wrapper around ``Vault.check_safety``.

Args:
    vault_path: Vault path to evaluate.
    action_type: Action name to classify.

Returns:
    Dict[str, Any]: Safety policy decision payload.

Example:
    result = check_safety("My_Backpack", "SYNC_IN")

## Classes

### `Vault`

High-level facade for working with a Provara vault path.

#### `Vault.create(cls, path: str | Path, uid: Optional[str] = None, actor: str = 'sovereign_genesis', include_quorum: bool = False, quiet: bool = False) -> 'Vault'`

Create and bootstrap a new vault, then return a ``Vault`` wrapper.

Args:
    path: Filesystem path for the new vault directory.
    uid: Optional stable vault identifier.
    actor: Actor label used for the genesis event.
    include_quorum: Whether to create a quorum recovery key.
    quiet: Suppress bootstrap console output when True.

Returns:
    Vault: Wrapper bound to the initialized vault path.

Raises:
    ValueError: If bootstrap cannot produce a compliant vault.

Example:
    vault = Vault.create("My_Backpack", actor="operator")

#### `Vault.replay_state(self) -> Dict[str, Any]`

Replay the vault event log and return the deterministic reducer state.

Returns:
    Dict[str, Any]: Current derived state with metadata, including
    ``state_hash``.

Raises:
    FileNotFoundError: If the vault event log does not exist.

#### `Vault.sync_from(self, remote_path: str | Path) -> Any`

Merge events from a remote vault into this vault.

Args:
    remote_path: Path to the source vault to merge from.

Returns:
    Any: The sync result object returned by ``sync_backpacks``.

#### `Vault.append_event(self, event_type: str, payload: Dict[str, Any], key_id: str, private_key_b64: str, actor: str = 'provara_sdk') -> Dict[str, Any]`

Append a signed event to ``events.ndjson``.

Args:
    event_type: Provara event type such as ``OBSERVATION``.
    payload: Event payload object.
    key_id: Actor signing key identifier.
    private_key_b64: Base64 Ed25519 private key.
    actor: Human-readable actor label.

Returns:
    Dict[str, Any]: Signed event object as persisted.

Raises:
    ValueError: If key material is invalid.
    OSError: If event file write fails.

#### `Vault.checkpoint(self, key_id: str, private_key_b64: str) -> Path`

Create and save a signed checkpoint for the current state.

Args:
    key_id: Signing key identifier for checkpoint attestation.
    private_key_b64: Base64 Ed25519 private key.

Returns:
    Path: Path to the created checkpoint file.

#### `Vault.anchor_to_l2(self, key_id: str, private_key_b64: str, network: str = 'base-mainnet') -> Dict[str, Any]`

Record a simulated L2 anchoring attestation in the vault.

Args:
    key_id: Signing key identifier used for the attestation event.
    private_key_b64: Base64 Ed25519 private key.
    network: Target network label for anchor metadata.

Returns:
    Dict[str, Any]: The appended anchor attestation event.

Raises:
    FileNotFoundError: If ``merkle_root.txt`` is missing.

#### `Vault.create_agent(self, agent_name: str, parent_key_id: str, parent_private_key_b64: str) -> Dict[str, Any]`

Create a child agent vault and record its creation in this vault.

Args:
    agent_name: Directory and logical label for the child agent.
    parent_key_id: Parent vault key used to sign creation evidence.
    parent_private_key_b64: Parent signing key material.

Returns:
    Dict[str, Any]: Child vault credentials and creation metadata.

Raises:
    ValueError: If child vault bootstrap fails.

#### `Vault.log_task(self, key_id: str, private_key_b64: str, task_id: str, status: str, output_hash: str, details: Optional[Dict[str, Any]] = None, actor: str = 'agent_worker') -> Dict[str, Any]`

Record a task completion observation in the vault.

Args:
    key_id: Signing key identifier.
    private_key_b64: Base64 Ed25519 private key.
    task_id: Task identifier.
    status: Completion status label.
    output_hash: Hash of produced artifact or output.
    details: Optional extra task metadata.
    actor: Actor name for event attribution.

Returns:
    Dict[str, Any]: Signed event that was appended.

#### `Vault.send_message(self, sender_key_id: str, sender_private_key_b64: str, sender_encryption_private_key_b64: str, recipient_encryption_public_key_b64: str, message: Dict[str, Any], subject: Optional[str] = None) -> Dict[str, Any]`

Encrypt and append a peer-to-peer message event.

Args:
    sender_key_id: Sender signing key identifier.
    sender_private_key_b64: Sender Ed25519 private key.
    sender_encryption_private_key_b64: Sender X25519 private key.
    recipient_encryption_public_key_b64: Recipient X25519 public key.
    message: JSON-serializable message body.
    subject: Optional message subject.

Returns:
    Dict[str, Any]: Signed message wrapper event.

#### `Vault.get_messages(self, my_encryption_private_key_b64: str) -> List[Dict[str, Any]]`

Decrypt inbox messages addressed to the supplied encryption key.

Args:
    my_encryption_private_key_b64: Recipient X25519 private key.

Returns:
    List[Dict[str, Any]]: Decrypted message objects with sender metadata.

#### `Vault.check_safety(self, action_type: str) -> Dict[str, Any]`

Evaluate an action against the vault safety policy.

Args:
    action_type: Proposed action name (for example ``REKEY``).

Returns:
    Dict[str, Any]: Decision payload including status and rationale.
