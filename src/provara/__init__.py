"""
Provara Protocol SDK
====================

A sovereign, tamper-evident memory substrate for AI agents and digital institutions.

Usage:
    from provara import SovereignReducer, bootstrap_backpack, sign_event

    reducer = SovereignReducer()
    reducer.apply_events(events)
    print(reducer.export_state())
"""

from pathlib import Path
from typing import Any, Dict, Optional

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
from .sync_v0 import sync_backpacks, load_events
from .checkpoint_v0 import create_checkpoint, load_latest_checkpoint
from .perception_v0 import emit_perception_event, PerceptionTier


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
        result = bootstrap_backpack(
            Path(path),
            uid=uid,
            actor=actor,
            include_quorum=include_quorum,
            quiet=quiet,
        )
        if not result.success:
            raise ValueError(f"Bootstrap failed: {result.errors}")
        return cls(path)

    def replay_state(self) -> Dict[str, Any]:
        events = load_events(self.path / "events" / "events.ndjson")
        reducer = SovereignReducer()
        reducer.apply_events(events)
        return reducer.export_state()

    def sync_from(self, remote_path: str | Path) -> Any:
        return sync_backpacks(self.path, Path(remote_path).resolve())


# Backward-compatible alias while public API transitions.
SovereignReducerV0 = SovereignReducer

__version__ = "1.0.0"
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
]
