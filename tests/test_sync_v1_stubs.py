import pytest
from pathlib import Path
from provara.sync_v1 import (
    CausalFork, SyncDelta, SyncV1Result, merge_v1, get_causal_delta,
    compute_state_vector, detect_forks_v1, get_total_order_key
)

def test_sync_v1_structures():
    fork = CausalFork(actor_id="a1", fork_point_id="evt_1", competing_event_ids=["evt_2", "evt_3"])
    assert fork.actor_id == "a1"
    
    delta = SyncDelta(source_vector={}, events=[], manifest_root="root")
    assert delta.manifest_root == "root"
    
    res = SyncV1Result(success=True, new_events_added=0, forks_detected=[], state_hash="abc")
    assert res.success is True

def test_sync_v1_stubs(tmp_path):
    with pytest.raises(NotImplementedError):
        merge_v1(tmp_path, SyncDelta({}, [], ""))
    
    with pytest.raises(NotImplementedError):
        get_causal_delta(tmp_path, {})
        
    with pytest.raises(NotImplementedError):
        compute_state_vector(tmp_path)
        
    with pytest.raises(NotImplementedError):
        detect_forks_v1([])
        
    with pytest.raises(NotImplementedError):
        get_total_order_key({})
