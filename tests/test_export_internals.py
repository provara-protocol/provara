import pytest
from pathlib import Path
from provara.export import _build_chain_proof, _build_merkle_proof
from provara.bootstrap_v0 import bootstrap_backpack

def test_build_chain_proof_not_found():
    events = [{"event_id": "evt_1", "actor": "a"}]
    target = {"event_id": "evt_2", "actor": "a"}
    res = _build_chain_proof(events, target)
    assert "error" in res

def test_build_merkle_proof_no_manifest(tmp_path):
    res = _build_merkle_proof(tmp_path, {})
    assert "error" in res
