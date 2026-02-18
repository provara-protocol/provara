"""
crypto_shred.py — Crypto-Shredding for Provara Protocol

Implements GDPR Article 17 (Right to Erasure) via cryptographic erasure:
- Encrypt event payloads with AES-256-GCM
- Store DEKs in mutable sidecar database
- Destroy DEKs to "erase" content while preserving hash chain

Usage:
    from provara.crypto_shred import encrypt_event_data, decrypt_event_data, shred_event
    
    # Encrypt before appending
    ciphertext, nonce, key_id = encrypt_event_data({"ssn": "123-45-6789"})
    
    # Decrypt for reading
    data = decrypt_event_data(ciphertext, nonce, key_id, vault_path)
    
    # Shred for GDPR erasure
    shred_event(vault_path, event_id, keyfile_path, reason="GDPR_ERASURE")
"""

from __future__ import annotations
import os
import json
import base64
import datetime
import sqlite3
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, cast

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .canonical_json import canonical_hash, canonical_dumps
from .backpack_signing import load_private_key_b64, sign_event
from .sync_v0 import load_events, write_events
from .manifest_generator import build_manifest, manifest_leaves
from .backpack_integrity import merkle_root_hex, MANIFEST_EXCLUDE, canonical_json_bytes


# ---------------------------------------------------------------------------
# Privacy Key Store (SQLite sidecar)
# ---------------------------------------------------------------------------

class PrivacyKeyStore:
    """Mutable sidecar for Data Encryption Keys (DEKs).
    
    Stored separately from append-only event log to enable key destruction.
    """
    
    def __init__(self, vault_path: Path) -> None:
        self.db_path = vault_path / "identity" / "privacy_keys.db"
        self._init_db()
    
    def _init_db(self) -> None:
        """Initialize database schema."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS keys (
                    key_id TEXT PRIMARY KEY,
                    key_bytes BLOB NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    actor_id TEXT,
                    event_id TEXT
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_actor ON keys(actor_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_event ON keys(event_id)
            """)
    
    def store_key(
        self,
        key_id: str,
        key_bytes: bytes,
        actor_id: Optional[str] = None,
        event_id: Optional[str] = None,
    ) -> None:
        """Store a Data Encryption Key.
        
        Args:
            key_id: Unique key identifier.
            key_bytes: Raw AES-256 key bytes (32 bytes).
            actor_id: Actor ID (for per-actor mode).
            event_id: Event ID (for per-event mode).
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO keys (key_id, key_bytes, actor_id, event_id) VALUES (?, ?, ?, ?)",
                (key_id, key_bytes, actor_id, event_id),
            )
    
    def get_key(self, key_id: str) -> Optional[bytes]:
        """Retrieve a DEK by ID.
        
        Args:
            key_id: Key identifier.
            
        Returns:
            Key bytes or None if shredded/missing.
        """
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute("SELECT key_bytes FROM keys WHERE key_id = ?", (key_id,))
            row = cur.fetchone()
            return bytes(row[0]) if row else None
    
    def shred_key(self, key_id: str) -> bool:
        """Destroy a DEK (cryptographic erasure).
        
        Args:
            key_id: Key identifier to shred.
            
        Returns:
            True if key was deleted, False if not found.
        """
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute("DELETE FROM keys WHERE key_id = ?", (key_id,))
            return cur.rowcount > 0
    
    def shred_actor_keys(self, actor_id: str) -> int:
        """Destroy all DEKs for an actor.
        
        Args:
            actor_id: Actor identifier.
            
        Returns:
            Number of keys shredded.
        """
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute("DELETE FROM keys WHERE actor_id = ?", (actor_id,))
            return cur.rowcount
    
    def get_actor_keys(self, actor_id: str) -> List[str]:
        """List all key IDs for an actor.
        
        Args:
            actor_id: Actor identifier.
            
        Returns:
            List of key IDs.
        """
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute("SELECT key_id FROM keys WHERE actor_id = ?", (actor_id,))
            return [row[0] for row in cur.fetchall()]
    
    def key_exists(self, key_id: str) -> bool:
        """Check if a key exists.
        
        Args:
            key_id: Key identifier.
            
        Returns:
            True if key exists, False otherwise.
        """
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute("SELECT 1 FROM keys WHERE key_id = ?", (key_id,))
            return cur.fetchone() is not None


# ---------------------------------------------------------------------------
# Encryption/Decryption
# ---------------------------------------------------------------------------

def encrypt_event_data(
    data: Dict[str, Any],
    key_id: Optional[str] = None,
    actor_id: Optional[str] = None,
    event_id: Optional[str] = None,
) -> Tuple[bytes, bytes, str]:
    """Encrypt event data with AES-256-GCM.
    
    Args:
        data: Payload dictionary to encrypt.
        key_id: Optional key ID (generated if not provided).
        actor_id: Actor ID for key storage.
        event_id: Event ID for key storage.
        
    Returns:
        Tuple of (ciphertext, nonce, key_id).
        
    Raises:
        TypeError: If data cannot be serialized to JSON.
    """
    # Generate key
    key = AESGCM.generate_key(bit_length=256)
    kid = key_id or f"dek_{uuid.uuid4()}"
    
    # Generate nonce
    nonce = os.urandom(12)  # 96-bit nonce for GCM
    
    # Canonicalize before encryption
    plaintext = canonical_dumps(data).encode("utf-8")
    
    # Encrypt
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    
    # Store key (caller must pass vault_path separately)
    # This is done by the caller in create_encrypted_event
    
    return ciphertext, nonce, kid


def decrypt_event_data(
    ciphertext: bytes,
    nonce: bytes,
    key_id: str,
    key_store: PrivacyKeyStore,
) -> Optional[Dict[str, Any]]:
    """Decrypt event data using stored DEK.
    
    Args:
        ciphertext: Encrypted data.
        nonce: AES-GCM nonce.
        key_id: Key identifier.
        key_store: PrivacyKeyStore instance.
        
    Returns:
        Decrypted payload dict, or None if key shredded/missing.
        
    Raises:
        ValueError: If decryption fails (wrong key, corrupted data).
    """
    # Retrieve key
    key = key_store.get_key(key_id)
    if key is None:
        return None  # Key shredded - data unrecoverable
    
    # Decrypt
    aesgcm = AESGCM(key)
    try:
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        data = json.loads(plaintext.decode("utf-8"))
        if isinstance(data, dict):
            return cast(Dict[str, Any], data)
        return None
    except Exception as e:
        raise ValueError(f"Decryption failed: {e}")


def create_encrypted_payload(
    data: Dict[str, Any],
    key_store: PrivacyKeyStore,
    actor_id: Optional[str] = None,
    event_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Create encrypted payload wrapper.
    
    Args:
        data: Payload to encrypt.
        key_store: PrivacyKeyStore instance.
        actor_id: Actor ID for key storage.
        event_id: Event ID for key storage.
        
    Returns:
        Encrypted payload wrapper with _privacy, kid, nonce, ciphertext.
    """
    # Generate key and encrypt
    key = AESGCM.generate_key(bit_length=256)
    kid = f"dek_{uuid.uuid4()}"
    nonce = os.urandom(12)
    
    plaintext = canonical_dumps(data).encode("utf-8")
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    
    # Store key
    key_store.store_key(kid, key, actor_id, event_id)
    
    # Create wrapper
    return {
        "_privacy": "aes-gcm-v1",
        "kid": kid,
        "nonce": base64.b64encode(nonce).decode("utf-8"),
        "ciphertext": base64.b64encode(ciphertext).decode("utf-8"),
    }


def decrypt_payload(
    payload: Dict[str, Any],
    key_store: PrivacyKeyStore,
) -> Optional[Dict[str, Any]]:
    """Decrypt payload wrapper.
    
    Args:
        payload: Encrypted payload wrapper.
        key_store: PrivacyKeyStore instance.
        
    Returns:
        Decrypted payload, or None if key shredded.
        
    Raises:
        ValueError: If payload format invalid or decryption fails.
    """
    if payload.get("_privacy") != "aes-gcm-v1":
        raise ValueError("Unsupported privacy scheme")
    
    kid = payload["kid"]
    nonce = base64.b64decode(payload["nonce"])
    ciphertext = base64.b64decode(payload["ciphertext"])
    
    return decrypt_event_data(ciphertext, nonce, kid, key_store)


# ---------------------------------------------------------------------------
# Shredding Operations
# ---------------------------------------------------------------------------

def _load_keys_internal(keys_path: Path) -> Dict[str, str]:
    """Load private keys from file.
    
    Args:
        keys_path: Path to private keys JSON.
        
    Returns:
        Dict mapping key_id to private_key_b64.
    """
    if not keys_path.exists():
        raise FileNotFoundError(f"Private keys file not found at {keys_path}")
    data = json.loads(keys_path.read_text())
    
    if "keys" in data and isinstance(data["keys"], list):
        return {str(k["key_id"]): str(k["private_key_b64"]) for k in data["keys"]}
    else:
        return {str(k): str(v) for k, v in data.items() if k != "WARNING"}


def shred_event(
    vault_path: Path,
    event_id: str,
    keyfile_path: Path,
    reason: str = "GDPR_ERASURE",
    reason_detail: Optional[str] = None,
    authority: Optional[str] = None,
    actor: Optional[str] = None,
) -> Dict[str, Any]:
    """Crypto-shred a single event by destroying its DEK.
    
    Args:
        vault_path: Path to vault directory.
        event_id: Event ID to shred.
        keyfile_path: Path to private keys JSON.
        reason: Erasure reason (GDPR_ERASURE, LEGAL_ORDER, etc.).
        reason_detail: Optional free-text explanation.
        authority: Authority authorizing erasure.
        actor: Actor name for shred event (default: provara_redactor).
        
    Returns:
        Shred event dict.
        
    Raises:
        ValueError: If event not found or already shredded.
        FileNotFoundError: If vault or keys not found.
    """
    events_path = vault_path / "events" / "events.ndjson"
    if not events_path.exists():
        raise FileNotFoundError(f"Events log not found at {events_path}")
    
    key_store = PrivacyKeyStore(vault_path)
    
    # Load events
    all_events = load_events(events_path)
    
    # Find target event
    target_event = None
    target_index = -1
    for i, e in enumerate(all_events):
        if e.get("event_id") == event_id:
            target_event = e
            target_index = i
            break
    
    if target_event is None:
        raise ValueError(f"Event {event_id} not found")
    
    # Check if already shredded
    payload = target_event.get("payload", {})
    if isinstance(payload, dict) and payload.get("_privacy") == "aes-gcm-v1":
        kid = payload.get("kid")
        if not key_store.key_exists(kid):
            raise ValueError(f"Event {event_id} already shredded")
    
    # Get key ID for shredding
    kid = payload.get("kid") if isinstance(payload, dict) else None
    if not kid:
        raise ValueError(f"Event {event_id} is not encrypted")
    
    # Create shred event
    actor_name = actor or "provara_redactor"
    actor_events = [e for e in all_events if e.get("actor") == actor_name]
    prev_hash = actor_events[-1].get("event_id") if actor_events else None
    
    shred_payload = {
        "target_event_id": event_id,
        "reason": reason,
        "reason_detail": reason_detail,
        "authority": authority or "System",
        "shred_scope": "single_event",
    }
    
    shred_event_dict = {
        "type": "com.provara.crypto_shred",
        "actor": actor_name,
        "prev_event_hash": prev_hash,
        "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "payload": shred_payload,
    }
    
    # Add ts_logical if used
    if actor_events:
        shred_event_dict["ts_logical"] = actor_events[-1].get("ts_logical", 0) + 1
    elif any("ts_logical" in e for e in all_events):
        shred_event_dict["ts_logical"] = 1
    
    # Sign shred event
    keys_data = _load_keys_internal(keyfile_path)
    kid_sign = list(keys_data.keys())[0]
    priv = load_private_key_b64(keys_data[kid_sign])
    
    eid_hash = canonical_hash(shred_event_dict)
    shred_event_dict["event_id"] = f"evt_{eid_hash[:24]}"
    signed_shred = sign_event(shred_event_dict, priv, kid_sign)
    
    # Destroy DEK
    key_store.shred_key(kid)
    
    # Append shred event
    all_events.append(signed_shred)
    write_events(events_path, all_events)
    
    # Regenerate manifest
    exclude = set(MANIFEST_EXCLUDE)
    manifest = build_manifest(vault_path, exclude)
    leaves = manifest_leaves(manifest)
    root_hex = merkle_root_hex(leaves)
    
    (vault_path / "manifest.json").write_bytes(canonical_json_bytes(manifest))
    (vault_path / "merkle_root.txt").write_text(root_hex + "\n", encoding="utf-8")
    
    return signed_shred


def shred_actor(
    vault_path: Path,
    actor_id: str,
    keyfile_path: Path,
    reason: str = "GDPR_ERASURE",
    reason_detail: Optional[str] = None,
    authority: Optional[str] = None,
    actor: Optional[str] = None,
) -> Dict[str, Any]:
    """Crypto-shred all events by an actor.
    
    Args:
        vault_path: Path to vault directory.
        actor_id: Actor ID whose events to shred.
        keyfile_path: Path to private keys JSON.
        reason: Erasure reason.
        reason_detail: Optional free-text explanation.
        authority: Authority authorizing erasure.
        actor: Actor name for shred event.
        
    Returns:
        Shred event dict.
        
    Raises:
        ValueError: If no events found for actor.
    """
    events_path = vault_path / "events" / "events.ndjson"
    if not events_path.exists():
        raise FileNotFoundError(f"Events log not found at {events_path}")
    
    key_store = PrivacyKeyStore(vault_path)
    
    # Load events
    all_events = load_events(events_path)
    
    # Count actor events
    actor_events = [e for e in all_events if e.get("actor") == actor_id]
    if not actor_events:
        raise ValueError(f"No events found for actor {actor_id}")
    
    # Get all key IDs for actor
    key_ids = key_store.get_actor_keys(actor_id)
    
    # Create shred event
    actor_name = actor or "provara_redactor"
    admin_events = [e for e in all_events if e.get("actor") == actor_name]
    prev_hash = admin_events[-1].get("event_id") if admin_events else None
    
    shred_payload = {
        "target_actor_id": actor_id,
        "reason": reason,
        "reason_detail": reason_detail,
        "authority": authority or "System",
        "shred_scope": "actor_wide",
        "events_affected": len(actor_events),
        "keys_destroyed": len(key_ids),
    }
    
    shred_event_dict = {
        "type": "com.provara.crypto_shred",
        "actor": actor_name,
        "prev_event_hash": prev_hash,
        "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "payload": shred_payload,
    }
    
    # Add ts_logical if used
    if admin_events:
        shred_event_dict["ts_logical"] = admin_events[-1].get("ts_logical", 0) + 1
    elif any("ts_logical" in e for e in all_events):
        shred_event_dict["ts_logical"] = 1
    
    # Sign shred event
    keys_data = _load_keys_internal(keyfile_path)
    kid_sign = list(keys_data.keys())[0]
    priv = load_private_key_b64(keys_data[kid_sign])
    
    eid_hash = canonical_hash(shred_event_dict)
    shred_event_dict["event_id"] = f"evt_{eid_hash[:24]}"
    signed_shred = sign_event(shred_event_dict, priv, kid_sign)
    
    # Destroy all actor keys
    for kid in key_ids:
        key_store.shred_key(kid)
    
    # Append shred event
    all_events.append(signed_shred)
    write_events(events_path, all_events)
    
    # Regenerate manifest
    exclude = set(MANIFEST_EXCLUDE)
    manifest = build_manifest(vault_path, exclude)
    leaves = manifest_leaves(manifest)
    root_hex = merkle_root_hex(leaves)
    
    (vault_path / "manifest.json").write_bytes(canonical_json_bytes(manifest))
    (vault_path / "merkle_root.txt").write_text(root_hex + "\n", encoding="utf-8")
    
    return signed_shred


# ---------------------------------------------------------------------------
# Encrypted Vault Creation
# ---------------------------------------------------------------------------

def create_encrypted_vault(
    vault_path: Path,
    actor_name: str,
    encryption_mode: str = "per-event",
) -> Path:
    """Initialize a vault with encryption enabled.
    
    Args:
        vault_path: Path to vault directory.
        actor_name: Actor name for genesis event.
        encryption_mode: "per-event" or "per-actor".
        
    Returns:
        Path to created vault.
        
    Raises:
        ValueError: If invalid encryption mode.
    """
    if encryption_mode not in ("per-event", "per-actor"):
        raise ValueError(f"Invalid encryption mode: {encryption_mode}")
    
    # Create vault structure
    vault_path.mkdir(parents=True, exist_ok=True)
    (vault_path / "events").mkdir(exist_ok=True)
    (vault_path / "identity").mkdir(exist_ok=True)
    (vault_path / "policies").mkdir(exist_ok=True)
    (vault_path / "state").mkdir(exist_ok=True)
    (vault_path / "artifacts" / "cas").mkdir(parents=True, exist_ok=True)
    
    # Initialize key store
    key_store = PrivacyKeyStore(vault_path)
    
    # Store encryption mode marker
    config_path = vault_path / "identity" / "encryption_config.json"
    config_path.write_text(json.dumps({
        "encryption_enabled": True,
        "encryption_mode": encryption_mode,
        "algorithm": "AES-256-GCM",
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }, indent=2))
    
    return vault_path


def is_vault_encrypted(vault_path: Path) -> bool:
    """Check if vault has encryption enabled.
    
    Args:
        vault_path: Path to vault directory.
        
    Returns:
        True if encryption enabled, False otherwise.
    """
    config_path = vault_path / "identity" / "encryption_config.json"
    if not config_path.exists():
        return False
    
    config = json.loads(config_path.read_text())
    return config.get("encryption_enabled", False)


def get_encryption_mode(vault_path: Path) -> Optional[str]:
    """Get vault encryption mode.
    
    Args:
        vault_path: Path to vault directory.
        
    Returns:
        "per-event", "per-actor", or None.
    """
    config_path = vault_path / "identity" / "encryption_config.json"
    if not config_path.exists():
        return None
    
    config = json.loads(config_path.read_text())
    return config.get("encryption_mode")


# ---------------------------------------------------------------------------
# Verification Helpers
# ---------------------------------------------------------------------------

def verify_encrypted_event(
    event: Dict[str, Any],
    key_store: PrivacyKeyStore,
) -> Tuple[bool, str]:
    """Verify an encrypted event.
    
    Args:
        event: Event dict.
        key_store: PrivacyKeyStore instance.
        
    Returns:
        Tuple of (is_valid, message).
    """
    payload = event.get("payload", {})
    
    if not isinstance(payload, dict):
        return False, "Invalid payload format"
    
    if payload.get("_privacy") != "aes-gcm-v1":
        return True, "Event not encrypted (normal)"
    
    # Encrypted event - check if key exists
    kid = payload.get("kid")
    if not kid:
        return False, "Missing key ID"
    
    if key_store.key_exists(kid):
        return True, "Event encrypted, key available"
    else:
        return True, "Event shredded (key destroyed)"


def count_shredded_events(vault_path: Path) -> Tuple[int, int]:
    """Count shredded events in vault.
    
    Args:
        vault_path: Path to vault directory.
        
    Returns:
        Tuple of (total_events, shredded_count).
    """
    events_path = vault_path / "events" / "events.ndjson"
    if not events_path.exists():
        return 0, 0
    
    key_store = PrivacyKeyStore(vault_path)
    all_events = load_events(events_path)
    
    shredded = 0
    for event in all_events:
        payload = event.get("payload", {})
        if isinstance(payload, dict) and payload.get("_privacy") == "aes-gcm-v1":
            kid = payload.get("kid")
            if kid and not key_store.key_exists(kid):
                shredded += 1
    
    return len(all_events), shredded
