#!/usr/bin/env python3
"""
verify.py -- GitHub Action entrypoint for Provara vault verification.

Called by .github/actions/provara-verify/action.yml.
Reads configuration from environment variables, runs verification, and
writes results to $GITHUB_OUTPUT and optionally $GITHUB_STEP_SUMMARY.

Can also be imported as a module for testing.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any


def run_verification(
    vault_path_str: str,
    verify_timestamps: bool = False,
) -> dict[str, Any]:
    """Run full vault verification. Returns a result dict.

    Args:
        vault_path_str: Absolute or relative path to the Provara vault.
        verify_timestamps: If True, also verify RFC 3161 timestamps.

    Returns:
        Dict with keys: status, vault_path, event_count, actor_count,
        chain_integrity, signature_integrity, timestamp_count,
        timestamps_valid, errors.
    """
    result: dict[str, Any] = {
        "status": "PASS",
        "vault_path": vault_path_str,
        "event_count": 0,
        "actor_count": 0,
        "chain_integrity": True,
        "signature_integrity": True,
        "timestamp_count": 0,
        "timestamps_valid": True,
        "errors": [],
    }

    vp = Path(vault_path_str)
    if not vp.is_dir():
        result["status"] = "FAIL"
        result["errors"].append(f"Vault path is not a directory: {vp}")
        return result

    # Cryptographic integrity: Ed25519 signatures + SHA-256 chain + Merkle root
    try:
        from provara.backpack_integrity import validate_vault_structure
        validate_vault_structure(vp)
    except Exception as exc:
        result["status"] = "FAIL"
        result["chain_integrity"] = False
        result["signature_integrity"] = False
        result["errors"].append(str(exc))

    # Event stats via SQLite index
    try:
        from provara.query import VaultIndex
        with VaultIndex(vp) as idx:
            idx.update()
            actors = idx.get_actor_summary()
            result["actor_count"] = len(actors)
            result["event_count"] = sum(actors.values())
    except Exception as exc:
        result["errors"].append(f"Stats error: {exc}")

    # RFC 3161 timestamp verification (optional)
    if verify_timestamps:
        try:
            from provara.rfc3161 import verify_all_timestamps
            ts_results = verify_all_timestamps(vp)
            result["timestamp_count"] = len(ts_results)
            failed = [r for r in ts_results if not getattr(r, "valid", False)]
            if failed:
                result["timestamps_valid"] = False
                result["status"] = "FAIL"
                result["errors"].append(
                    f"{len(failed)} of {len(ts_results)} timestamps failed"
                )
        except Exception as exc:
            result["errors"].append(f"Timestamp verification error: {exc}")

    return result


def write_outputs(
    result: dict[str, Any],
    github_output_path: str,
    output_report_path: str,
    step_summary_path: str,
) -> None:
    """Write GitHub Action outputs, optional report file, and job summary."""
    # $GITHUB_OUTPUT  (key=value pairs)
    if github_output_path:
        with open(github_output_path, "a", encoding="utf-8") as fh:
            fh.write(f"status={result['status']}\n")
            fh.write(f"event-count={result['event_count']}\n")
            fh.write(f"actor-count={result['actor_count']}\n")
            fh.write(f"chain-integrity={str(result['chain_integrity']).lower()}\n")
            fh.write(
                f"signature-integrity={str(result['signature_integrity']).lower()}\n"
            )

    # Optional JSON report
    if output_report_path:
        Path(output_report_path).write_text(
            json.dumps(result, indent=2), encoding="utf-8"
        )

    # \  (Markdown table)
    if step_summary_path:
        icon = "✅" if result["status"] == "PASS" else "❌"
        ts_row = ""
        if result.get("timestamp_count", 0) > 0:
            valid_ts = (
                result["timestamp_count"] if result["timestamps_valid"] else 0
            )
            ts_row = (
                f"| Timestamps verified | {valid_ts}/{result['timestamp_count']} |\n"
            )
        error_section = ""
        if result["errors"]:
            lines = "\n".join(f"- {e}" for e in result["errors"])
            error_section = f"\n\n**Errors:**\n{lines}"
        summary = (
            f"## {icon} Provara Vault Verified\n\n"
            f"| Property | Value |\n"
            f"|----------|-------|\n"
            f"| Status | **{result['status']}** |\n"
            f"| Events | {result['event_count']:,} |\n"
            f"| Actors | {result['actor_count']} |\n"
            f"| Chain integrity | {'✓' if result['chain_integrity'] else '✗'} |\n"
            f"| Signature integrity |"
            f" {'✓' if result['signature_integrity'] else '✗'} |\n"
            f"{ts_row}"
            f"{error_section}\n"
        )
        with open(step_summary_path, "a", encoding="utf-8") as fh:
            fh.write(summary)


def main() -> int:
    """Entry point when run as a script in a GitHub Actions environment."""
    vault_path = os.environ.get("VAULT_PATH", "")
    fail_on_error = os.environ.get("FAIL_ON_ERROR", "true").lower() == "true"
    verify_timestamps = (
        os.environ.get("VERIFY_TIMESTAMPS", "false").lower() == "true"
    )
    output_report = os.environ.get("OUTPUT_REPORT", "")
    github_output = os.environ.get("GITHUB_OUTPUT", "")
    github_step_summary = os.environ.get("GITHUB_STEP_SUMMARY", "")

    if not vault_path:
        print(
            "ERROR: VAULT_PATH environment variable is required", file=sys.stderr
        )
        return 1

    result = run_verification(vault_path, verify_timestamps=verify_timestamps)

    write_outputs(result, github_output, output_report, github_step_summary)

    icon = "✅" if result["status"] == "PASS" else "❌"
    print(f"{icon} Provara Vault: {result['status']}")
    print(
        f"   Events: {result['event_count']:,}  |  Actors: {result['actor_count']}"
    )
    print(
        f"   Chain: {'VALID' if result['chain_integrity'] else 'INVALID'}"
        f"  |  Sigs: {'VALID' if result['signature_integrity'] else 'INVALID'}"
    )
    for err in result["errors"]:
        print(f"   Error: {err}", file=sys.stderr)

    if result["status"] == "FAIL" and fail_on_error:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
