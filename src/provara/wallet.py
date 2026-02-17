"""
wallet.py — Provara Economic Bridge

Enables interoperability between Provara Identity Keys and Crypto Wallets.
Currently supports:
- Solana (Ed25519): Native compatibility.
  Provara Key <-> Solana CLI Keypair (id.json)

Dependencies: None (uses stdlib + cryptography)
"""

from __future__ import annotations
import json
import base64
from pathlib import Path
from typing import Dict, Any, List

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey
)
from cryptography.hazmat.primitives import serialization

from .backpack_signing import (
    load_private_key_b64, 
    key_id_from_public_bytes
)

def export_to_solana(private_key_b64: str) -> List[int]:
    """
    Convert a Provara private key (Base64) to Solana CLI format (JSON byte array).
    Solana format: [priv_bytes (32) + pub_bytes (32)] (64 ints total)
    """
    # 1. Decode Private Key bytes (32 bytes)
    # cryptography serialization returns the raw seed for Ed25519
    priv_obj = load_private_key_b64(private_key_b64)
    
    # Extract raw private bytes (32 bytes)
    priv_bytes = priv_obj.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption()
    )
    
    # 2. Derive Public Key bytes (32 bytes)
    pub_obj = priv_obj.public_key()
    pub_bytes = pub_obj.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )
    
    # 3. Concatenate per Solana spec
    full_keypair = priv_bytes + pub_bytes
    
    # 4. Convert to integer list
    return list(full_keypair)

def import_from_solana(solana_keypair: List[int]) -> Dict[str, str]:
    """
    Convert a Solana CLI keypair (list of 64 ints) to Provara format.
    Returns: {"key_id": "...", "private_key_b64": "..."}
    """
    if len(solana_keypair) != 64:
        raise ValueError("Invalid Solana keypair: expected 64 bytes")
        
    # Extract first 32 bytes (private seed)
    priv_bytes = bytes(solana_keypair[:32])
    
    # Create object
    priv_obj = Ed25519PrivateKey.from_private_bytes(priv_bytes)
    
    # Derive Provara formats
    priv_b64 = base64.b64encode(
        priv_obj.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption()
        )
    ).decode("utf-8")
    
    pub_obj = priv_obj.public_key()
    pub_bytes = pub_obj.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )
    
    kid = key_id_from_public_bytes(pub_bytes)
    
    return {
        "key_id": kid,
        "private_key_b64": priv_b64
    }
