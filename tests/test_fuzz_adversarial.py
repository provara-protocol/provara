"""Stateful adversarial fuzzing for append-only vault invariants."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import tempfile
from pathlib import Path
from typing import Any

from hypothesis import settings, strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, rule

from provara.backpack_integrity import MANIFEST_EXCLUDE, merkle_root_hex
from provara.backpack_signing import load_private_key_b64, sign_event
from provara.bootstrap_v0 import bootstrap_backpack
from provara.canonical_json import canonical_dumps, canonical_hash
from provara.cli import cmd_manifest
from provara.manifest_generator import build_manifest, manifest_leaves
from provara.sync_v0 import load_events, load_keys_registry, verify_all_signatures, verify_causal_chain


event_types = st.sampled_from(["OBSERVATION", "ATTESTATION", "RETRACTION", "CORRECTION"])
actor_names = st.text(
    min_size=1,
    max_size=50,
    alphabet=st.characters(whitelist_categories=("L", "N")),
)
json_data = st.recursive(
    st.one_of(
        st.none(),
        st.booleans(),
        st.integers(),
        st.floats(allow_nan=False, allow_infinity=False),
        st.text(),
    ),
    lambda children: st.one_of(
        st.lists(children, max_size=5),
        st.dictionaries(st.text(min_size=1, max_size=20), children, max_size=5),
    ),
    max_leaves=10,
)


class VaultStateMachine(RuleBasedStateMachine):
    """Exercise random operation sequences while checking protocol invariants."""

    def __init__(self) -> None:
        super().__init__()
        self._tmp = tempfile.TemporaryDirectory()
        self.vault_path = Path(self._tmp.name) / "vault"
        result = bootstrap_backpack(self.vault_path, actor="stateful_fuzzer", quiet=True)
        assert result.success is True, result.errors
        assert result.root_key_id is not None
        assert result.root_private_key_b64 is not None
        self.key_id = result.root_key_id
        self.private_key = load_private_key_b64(result.root_private_key_b64)
        self.events_path = self.vault_path / "events" / "events.ndjson"
        self.keys_path = self.vault_path / "identity" / "keys.json"
        self.base_time = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)
        self.step_counter = 0

        self.expected_event_ids: list[str] = []
        self.expected_actors: set[str] = set()
        self.actor_heads: dict[str, str] = {}
        for event in load_events(self.events_path):
            event_id = event.get("event_id")
            actor = event.get("actor")
            if isinstance(event_id, str):
                self.expected_event_ids.append(event_id)
            if isinstance(actor, str) and isinstance(event_id, str):
                self.expected_actors.add(actor)
                self.actor_heads[actor] = event_id

    def teardown(self) -> None:
        self._tmp.cleanup()

    @rule(actor=actor_names, event_type=event_types, data=json_data)
    def append_event(self, actor: str, event_type: str, data: Any) -> None:
        """Append a random signed event and update expected model state."""
        self.step_counter += 1
        event = {
            "type": event_type,
            "namespace": "local",
            "actor": actor,
            "actor_key_id": self.key_id,
            "ts_logical": self.step_counter,
            "prev_event_hash": self.actor_heads.get(actor),
            "timestamp_utc": (self.base_time + dt.timedelta(seconds=self.step_counter)).isoformat(),
            "payload": {"fuzz_data": data},
        }
        event["event_id"] = f"evt_{canonical_hash(event)[:24]}"
        signed = sign_event(event, self.private_key, self.key_id)
        with self.events_path.open("a", encoding="utf-8") as handle:
            handle.write(canonical_dumps(signed) + "\n")

        self.expected_event_ids.append(signed["event_id"])
        self.expected_actors.add(actor)
        self.actor_heads[actor] = signed["event_id"]

    @rule()
    def verify_chain(self) -> None:
        """Every actor chain remains causally valid."""
        events = load_events(self.events_path)
        for actor in self.expected_actors:
            assert verify_causal_chain(events, actor), actor

    @rule()
    def verify_signatures(self) -> None:
        """All event signatures verify against current key registry."""
        events = load_events(self.events_path)
        registry = load_keys_registry(self.keys_path)
        valid, invalid, _errors = verify_all_signatures(events, registry)
        assert invalid == 0
        assert valid >= len(self.expected_event_ids)

    @rule()
    def verify_manifest(self) -> None:
        """Merkle root matches a fresh deterministic manifest rebuild."""
        cmd_manifest(argparse.Namespace(path=str(self.vault_path)))
        rebuilt_manifest = build_manifest(self.vault_path, set(MANIFEST_EXCLUDE))
        rebuilt_root = merkle_root_hex(manifest_leaves(rebuilt_manifest))
        stored_root = (self.vault_path / "merkle_root.txt").read_text(encoding="utf-8").strip()
        stored_manifest = json.loads((self.vault_path / "manifest.json").read_text(encoding="utf-8"))
        assert stored_root == rebuilt_root
        assert stored_manifest["files"] == rebuilt_manifest["files"]

    @invariant()
    def event_count_matches(self) -> None:
        """Observed event count matches model event count."""
        assert len(load_events(self.events_path)) == len(self.expected_event_ids)

    @invariant()
    def no_duplicate_ids(self) -> None:
        """All persisted events have unique event IDs."""
        events = load_events(self.events_path)
        event_ids = [event.get("event_id") for event in events if "event_id" in event]
        assert len(event_ids) == len(set(event_ids))


TestVaultStateMachine = VaultStateMachine.TestCase
TestVaultStateMachine.settings = settings(
    max_examples=40,
    stateful_step_count=20,
    deadline=5000,
)

