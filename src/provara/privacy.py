"""
privacy.py — Cryptographic Erasure for Provara Vaults

Implements "Crypto-Shredding" to reconcile immutability with GDPR.
- Encrypts sensitive data with ephemeral keys.
- Stores keys in a mutable sidecar (sqlite/json).
- Deletes keys to "erase" data while preserving the chain.
"""

from __future__ import annotations
import os
import json
import base64
import sqlite3
from pathlib import Path
from typing import Dict, Any, Optional, cast

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

class PrivacyKeyStore:
    """Mutable sidecar for ephemeral data keys."""
    def __init__(self, vault_path: Path):
        self.db_path = vault_path / "identity" / "privacy_keys.db"
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS keys (
                    key_id TEXT PRIMARY KEY,
                    key_bytes BLOB NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

    def store_key(self, key_id: str, key_bytes: bytes) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("INSERT INTO keys (key_id, key_bytes) VALUES (?, ?)", (key_id, key_bytes))

    def get_key(self, key_id: str) -> Optional[bytes]:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute("SELECT key_bytes FROM keys WHERE key_id = ?", (key_id,))
            row = cur.fetchone()
            return bytes(row[0]) if row else None

    def shred_key(self, key_id: str) -> bool:
        """The 'Erasure' operation."""
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute("DELETE FROM keys WHERE key_id = ?", (key_id,))
            return cur.rowcount > 0

class PrivacyWrapper:
    """Encrypts/Decrypts payloads using AES-GCM."""
    
    def __init__(self, vault_path: Path):
        self.keystore = PrivacyKeyStore(vault_path)

    def encrypt(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Returns a wrapper dict:
        {
            "_privacy": "aes-gcm-v1",
            "kid": "<uuid>",
            "nonce": "<b64>",
            "ciphertext": "<b64>"
        }
        """
        import uuid
        key = AESGCM.generate_key(bit_length=256)
        kid = str(uuid.uuid4())
        nonce = os.urandom(12)
        aesgcm = AESGCM(key)
        
        # Canonicalize before encryption to ensure integrity
        plaintext = json.dumps(data, sort_keys=True).encode("utf-8")
        ciphertext = aesgcm.encrypt(nonce, plaintext, None)
        
        self.keystore.store_key(kid, key)
        
        return {
            "_privacy": "aes-gcm-v1",
            "kid": kid,
            "nonce": base64.b64encode(nonce).decode("utf-8"),
            "ciphertext": base64.b64encode(ciphertext).decode("utf-8")
        }

    def decrypt(self, wrapper: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Returns decrypted dict or None if key is shredded.
        """
        if wrapper.get("_privacy") != "aes-gcm-v1":
            raise ValueError("Unsupported privacy scheme")
            
        kid = wrapper["kid"]
        key = self.keystore.get_key(kid)
        if not key:
            return None # DATA ERASED
            
        nonce = base64.b64decode(wrapper["nonce"])
        ciphertext = base64.b64decode(wrapper["ciphertext"])
        aesgcm = AESGCM(key)
        
        try:
            plaintext = aesgcm.decrypt(nonce, ciphertext, None)
            parsed = json.loads(plaintext)
            if isinstance(parsed, dict):
                return cast(Dict[str, Any], parsed)
            return None
        except Exception:
            return None

    def shred(self, kid: str) -> bool:
        return self.keystore.shred_key(kid)
