"""Provara Python SDK public API.

This module exposes the high-level ``Vault`` facade and stable top-level imports
for signing, replay, sync, checkpointing, and integration helpers.

Example:
    from provara import Vault

    vault = Vault.create("My_Backpack")
    state = vault.replay_state()
    print(state["metadata"]["state_hash"])
"""

from importlib import import_module
from pathlib import Path
from typing import Any, Dict, List, Optional

from .canonical_json import canonical_dumps, canonical_hash, canonical_bytes
from .backpack_signing import (
    BackpackKeypair,
    sign_event,
    verify_event_signature,
    load_private_key_b64,
    load_public_key_b64,
    key_id_from_public_bytes,
)
from .backpack_integrity import merkle_root_hex
from .reducer_v0 import SovereignReducerV0 as SovereignReducer
from .bootstrap_v0 import bootstrap_backpack
from .checkpoint_v0 import create_checkpoint, load_latest_checkpoint
from .perception_v0 import emit_perception_event, PerceptionTier
from .market import record_market_alpha, record_hedge_fund_sim
from .oracle import validate_market_alpha


class Vault:
    """High-level facade for working with a Provara vault path."""

    def __init__(self, path: str | Path):
        self.path = Path(path).resolve()

    @classmethod
    def create(
        cls,
        path: str | Path,
        uid: Optional[str] = None,
        actor: str = "sovereign_genesis",
        include_quorum: bool = False,
        quiet: bool = False,
    ) -> "Vault":
        """Create and bootstrap a new vault, then return a ``Vault`` wrapper.

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
        """
        result = bootstrap_backpack(
            Path(path),
            uid=uid,
            actor=actor,
            include_quorum=include_quorum,
            quiet=quiet,
        )
        if not result.success:
            raise ValueError(
                "ERROR: Vault bootstrap failed. Bootstrap must produce a compliant "
                "genesis state and key registry before use. Fix: create the vault in "
                "an empty directory and review bootstrap errors. "
                "(See: PROTOCOL_PROFILE.txt §13) "
                f"Details: {result.errors}"
            )
        return cls(path)

    def replay_state(self) -> Dict[str, Any]:
        """Replay the vault event log and return the deterministic reducer state.

        Returns:
            Dict[str, Any]: Current derived state with metadata, including
            ``state_hash``.

        Raises:
            FileNotFoundError: If the vault event log does not exist.
        """
        from .sync_v0 import iter_events
        events = iter_events(self.path / "events" / "events.ndjson")
        reducer = SovereignReducer()
        reducer.apply_events(events)
        return reducer.export_state()

    def sync_from(self, remote_path: str | Path) -> Any:
        """Merge events from a remote vault into this vault.

        Args:
            remote_path: Path to the source vault to merge from.

        Returns:
            Any: The sync result object returned by ``sync_backpacks``.
        """
        return sync_backpacks(self.path, Path(remote_path).resolve())

    def append_event(
        self,
        event_type: str,
        payload: Dict[str, Any],
        key_id: str,
        private_key_b64: str,
        actor: str = "provara_sdk",
    ) -> Dict[str, Any]:
        """Append a signed event to ``events.ndjson``.

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
        """
        import json
        from datetime import datetime, timezone
        from .sync_v0 import write_events, iter_events

        # 1. Load keys
        priv = load_private_key_b64(private_key_b64)

        # 2. Find prev_hash (Streaming Search)
        events_file = self.path / "events" / "events.ndjson"
        prev_hash = None
        for e in iter_events(events_file):
            if e.get("actor_key_id") == key_id:
                prev_hash = e.get("event_id")

        # 3. Build event
        event = {
            "type": event_type.upper(),
            "actor": actor,
            "prev_event_hash": prev_hash,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "payload": payload,
        }

        # 4. Content ID
        eid_hash = canonical_hash(event)
        event["event_id"] = f"evt_{eid_hash[:24]}"

        # 5. Sign
        signed = sign_event(event, priv, key_id)

        # 6. Append
        with open(events_file, "a", encoding="utf-8") as f:
            f.write(canonical_dumps(signed) + "\n")

        return signed

    def checkpoint(self, key_id: str, private_key_b64: str) -> Path:
        """Create and save a signed checkpoint for the current state.

        Args:
            key_id: Signing key identifier for checkpoint attestation.
            private_key_b64: Base64 Ed25519 private key.

        Returns:
            Path: Path to the created checkpoint file.
        """
        state = self.replay_state()
        priv = load_private_key_b64(private_key_b64)
        cp = create_checkpoint(self.path, state, priv, key_id)
        from .checkpoint_v0 import save_checkpoint
        return save_checkpoint(self.path, cp)

    def anchor_to_l2(
        self,
        key_id: str,
        private_key_b64: str,
        network: str = "base-mainnet",
    ) -> Dict[str, Any]:
        """Record a simulated L2 anchoring attestation in the vault.

        Args:
            key_id: Signing key identifier used for the attestation event.
            private_key_b64: Base64 Ed25519 private key.
            network: Target network label for anchor metadata.

        Returns:
            Dict[str, Any]: The appended anchor attestation event.

        Raises:
            FileNotFoundError: If ``merkle_root.txt`` is missing.
        """
        # 1. Get current Merkle root
        merkle_root_path = self.path / "merkle_root.txt"
        if not merkle_root_path.exists():
            raise FileNotFoundError(
                "ERROR: merkle_root.txt is missing. Anchoring requires a current "
                "manifest Merkle root to attest state integrity. Fix: run `provara "
                "manifest <vault>` and retry. (See: PROTOCOL_PROFILE.txt §11)"
            )
        merkle_root = merkle_root_path.read_text(encoding="utf-8").strip()

        # 2. MOCK L2 TRANSACTION
        # In production, this would use web3.py to call a contract
        import hashlib
        tx_hash = f"0x{hashlib.sha256(merkle_root.encode()).hexdigest()}"

        payload = {
            "subject": "vault:state_root",
            "predicate": "anchored",
            "value": {
                "merkle_root": merkle_root,
                "network": network,
                "tx_hash": tx_hash,
                "contract_address": "0xProvaraAnchorV1MockAddress",
            },
            "confidence": 1.0,
            "extension": "provara.crypto.l2_anchor_v1"
        }

        # 3. Record as ATTESTATION
        return self.append_event("ATTESTATION", payload, key_id, private_key_b64, actor="anchor_service")

    def create_agent(
        self,
        agent_name: str,
        parent_key_id: str,
        parent_private_key_b64: str,
    ) -> Dict[str, Any]:
        """Create a child agent vault and record its creation in this vault.

        Args:
            agent_name: Directory and logical label for the child agent.
            parent_key_id: Parent vault key used to sign creation evidence.
            parent_private_key_b64: Parent signing key material.

        Returns:
            Dict[str, Any]: Child vault credentials and creation metadata.

        Raises:
            ValueError: If child vault bootstrap fails.
        """
        import uuid
        from datetime import datetime, timezone
        
        # 1. New Identity
        new_kp = BackpackKeypair.generate()
        
        # 1b. Dedicated Encryption Key (X25519)
        from cryptography.hazmat.primitives.asymmetric import x25519
        from cryptography.hazmat.primitives import serialization
        import base64
        
        enc_priv = x25519.X25519PrivateKey.generate()
        enc_pub = enc_priv.public_key()
        
        enc_priv_b64 = base64.b64encode(
            enc_priv.private_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PrivateFormat.Raw,
                encryption_algorithm=serialization.NoEncryption()
            )
        ).decode("utf-8")
        
        enc_pub_b64 = base64.b64encode(
            enc_pub.public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw
            )
        ).decode("utf-8")

        agent_uid = f"agent-{uuid.uuid4()}"
        agent_dir = self.path.parent / agent_name
        
        # 2. Bootstrap Child Vault
        res = bootstrap_backpack(
            agent_dir,
            uid=agent_uid,
            actor=agent_name,
            quiet=True
        )
        if not res.success:
            raise ValueError(
                "ERROR: Agent vault bootstrap failed. Sub-agent creation depends on "
                "a valid child vault genesis and key material. Fix: retry with a "
                "writable target path and inspect bootstrap errors. "
                "(See: PROTOCOL_PROFILE.txt §13) "
                f"Details: {res.errors}"
            )
            
        # 3. Record in Parent Vault
        payload = {
            "subject": f"agent:{agent_name}",
            "predicate": "created",
            "value": {
                "agent_uid": agent_uid,
                "agent_root_key_id": res.root_key_id,
                "agent_encryption_pubkey_b64": enc_pub_b64,
                "vault_path": str(agent_dir),
                "created_at_utc": datetime.now(timezone.utc).isoformat(),
            },
            "extension": "provara.agent.lifecycle_v1"
        }
        
        # Sign with PARENT authority
        event = self.append_event(
            "OBSERVATION", 
            payload, 
            parent_key_id, 
            parent_private_key_b64, 
            actor="agent_factory"
        )
        
        return {
            "agent_name": agent_name,
            "agent_uid": agent_uid,
            "vault_path": str(agent_dir),
            "root_key_id": res.root_key_id,
            "root_private_key": res.root_private_key_b64,
            "encryption_private_key": enc_priv_b64,
            "encryption_public_key": enc_pub_b64,
            "creation_event_id": event["event_id"]
        }

    def log_task(
        self,
        key_id: str,
        private_key_b64: str,
        task_id: str,
        status: str,
        output_hash: str,
        details: Optional[Dict[str, Any]] = None,
        actor: str = "agent_worker",
    ) -> Dict[str, Any]:
        """Record a task completion observation in the vault.

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
        """
        value = {
            "task_id": task_id,
            "status": status.upper(),
            "output_hash": output_hash,
        }
        if details:
            value.update(details)
            
        payload = {
            "subject": f"task:{task_id}",
            "predicate": "completed",
            "value": value,
            "confidence": 1.0,
            "extension": "provara.agent.task_v1"
        }
        
        return self.append_event("OBSERVATION", payload, key_id, private_key_b64, actor=actor)

    def send_message(
        self,
        sender_key_id: str,
        sender_private_key_b64: str,
        sender_encryption_private_key_b64: str,
        recipient_encryption_public_key_b64: str,
        message: Dict[str, Any],
        subject: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Encrypt and append a peer-to-peer message event.

        Args:
            sender_key_id: Sender signing key identifier.
            sender_private_key_b64: Sender Ed25519 private key.
            sender_encryption_private_key_b64: Sender X25519 private key.
            recipient_encryption_public_key_b64: Recipient X25519 public key.
            message: JSON-serializable message body.
            subject: Optional message subject.

        Returns:
            Dict[str, Any]: Signed message wrapper event.
        """
        from .messaging import send_encrypted_message

        wrapper = send_encrypted_message(
            sender_encryption_private_key_b64, 
            recipient_encryption_public_key_b64, 
            message
        )
        
        # Determine recipient key_id (for indexing) 
        # (This remains the Ed25519 key ID for identifying the actor)
        
        payload = {
            "recipient_encryption_pubkey_b64": recipient_encryption_public_key_b64,
            "sender_pubkey_b64": wrapper["sender_pubkey_b64"],
            "nonce": wrapper["nonce"],
            "ciphertext": wrapper["ciphertext"],
            "subject": subject or "P2P Message",
            "extension": "provara.messaging.encrypted_v1"
        }
        
        return self.append_event("OBSERVATION", payload, sender_key_id, sender_private_key_b64, actor="p2p_messenger")

    def get_messages(
        self,
        my_encryption_private_key_b64: str,
    ) -> List[Dict[str, Any]]:
        """Decrypt inbox messages addressed to the supplied encryption key.

        Args:
            my_encryption_private_key_b64: Recipient X25519 private key.

        Returns:
            List[Dict[str, Any]]: Decrypted message objects with sender metadata.
        """
        from .sync_v0 import iter_events
        
        events_file = self.path / "events" / "events.ndjson"
        messages = []
        
        # Derive my public key to filter messages
        from cryptography.hazmat.primitives.asymmetric import x25519
        from cryptography.hazmat.primitives import serialization
        import base64
        priv_bytes = base64.b64decode(my_encryption_private_key_b64)
        my_pub_b64 = base64.b64encode(
            x25519.X25519PrivateKey.from_private_bytes(priv_bytes).public_key().public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw
            )
        ).decode("utf-8")
        
        for e in iter_events(events_file):
            payload = e.get("payload", {})
            if payload.get("extension") == "provara.messaging.encrypted_v1":
                if payload.get("recipient_encryption_pubkey_b64") == my_pub_b64:
                    # Found a message for me!
                    sender_pub_b64 = payload.get("sender_pubkey_b64")
                    
                    try:
                        from .messaging import receive_encrypted_message

                        decrypted = receive_encrypted_message(
                            my_encryption_private_key_b64,
                            sender_pub_b64,
                            payload
                        )
                        messages.append({
                            "from_actor": e.get("actor"),
                            "from_key_id": e.get("actor_key_id"),
                            "subject": payload.get("subject"),
                            "timestamp": e.get("timestamp_utc"),
                            "body": decrypted
                        })
                    except Exception:
                        # Failed to decrypt
                        continue
                        
        return messages

    def check_safety(self, action_type: str) -> Dict[str, Any]:
        """Evaluate an action against the vault safety policy.

        Args:
            action_type: Proposed action name (for example ``REKEY``).

        Returns:
            Dict[str, Any]: Decision payload including status and rationale.
        """
        import json
        policy_path = self.path / "policies" / "safety_policy.json"
        if not policy_path.exists():
            return {"status": "APPROVED", "reason": "No safety policy found (L0 default)"}
            
        policy = json.loads(policy_path.read_text())
        
        # Action to Tier Mapping (Extensible)
        tier_map = {
            "READ": "L0",
            "REPLAY": "L0",
            "APPEND_OBSERVATION": "L1",
            "APPEND_ASSERTION": "L1",
            "CHECKPOINT": "L1",
            "SYNC_OUT": "L1",
            "REKEY": "L2",
            "UPDATE_POLICY": "L2",
            "SYNC_IN": "L2",
            "DELETE_VAULT": "L3",
            "EXPORT_PRIVATE_KEYS": "L3"
        }
        
        target_tier = tier_map.get(action_type.upper(), "L1") # Default to L1 for unknown
        tier_config = policy.get("action_classes", {}).get(target_tier)
        
        if not tier_config:
            return {"status": "BLOCKED", "reason": f"Tier {target_tier} not defined in policy"}
            
        approval = tier_config.get("approval")
        
        if approval == "remote_signature_or_mfa":
            return {"status": "REQUIRES_MFA", "tier": target_tier, "reason": tier_config.get("description")}
        elif target_tier == "L3":
            return {"status": "BLOCKED", "tier": "L3", "reason": "L3 actions are human-only"}
        else:
            return {
                "status": "APPROVED", 
                "tier": target_tier, 
                "approval": approval,
                "description": tier_config.get("description")
            }


# Backward-compatible alias while public API transitions.
SovereignReducerV0 = SovereignReducer

_OPTIONAL_EXPORTS = {
    "generate_resume": (".resume", "generate_resume"),
    "export_to_solana": (".wallet", "export_to_solana"),
    "import_from_solana": (".wallet", "import_from_solana"),
    "PrivacyWrapper": (".privacy", "PrivacyWrapper"),
    "send_encrypted_message": (".messaging", "send_encrypted_message"),
    "receive_encrypted_message": (".messaging", "receive_encrypted_message"),
}


def __getattr__(name: str) -> Any:
    """Lazy-load optional exports on first access.

    Args:
        name: Requested attribute name.

    Returns:
        Any: Loaded module attribute value.

    Raises:
        ImportError: If optional dependency import fails.
        AttributeError: If the attribute is not part of optional exports.
    """
    if name in _OPTIONAL_EXPORTS:
        module_name, attr_name = _OPTIONAL_EXPORTS[name]
        try:
            module = import_module(module_name, __name__)
            value = getattr(module, attr_name)
        except Exception as exc:
            raise ImportError(
                f"Optional Provara export '{name}' is unavailable: {exc}"
            ) from exc
        globals()[name] = value
        return value
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


def check_safety(vault_path: str | Path, action_type: str) -> Dict[str, Any]:
    """Compatibility wrapper around ``Vault.check_safety``.

    Args:
        vault_path: Vault path to evaluate.
        action_type: Action name to classify.

    Returns:
        Dict[str, Any]: Safety policy decision payload.

    Example:
        result = check_safety("My_Backpack", "SYNC_IN")
    """
    return Vault(vault_path).check_safety(action_type)


def sync_backpacks(*args: Any, **kwargs: Any) -> Any:
    """Lazy wrapper around ``provara.sync_v0.sync_backpacks``."""
    from .sync_v0 import sync_backpacks as _sync_backpacks
    return _sync_backpacks(*args, **kwargs)


def load_events(*args: Any, **kwargs: Any) -> Any:
    """Lazy wrapper around ``provara.sync_v0.load_events``."""
    from .sync_v0 import load_events as _load_events
    return _load_events(*args, **kwargs)


__version__ = "1.0.1"
__all__ = [
    "Vault",
    "SovereignReducer",
    "SovereignReducerV0",
    "bootstrap_backpack",
    "sync_backpacks",
    "canonical_dumps",
    "canonical_hash",
    "canonical_bytes",
    "BackpackKeypair",
    "sign_event",
    "verify_event_signature",
    "load_private_key_b64",
    "load_public_key_b64",
    "key_id_from_public_bytes",
    "merkle_root_hex",
    "load_events",
    "create_checkpoint",
    "load_latest_checkpoint",
    "emit_perception_event",
    "PerceptionTier",
    "record_market_alpha",
    "record_hedge_fund_sim",
    "validate_market_alpha",
    "generate_resume",
    "check_safety",
    "export_to_solana",
    "import_from_solana",
    "PrivacyWrapper",
    "send_encrypted_message",
    "receive_encrypted_message",
]
