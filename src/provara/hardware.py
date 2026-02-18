"""
hardware.py — Provara Hardware Key Interface (FIDO2 / PKCS#11)

Provides an abstract interface for interacting with hardware security tokens
such as YubiKeys, SoloKeys, and HSMs.
"""

from __future__ import annotations
import base64
from typing import Optional, Protocol, List

class HardwareToken(Protocol):
    """Protocol for hardware token implementations."""
    def get_id(self) -> str: ...
    def get_public_key(self) -> bytes: ...
    def sign(self, data: bytes) -> bytes: ...

def detect_hardware_key() -> List[str]:
    """
    Scan for available hardware tokens.
    Returns a list of token identifiers.
    """
    # This is a stub for the logic that would use python-fido2 or PyKCS11
    # For now, it returns an empty list unless mocked.
    return []

def sign_with_hardware(token_id: str, message: bytes) -> bytes:
    """
    Prepare and execute a hardware-backed signature.
    """
    # 1. préparer le token (demande de toucher, PIN, etc.)
    # 2. envoyer le hash au token
    # 3. récupérer la signature
    raise NotImplementedError("Hardware signing requires a physical token and driver.")

def export_public_key_from_hardware(token_id: str) -> bytes:
    """
    Retrieve the public key from a specific hardware token.
    """
    raise NotImplementedError("Hardware communication not available in prototype.")

class MockHardwareToken:
    """Mock implementation for testing purposes."""
    def __init__(self, token_id: str):
        self.token_id = token_id
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        self._sk = Ed25519PrivateKey.generate()
        self._pk = self._sk.public_key()

    def get_id(self) -> str:
        return self.token_id

    def get_public_key(self) -> bytes:
        from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
        return self._pk.public_bytes(Encoding.Raw, PublicFormat.Raw)

    def sign(self, data: bytes) -> bytes:
        return self._sk.sign(data)
