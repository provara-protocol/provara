"""
sync_v1.py — Provara Offline-First Sync Interface Contract (v1.0)

This module defines the interface for advanced sync operations including
fork detection, total ordering, and causal delta reconciliation.
"""

from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

@dataclass
class CausalFork:
    """Represents a detected causal fork in an actor's chain."""
    actor_id: str
    fork_point_id: str
    competing_event_ids: List[str]

@dataclass
class SyncDelta:
    """A bundle of events and metadata for delta reconciliation."""
    source_vector: Dict[str, str]  # actor_id -> last_event_id
    events: List[Dict[str, Any]]
    manifest_root: str

@dataclass
class SyncV1Result:
    """Result of a sync_v1 operation."""
    success: bool
    new_events_added: int
    forks_detected: List[CausalFork]
    state_hash: str

def merge_v1(
    local_vault: Path,
    remote_delta: SyncDelta,
    signing_key_id: Optional[str] = None,
    signing_private_key: Optional[str] = None
) -> SyncV1Result:
    """
    Perform a v1 total-order merge of a remote delta into a local vault.
    
    1. Dedup events
    2. Re-establish deterministic total order
    3. Detect forks and optionally sign CONFLICT events
    4. Recompute reducer state
    """
    raise NotImplementedError

def get_causal_delta(
    vault_path: Path,
    remote_vector: Dict[str, str]
) -> SyncDelta:
    """
    Identify and bundle all events in the vault that are causal successors 
    to the event IDs provided in the remote state vector.
    """
    raise NotImplementedError

def compute_state_vector(vault_path: Path) -> Dict[str, str]:
    """
    Scan the event log and return a map of each actor to their latest 
    known event_id.
    """
    raise NotImplementedError

def detect_forks_v1(events: List[Dict[str, Any]]) -> List[CausalFork]:
    """
    Exhaustively scan events for causal forks (Type 2 conflicts).
    """
    raise NotImplementedError

def get_total_order_key(event: Dict[str, Any]) -> Tuple[int, str, str]:
    """
    Compute the deterministic sorting key for total ordering.
    (ts_logical, timestamp_utc, event_id)
    """
    raise NotImplementedError
