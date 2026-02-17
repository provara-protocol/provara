"""
checkpoint_v0.py — Backpack v1.0 Checkpoint System

Implements signed state materializations for fast replay.
Checkpoints are verifier optimizations, not evidence. They live in
checkpoints/NNNNNNNNNN.chk and are signed by an authorized key.
"""

from __future__ import annotations
import base64
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from .canonical_json import canonical_bytes, canonical_dumps
from .backpack_signing import _utc_now_iso, verify_manifest_signature

@dataclass(frozen=True)
class Checkpoint:
    merkle_root: Optional[str]
    last_event_id: Optional[str]
    event_count: int
    state: Dict[str, Any]
    key_id: str
    signed_at_utc: str
    sig: str
    spec_version: str = "1.0"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "merkle_root": self.merkle_root,
            "last_event_id": self.last_event_id,
            "event_count": self.event_count,
            "state": self.state,
            "key_id": self.key_id,
            "signed_at_utc": self.signed_at_utc,
            "sig": self.sig,
            "spec_version": self.spec_version,
        }

def create_checkpoint(
    backpack_path: Path,
    state: Dict[str, Any],
    private_key: Ed25519PrivateKey,
    key_id: str,
) -> Checkpoint:
    """
    Create a signed checkpoint of the current state.
    """
    merkle_root_path = backpack_path / "merkle_root.txt"
    merkle_root = None
    if merkle_root_path.exists():
        merkle_root = merkle_root_path.read_text(encoding="utf-8").strip()
    
    metadata = state.get("metadata", {})
    last_event_id = metadata.get("last_event_id")
    event_count = metadata.get("event_count", 0)
    
    # State without metadata.state_hash (already handled by reducer)
    # Actually, we want to include the full state as derived by the reducer.
    
    checkpoint_data = {
        "merkle_root": merkle_root,
        "last_event_id": last_event_id,
        "event_count": event_count,
        "state": {
            "canonical": state.get("canonical", {}),
            "local": state.get("local", {}),
            "contested": state.get("contested", {}),
            "archived": state.get("archived", {}),
            "metadata_partial": {
                "last_event_id": last_event_id,
                "event_count": event_count,
                "current_epoch": metadata.get("current_epoch"),
                "reducer": metadata.get("reducer"),
            }
        },
        "key_id": key_id,
        "spec_version": "1.0",
        "signed_at_utc": _utc_now_iso(),
    }
    
    signable_bytes = canonical_bytes(checkpoint_data)
    sig_bytes = private_key.sign(signable_bytes)
    
    return Checkpoint(
        merkle_root=merkle_root,
        last_event_id=last_event_id,
        event_count=event_count,
        state=checkpoint_data["state"],
        key_id=key_id,
        signed_at_utc=checkpoint_data["signed_at_utc"],
        sig=base64.b64encode(sig_bytes).decode("ascii"),
    )

def verify_checkpoint(
    checkpoint_dict: Dict[str, Any],
    public_key: Ed25519PublicKey,
) -> bool:
    """
    Verify a checkpoint record's signature.
    """
    sig_b64 = checkpoint_dict.get("sig")
    if not sig_b64:
        return False

    try:
        sig_bytes = base64.b64decode(sig_b64)
    except Exception:
        return False

    # Reconstruct signable (everything except sig itself)
    check = {k: v for k, v in checkpoint_dict.items() if k != "sig"}
    payload_bytes = canonical_bytes(check)

    try:
        public_key.verify(sig_bytes, payload_bytes)
        return True
    except Exception:
        return False

def save_checkpoint(backpack_path: Path, checkpoint: Checkpoint) -> Path:
    """
    Save a checkpoint to checkpoints/NNNNNNNNNN.chk
    """
    cp_dir = backpack_path / "checkpoints"
    cp_dir.mkdir(parents=True, exist_ok=True)
    
    filename = f"{checkpoint.event_count:010d}.chk"
    cp_path = cp_dir / filename
    
    cp_path.write_text(canonical_dumps(checkpoint.to_dict()), encoding="utf-8")
    return cp_path

def load_latest_checkpoint(backpack_path: Path) -> Optional[Dict[str, Any]]:
    """
    Load the latest checkpoint from checkpoints/ directory.
    """
    cp_dir = backpack_path / "checkpoints"
    if not cp_dir.is_dir():
        return None
    
    checkpoints = sorted(cp_dir.glob("*.chk"), reverse=True)
    if not checkpoints:
        return None
    
    try:
        data = json.loads(checkpoints[0].read_text(encoding="utf-8"))
        return dict(data) if isinstance(data, dict) else None
    except (json.JSONDecodeError, OSError):
        return None
