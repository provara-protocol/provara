"""forensic_export.py — Chain-of-Custody Forensic Bundle Generator.

Produces a self-contained directory that a third party can inspect and verify
without installing the Provara package.  The bundle includes a standalone
``verify.py`` script (requires only ``cryptography``) that checks:

  - Ed25519 signatures on all signed events
  - Actor-level chain linkage (prev_event_hash continuity)
  - SHA-256 file hashes of all bundle files

Bundle layout
-------------
  <output>/
    README.txt
    verify.py
    verification_report.json
    chain_of_custody.json
    events/events.ndjson
    identity/genesis.json
    identity/keys.json
    manifest/manifest.json
    manifest/merkle_root.txt
    signatures/signature_report.json
    raw/vault_snapshot.tar.gz   (optional, --include-raw)
"""

from __future__ import annotations

import base64
import hashlib
import json
import platform
import shutil
import sys
import tarfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .canonical_json import canonical_bytes
from .sync_v0 import load_events

_SOFTWARE_VERSION = "provara 1.0.1"


# ---------------------------------------------------------------------------
# Public dataclass
# ---------------------------------------------------------------------------


@dataclass
class ForensicBundle:
    """Metadata and integrity summary returned by ``forensic_export()``."""

    export_timestamp: str
    software_version: str
    python_version: str
    os_info: str
    vault_path: str
    event_count: int
    actor_count: int
    chain_integrity: bool
    signature_integrity: bool
    files: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _build_key_map(keys_data: dict[str, Any]) -> dict[str, Any]:
    """Return a key_id → Ed25519PublicKey mapping from a keys.json dict."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    key_map: dict[str, Any] = {}
    for entry in keys_data.get("keys", []):
        kid = entry.get("key_id")
        pub_b64 = entry.get("public_key_b64")
        if kid and pub_b64:
            raw = base64.b64decode(pub_b64)
            key_map[str(kid)] = Ed25519PublicKey.from_public_bytes(raw)
    return key_map


def _verify_chain(events: list[dict[str, Any]]) -> tuple[bool, list[str]]:
    """Return (all_ok, error_list) for actor-level chain linkage."""
    errors: list[str] = []
    last_by_actor: dict[str, str] = {}
    for event in events:
        eid = str(event.get("event_id", ""))
        actor = str(event.get("actor", ""))
        prev = event.get("prev_event_hash")
        if actor in last_by_actor:
            if prev != last_by_actor[actor]:
                errors.append(
                    f"chain break: event {eid}, actor {actor}: "
                    f"expected {last_by_actor[actor]!r}, got {prev!r}"
                )
        else:
            if prev is not None:
                errors.append(
                    f"chain break: first event for actor {actor}: "
                    f"must have null prev_event_hash, got {prev!r}"
                )
        last_by_actor[actor] = eid
    return len(errors) == 0, errors


def _verify_signatures(
    events: list[dict[str, Any]], key_map: dict[str, Any]
) -> tuple[bool, list[str]]:
    """Return (all_ok, error_list) for Ed25519 signature checks."""
    from cryptography.exceptions import InvalidSignature

    errors: list[str] = []
    for event in events:
        sig_b64 = event.get("sig")
        if not sig_b64:
            continue
        eid = str(event.get("event_id", ""))
        kid = str(event.get("actor_key_id", ""))
        if kid not in key_map:
            errors.append(f"unknown key {kid!r} on event {eid}")
            continue
        try:
            sig_bytes = base64.b64decode(sig_b64)
            payload = {k: v for k, v in event.items() if k != "sig"}
            key_map[kid].verify(sig_bytes, canonical_bytes(payload))
        except InvalidSignature:
            errors.append(f"invalid signature on event {eid}")
        except Exception as exc:
            errors.append(f"signature check error on event {eid}: {exc}")
    return len(errors) == 0, errors


# ---------------------------------------------------------------------------
# Standalone verify.py template
# ---------------------------------------------------------------------------

_VERIFY_PY = '''\
#!/usr/bin/env python3
"""Provara Chain-of-Custody Verifier.

Standalone script — no Provara package required.
Requirements: cryptography >= 41.0  (pip install cryptography)

Usage:  python verify.py
Exit:   0 = all checks pass, 1 = one or more checks failed
"""
from __future__ import annotations

import base64
import hashlib
import json
import sys
from pathlib import Path

BUNDLE = Path(__file__).parent


def _jcs_dumps(obj: object) -> str:
    """Minimal RFC 8785 / JCS canonical JSON."""
    import json as _json
    return _json.dumps(
        obj, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    )


def _canonical_bytes(obj: object) -> bytes:
    return _jcs_dumps(obj).encode("utf-8")


def _verify_sig(event: dict, pub_key: object) -> bool:  # type: ignore[type-arg]
    from cryptography.exceptions import InvalidSignature  # type: ignore[import]
    sig_b64 = event.get("sig")
    if not sig_b64:
        return True
    try:
        sig = base64.b64decode(sig_b64)
        payload = {k: v for k, v in event.items() if k != "sig"}
        pub_key.verify(sig, _canonical_bytes(payload))  # type: ignore[union-attr]
        return True
    except InvalidSignature:
        return False


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (  # type: ignore[import]
        Ed25519PublicKey,
    )

    errors: list[str] = []

    # Load keys ---
    keys_path = BUNDLE / "identity" / "keys.json"
    if not keys_path.exists():
        print("FAIL — identity/keys.json not found")
        return 1
    keys_data = json.loads(keys_path.read_text("utf-8"))
    key_map: dict[str, object] = {}
    for entry in keys_data.get("keys", []):
        kid = entry.get("key_id")
        pub_b64 = entry.get("public_key_b64")
        if kid and pub_b64:
            raw = base64.b64decode(pub_b64)
            key_map[kid] = Ed25519PublicKey.from_public_bytes(raw)

    # Load events ---
    events_path = BUNDLE / "events" / "events.ndjson"
    if not events_path.exists():
        print("PASS — no events in bundle")
        return 0
    events: list[dict] = []  # type: ignore[type-arg]
    with open(events_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    errors.append(f"invalid JSON in events.ndjson: {exc}")

    # Chain verification ---
    last_by_actor: dict[str, str] = {}
    for event in events:
        eid = str(event.get("event_id", ""))
        actor = str(event.get("actor", ""))
        prev = event.get("prev_event_hash")
        if actor in last_by_actor:
            if prev != last_by_actor[actor]:
                errors.append(
                    f"chain break: event {eid}, actor {actor}: "
                    f"expected {last_by_actor[actor]!r}, got {prev!r}"
                )
        else:
            if prev is not None:
                errors.append(
                    f"chain break: first event for actor {actor}: "
                    f"must have null prev_event_hash, got {prev!r}"
                )
        last_by_actor[actor] = eid

    # Signature verification ---
    for event in events:
        eid = str(event.get("event_id", ""))
        kid = str(event.get("actor_key_id", ""))
        if event.get("sig"):
            if kid not in key_map:
                errors.append(f"unknown key_id {kid!r} on event {eid}")
            elif not _verify_sig(event, key_map[kid]):
                errors.append(f"invalid signature on event {eid}")

    # File integrity ---
    sig_report_path = BUNDLE / "signatures" / "signature_report.json"
    if sig_report_path.exists():
        report = json.loads(sig_report_path.read_text("utf-8"))
        for item in report.get("file_hashes", []):
            rel = item.get("path", "")
            expected_hex = item.get("sha256", "")
            fpath = BUNDLE / rel
            if not fpath.exists():
                errors.append(f"bundle file missing: {rel}")
            else:
                actual_hex = _sha256_file(fpath)
                if actual_hex != expected_hex:
                    errors.append(
                        f"file hash mismatch: {rel} "
                        f"(expected {expected_hex[:12]}..., got {actual_hex[:12]}...)"
                    )

    # Report ---
    if errors:
        print(f"FAIL — {len(errors)} error(s):")
        for err in errors:
            print(f"  {err}")
        return 1
    print(
        f"PASS — {len(events)} event(s), {len(last_by_actor)} actor(s), "
        "chain intact, signatures valid, file hashes verified"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def forensic_export(
    vault_path: Path,
    output_path: Path,
    include_raw: bool = False,
) -> ForensicBundle:
    """Export a vault as a self-contained chain-of-custody forensic bundle.

    Args:
        vault_path:  Source vault directory.
        output_path: Directory to create (must not already exist).
        include_raw: If True, include ``raw/vault_snapshot.tar.gz``.

    Returns:
        ForensicBundle with metadata and integrity status.

    Raises:
        FileNotFoundError: If vault_path does not exist.
        ValueError: If output_path already exists.
    """
    vp = Path(vault_path).resolve()
    op = Path(output_path).resolve()

    if not vp.exists():
        raise FileNotFoundError(f"Vault not found: {vp}")
    if op.exists():
        raise ValueError(f"Output path already exists: {op}")

    op.mkdir(parents=True)

    # ------------------------------------------------------------------
    # 1.  Read vault data
    # ------------------------------------------------------------------
    events_src = vp / "events" / "events.ndjson"
    events: list[dict[str, Any]] = []
    if events_src.exists():
        events = load_events(events_src)

    keys_src = vp / "identity" / "keys.json"
    keys_data: dict[str, Any] = {}
    if keys_src.exists():
        keys_data = json.loads(keys_src.read_text(encoding="utf-8"))

    genesis_src = vp / "identity" / "genesis.json"
    manifest_src = vp / "manifest.json"
    merkle_src = vp / "merkle_root.txt"

    # ------------------------------------------------------------------
    # 2.  Integrity checks
    # ------------------------------------------------------------------
    key_map = _build_key_map(keys_data)
    chain_ok, chain_errors = _verify_chain(events)
    sig_ok, sig_errors = _verify_signatures(events, key_map)
    actors: set[str] = {str(e.get("actor", "")) for e in events if e.get("actor")}

    # ------------------------------------------------------------------
    # 3.  Copy vault files into bundle
    # ------------------------------------------------------------------
    (op / "events").mkdir()
    (op / "identity").mkdir()
    (op / "manifest").mkdir()
    (op / "signatures").mkdir()

    if events_src.exists():
        shutil.copy2(events_src, op / "events" / "events.ndjson")
    if genesis_src.exists():
        shutil.copy2(genesis_src, op / "identity" / "genesis.json")
    if keys_src.exists():
        shutil.copy2(keys_src, op / "identity" / "keys.json")
    if manifest_src.exists():
        shutil.copy2(manifest_src, op / "manifest" / "manifest.json")
    if merkle_src.exists():
        shutil.copy2(merkle_src, op / "manifest" / "merkle_root.txt")

    # ------------------------------------------------------------------
    # 4.  chain_of_custody.json  — per-event record
    # ------------------------------------------------------------------
    chain_records: list[dict[str, Any]] = []
    for event in events:
        eid = str(event.get("event_id", ""))
        actor = str(event.get("actor", ""))
        etype = str(event.get("type", event.get("event_type", "")))
        ts = str(event.get("timestamp_utc", event.get("timestamp", "")))
        prev = event.get("prev_event_hash")
        kid = str(event.get("actor_key_id", ""))

        sig_valid = True
        if event.get("sig") and kid in key_map:
            from cryptography.exceptions import InvalidSignature
            try:
                sig_bytes = base64.b64decode(event["sig"])
                payload = {k: v for k, v in event.items() if k != "sig"}
                key_map[kid].verify(sig_bytes, canonical_bytes(payload))
            except (InvalidSignature, Exception):
                sig_valid = False

        chain_records.append({
            "event_id": eid,
            "type": etype,
            "actor": actor,
            "actor_key_id": kid,
            "timestamp_utc": ts,
            "prev_event_hash": prev,
            "sig_valid": sig_valid,
        })

    (op / "chain_of_custody.json").write_text(
        json.dumps(
            {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "vault_path": str(vp),
                "event_count": len(events),
                "chain_intact": chain_ok,
                "chain_errors": chain_errors,
                "events": chain_records,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    # ------------------------------------------------------------------
    # 5.  signature_report.json  — file hashes + sig summary
    # ------------------------------------------------------------------
    tracked: list[str] = [
        "events/events.ndjson",
        "identity/genesis.json",
        "identity/keys.json",
        "manifest/manifest.json",
        "manifest/merkle_root.txt",
    ]
    file_hashes: list[dict[str, str]] = [
        {"path": rel, "sha256": _sha256_file(op / rel)}
        for rel in tracked
        if (op / rel).exists()
    ]

    (op / "signatures" / "signature_report.json").write_text(
        json.dumps(
            {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "events_total": len(events),
                "events_signed": sum(1 for e in events if e.get("sig")),
                "events_unsigned": sum(1 for e in events if not e.get("sig")),
                "signature_errors": sig_errors,
                "all_signatures_valid": sig_ok,
                "file_hashes": file_hashes,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    # ------------------------------------------------------------------
    # 6.  verification_report.json  — machine-readable summary
    # ------------------------------------------------------------------
    export_ts = datetime.now(timezone.utc).isoformat()
    (op / "verification_report.json").write_text(
        json.dumps(
            {
                "export_timestamp": export_ts,
                "software_version": _SOFTWARE_VERSION,
                "python_version": sys.version.split()[0],
                "os_info": platform.platform(),
                "vault_path": str(vp),
                "event_count": len(events),
                "actor_count": len(actors),
                "chain_integrity": chain_ok,
                "signature_integrity": sig_ok,
                "chain_errors": chain_errors,
                "signature_errors": sig_errors,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    # ------------------------------------------------------------------
    # 7.  verify.py  — standalone script
    # ------------------------------------------------------------------
    (op / "verify.py").write_text(_VERIFY_PY, encoding="utf-8")

    # ------------------------------------------------------------------
    # 8.  Optional raw snapshot
    # ------------------------------------------------------------------
    if include_raw:
        raw_dir = op / "raw"
        raw_dir.mkdir()
        with tarfile.open(raw_dir / "vault_snapshot.tar.gz", "w:gz") as tar:
            tar.add(str(vp), arcname="vault")

    # ------------------------------------------------------------------
    # 9.  README.txt
    # ------------------------------------------------------------------
    seal_line = "YES" if chain_ok else "NO — see chain_of_custody.json"
    sig_line = "YES" if sig_ok else "NO — see signatures/signature_report.json"
    readme_lines = [
        "PROVARA CHAIN-OF-CUSTODY FORENSIC BUNDLE",
        "=" * 42,
        "",
        f"Exported:         {export_ts}",
        f"Software:         {_SOFTWARE_VERSION}",
        f"Source vault:     {vp}",
        f"Events:           {len(events)}",
        f"Actors:           {len(actors)}",
        f"Chain intact:     {seal_line}",
        f"Signatures valid: {sig_line}",
        "",
        "CONTENTS",
        "--------",
        "  README.txt                        this file",
        "  verify.py                         standalone verification script",
        "  verification_report.json          machine-readable integrity summary",
        "  chain_of_custody.json             per-event chain record",
        "  events/events.ndjson              copy of the event log",
        "  identity/genesis.json             vault genesis record",
        "  identity/keys.json                public keys (no private keys included)",
        "  manifest/manifest.json            vault file manifest",
        "  manifest/merkle_root.txt          vault Merkle root",
        "  signatures/signature_report.json  signature verification details",
    ]
    if include_raw:
        readme_lines.append("  raw/vault_snapshot.tar.gz         full vault snapshot")
    readme_lines += [
        "",
        "VERIFICATION",
        "------------",
        "  python verify.py",
        "",
        "  Requirements: Python 3.10+, cryptography >= 41.0",
        "  Exit 0 = all checks passed; exit 1 = failures detected.",
        "",
        "PROVENANCE",
        "----------",
        "  Generated by Provara Protocol toolkit <https://provara.dev>",
    ]
    (op / "README.txt").write_text("\n".join(readme_lines) + "\n", encoding="utf-8")

    # ------------------------------------------------------------------
    # 10.  Collect file list
    # ------------------------------------------------------------------
    file_list = sorted(
        str(f.relative_to(op)).replace("\\", "/")
        for f in op.rglob("*")
        if f.is_file()
    )

    return ForensicBundle(
        export_timestamp=export_ts,
        software_version=_SOFTWARE_VERSION,
        python_version=sys.version.split()[0],
        os_info=platform.platform(),
        vault_path=str(vp),
        event_count=len(events),
        actor_count=len(actors),
        chain_integrity=chain_ok,
        signature_integrity=sig_ok,
        files=file_list,
    )
