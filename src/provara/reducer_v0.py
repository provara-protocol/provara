"""
reducer_v0.py — Backpack v1.0 Deterministic Reducer (v0 hardened)

Core invariants:
  1. Events are immutable. Corrections are new events.
  2. Truth is not merged. Evidence is merged. Truth is recomputed.
  3. Deterministic: same events in same order → byte-identical state hash.
  4. Provenance + confidence required for any claim affecting belief/state.

This reducer does NOT verify signatures or hash-chains.
That responsibility belongs to the sync/verify layer.

Changelog vs original v0:
  - Fixed self-referential state hash (hash now excludes metadata.state_hash)
  - Contested records now capture ALL conflicting evidence, not just last
  - local/ cleaned on contest (no stale local entries for contested keys)
  - archived/ namespace implemented (superseded canonical beliefs preserved)
  - Agreeing evidence strengthens confidence (max, not overwrite)
  - REDUCER_EPOCH events tracked
  - Unknown event types preserved without crash (logged to _ignored_types)
  - Malformed events handled gracefully
"""

from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any, Dict, Iterable, List, Optional, Set
import copy

from .canonical_json import canonical_hash, canonical_dumps

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

REDUCER_NAME = "SovereignReducerV0"
REDUCER_VERSION = "0.2.0"
DEFAULT_CONFLICT_CONFIDENCE_THRESHOLD = 0.50
DEFAULT_OBSERVATION_CONFIDENCE = 0.50
DEFAULT_ASSERTION_CONFIDENCE = 0.35


# ---------------------------------------------------------------------------
# Evidence record
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Evidence:
    event_id: str
    actor: str
    namespace: str
    timestamp_utc: Optional[str]
    value: Any
    confidence: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "actor": self.actor,
            "namespace": self.namespace,
            "timestamp_utc": self.timestamp_utc,
            "value": self.value,
            "confidence": self.confidence,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VALID_NAMESPACES = frozenset({"canonical", "local", "contested", "archived"})


def belief_key(subject: str, predicate: str) -> str:
    return f"{subject}:{predicate}"


def _normalize_namespace(raw: Any) -> str:
    ns = str(raw or "local").strip().lower()
    return ns if ns in VALID_NAMESPACES else "local"


def _safe_float(val: Any, default: float) -> float:
    if val is None:
        return default
    try:
        f = float(val)
        return f if f == f else default  # NaN guard
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# Reducer
# ---------------------------------------------------------------------------

class SovereignReducerV0:
    """
    Four-namespace state model:
      canonical/  — attested institutional truth
      local/      — node-local observations (pending attestation)
      contested/  — conflicting high-confidence evidence
      archived/   — superseded canonical beliefs (audit trail)

    Evidence index kept internally for conflict analysis.
    """

    def __init__(
        self,
        conflict_confidence_threshold: float = DEFAULT_CONFLICT_CONFIDENCE_THRESHOLD,
    ):
        self.conflict_confidence_threshold = float(conflict_confidence_threshold)

        self.state: Dict[str, Any] = {
            "canonical": {},
            "local": {},
            "contested": {},
            "archived": {},
            "metadata": {
                "last_event_id": None,
                "event_count": 0,
                "state_hash": None,
                "current_epoch": None,
                "reducer": {
                    "name": REDUCER_NAME,
                    "version": REDUCER_VERSION,
                    "conflict_confidence_threshold": self.conflict_confidence_threshold,
                },
            },
        }

        # Internal: per-key evidence lists (not exported by default)
        self._evidence: Dict[str, List[Evidence]] = {}
        # Track unknown event types seen (diagnostic, not exported)
        self._ignored_types: Set[str] = set()

        # Compute initial state hash so the empty state is fully valid
        self.state["metadata"]["state_hash"] = self._compute_state_hash()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def apply_events(self, events: Iterable[Dict[str, Any]]) -> None:
        """Apply a sequence of events efficiently, hashing only once at the end."""
        for event in events:
            self._apply_event_internal(event)
        self.state["metadata"]["state_hash"] = self._compute_state_hash()

    def apply_event(self, event: Dict[str, Any]) -> None:
        """Apply a single event and update the state hash."""
        self._apply_event_internal(event)
        self.state["metadata"]["state_hash"] = self._compute_state_hash()

    def _apply_event_internal(self, event: Dict[str, Any]) -> None:
        """Core logic for applying an event without recomputing the state hash."""
        if not isinstance(event, dict):
            return  # malformed — skip silently

        e_type = event.get("type")
        event_id = event.get("event_id") or event.get("id") or "unknown_event"
        actor = str(event.get("actor") or "unknown")
        namespace = _normalize_namespace(event.get("namespace"))
        payload = event.get("payload") or {}

        if e_type == "OBSERVATION":
            self._handle_observation(event_id, actor, namespace, payload)
        elif e_type == "ASSERTION":
            self._handle_observation(
                event_id, actor, namespace, payload, is_assertion=True
            )
        elif e_type == "ATTESTATION":
            self._handle_attestation(event_id, actor, payload)
        elif e_type == "RETRACTION":
            self._handle_retraction(event_id, actor, payload)
        elif e_type == "REDUCER_EPOCH":
            self._handle_reducer_epoch(event_id, payload)
        else:
            # Unknown types: preserve in log, ignore in reducer.
            if e_type:
                self._ignored_types.add(str(e_type))

        # Update metadata (always, even for unknown types — they still count)
        self.state["metadata"]["last_event_id"] = event_id
        self.state["metadata"]["event_count"] += 1

    def export_state(self) -> Dict[str, Any]:
        """Deterministic, JSON-serializable snapshot of all four namespaces."""
        return {
            "canonical": self.state["canonical"],
            "local": self.state["local"],
            "contested": self.state["contested"],
            "archived": self.state["archived"],
            "metadata": self.state["metadata"],
        }

    def export_state_json(self) -> str:
        return canonical_dumps(self.export_state())

    def export_evidence(self) -> Dict[str, List[Dict[str, Any]]]:
        """Export raw evidence index (for audit/debug)."""
        return {
            key: [ev.to_dict() for ev in evs]
            for key, evs in sorted(self._evidence.items())
        }

    def load_checkpoint(self, checkpoint_dict: Dict[str, Any]) -> None:
        """
        Load reducer state from a checkpoint record.
        This is an optimization path for replay speed, not a source of truth.
        """
        cp_state = checkpoint_dict.get("state", {})
        if not isinstance(cp_state, dict):
            return

        self.state["canonical"] = dict(cp_state.get("canonical", {}))
        self.state["local"] = dict(cp_state.get("local", {}))
        self.state["contested"] = dict(cp_state.get("contested", {}))
        self.state["archived"] = dict(cp_state.get("archived", {}))

        metadata_partial = cp_state.get("metadata_partial", {})
        if isinstance(metadata_partial, dict):
            self.state["metadata"]["last_event_id"] = metadata_partial.get("last_event_id")
            self.state["metadata"]["event_count"] = int(metadata_partial.get("event_count", 0))
            self.state["metadata"]["current_epoch"] = metadata_partial.get("current_epoch")
            reducer_meta = metadata_partial.get("reducer")
            if isinstance(reducer_meta, dict):
                self.state["metadata"]["reducer"] = reducer_meta

        self.state["metadata"]["state_hash"] = self._compute_state_hash()

    # ------------------------------------------------------------------
    # State hash (non-self-referential)
    # ------------------------------------------------------------------

    def _compute_state_hash(self) -> str:
        """
        Hash over state content EXCLUDING metadata.state_hash itself.
        This prevents the hash from being self-referential / chain-dependent.
        An independent verifier can recompute this from the four namespaces
        plus the non-hash metadata fields.
        """
        hashable = {
            "canonical": self.state["canonical"],
            "local": self.state["local"],
            "contested": self.state["contested"],
            "archived": self.state["archived"],
            "metadata_partial": {
                "last_event_id": self.state["metadata"]["last_event_id"],
                "event_count": self.state["metadata"]["event_count"],
                "current_epoch": self.state["metadata"]["current_epoch"],
                "reducer": self.state["metadata"]["reducer"],
            },
        }
        return canonical_hash(hashable)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _handle_observation(
        self,
        event_id: str,
        actor: str,
        namespace: str,
        payload: Dict[str, Any],
        is_assertion: bool = False,
    ) -> None:
        subject = payload.get("subject")
        predicate = payload.get("predicate")
        if not subject or not predicate:
            return  # malformed observation — skip

        key = belief_key(str(subject), str(predicate))
        value = payload.get("value")
        default_conf = DEFAULT_ASSERTION_CONFIDENCE if is_assertion else DEFAULT_OBSERVATION_CONFIDENCE
        confidence = _safe_float(payload.get("confidence"), default_conf)
        ts = payload.get("timestamp") or payload.get("timestamp_utc")

        ev = Evidence(
            event_id=event_id,
            actor=actor,
            namespace=namespace,
            timestamp_utc=str(ts) if ts is not None else None,
            value=value,
            confidence=confidence,
        )
        self._evidence.setdefault(key, []).append(ev)

        # --- Conflict detection ---
        canonical_entry = self.state["canonical"].get(key)
        local_entry = self.state["local"].get(key)

        # Case 1: Conflicts with canonical
        if (
            canonical_entry
            and canonical_entry.get("value") != value
            and confidence >= self.conflict_confidence_threshold
        ):
            self._mark_contested(key, reason="conflicts_with_canonical")
            return

        # Case 2: Conflicts with existing local
        if local_entry and local_entry.get("value") != value:
            prev_conf = _safe_float(local_entry.get("confidence"), 0.0)
            if max(prev_conf, confidence) >= self.conflict_confidence_threshold:
                self._mark_contested(key, reason="conflicts_with_local")
                return

        # Case 3: Agreeing evidence — strengthen confidence, don't overwrite downward
        if local_entry and local_entry.get("value") == value:
            existing_conf = _safe_float(local_entry.get("confidence"), 0.0)
            if confidence <= existing_conf:
                # Same value, weaker confidence — keep existing, just record evidence
                return

        # Case 4: New or stronger-confidence local entry
        self.state["local"][key] = {
            "value": value,
            "confidence": confidence,
            "provenance": event_id,
            "actor": actor,
            "timestamp": str(ts) if ts is not None else None,
            "evidence_count": len(self._evidence.get(key, [])),
        }

    def _handle_attestation(
        self, event_id: str, actor: str, payload: Dict[str, Any]
    ) -> None:
        """
        Promote a belief to canonical/.
        If a canonical entry already exists for this key, archive it first.
        Clears local/ and contested/ for the key.
        """
        subject = payload.get("subject")
        predicate = payload.get("predicate")
        if not subject or not predicate:
            return

        key = belief_key(str(subject), str(predicate))
        value = payload.get("value")
        target_event_id = payload.get("target_event_id")

        # Archive existing canonical entry if present (superseded)
        existing_canonical = self.state["canonical"].get(key)
        if existing_canonical is not None:
            archived_list = self.state["archived"].setdefault(key, [])
            archived_entry = copy.deepcopy(existing_canonical)
            archived_entry["superseded_by"] = event_id
            archived_list.append(archived_entry)

        # Write new canonical
        self.state["canonical"][key] = {
            "value": value,
            "attested_by": payload.get("actor_key_id") or actor,
            "provenance": target_event_id or event_id,
            "attestation_event_id": event_id,
        }

        # Clean contested and local
        self.state["local"].pop(key, None)
        self.state["contested"].pop(key, None)

    def _handle_retraction(
        self, event_id: str, actor: str, payload: Dict[str, Any]
    ) -> None:
        """
        Retract a belief (PROTOCOL_PROFILE.txt EXTENSION RULES — core event type).

        Removes the key from local/ and contested/. If the key is in canonical/,
        archives the entry as retracted before removing it.
        """
        subject = payload.get("subject")
        predicate = payload.get("predicate")
        if not subject or not predicate:
            return

        key = belief_key(str(subject), str(predicate))

        # Archive canonical entry if present, marking it as retracted
        existing_canonical = self.state["canonical"].get(key)
        if existing_canonical is not None:
            archived_list = self.state["archived"].setdefault(key, [])
            archived_entry = copy.deepcopy(existing_canonical)
            archived_entry["superseded_by"] = event_id
            archived_entry["retracted"] = True
            archived_list.append(archived_entry)
            del self.state["canonical"][key]

        # Remove from local and contested
        self.state["local"].pop(key, None)
        self.state["contested"].pop(key, None)

    def _handle_reducer_epoch(
        self, event_id: str, payload: Dict[str, Any]
    ) -> None:
        """Record a reducer epoch transition."""
        self.state["metadata"]["current_epoch"] = {
            "epoch_id": payload.get("epoch_id"),
            "reducer_hash": payload.get("reducer_hash"),
            "effective_from_event_id": payload.get("effective_from_event_id") or event_id,
            "ontology_versions": payload.get("ontology_versions"),
        }

    # ------------------------------------------------------------------
    # Contested belief handling
    # ------------------------------------------------------------------

    def _mark_contested(self, key: str, reason: str) -> None:
        """
        Move a key into contested/ with ALL evidence collected so far.
        Remove from local/ to prevent stale entries.
        """
        all_evidence = self._evidence.get(key, [])

        # Group evidence by distinct value
        by_value: Dict[str, List[Dict[str, Any]]] = {}
        for ev in all_evidence:
            val_key = canonical_dumps(ev.value)  # deterministic grouping
            by_value.setdefault(val_key, []).append(ev.to_dict())

        self.state["contested"][key] = {
            "status": "AWAITING_RESOLUTION",
            "reason": reason,
            "canonical_value": (
                self.state["canonical"].get(key, {}).get("value")
            ),
            "evidence_by_value": {
                k: entries for k, entries in sorted(by_value.items())
            },
            "total_evidence_count": len(all_evidence),
        }

        # Remove from local — contested supersedes
        self.state["local"].pop(key, None)
