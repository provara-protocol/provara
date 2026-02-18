"""Tests for forensic_export — chain-of-custody bundle generation."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from provara.bootstrap_v0 import bootstrap_backpack
from provara.forensic_export import ForensicBundle, forensic_export


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def bootstrapped_vault(tmp_path: Path) -> Path:
    """A vault with one signed GENESIS event."""
    vault = tmp_path / "vault"
    result = bootstrap_backpack(vault, actor="tester", quiet=True)
    assert result.success
    return vault


@pytest.fixture
def empty_dir(tmp_path: Path) -> Path:
    """A directory with no vault content (no events.ndjson, no keys)."""
    d = tmp_path / "empty_vault"
    d.mkdir()
    return d


# ---------------------------------------------------------------------------
# Test: bundle structure
# ---------------------------------------------------------------------------


def test_bundle_structure(bootstrapped_vault: Path, tmp_path: Path) -> None:
    """All required files are present after a normal export."""
    bundle = tmp_path / "bundle"
    fb = forensic_export(bootstrapped_vault, bundle)

    assert isinstance(fb, ForensicBundle)
    assert (bundle / "README.txt").exists()
    assert (bundle / "verify.py").exists()
    assert (bundle / "verification_report.json").exists()
    assert (bundle / "chain_of_custody.json").exists()
    assert (bundle / "events" / "events.ndjson").exists()
    assert (bundle / "identity" / "keys.json").exists()
    assert (bundle / "signatures" / "signature_report.json").exists()
    # raw/ should NOT exist when include_raw is False
    assert not (bundle / "raw").exists()

    # ForensicBundle fields are populated
    assert fb.event_count >= 1  # at least GENESIS
    assert fb.actor_count >= 1
    assert fb.chain_integrity is True
    assert fb.signature_integrity is True
    assert fb.software_version.startswith("provara")
    assert fb.vault_path == str(bootstrapped_vault.resolve())
    assert len(fb.files) >= 6


# ---------------------------------------------------------------------------
# Test: verify.py passes on clean vault
# ---------------------------------------------------------------------------


def test_verify_py_passes_on_clean_vault(
    bootstrapped_vault: Path, tmp_path: Path
) -> None:
    """Standalone verify.py exits 0 on an unmodified bundle."""
    bundle = tmp_path / "bundle"
    forensic_export(bootstrapped_vault, bundle)

    result = subprocess.run(
        [sys.executable, str(bundle / "verify.py")],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"verify.py unexpectedly failed:\n{result.stdout}\n{result.stderr}"
    )
    assert "PASS" in result.stdout


# ---------------------------------------------------------------------------
# Test: verify.py fails on tampered event
# ---------------------------------------------------------------------------


def test_verify_py_fails_on_tampered_event(
    bootstrapped_vault: Path, tmp_path: Path
) -> None:
    """Adding a field to a signed event invalidates its signature."""
    bundle = tmp_path / "bundle"
    forensic_export(bootstrapped_vault, bundle)

    # Tamper: inject an extra field into the first event.
    # The canonical bytes will differ from what was signed → InvalidSignature.
    events_file = bundle / "events" / "events.ndjson"
    lines = events_file.read_text("utf-8").splitlines()
    assert lines, "events.ndjson should not be empty"
    first_event = json.loads(lines[0])
    first_event["_tampered"] = True
    lines[0] = json.dumps(first_event)
    events_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(bundle / "verify.py")],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1, (
        "verify.py should have failed after tampering but exited 0"
    )
    assert "FAIL" in result.stdout


# ---------------------------------------------------------------------------
# Test: empty vault (no events.ndjson)
# ---------------------------------------------------------------------------


def test_empty_vault_export(empty_dir: Path, tmp_path: Path) -> None:
    """Exporting a directory with no vault content completes without error."""
    bundle = tmp_path / "bundle"
    fb = forensic_export(empty_dir, bundle)

    assert fb.event_count == 0
    assert fb.actor_count == 0
    assert fb.chain_integrity is True   # vacuously true
    assert fb.signature_integrity is True  # vacuously true
    assert (bundle / "README.txt").exists()
    assert (bundle / "verify.py").exists()
    assert (bundle / "verification_report.json").exists()


# ---------------------------------------------------------------------------
# Test: include_raw creates tarball
# ---------------------------------------------------------------------------


def test_include_raw_creates_tarball(
    bootstrapped_vault: Path, tmp_path: Path
) -> None:
    """include_raw=True writes raw/vault_snapshot.tar.gz."""
    bundle = tmp_path / "bundle"
    forensic_export(bootstrapped_vault, bundle, include_raw=True)

    tar_path = bundle / "raw" / "vault_snapshot.tar.gz"
    assert tar_path.exists(), "vault_snapshot.tar.gz should exist"
    assert tar_path.stat().st_size > 0


# ---------------------------------------------------------------------------
# Test: output_path already exists raises ValueError
# ---------------------------------------------------------------------------


def test_raises_if_output_exists(
    bootstrapped_vault: Path, tmp_path: Path
) -> None:
    """forensic_export refuses to overwrite an existing output directory."""
    bundle = tmp_path / "bundle"
    bundle.mkdir()

    with pytest.raises(ValueError, match="already exists"):
        forensic_export(bootstrapped_vault, bundle)


# ---------------------------------------------------------------------------
# Test: missing vault raises FileNotFoundError
# ---------------------------------------------------------------------------


def test_raises_if_vault_missing(tmp_path: Path) -> None:
    """forensic_export raises FileNotFoundError for a non-existent vault."""
    with pytest.raises(FileNotFoundError):
        forensic_export(tmp_path / "nonexistent", tmp_path / "out")
