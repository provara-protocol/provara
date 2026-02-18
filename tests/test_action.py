"""Tests for .github/actions/provara-verify/verify.py.

Imports the action script directly.  All tests use real vault fixtures
so that the provara imports are exercised end-to-end.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Make the action's verify.py importable
# ---------------------------------------------------------------------------

_ACTION_DIR = (
    Path(__file__).resolve().parents[1]
    / ".github" / "actions" / "provara-verify"
)
if str(_ACTION_DIR) not in sys.path:
    sys.path.insert(0, str(_ACTION_DIR))

import verify as action_verify  # noqa: E402 (must be after sys.path update)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def vault(tmp_path: Path) -> Path:
    """A freshly bootstrapped Provara vault."""
    from provara.bootstrap_v0 import bootstrap_backpack
    vp = tmp_path / "vault"
    result = bootstrap_backpack(vp, actor="ci_agent", quiet=True)
    assert result.success
    return vp


@pytest.fixture()
def tampered_vault(vault: Path) -> Path:
    """A vault with a tampered event payload (breaks Ed25519 signature verification)."""
    events_file = vault / "events" / "events.ndjson"
    lines = events_file.read_text(encoding="utf-8").splitlines()
    assert lines
    first = json.loads(lines[0])
    # Inject a field without re-signing — Ed25519 sig will no longer match payload
    first.setdefault("data", {})["__tampered__"] = True
    lines[0] = json.dumps(first, separators=(",", ":"), sort_keys=True)
    events_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return vault


# ---------------------------------------------------------------------------
# run_verification
# ---------------------------------------------------------------------------


def test_run_verification_pass(vault: Path) -> None:
    result = action_verify.run_verification(str(vault))
    assert result["status"] == "PASS"
    assert result["event_count"] >= 1
    assert result["actor_count"] >= 1
    assert result["chain_integrity"] is True
    assert result["signature_integrity"] is True
    assert result["errors"] == []


def test_run_verification_fail_missing_vault(tmp_path: Path) -> None:
    result = action_verify.run_verification(str(tmp_path / "nonexistent"))
    assert result["status"] == "FAIL"
    assert result["errors"]


def test_run_verification_fail_tampered(tampered_vault: Path) -> None:
    result = action_verify.run_verification(str(tampered_vault))
    assert result["status"] == "FAIL"
    assert result["chain_integrity"] is False or result["signature_integrity"] is False


def test_run_verification_returns_vault_path(vault: Path) -> None:
    result = action_verify.run_verification(str(vault))
    assert result["vault_path"] == str(vault)


def test_run_verification_no_timestamps_by_default(vault: Path) -> None:
    result = action_verify.run_verification(str(vault), verify_timestamps=False)
    assert result["timestamp_count"] == 0
    assert result["timestamps_valid"] is True


# ---------------------------------------------------------------------------
# write_outputs
# ---------------------------------------------------------------------------


def test_write_outputs_github_output(tmp_path: Path) -> None:
    """GITHUB_OUTPUT file gets key=value pairs for all outputs."""
    out_file = tmp_path / "github_output"
    out_file.touch()
    result = {
        "status": "PASS",
        "event_count": 5,
        "actor_count": 2,
        "chain_integrity": True,
        "signature_integrity": True,
        "errors": [],
    }
    action_verify.write_outputs(result, str(out_file), "", "")
    content = out_file.read_text(encoding="utf-8")
    assert "status=PASS" in content
    assert "event-count=5" in content
    assert "actor-count=2" in content
    assert "chain-integrity=true" in content
    assert "signature-integrity=true" in content


def test_write_outputs_fail_status(tmp_path: Path) -> None:
    out_file = tmp_path / "github_output"
    out_file.touch()
    result = {
        "status": "FAIL",
        "event_count": 0,
        "actor_count": 0,
        "chain_integrity": False,
        "signature_integrity": False,
        "errors": ["verification failed"],
    }
    action_verify.write_outputs(result, str(out_file), "", "")
    content = out_file.read_text(encoding="utf-8")
    assert "status=FAIL" in content
    assert "chain-integrity=false" in content


def test_write_outputs_report_json(vault: Path, tmp_path: Path) -> None:
    """Output report file contains valid JSON with expected keys."""
    report_path = tmp_path / "report.json"
    result = action_verify.run_verification(str(vault))
    action_verify.write_outputs(result, "", str(report_path), "")
    assert report_path.exists()
    doc = json.loads(report_path.read_text(encoding="utf-8"))
    assert doc["status"] == "PASS"
    assert "event_count" in doc
    assert "actor_count" in doc
    assert "chain_integrity" in doc
    assert "signature_integrity" in doc


def test_write_outputs_step_summary(tmp_path: Path) -> None:
    """Step summary file gets Markdown table."""
    summary_path = tmp_path / "step_summary.md"
    summary_path.touch()
    result = {
        "status": "PASS",
        "event_count": 10,
        "actor_count": 3,
        "chain_integrity": True,
        "signature_integrity": True,
        "timestamp_count": 0,
        "timestamps_valid": True,
        "errors": [],
    }
    action_verify.write_outputs(result, "", "", str(summary_path))
    content = summary_path.read_text(encoding="utf-8")
    assert "PASS" in content
    assert "✅" in content


def test_write_outputs_step_summary_fail(tmp_path: Path) -> None:
    """Step summary shows error icon on FAIL."""
    summary_path = tmp_path / "step_summary.md"
    summary_path.touch()
    result = {
        "status": "FAIL",
        "event_count": 0,
        "actor_count": 0,
        "chain_integrity": False,
        "signature_integrity": False,
        "timestamp_count": 0,
        "timestamps_valid": True,
        "errors": ["chain broken"],
    }
    action_verify.write_outputs(result, "", "", str(summary_path))
    content = summary_path.read_text(encoding="utf-8")
    assert "FAIL" in content
    assert "❌" in content
    assert "chain broken" in content


# ---------------------------------------------------------------------------
# main() integration
# ---------------------------------------------------------------------------


def test_main_pass_exits_zero(vault: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """main() exits 0 for a valid vault."""
    gho = tmp_path / "gho"
    gho.touch()
    monkeypatch.setenv("VAULT_PATH", str(vault))
    monkeypatch.setenv("FAIL_ON_ERROR", "true")
    monkeypatch.setenv("VERIFY_TIMESTAMPS", "false")
    monkeypatch.setenv("OUTPUT_REPORT", "")
    monkeypatch.setenv("GITHUB_OUTPUT", str(gho))
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", "")
    monkeypatch.setenv("GITHUB_EVENT_NAME", "push")
    monkeypatch.setenv("PR_NUMBER", "")
    monkeypatch.setenv("GITHUB_REPOSITORY", "")
    assert action_verify.main() == 0


def test_main_fail_exits_one(tampered_vault: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """main() exits 1 for a tampered vault when fail-on-error is true."""
    gho = tmp_path / "gho"
    gho.touch()
    monkeypatch.setenv("VAULT_PATH", str(tampered_vault))
    monkeypatch.setenv("FAIL_ON_ERROR", "true")
    monkeypatch.setenv("VERIFY_TIMESTAMPS", "false")
    monkeypatch.setenv("OUTPUT_REPORT", "")
    monkeypatch.setenv("GITHUB_OUTPUT", str(gho))
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", "")
    monkeypatch.setenv("GITHUB_EVENT_NAME", "push")
    monkeypatch.setenv("PR_NUMBER", "")
    monkeypatch.setenv("GITHUB_REPOSITORY", "")
    assert action_verify.main() == 1


def test_main_fail_no_exit_when_not_fail_on_error(
    tampered_vault: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """main() exits 0 for a tampered vault when fail-on-error is false."""
    gho = tmp_path / "gho"
    gho.touch()
    monkeypatch.setenv("VAULT_PATH", str(tampered_vault))
    monkeypatch.setenv("FAIL_ON_ERROR", "false")
    monkeypatch.setenv("VERIFY_TIMESTAMPS", "false")
    monkeypatch.setenv("OUTPUT_REPORT", "")
    monkeypatch.setenv("GITHUB_OUTPUT", str(gho))
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", "")
    monkeypatch.setenv("GITHUB_EVENT_NAME", "push")
    monkeypatch.setenv("PR_NUMBER", "")
    monkeypatch.setenv("GITHUB_REPOSITORY", "")
    assert action_verify.main() == 0


def test_main_missing_vault_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """main() exits 1 when VAULT_PATH is not set."""
    monkeypatch.setenv("VAULT_PATH", "")
    assert action_verify.main() == 1


def test_main_writes_report(vault: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """main() writes the JSON report when OUTPUT_REPORT is set."""
    gho = tmp_path / "gho"
    gho.touch()
    report = tmp_path / "report.json"
    monkeypatch.setenv("VAULT_PATH", str(vault))
    monkeypatch.setenv("FAIL_ON_ERROR", "true")
    monkeypatch.setenv("VERIFY_TIMESTAMPS", "false")
    monkeypatch.setenv("OUTPUT_REPORT", str(report))
    monkeypatch.setenv("GITHUB_OUTPUT", str(gho))
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", "")
    monkeypatch.setenv("GITHUB_EVENT_NAME", "push")
    monkeypatch.setenv("PR_NUMBER", "")
    monkeypatch.setenv("GITHUB_REPOSITORY", "")
    action_verify.main()
    assert report.exists()
    doc = json.loads(report.read_text(encoding="utf-8"))
    assert doc["status"] == "PASS"
