"""Property-based fuzzing for core Provara protocol invariants."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import tempfile
from pathlib import Path

import pytest

try:
    from hypothesis import assume, given, settings, strategies as st
except ImportError:
    pytest.skip("hypothesis not installed", allow_module_level=True)

from provara import Vault
from provara.backpack_integrity import MANIFEST_EXCLUDE, canonical_json_bytes, merkle_root_hex
from provara.backpack_signing import load_private_key_b64, load_public_key_b64, verify_event_signature
from provara.bootstrap_v0 import bootstrap_backpack
from provara.canonical_json import canonical_dumps, canonical_hash
from provara.cli import cmd_manifest
from provara.manifest_generator import build_manifest, manifest_leaves
from provara.sync_v0 import load_events, verify_causal_chain


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


def _bootstrap(tmp_path: Path, actor: str = "fuzz_actor") -> tuple[Path, Vault, str, str]:
    vault_path = tmp_path / "vault"
    result = bootstrap_backpack(vault_path, actor=actor, quiet=True)
    assert result.success is True, result.errors
    assert result.root_key_id is not None
    assert result.root_private_key_b64 is not None
    return vault_path, Vault(vault_path), result.root_key_id, result.root_private_key_b64


@given(json_data)
@settings(deadline=5000, max_examples=300)
def test_canonical_json_roundtrip(data: object) -> None:
    """Canonical JSON roundtrips and remains byte-identical after re-canonicalization."""
    canonical = canonical_dumps(data)
    reparsed = json.loads(canonical)
    recanonicalized = canonical_dumps(reparsed)
    assert canonical == recanonicalized


@given(event_types, json_data)
@settings(deadline=5000, max_examples=50)
def test_event_signature_always_verifiable(
    event_type: str,
    data: object,
) -> None:
    """Any event created through the API has a valid signature."""
    with tempfile.TemporaryDirectory() as tmp:
        _, vault, key_id, private_key_b64 = _bootstrap(Path(tmp))
        signed = vault.append_event(event_type, {"fuzz_data": data}, key_id, private_key_b64, actor="sig_fuzzer")

        pub = load_public_key_b64(
            json.loads((vault.path / "identity" / "keys.json").read_text(encoding="utf-8"))["keys"][0]["public_key_b64"]
        )
        assert verify_event_signature(signed, pub)


@given(st.lists(st.tuples(actor_names, event_types, json_data), min_size=1, max_size=20))
@settings(deadline=5000, max_examples=40)
def test_chain_integrity_after_random_appends(
    events: list[tuple[str, str, object]],
) -> None:
    """Appending valid random event sequences preserves per-actor chain integrity."""
    with tempfile.TemporaryDirectory() as tmp:
        vault_path, _, key_id, private_key_b64 = _bootstrap(Path(tmp))
        events_path = vault_path / "events" / "events.ndjson"
        private_key = load_private_key_b64(private_key_b64)

        existing = load_events(events_path)
        actor_heads: dict[str, str] = {}
        for event in existing:
            actor = event.get("actor")
            event_id = event.get("event_id")
            if isinstance(actor, str) and isinstance(event_id, str):
                actor_heads[actor] = event_id

        base_time = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)
        for index, (actor, event_type, payload) in enumerate(events, start=1):
            event = {
                "type": event_type,
                "namespace": "local",
                "actor": actor,
                "actor_key_id": key_id,
                "ts_logical": index,
                "prev_event_hash": actor_heads.get(actor),
                "timestamp_utc": (base_time + dt.timedelta(seconds=index)).isoformat(),
                "payload": {"fuzz_data": payload},
            }
            event["event_id"] = f"evt_{canonical_hash(event)[:24]}"
            from provara.backpack_signing import sign_event

            signed = sign_event(event, private_key, key_id)
            with events_path.open("a", encoding="utf-8") as handle:
                handle.write(canonical_dumps(signed) + "\n")
            actor_heads[actor] = signed["event_id"]

        all_events = load_events(events_path)
        for actor in actor_heads:
            assert verify_causal_chain(all_events, actor), actor


@given(st.lists(event_types, min_size=1, max_size=10))
@settings(deadline=5000, max_examples=30)
def test_manifest_always_consistent(event_types_list: list[str]) -> None:
    """Manifest and Merkle root remain consistent after append operations."""
    with tempfile.TemporaryDirectory() as tmp:
        vault_path, vault, key_id, private_key_b64 = _bootstrap(Path(tmp))

        for index, event_type in enumerate(event_types_list):
            vault.append_event(
                event_type,
                {"index": index, "note": "manifest-fuzz"},
                key_id,
                private_key_b64,
                actor="manifest_fuzzer",
            )

        cmd_manifest(argparse.Namespace(path=str(vault_path)))

        manifest_on_disk = json.loads((vault_path / "manifest.json").read_text(encoding="utf-8"))
        merkle_on_disk = (vault_path / "merkle_root.txt").read_text(encoding="utf-8").strip()

        rebuilt_manifest = build_manifest(vault_path, set(MANIFEST_EXCLUDE))
        rebuilt_root = merkle_root_hex(manifest_leaves(rebuilt_manifest))

        assert manifest_on_disk["files"] == rebuilt_manifest["files"]
        assert manifest_on_disk["file_count"] == rebuilt_manifest["file_count"]
        assert merkle_on_disk == rebuilt_root
        assert (vault_path / "manifest.json").read_bytes() == canonical_json_bytes(manifest_on_disk)


@given(st.lists(json_data, min_size=2, max_size=50))
@settings(deadline=5000, max_examples=200)
def test_different_data_different_hashes(payloads: list[object]) -> None:
    """Distinct canonical JSON payloads map to distinct SHA-256 hashes."""
    unique_payloads: dict[str, object] = {}
    for payload in payloads:
        unique_payloads[canonical_dumps(payload)] = payload

    assume(len(unique_payloads) > 1)

    hashes = {canonical_hash(payload) for payload in unique_payloads.values()}
    assert len(hashes) == len(unique_payloads)
