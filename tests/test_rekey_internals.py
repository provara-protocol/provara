import pytest
from provara.rekey_backpack import _next_logical_ts, _last_event_id_for_actor, verify_rotation_events
from pathlib import Path
import json

def test_next_logical_ts_no_file(tmp_path):
    assert _next_logical_ts(tmp_path / "nonexistent", "actor") == 1

def test_next_logical_ts_corrupt_file(tmp_path):
    f = tmp_path / "corrupt.ndjson"
    f.write_text("invalid json\n")
    assert _next_logical_ts(f, "actor") == 1

def test_last_event_id_no_file(tmp_path):
    assert _last_event_id_for_actor(tmp_path / "nonexistent", "actor") is None

def test_verify_rotation_events_no_files(tmp_path):
    res = verify_rotation_events(tmp_path)
    assert "error" in res[0]
