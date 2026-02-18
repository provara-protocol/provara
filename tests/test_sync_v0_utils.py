import pytest
from provara.sync_v0 import _event_content_hash, verify_causal_chain, get_all_actors, verify_all_causal_chains

def test_event_content_hash():
    # With event_id
    assert _event_content_hash({"event_id": "abc"}) == "abc"
    # Without event_id
    h = _event_content_hash({"foo": "bar"})
    assert len(h) == 64

def test_verify_causal_chain_empty():
    assert verify_causal_chain([], "actor") is True

def test_verify_causal_chain_invalid_first():
    # First event must have null prev_hash
    events = [{"actor": "a", "event_id": "e1", "prev_event_hash": "e0"}]
    assert verify_causal_chain(events, "a") is False

def test_verify_causal_chain_invalid_link():
    events = [
        {"actor": "a", "event_id": "e1", "prev_event_hash": None},
        {"actor": "a", "event_id": "e2", "prev_event_hash": "wrong"}
    ]
    assert verify_causal_chain(events, "a") is False

def test_get_all_actors():
    events = [{"actor": "a1"}, {"actor": "a2"}, {"actor": None}, {}]
    assert get_all_actors(events) == {"a1", "a2"}

def test_verify_all_causal_chains():
    events = [{"actor": "a1", "event_id": "e1", "prev_event_hash": None}]
    res = verify_all_causal_chains(events)
    assert res["a1"] is True
