import pytest
import json
from pathlib import Path
from provara.sync_v0 import sync_backpacks, load_events, write_events
from provara.bootstrap_v0 import bootstrap_backpack

def test_sync_unsupported_strategy(tmp_path):
    v1 = tmp_path / "v1"
    v2 = tmp_path / "v2"
    bootstrap_backpack(v1)
    bootstrap_backpack(v2)
    
    res = sync_backpacks(v1, v2, strategy="UNKNOWN")
    assert res.success is False
    assert "Unsupported merge strategy" in res.errors[0]

def test_load_events_corrupt_json(tmp_path):
    events_file = tmp_path / "corrupt.ndjson"
    events_file.write_text('{"valid":"json"}\n{invalid json}\n{"more":"valid"}\n')
    
    events = load_events(events_file)
    assert len(events) == 2

def test_sync_no_events_file(tmp_path):
    v1 = tmp_path / "v1"
    v2 = tmp_path / "v2"
    v1.mkdir()
    v2.mkdir()
    
    # This should not raise, just result in 0 merged events
    res = sync_backpacks(v1, v2)
    assert res.events_merged == 0
