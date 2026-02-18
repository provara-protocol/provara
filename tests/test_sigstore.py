"""Tests for provara.sigstore_anchor.

Uses mocks for all Sigstore API calls so tests pass whether or not the
sigstore package is installed.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from provara.sigstore_anchor import (
    ANCHOR_FORMAT,
    ANCHORS_DIR,
    AnchorResult,
    _SIGSTORE_AVAILABLE,
    _build_payload,
    _current_event_count,
    _current_merkle_root,
    _extract_log_entry,
    list_anchors,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def vault(tmp_path: Path) -> Path:
    """A freshly bootstrapped Provara vault."""
    from provara.bootstrap_v0 import bootstrap_backpack
    vp = tmp_path / "vault"
    result = bootstrap_backpack(vp, actor="sigstore_tester", quiet=True)
    assert result.success
    return vp


def _make_mock_bundle(log_index: int = 42) -> MagicMock:
    """Build a MagicMock that mimics a Sigstore bundle (v3.x shape)."""
    mock_bundle = MagicMock()
    mock_entry = MagicMock()
    mock_entry.log_index = log_index
    mock_entry.log_id = "deadbeef1234567890abcdef"
    mock_entry.integrated_time = 1708296000  # 2026-02-18T12:00:00Z
    mock_bundle.verification_material.tlog_entries = [mock_entry]
    mock_bundle.to_json.return_value = {"mock": "bundle_data", "log_index": log_index}
    return mock_bundle


# ---------------------------------------------------------------------------
# AnchorResult dataclass (always importable — no sigstore needed)
# ---------------------------------------------------------------------------


def test_anchor_result_always_importable() -> None:
    """AnchorResult can be instantiated even without sigstore."""
    ar = AnchorResult(
        log_index=1,
        log_id="abc",
        integrated_time=datetime(2026, 2, 18, tzinfo=timezone.utc),
        verification_url="https://search.sigstore.dev/?logIndex=1",
        merkle_root="deadbeef",
        vault_event_count=5,
    )
    assert ar.log_index == 1
    assert ar.anchor_path is None  # optional, defaults to None


# ---------------------------------------------------------------------------
# _require_sigstore / ImportError gating
# ---------------------------------------------------------------------------


def test_anchor_requires_sigstore_when_unavailable(vault: Path) -> None:
    """anchor_to_sigstore raises ImportError when sigstore is not installed."""
    from provara.sigstore_anchor import anchor_to_sigstore
    with patch("provara.sigstore_anchor._SIGSTORE_AVAILABLE", False):
        with pytest.raises(ImportError, match="sigstore"):
            anchor_to_sigstore(vault)


def test_verify_requires_sigstore_when_unavailable(vault: Path, tmp_path: Path) -> None:
    """verify_sigstore_anchor raises ImportError when sigstore is not installed."""
    from provara.sigstore_anchor import verify_sigstore_anchor
    dummy = tmp_path / "anchor.json"
    dummy.write_text(json.dumps({"format": ANCHOR_FORMAT, "sigstore_bundle": {}}))
    with patch("provara.sigstore_anchor._SIGSTORE_AVAILABLE", False):
        with pytest.raises(ImportError, match="sigstore"):
            verify_sigstore_anchor(vault, dummy)


# ---------------------------------------------------------------------------
# _extract_log_entry
# ---------------------------------------------------------------------------


def test_extract_log_entry_primary_shape() -> None:
    """_extract_log_entry handles the primary v3.x bundle shape."""
    bundle = _make_mock_bundle(log_index=99)
    entry = _extract_log_entry(bundle)
    assert entry["log_index"] == 99
    assert entry["log_id"] == "deadbeef1234567890abcdef"
    assert entry["integrated_time"] == 1708296000


def test_extract_log_entry_fallback_shape() -> None:
    """_extract_log_entry falls back to bundle.log_entry shape."""
    bundle = MagicMock()
    # Cause the primary path to fail
    bundle.verification_material.tlog_entries = []  # IndexError
    bundle.log_entry.log_index = 7
    bundle.log_entry.log_id = "fallback_id"
    bundle.log_entry.integrated_time = 1000
    entry = _extract_log_entry(bundle)
    assert entry["log_index"] == 7


def test_extract_log_entry_raises_on_unknown_shape() -> None:
    """_extract_log_entry raises RuntimeError for unrecognised bundle shapes."""
    bundle = MagicMock(spec=[])  # no attributes at all
    with pytest.raises(RuntimeError, match="Cannot extract"):
        _extract_log_entry(bundle)


# ---------------------------------------------------------------------------
# anchor_to_sigstore (mocked)
# ---------------------------------------------------------------------------


def test_anchor_to_sigstore_returns_anchor_result(vault: Path) -> None:
    """anchor_to_sigstore returns an AnchorResult with correct fields."""
    from provara.sigstore_anchor import anchor_to_sigstore
    mock_bundle = _make_mock_bundle(log_index=42)
    with patch("provara.sigstore_anchor._SIGSTORE_AVAILABLE", True), \
         patch("provara.sigstore_anchor._sigstore_sign", return_value=mock_bundle):
        result = anchor_to_sigstore(vault)

    assert isinstance(result, AnchorResult)
    assert result.log_index == 42
    assert result.log_id == "deadbeef1234567890abcdef"
    assert isinstance(result.integrated_time, datetime)
    assert "42" in result.verification_url
    assert result.vault_event_count >= 1
    assert result.merkle_root != ""


def test_anchor_to_sigstore_creates_anchor_file(vault: Path) -> None:
    """anchor_to_sigstore writes a JSON anchor file to vault/anchors/."""
    from provara.sigstore_anchor import anchor_to_sigstore
    mock_bundle = _make_mock_bundle(log_index=7)
    with patch("provara.sigstore_anchor._SIGSTORE_AVAILABLE", True), \
         patch("provara.sigstore_anchor._sigstore_sign", return_value=mock_bundle):
        result = anchor_to_sigstore(vault)

    assert result.anchor_path is not None
    assert result.anchor_path.exists()
    doc = json.loads(result.anchor_path.read_text(encoding="utf-8"))
    assert doc["format"] == ANCHOR_FORMAT
    assert doc["log_index"] == 7
    assert "merkle_root" in doc
    assert "sigstore_bundle" in doc


def test_anchor_to_sigstore_event_id(vault: Path) -> None:
    """anchor_to_sigstore anchors a specific event when event_id is given."""
    from provara.bootstrap_v0 import bootstrap_backpack
    from provara.sync_v0 import load_events

    events_file = vault / "events" / "events.ndjson"
    events = load_events(events_file)
    event_id = events[0]["event_id"]

    from provara.sigstore_anchor import anchor_to_sigstore
    mock_bundle = _make_mock_bundle(log_index=100)
    with patch("provara.sigstore_anchor._SIGSTORE_AVAILABLE", True), \
         patch("provara.sigstore_anchor._sigstore_sign", return_value=mock_bundle):
        result = anchor_to_sigstore(vault, event_id=event_id)

    assert result.anchor_path is not None
    doc = json.loads(result.anchor_path.read_text(encoding="utf-8"))
    assert doc["event_id"] == event_id


def test_anchor_nonexistent_vault(tmp_path: Path) -> None:
    """anchor_to_sigstore raises ValueError for non-existent vault."""
    from provara.sigstore_anchor import anchor_to_sigstore
    with patch("provara.sigstore_anchor._SIGSTORE_AVAILABLE", True), \
         patch("provara.sigstore_anchor._sigstore_sign"):
        with pytest.raises(ValueError, match="not a directory"):
            anchor_to_sigstore(tmp_path / "nonexistent")


def test_anchor_unknown_event_id(vault: Path) -> None:
    """anchor_to_sigstore raises ValueError for unknown event_id."""
    from provara.sigstore_anchor import anchor_to_sigstore
    with patch("provara.sigstore_anchor._SIGSTORE_AVAILABLE", True), \
         patch("provara.sigstore_anchor._sigstore_sign"):
        with pytest.raises(ValueError, match="not found"):
            anchor_to_sigstore(vault, event_id="evt_nonexistent000000000000")


def test_anchor_staging_flag(vault: Path) -> None:
    """anchor_to_sigstore passes staging=True to _sigstore_sign."""
    from provara.sigstore_anchor import anchor_to_sigstore
    mock_bundle = _make_mock_bundle()
    calls: list[Any] = []

    def capture_sign(payload: bytes, staging: bool = False) -> Any:
        calls.append(staging)
        return mock_bundle

    with patch("provara.sigstore_anchor._SIGSTORE_AVAILABLE", True), \
         patch("provara.sigstore_anchor._sigstore_sign", side_effect=capture_sign):
        anchor_to_sigstore(vault, staging=True)

    assert calls == [True]


# ---------------------------------------------------------------------------
# verify_sigstore_anchor (mocked)
# ---------------------------------------------------------------------------


def _write_anchor(vault: Path, log_index: int = 42, event_id: Any = None) -> Path:
    """Write a plausible anchor file to vault/anchors/ for testing."""
    from provara.sigstore_anchor import _current_merkle_root
    merkle_root = _current_merkle_root(vault)
    anchors_dir = vault / ANCHORS_DIR
    anchors_dir.mkdir(exist_ok=True)
    anchor_file = anchors_dir / f"20260218T120000Z_{log_index}.json"
    doc: dict[str, Any] = {
        "format": ANCHOR_FORMAT,
        "event_id": event_id,
        "merkle_root": merkle_root,
        "vault_event_count": 1,
        "anchor_timestamp": "2026-02-18T12:00:00+00:00",
        "log_index": log_index,
        "log_id": "abc123",
        "integrated_time": "2026-02-18T12:00:01+00:00",
        "verification_url": f"https://search.sigstore.dev/?logIndex={log_index}",
        "sigstore_bundle": {"mock": "bundle"},
    }
    anchor_file.write_text(json.dumps(doc), encoding="utf-8")
    return anchor_file


def test_verify_anchor_pass(vault: Path) -> None:
    """verify_sigstore_anchor returns True when _sigstore_verify passes."""
    from provara.sigstore_anchor import verify_sigstore_anchor
    anchor_file = _write_anchor(vault, log_index=42)
    with patch("provara.sigstore_anchor._SIGSTORE_AVAILABLE", True), \
         patch("provara.sigstore_anchor._sigstore_verify", return_value=True):
        assert verify_sigstore_anchor(vault, anchor_file) is True


def test_verify_anchor_fail(vault: Path) -> None:
    """verify_sigstore_anchor returns False when bundle verification fails."""
    from provara.sigstore_anchor import verify_sigstore_anchor
    anchor_file = _write_anchor(vault, log_index=42)
    with patch("provara.sigstore_anchor._SIGSTORE_AVAILABLE", True), \
         patch("provara.sigstore_anchor._sigstore_verify", return_value=False):
        assert verify_sigstore_anchor(vault, anchor_file) is False


def test_verify_anchor_missing_file(vault: Path, tmp_path: Path) -> None:
    """verify_sigstore_anchor raises FileNotFoundError for missing anchor."""
    from provara.sigstore_anchor import verify_sigstore_anchor
    with patch("provara.sigstore_anchor._SIGSTORE_AVAILABLE", True):
        with pytest.raises(FileNotFoundError):
            verify_sigstore_anchor(vault, tmp_path / "nonexistent.json")


def test_verify_anchor_wrong_format(vault: Path, tmp_path: Path) -> None:
    """verify_sigstore_anchor raises ValueError for unrecognised format."""
    from provara.sigstore_anchor import verify_sigstore_anchor
    bad_file = tmp_path / "bad.json"
    bad_file.write_text(json.dumps({"format": "unknown-v99"}))
    with patch("provara.sigstore_anchor._SIGSTORE_AVAILABLE", True):
        with pytest.raises(ValueError, match="Unrecognised anchor format"):
            verify_sigstore_anchor(vault, bad_file)


def test_verify_anchor_missing_bundle_field(vault: Path) -> None:
    """verify_sigstore_anchor raises ValueError when sigstore_bundle is absent."""
    from provara.sigstore_anchor import verify_sigstore_anchor
    anchor_file = _write_anchor(vault)
    doc = json.loads(anchor_file.read_text())
    del doc["sigstore_bundle"]
    anchor_file.write_text(json.dumps(doc))
    with patch("provara.sigstore_anchor._SIGSTORE_AVAILABLE", True):
        with pytest.raises(ValueError, match="missing sigstore_bundle"):
            verify_sigstore_anchor(vault, anchor_file)


# ---------------------------------------------------------------------------
# list_anchors
# ---------------------------------------------------------------------------


def test_list_anchors_empty(tmp_path: Path) -> None:
    """list_anchors returns empty list when no anchors directory exists."""
    vp = tmp_path / "v"
    vp.mkdir()
    assert list_anchors(vp) == []


def test_list_anchors_after_writing(vault: Path) -> None:
    """list_anchors returns one entry for each anchor file written."""
    _write_anchor(vault, log_index=10)
    _write_anchor(vault, log_index=20)
    anchors = list_anchors(vault)
    assert len(anchors) == 2
    assert all(a["format"] == ANCHOR_FORMAT for a in anchors)
    assert all("anchor_file" in a for a in anchors)
    # sigstore_bundle is excluded from listing
    assert all("sigstore_bundle" not in a for a in anchors)


def test_list_anchors_sorted_by_timestamp(vault: Path) -> None:
    """list_anchors returns entries sorted by anchor_timestamp ascending."""
    anchors_dir = vault / ANCHORS_DIR
    anchors_dir.mkdir(exist_ok=True)
    for i, ts in enumerate(["20260220T000000Z", "20260218T000000Z", "20260219T000000Z"]):
        f = anchors_dir / f"{ts}_{i}.json"
        doc = {
            "format": ANCHOR_FORMAT,
            "anchor_timestamp": f"2026-02-{18 + i:02d}T00:00:00+00:00",
            "log_index": i,
        }
        f.write_text(json.dumps(doc))
    anchors = list_anchors(vault)
    timestamps = [a["anchor_timestamp"] for a in anchors]
    assert timestamps == sorted(timestamps)
