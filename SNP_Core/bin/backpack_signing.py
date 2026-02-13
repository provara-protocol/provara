"""
backpack_signing.py — Backpack v1.0 Cryptographic Signing Layer

Implements:
  - Ed25519 keypair generation (RFC 8032, mandatory-to-implement per spec)
  - Event signing and verification
  - Manifest signing and verification
  - Key serialization (base64-encoded raw keys)

Dependencies:
  - cryptography >= 41.0 (pip install cryptography)

Security model:
  - Private keys NEVER enter the backpack. They live in HSM, env var, or
    operator-controlled keyfile.
  - Public keys are stored in identity/keys.json.
  - Every event carries: actor_key_id + sig (detached Ed25519 over canonical JSON).
  - Manifest carries: manifest.sig (detached Ed25519 over merkle_root + manifest header).

This module is the foundation for:
  - rekey_backpack.py (key rotation)
  - sync_v0.py (signature verification on merge)
  - bootstrap_v0.py (genesis signing)
"""

from __future__ import annotations
import base64
import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)
from cryptography.exceptions import InvalidSignature

from canonical_json import canonical_bytes, canonical_dumps, canonical_hash


# ---------------------------------------------------------------------------
# Key ID derivation
# ---------------------------------------------------------------------------

def key_id_from_public_bytes(pub_bytes: bytes) -> str:
    """
    Derive a stable key_id from raw public key bytes.
    Format: 'bp1_' + first 16 hex chars of SHA-256(pub_bytes).
    The 'bp1_' prefix identifies Backpack v1 key IDs.
    """
    digest = hashlib.sha256(pub_bytes).hexdigest()
    return f"bp1_{digest[:16]}"


# ---------------------------------------------------------------------------
# Keypair management
# ---------------------------------------------------------------------------

@dataclass
class BackpackKeypair:
    """An Ed25519 keypair with Backpack-specific metadata."""
    private_key: Ed25519PrivateKey
    public_key: Ed25519PublicKey
    key_id: str
    public_key_b64: str  # base64-encoded raw public key

    @classmethod
    def generate(cls) -> "BackpackKeypair":
        """Generate a new Ed25519 keypair."""
        sk = Ed25519PrivateKey.generate()
        pk = sk.public_key()
        pub_bytes = pk.public_bytes(Encoding.Raw, PublicFormat.Raw)
        pub_b64 = base64.b64encode(pub_bytes).decode("ascii")
        kid = key_id_from_public_bytes(pub_bytes)
        return cls(
            private_key=sk,
            public_key=pk,
            key_id=kid,
            public_key_b64=pub_b64,
        )

    def private_key_b64(self) -> str:
        """Export private key as base64. NEVER store this in the backpack."""
        raw = self.private_key.private_bytes(
            Encoding.Raw, PrivateFormat.Raw, NoEncryption()
        )
        return base64.b64encode(raw).decode("ascii")

    def to_keys_entry(
        self,
        roles: Optional[List[str]] = None,
        scopes: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Produce a keys.json entry (public data only)."""
        return {
            "key_id": self.key_id,
            "algorithm": "Ed25519",
            "public_key_b64": self.public_key_b64,
            "roles": roles or ["root", "attestation"],
            "scopes": scopes or ["all"],
            "status": "active",
            "created_at_utc": _utc_now_iso(),
        }


def load_private_key_b64(b64_str: str) -> Ed25519PrivateKey:
    """Load an Ed25519 private key from base64-encoded raw bytes."""
    raw = base64.b64decode(b64_str)
    return Ed25519PrivateKey.from_private_bytes(raw)


def load_public_key_b64(b64_str: str) -> Ed25519PublicKey:
    """Load an Ed25519 public key from base64-encoded raw bytes."""
    raw = base64.b64decode(b64_str)
    return Ed25519PublicKey.from_public_bytes(raw)


# ---------------------------------------------------------------------------
# Event signing
# ---------------------------------------------------------------------------

def sign_event(
    event: Dict[str, Any],
    private_key: Ed25519PrivateKey,
    key_id: str,
) -> Dict[str, Any]:
    """
    Sign an event dict with Ed25519.

    Process:
      1. Set actor_key_id on the event.
      2. Remove any existing 'sig' field.
      3. Canonicalize the event (without sig).
      4. Sign the canonical bytes.
      5. Attach sig as base64.

    Returns the event dict with 'actor_key_id' and 'sig' fields set.
    """
    event = dict(event)  # shallow copy
    event["actor_key_id"] = key_id

    # Remove sig before signing (canonical form = event without sig)
    event.pop("sig", None)
    payload_bytes = canonical_bytes(event)

    sig_bytes = private_key.sign(payload_bytes)
    event["sig"] = base64.b64encode(sig_bytes).decode("ascii")
    return event


def verify_event_signature(
    event: Dict[str, Any],
    public_key: Ed25519PublicKey,
) -> bool:
    """
    Verify an event's Ed25519 signature.

    Returns True if valid, False if invalid or missing sig.
    """
    sig_b64 = event.get("sig")
    if not sig_b64:
        return False

    try:
        sig_bytes = base64.b64decode(sig_b64)
    except Exception:
        return False

    # Reconstruct the signed payload (event without sig)
    check_event = {k: v for k, v in event.items() if k != "sig"}
    payload_bytes = canonical_bytes(check_event)

    try:
        public_key.verify(sig_bytes, payload_bytes)
        return True
    except InvalidSignature:
        return False


# ---------------------------------------------------------------------------
# Manifest signing
# ---------------------------------------------------------------------------

def sign_manifest(
    manifest_path: Path,
    merkle_root_path: Path,
    private_key: Ed25519PrivateKey,
    key_id: str,
) -> Dict[str, Any]:
    """
    Sign the manifest by creating a detached signature over:
      canonical_json({"merkle_root": <root>, "key_id": <kid>, "spec_version": "1.0"})

    Returns the signature record (to be written as manifest.sig).
    """
    merkle_root = merkle_root_path.read_text(encoding="utf-8").strip()

    signable = {
        "merkle_root": merkle_root,
        "key_id": key_id,
        "spec_version": "1.0",
        "signed_at_utc": _utc_now_iso(),
    }
    signable_bytes = canonical_bytes(signable)
    sig_bytes = private_key.sign(signable_bytes)

    return {
        "merkle_root": merkle_root,
        "key_id": key_id,
        "spec_version": "1.0",
        "signed_at_utc": signable["signed_at_utc"],
        "sig": base64.b64encode(sig_bytes).decode("ascii"),
    }


def verify_manifest_signature(
    sig_record: Dict[str, Any],
    public_key: Ed25519PublicKey,
    expected_merkle_root: Optional[str] = None,
) -> bool:
    """Verify a manifest.sig record."""
    sig_b64 = sig_record.get("sig")
    if not sig_b64:
        return False

    try:
        sig_bytes = base64.b64decode(sig_b64)
    except Exception:
        return False

    # Reconstruct signable (everything except sig itself)
    check = {k: v for k, v in sig_record.items() if k != "sig"}
    payload_bytes = canonical_bytes(check)

    try:
        public_key.verify(sig_bytes, payload_bytes)
    except InvalidSignature:
        return False

    # Optionally verify merkle root matches current
    if expected_merkle_root and sig_record.get("merkle_root") != expected_merkle_root:
        return False

    return True


# ---------------------------------------------------------------------------
# Key registry helpers
# ---------------------------------------------------------------------------

def load_keys_registry(keys_path: Path) -> Dict[str, Dict[str, Any]]:
    """Load keys.json and return a dict keyed by key_id."""
    data = json.loads(keys_path.read_text(encoding="utf-8"))
    registry = {}
    for entry in data.get("keys", []):
        kid = entry.get("key_id")
        if kid:
            registry[kid] = entry
    return registry


def resolve_public_key(
    key_id: str,
    keys_registry: Dict[str, Dict[str, Any]],
) -> Optional[Ed25519PublicKey]:
    """Look up a public key from the registry by key_id."""
    entry = keys_registry.get(key_id)
    if not entry:
        return None
    if entry.get("status") == "revoked":
        return None  # revoked keys cannot verify new events
    pub_b64 = entry.get("public_key_b64")
    if not pub_b64:
        return None
    try:
        return load_public_key_b64(pub_b64)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _utc_now_iso() -> str:
    """Current UTC time in ISO 8601 format."""
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).isoformat()
