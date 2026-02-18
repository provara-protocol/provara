"""Streaming reducer for large Provara vaults.

The reducer reads ``events/events.ndjson`` incrementally and maintains a compact
running state suitable for very large logs.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterator

from .canonical_json import canonical_dumps, canonical_hash


@dataclass
class VaultState:
    event_count: int
    actor_chain_heads: dict[str, str]
    actors: set[str]
    type_counts: dict[str, int]
    merkle_root: str
    last_event_id: str
    last_event_offset: int
    _merkle_frontier: dict[int, bytes] = field(default_factory=dict, repr=False, compare=False)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_count": self.event_count,
            "actor_chain_heads": dict(self.actor_chain_heads),
            "actors": sorted(self.actors),
            "type_counts": dict(self.type_counts),
            "merkle_root": self.merkle_root,
            "last_event_id": self.last_event_id,
            "last_event_offset": self.last_event_offset,
            "merkle_frontier": {
                str(level): digest.hex()
                for level, digest in sorted(self._merkle_frontier.items())
            },
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VaultState":
        actors_raw = data.get("actors") or []
        frontier_raw = data.get("merkle_frontier") or {}
        frontier: dict[int, bytes] = {}
        if isinstance(frontier_raw, dict):
            for k, v in frontier_raw.items():
                try:
                    frontier[int(k)] = bytes.fromhex(str(v))
                except (TypeError, ValueError):
                    continue

        state = cls(
            event_count=int(data.get("event_count", 0)),
            actor_chain_heads={
                str(k): str(v)
                for k, v in dict(data.get("actor_chain_heads", {})).items()
            },
            actors={str(v) for v in actors_raw},
            type_counts={
                str(k): int(v)
                for k, v in dict(data.get("type_counts", {})).items()
            },
            merkle_root=str(data.get("merkle_root") or hashlib.sha256(b"").hexdigest()),
            last_event_id=str(data.get("last_event_id") or ""),
            last_event_offset=int(data.get("last_event_offset", 0)),
            _merkle_frontier=frontier,
        )
        return state


def _empty_state() -> VaultState:
    return VaultState(
        event_count=0,
        actor_chain_heads={},
        actors=set(),
        type_counts={},
        merkle_root=hashlib.sha256(b"").hexdigest(),
        last_event_id="",
        last_event_offset=0,
        _merkle_frontier={},
    )


def _append_merkle_leaf(frontier: dict[int, bytes], leaf_bytes: bytes) -> None:
    node = hashlib.sha256(leaf_bytes).digest()
    level = 0
    while True:
        existing = frontier.get(level)
        if existing is None:
            frontier[level] = node
            return
        node = hashlib.sha256(existing + node).digest()
        del frontier[level]
        level += 1


def _frontier_root(frontier: dict[int, bytes]) -> str:
    if not frontier:
        return hashlib.sha256(b"").hexdigest()

    max_level = max(frontier)
    carry: bytes | None = None
    level = 0

    while True:
        node = frontier.get(level)
        has_higher = level < max_level

        if carry is not None and node is not None:
            carry = hashlib.sha256(node + carry).digest()
        elif carry is None and node is not None:
            if has_higher:
                carry = hashlib.sha256(node + node).digest()
            else:
                return node.hex()
        elif carry is not None and node is None:
            if has_higher:
                carry = hashlib.sha256(carry + carry).digest()
            else:
                return carry.hex()

        level += 1


def load_checkpoint(path: str | Path) -> VaultState:
    cp_path = Path(path)
    payload = json.loads(cp_path.read_text(encoding="utf-8"))

    if isinstance(payload, dict) and "state" in payload and isinstance(payload["state"], dict):
        return VaultState.from_dict(payload["state"])
    if isinstance(payload, dict):
        return VaultState.from_dict(payload)
    raise ValueError("Checkpoint must be a JSON object")


def save_checkpoint(path: str | Path, state: VaultState) -> Path:
    cp_path = Path(path)
    cp_path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "format": "provara.reducer_v1.checkpoint",
        "state": state.to_dict(),
    }
    cp_path.write_text(canonical_dumps(record), encoding="utf-8")
    return cp_path


def _event_log_path(vault_path: str | Path) -> Path:
    root = Path(vault_path)
    return root / "events" / "events.ndjson"


def reduce_stream(
    vault_path: str | Path,
    checkpoint: str | Path | None = None,
    snapshot_interval: int = 10000,
) -> Iterator[VaultState]:
    """Stream-process events, yielding state snapshots."""
    if snapshot_interval <= 0:
        raise ValueError("snapshot_interval must be > 0")

    state = _empty_state() if checkpoint is None else load_checkpoint(checkpoint)
    events_path = _event_log_path(vault_path)

    if not events_path.exists():
        yield state
        return

    with events_path.open("rb") as f:
        if state.last_event_offset:
            f.seek(state.last_event_offset)

        since_snapshot = 0

        while True:
            raw = f.readline()
            if not raw:
                break

            next_offset = f.tell()
            line = raw.strip()
            if not line:
                state.last_event_offset = next_offset
                continue

            try:
                event = json.loads(line.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                state.last_event_offset = next_offset
                continue

            event_id = str(event.get("event_id") or canonical_hash(event))
            actor = str(event.get("actor") or "")
            event_type = str(event.get("type") or "")

            state.event_count += 1
            state.last_event_id = event_id
            state.last_event_offset = next_offset

            if actor:
                state.actors.add(actor)
                state.actor_chain_heads[actor] = event_id
            if event_type:
                state.type_counts[event_type] = state.type_counts.get(event_type, 0) + 1

            canonical_event_bytes = canonical_dumps(event).encode("utf-8")
            _append_merkle_leaf(state._merkle_frontier, canonical_event_bytes)
            state.merkle_root = _frontier_root(state._merkle_frontier)

            since_snapshot += 1
            if since_snapshot >= snapshot_interval:
                since_snapshot = 0
                yield VaultState.from_dict(state.to_dict())

        if since_snapshot > 0 or state.event_count == 0:
            yield VaultState.from_dict(state.to_dict())
