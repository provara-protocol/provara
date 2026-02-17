"""
messaging.py — Provara Sovereign Messaging (Agent-to-Agent Encryption)

Enables secure P2P communication using native X25519 encryption keys.
"""

from __future__ import annotations
import os
import base64
import json
from pathlib import Path
from typing import Dict, Any, cast

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

def send_encrypted_message(
    sender_encryption_private_key_b64: str,
    recipient_encryption_public_key_b64: str,
    message_dict: Dict[str, Any]
) -> Dict[str, str]:
    """
    Encrypt a message for a recipient using X25519 DH key exchange.
    Returns: { "sender_pubkey_b64": "...", "nonce": "...", "ciphertext": "..." }
    """
    # 1. Load X25519 Keys
    priv_bytes = base64.b64decode(sender_encryption_private_key_b64)
    sender_priv = x25519.X25519PrivateKey.from_private_bytes(priv_bytes)
    
    pub_bytes = base64.b64decode(recipient_encryption_public_key_b64)
    recipient_pub = x25519.X25519PublicKey.from_public_bytes(pub_bytes)
    
    # 2. Key Exchange (Diffie-Hellman)
    shared_key = sender_priv.exchange(recipient_pub)
    
    # 3. Key Derivation (HKDF)
    derived_key = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=b"provara-sovereign-messaging-v1",
    ).derive(shared_key)
    
    # 4. Encryption (AES-GCM)
    aesgcm = AESGCM(derived_key)
    nonce = os.urandom(12)
    plaintext = json.dumps(message_dict, sort_keys=True).encode("utf-8")
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    
    sender_pub_b64 = base64.b64encode(
        sender_priv.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
    ).decode("utf-8")
    
    return {
        "sender_pubkey_b64": sender_pub_b64,
        "nonce": base64.b64encode(nonce).decode("utf-8"),
        "ciphertext": base64.b64encode(ciphertext).decode("utf-8")
    }

def receive_encrypted_message(
    recipient_encryption_private_key_b64: str,
    sender_encryption_public_key_b64: str,
    message_wrapper: Dict[str, str]
) -> Dict[str, Any]:
    """
    Decrypt a message from a sender.
    """
    # 1. Load X25519 Keys
    priv_bytes = base64.b64decode(recipient_encryption_private_key_b64)
    recipient_priv = x25519.X25519PrivateKey.from_private_bytes(priv_bytes)
    
    pub_bytes = base64.b64decode(sender_encryption_public_key_b64)
    sender_pub = x25519.X25519PublicKey.from_public_bytes(pub_bytes)
    
    # 2. Key Exchange
    shared_key = recipient_priv.exchange(sender_pub)
    
    # 3. Key Derivation
    derived_key = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=b"provara-sovereign-messaging-v1",
    ).derive(shared_key)
    
    # 4. Decryption
    aesgcm = AESGCM(derived_key)
    nonce = base64.b64decode(message_wrapper["nonce"])
    ciphertext = base64.b64decode(message_wrapper["ciphertext"])
    
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    parsed = json.loads(plaintext)
    if not isinstance(parsed, dict):
        raise ValueError("Decrypted message payload must be a JSON object")
    return cast(Dict[str, Any], parsed)
